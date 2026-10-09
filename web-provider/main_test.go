package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestInfoNeedsNoSSHOrSecrets(t *testing.T) {
	var out bytes.Buffer
	if run(strings.NewReader(`{"op":"info"}`), &out) != 0 {
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
