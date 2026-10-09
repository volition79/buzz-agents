package main

import (
	"bufio"
	"bytes"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestConnectionClassification(t *testing.T) {
	id := strings.Repeat("a", 24)
	for _, tc := range []struct {
		name   string
		status int
		body   string
		want   connectionState
	}{
		{"healthy", 200, `{"ok":true,"device_id":"` + id + `"}`, connectionHealthy},
		{"explicit-revocation", 401, `{"ok":false,"error":"connection_revoked_or_invalid"}`, connectionInvalid},
		{"generic-unauthorized", 401, `{"error":"unauthorized"}`, connectionUnknown},
		{"server-failure", 503, `{"ok":false}`, connectionUnknown},
		{"older-server", 404, `{"ok":false,"error":"not_found"}`, connectionUnknown},
		{"wrong-device", 200, `{"ok":true,"device_id":"bbbbbbbbbbbbbbbbbbbbbbbb"}`, connectionUnknown},
		{"malformed", 200, `<html>maintenance</html>`, connectionUnknown},
		{"trailing-data", 200, `{"ok":true,"device_id":"` + id + `"}unexpected`, connectionUnknown},
		{"oversize", 200, strings.Repeat(" ", 4097), connectionUnknown},
	} {
		t.Run(tc.name, func(t *testing.T) {
			server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/api/device/check" || r.Method != "POST" || r.Header.Get("Authorization") != "Bearer "+strings.Repeat("t", 43) {
					t.Error("unexpected request")
				}
				w.WriteHeader(tc.status)
				fmt.Fprint(w, tc.body)
			}))
			defer server.Close()
			if got := checkConnection(Connection{server.URL, strings.Repeat("t", 43), id}, server.Client()); got != tc.want {
				t.Fatalf("got %v want %v", got, tc.want)
			}
		})
	}
	server := httptest.NewTLSServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	client := server.Client()
	server.Close()
	if got := checkConnection(Connection{server.URL, strings.Repeat("t", 43), id}, client); got != connectionUnknown {
		t.Fatal("transport failure treated as invalid")
	}
}

func TestConnectionChoiceByState(t *testing.T) {
	for _, tc := range []struct {
		name, input string
		states      []connectionState
		want        connectionChoice
		checks      int
	}{
		{"healthy-enter", "\n", []connectionState{connectionHealthy}, connectionKeep, 1},
		{"revoked-enter", "\n", []connectionState{connectionInvalid}, connectionReconnect, 1},
		{"damaged-enter", "\n", []connectionState{connectionDamaged}, connectionReconnect, 1},
		{"unknown-retry-healthy", "\n\n", []connectionState{connectionUnknown, connectionHealthy}, connectionKeep, 2},
		{"unknown-retry-revoked", "\n\n", []connectionState{connectionUnknown, connectionInvalid}, connectionReconnect, 2},
		{"unknown-uppercase-reconnect", "R\n", []connectionState{connectionUnknown}, connectionReconnect, 1},
		{"unknown-retry-cancel", "\nN\n", []connectionState{connectionUnknown}, connectionCancel, 2},
		{"invalid-input", "x\nn\n", []connectionState{connectionInvalid}, connectionCancel, 1},
		{"healthy-eof", "", []connectionState{connectionHealthy}, connectionCancel, 1},
		{"revoked-eof", "", []connectionState{connectionInvalid}, connectionCancel, 1},
		{"unknown-eof", "", []connectionState{connectionUnknown}, connectionCancel, 1},
	} {
		t.Run(tc.name, func(t *testing.T) {
			checks := 0
			var out bytes.Buffer
			got := chooseConnection(bufio.NewReader(strings.NewReader(tc.input)), &out, func() connectionState {
				index := checks
				if index >= len(tc.states) {
					index = len(tc.states) - 1
				}
				checks++
				return tc.states[index]
			})
			if got != tc.want || checks != tc.checks {
				t.Fatalf("choice=%v checks=%d, want %v %d", got, checks, tc.want, tc.checks)
			}
			if tc.states[0] != connectionHealthy && len(tc.states) == 1 && strings.Contains(out.String(), "Enter: 기존 연결 유지") {
				t.Fatal("unverified connection offered as keep default")
			}
		})
	}
}
