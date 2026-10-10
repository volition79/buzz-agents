package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// CI supplies independently verified public executable bytes, never fake hashes.
func TestAllReleasedProvidersUpgrade(t *testing.T) {
	directory := os.Getenv("BUZZ_PROVIDER_HISTORY_DIR")
	if directory == "" {
		t.Skip("public release fixtures not supplied")
	}
	files, err := filepath.Glob(filepath.Join(directory, "*.exe"))
	if err != nil || len(files) == 0 {
		t.Fatal("missing release fixtures", err)
	}
	for _, file := range files {
		t.Run(filepath.Base(file), func(t *testing.T) {
			old, err := os.ReadFile(file)
			if err != nil {
				t.Fatal(err)
			}
			if !compatibleProvider(old) {
				t.Fatal("official released provider is not upgradeable")
			}
			for _, mode := range []string{"healthy", "reconnect"} {
				t.Run(mode, func(t *testing.T) {
					home := t.TempDir()
					bin := filepath.Join(home, ".local", "bin")
					dir := filepath.Join(home, ".buzz-agents-web")
					os.MkdirAll(bin, 0700)
					os.MkdirAll(dir, 0700)
					target := filepath.Join(bin, "buzz-backend-hostinger-https.exe")
					os.WriteFile(target, old, 0600)
					config := filepath.Join(dir, "connection.json")
					before, _ := json.Marshal(Connection{Endpoint: "https://previous.example.com", Token: strings.Repeat("o", 43), DeviceID: strings.Repeat("a", 24)})
					os.WriteFile(config, before, 0600)
					var e error
					if mode == "healthy" {
						e = upgradeConnectedProvider(home)
					} else {
						server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
							w.Header().Set("Content-Type", "application/json")
							w.Write([]byte(`{"ok":true,"token":"` + strings.Repeat("n", 43) + `","device_id":"bbbbbbbbbbbbbbbbbbbbbbbb"}`))
						}))
						defer server.Close()
						e = installConnection(Pairing{1, server.URL, strings.Repeat("p", 43)}, home, server.Client(), true, commitFile)
					}
					if e != nil {
						t.Fatal(e)
					}
					after, _ := os.ReadFile(target)
					if !bytes.Equal(after, provider) {
						t.Fatal("not upgraded")
					}
					unchanged, _ := os.ReadFile(config)
					if mode == "healthy" && !bytes.Equal(unchanged, before) {
						t.Fatal("credentials changed")
					}
					if mode == "reconnect" {
						c, _, err := readConnection(home)
						if err != nil || c.DeviceID != "bbbbbbbbbbbbbbbbbbbbbbbb" {
							t.Fatal("reconnect not saved", err)
						}
					}
				})
			}
			if compatibleProvider(append(append([]byte(nil), old...), []byte(strings.Repeat("tampered", 2))...)) {
				t.Fatal("tampered release accepted")
			}
		})
	}
}
