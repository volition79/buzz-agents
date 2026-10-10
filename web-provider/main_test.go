package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestInfoNeedsNoSSHOrSecrets(t *testing.T) {
	var out bytes.Buffer
	if run(strings.NewReader(`{"op":"info"}`), &out, io.Discard) != 0 {
		t.Fatal(out.String())
	}
	var data map[string]any
	json.Unmarshal(out.Bytes(), &data)
	props := data["config_schema"].(map[string]any)["properties"].(map[string]any)
	for key := range props {
		for _, bad := range []string{"ssh", "password", "token", "secret", "key"} {
			if strings.Contains(key, bad) {
				t.Fatal(key)
			}
		}
	}
	if data["protocol_version"] != float64(1) {
		t.Fatal(data)
	}
}
func TestStrictEndpoint(t *testing.T) {
	for _, bad := range []string{"http://example.com", "https://user:pw@example.com", "https://example.com/x", "https://example.com?token=x", "https://example.com#x", "https:///path"} {
		if _, err := endpoint(bad); err == nil {
			t.Fatal(bad)
		}
	}
}
func TestTLSDeployIdentityAndSecretsOnlyInBody(t *testing.T) {
	token := strings.Repeat("a", 43)
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.String() != "/api/device/deploy" || r.Header.Get("Authorization") != "Bearer "+token {
			t.Error("wrong request")
		}
		body, _ := io.ReadAll(r.Body)
		if !bytes.Contains(body, []byte("fixture-private")) {
			t.Error("missing launch payload")
		}
		io.WriteString(w, `{"ok":true,"agent_id":"buzz-native-bbbbbbbbbbbbbbbbbbbb","private":"never-return"}`)
	}))
	defer server.Close()
	result, err := deploy(context.Background(), Connection{Endpoint: server.URL, Token: token}, []byte(`{"agent":{"private_key_nsec":"fixture-private"}}`), server.Client())
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := json.Marshal(result)
	if strings.Contains(string(raw), "private") || strings.Contains(string(raw), token) {
		t.Fatal(string(raw))
	}
}
func TestInvalidIDAndUnsafeErrorsRejected(t *testing.T) {
	for _, reply := range []string{`{"ok":true,"agent_id":"../../shell"}`, `{"ok":false,"error":"nsec secret value"}`, `{"ok":false,"error":"nsec1SecretWithoutSpaces"}`, strings.Repeat("x", maxBytes+1)} {
		server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, reply) }))
		_, err := deploy(context.Background(), Connection{Endpoint: server.URL, Token: strings.Repeat("a", 43)}, []byte(`{}`), server.Client())
		server.Close()
		if err == nil || strings.Contains(err.Error(), "nsec") {
			t.Fatal(err)
		}
	}
}
func TestRedirectNeverSendsCredentialsToSecondHost(t *testing.T) {
	hits := 0
	second := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { hits++ }))
	defer second.Close()
	first := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { http.Redirect(w, r, second.URL, 307) }))
	defer first.Close()
	c := client()
	c.Transport = first.Client().Transport
	_, err := deploy(context.Background(), Connection{Endpoint: first.URL, Token: strings.Repeat("a", 43)}, []byte(`{}`), c)
	if err == nil || hits != 0 {
		t.Fatalf("redirect followed: %v %d", err, hits)
	}
}
func TestUntrustedTLSIsNotSilentlyAccepted(t *testing.T) {
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {}))
	defer server.Close()
	_, err := deploy(context.Background(), Connection{Endpoint: server.URL, Token: strings.Repeat("a", 43)}, []byte(`{}`), client())
	if err == nil {
		t.Fatal("untrusted certificate accepted")
	}
}

// Mirrors Buzz invoke_provider: exit != 0 surfaces stderr, not stdout JSON.
func TestBuzzHarnessLogReceivesSafeTLSFailure(t *testing.T) {
	for _, tc := range []struct{ reply, code string }{
		{`{"ok":false,"error":"set_bot_parallelism_to_one"}`, "set_bot_parallelism_to_one"},
		{`{"ok":false,"error":"desktop_launch_contract_required"}`, "desktop_launch_contract_required"},
		{`{"ok":false,"error":"invalid_relay"}`, "invalid_relay"},
		{`{"ok":false,"error":"host_command_failed"}`, "host_command_failed"},
		{`{"ok":false,"error":"invalid_replay_floor"}`, "invalid_replay_floor"},
		{`{"ok":false,"error":"host_capacity_unavailable"}`, "host_capacity_unavailable"},
		{`{"ok":false,"error":"unsupported_environment_SECRET_VALUE"}`, "unsupported_environment"},
		{`{"ok":false,"error":"nsec1SECRET_VALUE"}`, "remote_deploy_refused"},
	} {
		t.Run(tc.code, func(t *testing.T) {
			server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(http.StatusBadRequest)
				io.WriteString(w, tc.reply)
			}))
			defer server.Close()
			var out, diagnostic bytes.Buffer
			status := runUsing(strings.NewReader(`{"op":"deploy","agent":{"private_key_nsec":"SECRET_VALUE"}}`), &out, &diagnostic,
				func() (Connection, error) {
					return Connection{Endpoint: server.URL, Token: strings.Repeat("t", 43)}, nil
				}, server.Client())
			if status != 1 || !strings.Contains(diagnostic.String(), tc.code) || !strings.Contains(out.String(), `"ok":false`) {
				t.Fatal(status, out.String(), diagnostic.String())
			}
			if strings.Contains(diagnostic.String(), "SECRET_VALUE") || strings.Contains(diagnostic.String(), server.URL) || strings.Contains(diagnostic.String(), strings.Repeat("t", 43)) {
				t.Fatal("secret leaked")
			}
		})
	}
}
func TestMalformedRequestCannotEchoSecrets(t *testing.T) {
	var out, diagnostic bytes.Buffer
	status := run(strings.NewReader(`{"op":"deploy","agent":"SECRET_VALUE"`), &out, &diagnostic)
	if status != 1 || !strings.Contains(diagnostic.String(), "invalid_json") || strings.Contains(out.String()+diagnostic.String(), "SECRET_VALUE") {
		t.Fatal(status, out.String(), diagnostic.String())
	}
}
func TestSuccessfulDeployRemainsMachineReadable(t *testing.T) {
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		io.WriteString(w, `{"ok":true,"agent_id":"buzz-native-bbbbbbbbbbbbbbbbbbbb"}`)
	}))
	defer server.Close()
	var out, diagnostic bytes.Buffer
	status := runUsing(strings.NewReader(`{"op":"deploy","request_id":"fixture","agent":{}}`), &out, &diagnostic,
		func() (Connection, error) {
			return Connection{Endpoint: server.URL, Token: strings.Repeat("t", 43)}, nil
		}, server.Client())
	var result map[string]any
	if status != 0 || diagnostic.Len() != 0 || json.Unmarshal(out.Bytes(), &result) != nil || result["ok"] != true {
		t.Fatal(status, out.String(), diagnostic.String())
	}
}

func TestResourceUpgradeHintPreservesCode(t *testing.T) {
	for _, code := range []string{"stop_native_bot_before_resource_upgrade", "stop_native_bot_before_image_upgrade"} {
		if got := safeErrorCode(errors.New(code)); got != code {
			t.Fatalf("code: %s", got)
		}
		if !strings.Contains(errorHint(code), "Windows Buzz") {
			t.Fatal("missing concrete stop guidance")
		}
	}
}

func TestOptionalPromptBudgetsAndOfficialTimeoutDefaults(t *testing.T) {
	props := info()["config_schema"].(map[string]any)["properties"].(map[string]any)
	for _, name := range []string{"turn_limit", "daily_limit"} {
		field := props[name].(map[string]any)
		if field["minimum"] != 0 || field["default"] != 0 {
			t.Fatalf("%s must permit and default to disabled: %v", name, field)
		}
	}
	duration := props["max_turn_seconds"].(map[string]any)
	if duration["default"] != 7200 || duration["maximum"] != 604800 {
		t.Fatalf("official duration defaults/cap differ: %v", duration)
	}
}
