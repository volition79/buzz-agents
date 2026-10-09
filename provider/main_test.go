package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func call(raw string) (int, map[string]any, string) {
	var out bytes.Buffer
	code := run(strings.NewReader(raw), &out)
	var answer map[string]any
	json.Unmarshal(out.Bytes(), &answer)
	return code, answer, out.String()
}
func TestInfoContract(t *testing.T) {
	code, a, _ := call(`{"op":"info","request_id":"test"}`)
	if code != 0 || a["ok"] != true || a["protocol_version"] != float64(1) {
		t.Fatalf("bad info: %v", a)
	}
}
func TestInfoNoSecretConfigFields(t *testing.T) {
	_, a, _ := call(`{"op":"info"}`)
	schema := a["config_schema"].(map[string]any)
	for k := range schema["properties"].(map[string]any) {
		for _, word := range []string{"secret", "password", "token", "key", "credential"} {
			if strings.Contains(k, word) {
				t.Fatalf("secret schema field %s", k)
			}
		}
	}
}
func TestMalformedAndUnsupportedInput(t *testing.T) {
	for _, raw := range []string{`{`, `{"op":"remove"}`, strings.Repeat("x", maxBytes+1)} {
		code, a, _ := call(raw)
		if code == 0 || a["ok"] != false {
			t.Fatal("unsafe input accepted")
		}
	}
}
func TestAliasCannotInjectSSHOptions(t *testing.T) {
	for _, alias := range []string{"-oProxyCommand=evil", "x;id", "root@host", "host -v", "../host"} {
		raw, _ := json.Marshal(map[string]any{"op": "deploy", "agent": map[string]any{}, "provider_config": map[string]any{"ssh_alias": alias}})
		code, _, _ := call(string(raw))
		if code == 0 {
			t.Fatal("unsafe alias accepted")
		}
	}
}
func fakeSSH(t *testing.T, script string) {
	t.Helper()
	dir := t.TempDir()
	p := filepath.Join(dir, "ssh")
	if err := os.WriteFile(p, []byte("#!/bin/sh\n"+script), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("SystemRoot", "")
	t.Setenv("PATH", dir+string(os.PathListSeparator)+os.Getenv("PATH"))
}
func TestDeployPassesSecretsOnlyThroughStdin(t *testing.T) {
	fakeSSH(t, `case "$*" in *private-value*) exit 9;; esac
cat >/dev/null
printf '%s\n' '{"ok":true,"agent_id":"buzz-native-bbbbbbbbbbbbbbbbbbbb","secret":"not-for-output"}'
`)
	code, a, raw := call(`{"op":"deploy","agent":{"private_key_nsec":"private-value"},"provider_config":{"ssh_alias":"buzz-vps"}}`)
	if code != 0 || a["ok"] != true || strings.Contains(raw, "secret") || strings.Contains(raw, "private-value") {
		t.Fatalf("bad deploy: %s", raw)
	}
}
func TestFailedSSHNeverEchoesStderr(t *testing.T) {
	fakeSSH(t, `cat >/dev/null; echo 'nsec1SUPERSECRET' >&2; exit 4`)
	code, _, raw := call(`{"op":"deploy","agent":{},"provider_config":{"ssh_alias":"buzz-vps"}}`)
	if code == 0 || strings.Contains(raw, "SUPERSECRET") {
		t.Fatal("stderr leak")
	}
}
func TestServerFailureCodeSafe(t *testing.T) {
	fakeSSH(t, `cat >/dev/null; echo '{"ok":false,"error":"stop_native_bot_before_changing_settings"}';exit 1`)
	code, a, _ := call(`{"op":"deploy","agent":{},"provider_config":{"ssh_alias":"buzz-vps"}}`)
	if code == 0 || a["error"] != "stop_native_bot_before_changing_settings" {
		t.Fatal(a)
	}
}
func TestUnsafeRemoteIDRejected(t *testing.T) {
	fakeSSH(t, `cat >/dev/null; echo '{"ok":true,"agent_id":"../../danger"}'`)
	code, _, _ := call(`{"op":"deploy","agent":{},"provider_config":{"ssh_alias":"buzz-vps"}}`)
	if code == 0 {
		t.Fatal("invalid id accepted")
	}
}

func TestEasySetupUsesDedicatedConfig(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	dir := filepath.Join(home, ".buzz-agents")
	os.MkdirAll(dir, 0700)
	p := filepath.Join(dir, "ssh_config")
	os.WriteFile(p, []byte("Host buzz-vps\n"), 0600)
	args, err := sshArgs("buzz-vps")
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(strings.Join(args, "|"), "-F|"+p) {
		t.Fatal(args)
	}
	args, err = sshArgs("other-host")
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(strings.Join(args, "|"), "-F|") {
		t.Fatal("legacy alias redirected")
	}
}
