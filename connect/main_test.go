package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPairingValidation(t *testing.T) {
	for _, endpoint := range []string{"http://example.com", "https://u:p@example.com", "https://example.com/path", "https://example.com?code=secret"} {
		if validate(Pairing{Schema: 1, Endpoint: endpoint, Code: strings.Repeat("a", 43)}) == nil {
			t.Fatal(endpoint)
		}
	}
	if validate(Pairing{Schema: 1, Endpoint: "https://example.com", Code: "short"}) == nil {
		t.Fatal("short token")
	}
}
func TestPairExchangeAndInstallPersistsOnlyScopedConnection(t *testing.T) {
	home := t.TempDir()
	code := strings.Repeat("p", 43)
	token := strings.Repeat("t", 43)
	calls := 0
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.URL.String() != "/api/pair/exchange" {
			t.Error(r.URL.String())
		}
		raw, _ := io.ReadAll(r.Body)
		if !strings.Contains(string(raw), code) || strings.Contains(string(raw), "password") {
			t.Error(string(raw))
		}
		io.WriteString(w, `{"ok":true,"token":"`+token+`","device_id":"aaaaaaaaaaaaaaaaaaaaaaaa"}`)
	}))
	defer server.Close()
	p := Pairing{Schema: 1, Endpoint: server.URL, Code: code}
	if err := install(p, home, server.Client()); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(filepath.Join(home, ".buzz-agents-web", "connection.json"))
	if err != nil {
		t.Fatal(err)
	}
	var c Connection
	if json.Unmarshal(raw, &c) != nil || c.Token != token || strings.Contains(string(raw), code) {
		t.Fatal("wrong persisted credential")
	}
	if err := install(p, home, server.Client()); err == nil {
		t.Fatal("existing connection overwritten")
	}
	if calls != 1 {
		t.Fatal("replayed one-use pairing")
	}
	if _, err := os.Stat(filepath.Join(home, ".local", "bin", "buzz-backend-hostinger-https.exe")); err != nil {
		t.Fatal(err)
	}
}
func TestExistingDifferentProviderPreservedBeforeExchange(t *testing.T) {
	home := t.TempDir()
	bin := filepath.Join(home, ".local", "bin")
	os.MkdirAll(bin, 0700)
	target := filepath.Join(bin, "buzz-backend-hostinger-https.exe")
	os.WriteFile(target, []byte("original"), 0600)
	err := install(Pairing{Schema: 1, Endpoint: "https://example.com", Code: strings.Repeat("a", 43)}, home, &http.Client{})
	if err == nil {
		t.Fatal("overwrite allowed")
	}
	raw, _ := os.ReadFile(target)
	if string(raw) != "original" {
		t.Fatal("modified original")
	}
}
func TestServerSecretsNeverEchoedOnPairingFailure(t *testing.T) {
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(400)
		io.WriteString(w, `{"error":"private-server-secret"}`)
	}))
	defer server.Close()
	_, err := exchange(Pairing{Schema: 1, Endpoint: server.URL, Code: strings.Repeat("a", 43)}, "fixture", server.Client())
	if err == nil || strings.Contains(err.Error(), "private-server-secret") {
		t.Fatal(err)
	}
}
