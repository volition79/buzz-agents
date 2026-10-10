// Buzz backend v1 over HTTPS. No SSH, password, human nsec, or shell bootstrap.
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

const maxBytes = 512 * 1024

type Connection struct {
	Endpoint string `json:"endpoint"`
	Token    string `json:"token"`
	DeviceID string `json:"device_id"`
}

type Request struct {
	Op     string                     `json:"op"`
	Agent  json.RawMessage            `json:"agent"`
	Config map[string]json.RawMessage `json:"provider_config"`
}

var tokenPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{32,100}$`)
var idPattern = regexp.MustCompile(`^buzz-native-[a-f0-9]{20}$`)

// Never echo an arbitrary server string even if it resembles a machine code.
var publicErrors = map[string]bool{
	"host_memory_reserve_exhausted":    true,
	"invalid_host_settings":            true,
	"invalid_relay":                    true,
	"invalid_owner_attestation":        true,
	"invalid_replay_floor":             true,
	"relay_mesh_not_supported":         true,
	"unsupported_environment":          true,
	"host_command_failed":              true,
	"host_command_failed_or_timed_out": true,
	"host_response_too_large":          true,
	"nostr_helper_failed":              true,
	"nostr_helper_invalid":             true,
	"host_capacity_unavailable":        true,
	"requested_cpu_exceeds_host":       true,
	"requested_memory_exceeds_host":    true,

	"connection_revoked_or_invalid":                         true,
	"configure_relay_first":                                 true,
	"desktop_launch_contract_required":                      true,
	"relay_mismatch":                                        true,
	"owner_attestation_required":                            true,
	"human_key_must_not_be_deployed":                        true,
	"unsupported_harness_use_codex_acp_or_claude_agent_acp": true,
	"unsupported_provider_configuration":                    true,
	"set_bot_parallelism_to_one":                            true,
	"stop_native_bot_before_changing_settings":              true,
	"stop_native_bot_before_image_upgrade":                  true,
	"aggregate_memory_budget_exceeded":                      true,
	"registered_bot_limit":                                  true,
	"image_changed_revalidate_before_deploy":                true,
	"deployment_not_running_inspect_host":                   true,
	"invalid_payload":                                       true,
	"invalid_environment":                                   true,
	"invalid_parallelism":                                   true,
	"custom_harness_arguments_not_supported":                true,
	"invalid_agent_identity":                                true,
	"public_anyone_mode_disabled":                           true,
	"invalid_allowlist":                                     true,
	"allowlist_required":                                    true,
	"invalid_name":                                          true,
	"invalid_memory":                                        true,
	"invalid_cpu":                                           true,
	"invalid_workspace":                                     true,
	"invalid_turn_seconds":                                  true,
	"invalid_turn_limit":                                    true,
	"invalid_window":                                        true,
	"invalid_daily_limit":                                   true,
	"invalid_native_turn_timeout":                           true,
	"invalid_idle_timeout":                                  true,
	"container_name_collision_no_changes_made":              true,
	"service_unavailable_check_docker_manager":              true,
}

func endpoint(value string) (string, error) {
	u, err := url.Parse(value)
	if err != nil || u.Scheme != "https" || u.Hostname() == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || (u.Path != "" && u.Path != "/") || u.Opaque != "" {
		return "", errors.New("https_endpoint_required")
	}
	return strings.TrimRight(value, "/"), nil
}

func connection() (Connection, error) {
	var c Connection
	home, err := os.UserHomeDir()
	if err != nil {
		return c, errors.New("home_directory_unavailable")
	}
	f, err := os.Open(filepath.Join(home, ".buzz-agents-web", "connection.json"))
	if err != nil {
		return c, errors.New("run_windows_connection_program_first")
	}
	defer f.Close()
	raw, err := io.ReadAll(io.LimitReader(f, 4097))
	if err != nil || len(raw) > 4096 || json.Unmarshal(raw, &c) != nil || !tokenPattern.MatchString(c.Token) {
		return c, errors.New("invalid_connection_file")
	}
	c.Endpoint, err = endpoint(c.Endpoint)
	return c, err
}

func client() *http.Client {
	return &http.Client{Timeout: 240 * time.Second, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return errors.New("redirect_refused") }}
}

func deploy(ctx context.Context, c Connection, raw []byte, transport *http.Client) (map[string]any, error) {
	base, err := endpoint(c.Endpoint)
	if err != nil {
		return nil, err
	}
	if !tokenPattern.MatchString(c.Token) {
		return nil, errors.New("invalid_connection_token")
	}
	req, err := http.NewRequestWithContext(ctx, "POST", base+"/api/device/deploy", bytes.NewReader(raw))
	if err != nil {
		return nil, errors.New("invalid_request")
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.Token)
	response, err := transport.Do(req)
	if err != nil {
		return nil, errors.New("https_deploy_unconfirmed_check_setup_do_not_blindly_retry")
	}
	defer response.Body.Close()
	data, err := io.ReadAll(io.LimitReader(response.Body, maxBytes+1))
	var result map[string]any
	if err != nil || len(data) > maxBytes || json.Unmarshal(data, &result) != nil {
		return nil, errors.New("invalid_server_response")
	}
	if response.StatusCode != http.StatusOK || result["ok"] != true {
		if code, ok := result["error"].(string); ok && publicErrors[code] {
			return nil, errors.New(code)
		}
		// An unsupported environment name can itself contain private text.
		// Report the category, never echo the arbitrary suffix or server body.
		if code, ok := result["error"].(string); ok && strings.HasPrefix(code, "unsupported_environment_") {
			return nil, errors.New("unsupported_environment")
		}
		return nil, errors.New("remote_deploy_refused")
	}
	id, ok := result["agent_id"].(string)
	if !ok || !idPattern.MatchString(id) {
		return nil, errors.New("invalid_remote_agent_id")
	}
	return map[string]any{"ok": true, "agent_id": id}, nil
}

func info() map[string]any {
	return map[string]any{"ok": true, "name": "Hostinger VPS — HTTPS", "version": "0.4.0", "protocol_version": 1,
		"description": "Buzz의 봇별 동시 실행 설정을 따릅니다 (기본 10, 1~32). VPS 성능에 맞게 직접 조절하세요. 배포 후 설정 화면에서 로그인하세요. / Follows Buzz per-agent concurrency (default 10, range 1–32). Adjust it to your VPS capacity. Sign in on the setup page after deployment.",
		"config_schema": map[string]any{"type": "object", "additionalProperties": false, "properties": map[string]any{
			"workspace":        map[string]any{"type": "string", "title": "공유 작업 폴더", "default": "team"},
			"memory_mb":        map[string]any{"type": "integer", "title": "RAM 한도 (MiB)", "minimum": 512, "default": 1536},
			"cpus":             map[string]any{"type": "number", "title": "CPU 한도", "minimum": 0.1, "default": 0.75},
			"max_turn_seconds": map[string]any{"type": "integer", "title": "작업당 최대 시간 (초)", "minimum": 60, "maximum": 7200, "default": 1800},
			"turn_limit":       map[string]any{"type": "integer", "title": "시간 구간당 작업 시작 한도", "minimum": 1, "maximum": 500, "default": 20},
			"window_seconds":   map[string]any{"type": "integer", "title": "집계 구간 (초)", "minimum": 60, "maximum": 86400, "default": 3600},
			"daily_limit":      map[string]any{"type": "integer", "title": "24시간 작업 시작 한도", "minimum": 1, "maximum": 2000, "default": 100},
		}}}
}

func run(input io.Reader, output io.Writer, diagnostics io.Writer) int {
	return runUsing(input, output, diagnostics, connection, client())
}

func runUsing(input io.Reader, output io.Writer, diagnostics io.Writer, load func() (Connection, error), transport *http.Client) int {
	raw, err := io.ReadAll(io.LimitReader(input, maxBytes+1))
	var request Request
	var answer map[string]any
	if err != nil || len(raw) > maxBytes {
		err = errors.New("request_too_large")
	} else if json.Unmarshal(raw, &request) != nil {
		err = errors.New("invalid_json")
	} else if request.Op == "info" {
		answer = info()
	} else if request.Op == "deploy" {
		if len(request.Agent) == 0 || bytes.Equal(request.Agent, []byte("null")) {
			err = errors.New("missing_agent")
		} else {
			var c Connection
			c, err = load()
			if err == nil {
				answer, err = deploy(context.Background(), c, raw, transport)
			}
		}
	} else {
		err = errors.New("unsupported_operation")
	}
	if err != nil {
		code := safeErrorCode(err)
		fmt.Fprintln(output, `{"ok":false,"error":`+quote(code)+`}`)
		// Buzz discards stdout on nonzero exit. stderr is its Harness log input.
		fmt.Fprintln(diagnostics, "buzz-agents: "+code+". "+errorHint(code))
		return 1
	}
	json.NewEncoder(output).Encode(answer)
	return 0
}
func quote(value string) string { data, _ := json.Marshal(value); return string(data) }
func main()                     { os.Exit(run(os.Stdin, os.Stdout, os.Stderr)) }

// Deliberately no endpoint, token, raw request, env values, or server response.
func safeErrorCode(err error) string {
	code := err.Error()
	if publicErrors[code] {
		return code
	}
	switch code {
	case "home_directory_unavailable", "run_windows_connection_program_first", "invalid_connection_file",
		"https_endpoint_required", "invalid_connection_token", "invalid_request",
		"https_deploy_unconfirmed_check_setup_do_not_blindly_retry", "invalid_server_response",
		"invalid_remote_agent_id", "remote_deploy_refused", "unsupported_environment",
		"request_too_large", "invalid_json", "missing_agent", "unsupported_operation":
		return code
	}
	return "provider_internal_error"
}
func errorHint(code string) string {
	switch code {
	case "run_windows_connection_program_first", "invalid_connection_file", "invalid_connection_token", "connection_revoked_or_invalid":
		return "Download a new Windows connection bundle from VPS setup and reconnect."
	case "set_bot_parallelism_to_one":
		return "The server still requires parallelism 1. Update buzz-agents or set the bot's parallelism to 1 before retrying."
	case "desktop_launch_contract_required":
		return "The resolved Buzz launch block or Relay owner does not match. Check Buzz compatibility and the configured owner."
	case "unsupported_environment":
		return "A launch environment setting is unsupported. Review custom environment settings; values are not logged."
	case "unsupported_harness_use_codex_acp_or_claude_agent_acp", "custom_harness_arguments_not_supported":
		return "Select Claude Code or Codex with its standard adapter and no custom arguments."
	case "https_deploy_unconfirmed_check_setup_do_not_blindly_retry", "invalid_server_response", "invalid_remote_agent_id":
		return "Deployment outcome is unknown. Check the existing bot in VPS setup before retrying."
	case "relay_mismatch", "owner_attestation_required", "human_key_must_not_be_deployed", "invalid_agent_identity":
		return "Check the community and bot identity against VPS setup. Do not paste your personal private key into logs."
	case "configure_relay_first":
		return "Connect your Relay on the VPS setup page first."
	default:
		return "Check VPS setup and Docker Manager broker/portal logs using this error code."
	}
}
