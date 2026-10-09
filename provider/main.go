// Original native Buzz backend provider. Only OpenSSH carries secrets over the network.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"time"
)

const version = "0.3.0"
const maxBytes = 512 * 1024

var aliasPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`)

type Request struct {
	Op        string                     `json:"op"`
	RequestID string                     `json:"request_id"`
	Agent     json.RawMessage            `json:"agent"`
	Config    map[string]json.RawMessage `json:"provider_config"`
}

type capBuffer struct {
	bytes.Buffer
	maximum int
}

func (b *capBuffer) Write(p []byte) (int, error) {
	if b.Len()+len(p) > b.maximum {
		return 0, fmt.Errorf("output limit")
	}
	return b.Buffer.Write(p)
}

func info() map[string]any {
	return map[string]any{
		"ok": true, "name": "Hostinger VPS — Native Buzz", "version": version, "protocol_version": 1,
		"description": "Deploy independent Codex/Claude bots through a restricted SSH host. No fixed workflow. Stop before reconfiguring.",
		"config_schema": map[string]any{
			"type": "object", "additionalProperties": false, "required": []string{"ssh_alias"},
			"properties": map[string]any{
				"ssh_alias":        map[string]any{"type": "string", "title": "OpenSSH host alias", "default": "buzz-vps"},
				"workspace":        map[string]any{"type": "string", "title": "VPS workspace group", "default": "team"},
				"memory_mb":        map[string]any{"type": "integer", "title": "RAM limit (MiB)", "minimum": 512, "maximum": 4096, "default": 1536},
				"cpus":             map[string]any{"type": "number", "title": "CPU limit", "minimum": 0.1, "maximum": 1.5, "default": 0.75},
				"max_turn_seconds": map[string]any{"type": "integer", "title": "Maximum time per AI turn (seconds)", "minimum": 60, "maximum": 7200, "default": 1800},
				"turn_limit":       map[string]any{"type": "integer", "title": "Maximum prompt starts per window", "minimum": 1, "maximum": 500, "default": 20},
				"window_seconds":   map[string]any{"type": "integer", "title": "Rate window (seconds)", "minimum": 60, "maximum": 86400, "default": 3600},
				"daily_limit":      map[string]any{"type": "integer", "title": "Maximum prompt starts in 24 hours", "minimum": 1, "maximum": 2000, "default": 100},
			},
		},
	}
}

func sshPath() (string, error) {
	// On Windows use the OS OpenSSH binary, not an executable from the project cwd.
	if root := os.Getenv("SystemRoot"); root != "" {
		p := filepath.Join(root, "System32", "OpenSSH", "ssh.exe")
		if s, e := os.Stat(p); e == nil && !s.IsDir() {
			return p, nil
		}
	}
	return exec.LookPath("ssh")
}

func deploy(ctx context.Context, request Request, raw []byte) (map[string]any, error) {
	var alias string
	if err := json.Unmarshal(request.Config["ssh_alias"], &alias); err != nil || !aliasPattern.MatchString(alias) {
		return nil, fmt.Errorf("invalid_ssh_alias")
	}
	if len(request.Agent) == 0 || bytes.Equal(request.Agent, []byte("null")) {
		return nil, fmt.Errorf("missing_agent")
	}
	ssh, err := sshPath()
	if err != nil {
		return nil, fmt.Errorf("openssh_not_found")
	}
	// No shell; no secrets in argv. Host key checking never silently accepts a new host.
	args, err := sshArgs(alias)
	if err != nil {
		return nil, err
	}
	command := exec.CommandContext(ctx, ssh, args...)
	command.Stdin = bytes.NewReader(raw)
	out := &capBuffer{maximum: maxBytes}
	diagnostic := &capBuffer{maximum: 65536}
	command.Stdout = out
	command.Stderr = diagnostic
	err = command.Run()
	var answer map[string]any
	decodeErr := json.Unmarshal(out.Bytes(), &answer)
	if err != nil || decodeErr != nil {
		// A failed SSH command can have applied a deploy; do not auto-retry.
		// Valid server error codes are safe; never echo stderr or an arbitrary server message.
		if code, ok := answer["error"].(string); ok && regexp.MustCompile(`^[A-Za-z0-9_]{1,160}$`).MatchString(code) {
			return nil, fmt.Errorf("%s", code)
		}
		return nil, fmt.Errorf("ssh_deploy_unconfirmed_check_host_do_not_blindly_retry")
	}
	if answer["ok"] != true {
		return nil, fmt.Errorf("remote_deploy_refused")
	}
	id, ok := answer["agent_id"].(string)
	if !ok || !regexp.MustCompile(`^buzz-native-[a-f0-9]{20}$`).MatchString(id) {
		return nil, fmt.Errorf("invalid_remote_agent_id")
	}
	// Emit only protocol fields; no untrusted metadata or credentials from the remote response.
	return map[string]any{"ok": true, "agent_id": id}, nil
}

func sshArgs(alias string) ([]string, error) {
	args := []string{"-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
		"-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2"}
	if alias == "buzz-vps" {
		home, err := os.UserHomeDir()
		if err != nil {
			return nil, fmt.Errorf("home_directory_unavailable")
		}
		config := filepath.Join(home, ".buzz-agents", "ssh_config")
		if s, err := os.Stat(config); err == nil {
			if !s.Mode().IsRegular() {
				return nil, fmt.Errorf("invalid_setup_ssh_config")
			}
			args = append(args, "-F", config)
		} else if !os.IsNotExist(err) {
			return nil, fmt.Errorf("setup_ssh_config_unreadable")
		}
	}
	return append(args, alias, "buzz-agents-receive"), nil
}

func run(input io.Reader, output io.Writer) int {
	raw, err := io.ReadAll(io.LimitReader(input, maxBytes+1))
	if err != nil || len(raw) > maxBytes {
		json.NewEncoder(output).Encode(map[string]any{"ok": false, "error": "request_too_large"})
		return 1
	}
	var request Request
	if json.Unmarshal(raw, &request) != nil {
		json.NewEncoder(output).Encode(map[string]any{"ok": false, "error": "invalid_json"})
		return 1
	}
	var answer map[string]any
	switch request.Op {
	case "info":
		answer = info()
	case "deploy":
		ctx, cancel := context.WithTimeout(context.Background(), 240*time.Second)
		defer cancel()
		answer, err = deploy(ctx, request, raw)
	default:
		err = fmt.Errorf("unsupported_operation")
	}
	if err != nil {
		json.NewEncoder(output).Encode(map[string]any{"ok": false, "error": err.Error()})
		return 1
	}
	json.NewEncoder(output).Encode(answer)
	return 0
}
func main() { os.Exit(run(os.Stdin, os.Stdout)) }
