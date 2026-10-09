package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func connection() Connection {
	return Connection{Host: "192.0.2.1", Port: 22, Owner: strings.Repeat("a", 64), Relay: "wss://relay.example.com"}
}
func TestConnectionRejectsShellAndSSHConfigInjection(t *testing.T) {
	for _, host := range []string{"-oProxyCommand=id", "x\nProxyCommand id", "user@host", "host;id", "host/path"} {
		c := connection()
		c.Host = host
		if c.validate() == nil {
			t.Fatalf("accepted %q", host)
		}
	}
	for _, p := range []string{"C:/path\nIdentityFile bad", `C:/bad"path`, "C:/bad%h"} {
		if _, err := sshConfig(connection(), p); err == nil {
			t.Fatal("unsafe path")
		}
	}
	c := connection()
	c.Owner = "nsec1private"
	if c.validate() == nil {
		t.Fatal("private key accepted")
	}
}
func TestConfigUsesDedicatedPinnedIdentity(t *testing.T) {
	s, err := sshConfig(connection(), "C:/Users/사용자 이름/.buzz-agents")
	if err != nil {
		t.Fatal(err)
	}
	for _, part := range []string{"User buzzdeploy", "StrictHostKeyChecking yes", "IdentitiesOnly yes", "UserKnownHostsFile \"", "IdentityFile \""} {
		if !strings.Contains(s, part) {
			t.Fatal(part)
		}
	}
	if strings.Contains(s, "root") {
		t.Fatal("dedicated connection must not be root")
	}
}
func TestExistingFilesCannotBeOverwritten(t *testing.T) {
	p := filepath.Join(t.TempDir(), "existing")
	os.WriteFile(p, []byte("keep"), 0600)
	if exclusiveOrSame(p, []byte("replace"), 0600) == nil {
		t.Fatal("overwrote state")
	}
	if err := exclusiveOrSame(p, []byte("keep"), 0600); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(p)
	if string(data) != "keep" {
		t.Fatal("changed")
	}
}
func TestInstallCarriesOnlyPublicSetupDataAndChecksDedicatedConnection(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	dir := filepath.Join(home, ".buzz-agents")
	os.MkdirAll(dir, 0700)
	os.WriteFile(filepath.Join(dir, "vps_ed25519"), []byte("private fixture"), 0600)
	os.WriteFile(filepath.Join(dir, "vps_ed25519.pub"), []byte("ssh-ed25519 AAAA fixture"), 0600)
	var calls []string
	w := Wizard{dir: dir, ssh: "ssh", keygen: "ssh-keygen", run: func(_ string, args []string, in io.Reader, out, diag io.Writer) error {
		command := args[len(args)-1]
		calls = append(calls, command)
		if strings.HasPrefix(command, "python3 -c ") {
			if !strings.Contains(strings.Join(args, " "), "StrictHostKeyChecking=yes") {
				t.Fatal("unverified bootstrap")
			}
			var r map[string]string
			if json.NewDecoder(in).Decode(&r) != nil {
				t.Fatal("bad request")
			}
			if len(r) != 5 || r["owner"] != connection().Owner || strings.Contains(r["public_key"], "private") {
				t.Fatal("bad public data")
			}
			data, _ := base64.StdEncoding.DecodeString(r["archive"])
			sum := sha256.Sum256(data)
			if hex.EncodeToString(sum[:]) != r["sha256"] {
				t.Fatal("bad bundle digest")
			}
		}
		if command == "buzz-agents-status" {
			io.WriteString(out, `{"ok":true,"bots":[]}`)
		}
		return nil
	}}
	if err := w.install(connection()); err != nil {
		t.Fatal(err)
	}
	if len(calls) != 3 || calls[0] != "true" || calls[2] != "buzz-agents-status" {
		t.Fatal(calls)
	}
	if _, err := os.Stat(filepath.Join(home, ".local/bin/buzz-backend-hostinger.exe")); err != nil {
		t.Fatal(err)
	}
}
func TestFailedBootstrapDoesNotInstallProviderOrConnection(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	dir := filepath.Join(home, ".buzz-agents")
	os.MkdirAll(dir, 0700)
	os.WriteFile(filepath.Join(dir, "vps_ed25519"), []byte("fixture"), 0600)
	os.WriteFile(filepath.Join(dir, "vps_ed25519.pub"), []byte("ssh-ed25519 AAAA fixture"), 0600)
	w := Wizard{dir: dir, run: func(_ string, args []string, _ io.Reader, _, _ io.Writer) error {
		if args[len(args)-1] == "true" {
			return nil
		}
		return errors.New("build failure")
	}}
	if w.install(connection()) == nil {
		t.Fatal("false success")
	}
	for _, p := range []string{filepath.Join(dir, "ssh_config"), filepath.Join(home, ".local/bin/buzz-backend-hostinger.exe")} {
		if _, err := os.Stat(p); !os.IsNotExist(err) {
			t.Fatal("installed despite failure")
		}
	}
}
func TestLoginRunsOnVPSWithPTYAndNoTokenCopy(t *testing.T) {
	calls := 0
	w := Wizard{input: bufio.NewReader(strings.NewReader("1\n")), dir: t.TempDir(), run: func(_ string, args []string, in io.Reader, out, diag io.Writer) error {
		calls++
		command := args[len(args)-1]
		if calls == 1 {
			io.WriteString(out, `{"ok":true,"bots":[{"pubkey":"`+strings.Repeat("b", 64)+`","provider":"claude","name":"writer","status":"needs_login","container_running":true}]}`)
			return nil
		}
		if command != "buzz-agents-auth claude "+strings.Repeat("b", 64) || args[0] != "-tt" || in != os.Stdin {
			t.Fatal("not interactive remote authentication")
		}
		return nil
	}}
	if err := w.login(); err != nil {
		t.Fatal(err)
	}
	if calls != 2 {
		t.Fatal(calls)
	}
}
func TestUntrustedBotResponseRejected(t *testing.T) {
	for _, s := range []string{`{"ok":false}`, `{"ok":true,"bots":[{"pubkey":";id","provider":"codex"}]}`, `{"ok":true,"bots":[{"pubkey":"` + strings.Repeat("a", 64) + `","provider":"bash"}]}`} {
		if _, err := decodeStatus([]byte(s)); err == nil {
			t.Fatal("unsafe response")
		}
	}
}
