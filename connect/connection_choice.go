package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

type connectionState int

const (
	connectionUnknown connectionState = iota
	connectionHealthy
	connectionInvalid
	connectionDamaged
)

type connectionChoice int

const (
	connectionCancel connectionChoice = iota
	connectionKeep
	connectionReconnect
)

// A network failure, generic 401, old endpoint or malformed reply does not prove
// revocation. Only the portal's explicit rejection makes reconnect the default.
func checkConnection(c Connection, client *http.Client) connectionState {
	if validate(Pairing{1, c.Endpoint, c.Token}) != nil {
		return connectionDamaged
	}
	req, err := http.NewRequest("POST", strings.TrimRight(c.Endpoint, "/")+"/api/device/check", strings.NewReader("{}"))
	if err != nil {
		return connectionUnknown
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.Token)
	response, err := client.Do(req)
	if err != nil {
		return connectionUnknown
	}
	defer response.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(response.Body, 4097))
	var value struct {
		OK       bool   `json:"ok"`
		DeviceID string `json:"device_id"`
		Error    string `json:"error"`
	}
	if err != nil || len(raw) > 4096 || json.Unmarshal(raw, &value) != nil {
		return connectionUnknown
	}
	if response.StatusCode == http.StatusOK && value.OK && value.DeviceID == c.DeviceID && value.Error == "" {
		return connectionHealthy
	}
	if response.StatusCode == http.StatusUnauthorized && !value.OK && value.Error == "connection_revoked_or_invalid" {
		return connectionInvalid
	}
	return connectionUnknown
}

// Checking and choosing never consumes the pairing grant or alters local files.
// EOF always cancels; it must never mean "keep", retry forever, or reconnect.
func chooseConnection(in *bufio.Reader, out io.Writer, check func() connectionState) connectionChoice {
retry:
	for {
		state := check()
		switch state {
		case connectionHealthy:
			fmt.Fprintln(out, "기존 Windows 연결이 정상입니다. 다시 설치할 필요가 없습니다.")
			fmt.Fprintln(out, "Enter: 기존 연결 유지 / r: 재연결 (먼저 Buzz를 종료하세요) / n: 취소")
		case connectionInvalid:
			fmt.Fprintln(out, "서버에서 기존 연결이 해제되었거나 유효하지 않다고 확인했습니다. 재연결이 필요합니다.")
			fmt.Fprintln(out, "먼저 Buzz를 종료하세요. Enter: 재연결 / n: 취소")
		case connectionDamaged:
			fmt.Fprintln(out, "기존 연결 파일을 읽을 수 없습니다. 새 연결을 저장하는 데 성공한 경우에만 교체합니다.")
			fmt.Fprintln(out, "먼저 Buzz를 종료하세요. Enter: 재연결 / n: 취소")
		default:
			fmt.Fprintln(out, "기존 연결 상태를 확인하지 못했습니다. 서버 응답이나 네트워크 문제일 수 있으며, 연결 해제가 확인된 것은 아닙니다.")
			fmt.Fprintln(out, "Enter: 연결 확인 재시도 / r: 재연결 (먼저 Buzz를 종료하세요) / n: 취소")
		}
		for {
			answer, err := in.ReadString('\n')
			if err != nil {
				return connectionCancel
			}
			switch strings.ToLower(strings.TrimSpace(answer)) {
			case "n":
				return connectionCancel
			case "r":
				return connectionReconnect
			case "":
				switch state {
				case connectionHealthy:
					return connectionKeep
				case connectionInvalid, connectionDamaged:
					return connectionReconnect
				default:
					continue retry
				}
			default:
				fmt.Fprintln(out, "표시된 선택지를 입력해 주세요. 취소하려면 n을 입력하세요.")
			}
		}
	}
}
