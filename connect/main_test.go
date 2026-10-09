package main

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
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

func TestReconnectCommitsBeforeRevokingPrevious(t *testing.T) {
	home := t.TempDir()
	oldToken, newToken := strings.Repeat("o", 43), strings.Repeat("n", 43)
	oldID, newID := strings.Repeat("a", 24), strings.Repeat("b", 24)
	var server *httptest.Server
	server = httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/pair/exchange":
			io.WriteString(w, `{"ok":true,"token":"`+newToken+`","device_id":"`+newID+`"}`)
		case "/api/device/revoke-self":
			c, _, err := readConnection(home)
			if err != nil || c.Token != newToken {
				t.Error("old credential revoked before local commit")
			}
			if r.Header.Get("Authorization") != "Bearer "+oldToken {
				t.Error("wrong revoked credential")
			}
			io.WriteString(w, `{"ok":true}`)
		default:
			t.Error(r.URL.Path)
		}
	}))
	defer server.Close()
	dir := filepath.Join(home, ".buzz-agents-web")
	os.MkdirAll(dir, 0700)
	raw, _ := json.Marshal(Connection{server.URL, oldToken, oldID})
	os.WriteFile(filepath.Join(dir, "connection.json"), raw, 0600)
	if err := installConnection(Pairing{1, server.URL, strings.Repeat("p", 43)}, home, server.Client(), true, commitFile); err != nil {
		t.Fatal(err)
	}
	c, _, err := readConnection(home)
	if err != nil || c.Token != newToken {
		t.Fatal("new connection not saved")
	}
}

func TestSaveFailurePreservesOldConnectionAndCleansNewDevice(t *testing.T) {
	for _, cleanupOK := range []bool{true, false} {
		t.Run(map[bool]string{true: "cleanup", false: "manual-recovery"}[cleanupOK], func(t *testing.T) {
			home := t.TempDir()
			dir := filepath.Join(home, ".buzz-agents-web")
			os.MkdirAll(dir, 0700)
			original := []byte(`{"old":"partial-existing-file"}`)
			os.WriteFile(filepath.Join(dir, "connection.json"), original, 0600)
			cleanup := false
			server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path == "/api/pair/exchange" {
					io.WriteString(w, `{"ok":true,"token":"`+strings.Repeat("n", 43)+`","device_id":"bbbbbbbbbbbbbbbbbbbbbbbb"}`)
					return
				}
				if r.URL.Path != "/api/device/revoke-self" {
					t.Error(r.URL.Path)
				}
				cleanup = true
				if !cleanupOK {
					w.WriteHeader(500)
					return
				}
				io.WriteString(w, `{"ok":true}`)
			}))
			defer server.Close()
			err := installConnection(Pairing{1, server.URL, strings.Repeat("p", 43)}, home, server.Client(), true, func(string, string, bool) error { return os.ErrPermission })
			if err == nil || !cleanup {
				t.Fatal("save failure not cleaned up")
			}
			if !cleanupOK && !strings.Contains(err.Error(), "bbbbbbbbbbbbbbbbbbbbbbbb") {
				t.Fatal("missing orphan ID")
			}
			if strings.Contains(err.Error(), strings.Repeat("n", 43)) {
				t.Fatal("token leak")
			}
			raw, _ := os.ReadFile(filepath.Join(dir, "connection.json"))
			if string(raw) != string(original) {
				t.Fatal("old connection changed")
			}
			files, _ := filepath.Glob(filepath.Join(dir, ".connection-*.tmp"))
			if len(files) > 0 {
				t.Fatal("staging credential retained")
			}
		})
	}
}

func TestCommitNoClobberAndExclusiveInstallLock(t *testing.T) {
	dir := t.TempDir()
	target := filepath.Join(dir, "connection.json")
	source := filepath.Join(dir, "staging")
	os.WriteFile(target, []byte("old"), 0600)
	os.WriteFile(source, []byte("new"), 0600)
	if commitFile(source, target, false) == nil {
		t.Fatal("existing target replaced without approval")
	}
	raw, _ := os.ReadFile(target)
	if string(raw) != "old" {
		t.Fatal("old data lost")
	}
	if err := commitFile(source, target, true); err != nil {
		t.Fatal(err)
	}
	raw, _ = os.ReadFile(target)
	if string(raw) != "new" {
		t.Fatal("reconnect not committed")
	}
	unlock, err := lockInstall(filepath.Join(dir, "lock"))
	if err != nil {
		t.Fatal(err)
	}
	if second, err := lockInstall(filepath.Join(dir, "lock")); err == nil {
		second()
		t.Fatal("parallel installers allowed")
	}
	unlock()
	unlock, err = lockInstall(filepath.Join(dir, "lock"))
	if err != nil {
		t.Fatal("lock not released", err)
	}
	unlock()
}

func TestHealthyConnectionCheckDoesNotConsumePairing(t *testing.T) {
	token, id := strings.Repeat("t", 43), strings.Repeat("a", 24)
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/device/check" || r.Header.Get("Authorization") != "Bearer "+token {
			t.Error("unexpected request")
		}
		io.WriteString(w, `{"ok":true,"device_id":"`+id+`"}`)
	}))
	defer server.Close()
	if !deviceRequest(Connection{server.URL, token, id}, "check", server.Client()) {
		t.Fatal("healthy connection not recognized")
	}
}

func TestReviewedCompatibleProviderIsKept(t *testing.T) {
	home := t.TempDir()
	bin := filepath.Join(home, ".local", "bin")
	os.MkdirAll(bin, 0700)
	old := []byte("reviewed-compatible-provider-fixture")
	hash := fmt.Sprintf("%x", sha256.Sum256(old))
	compatibleProviders[hash] = true
	defer delete(compatibleProviders, hash)
	target := filepath.Join(bin, "buzz-backend-hostinger-https.exe")
	os.WriteFile(target, old, 0600)
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		io.WriteString(w, `{"ok":true,"token":"`+strings.Repeat("t", 43)+`","device_id":"aaaaaaaaaaaaaaaaaaaaaaaa"}`)
	}))
	defer server.Close()
	if err := install(Pairing{1, server.URL, strings.Repeat("p", 43)}, home, server.Client()); err != nil {
		t.Fatal(err)
	}
	after, _ := os.ReadFile(target)
	if string(after) != string(old) {
		t.Fatal("reviewed provider overwritten")
	}
	if compatibleProvider(append(old, byte('!'))) {
		t.Fatal("modified provider accepted")
	}
}
