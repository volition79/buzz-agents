// Installs a scoped HTTPS backend from a one-use pairing bundle. Never SSHs.
package main

import (
	"bufio"
	"bytes"
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

//go:embed assets/buzz-backend-hostinger-https.exe
var provider []byte

type Pairing struct {
	Schema   int    `json:"schema"`
	Endpoint string `json:"endpoint"`
	Code     string `json:"pairing_code"`
}
type Connection struct {
	Endpoint string `json:"endpoint"`
	Token    string `json:"token"`
	DeviceID string `json:"device_id"`
}

var tokenPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{32,100}$`)

func validate(p Pairing) error {
	u, e := url.Parse(p.Endpoint)
	if e != nil || p.Schema != 1 || !tokenPattern.MatchString(p.Code) || u.Scheme != "https" || u.Hostname() == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || (u.Path != "" && u.Path != "/") || u.Opaque != "" {
		return errors.New("올바른 HTTPS 연결 파일이 아닙니다.")
	}
	return nil
}

func exchange(p Pairing, name string, client *http.Client) (Connection, error) {
	c := Connection{}
	if err := validate(p); err != nil {
		return c, err
	}
	data, _ := json.Marshal(map[string]string{"pairing_code": p.Code, "name": name})
	req, err := http.NewRequest("POST", strings.TrimRight(p.Endpoint, "/")+"/api/pair/exchange", bytes.NewReader(data))
	if err != nil {
		return c, errors.New("연결 요청을 만들지 못했습니다.")
	}
	req.Header.Set("Content-Type", "application/json")
	response, err := client.Do(req)
	if err != nil {
		return c, errors.New("HTTPS 연결에 실패했습니다. 설정 화면에서 연결 목록을 확인한 뒤 새 연결 파일을 받으세요.")
	}
	defer response.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(response.Body, 4097))
	var answer struct {
		OK       bool   `json:"ok"`
		Token    string `json:"token"`
		DeviceID string `json:"device_id"`
	}
	if err != nil || len(raw) > 4096 || response.StatusCode != 200 || json.Unmarshal(raw, &answer) != nil || !answer.OK || !tokenPattern.MatchString(answer.Token) || !regexp.MustCompile(`^[a-f0-9]{24}$`).MatchString(answer.DeviceID) {
		return c, errors.New("연결 파일이 만료되었거나 이미 사용되었습니다. 설정 화면에서 다시 받아 주세요.")
	}
	return Connection{Endpoint: strings.TrimRight(p.Endpoint, "/"), Token: answer.Token, DeviceID: answer.DeviceID}, nil
}

func protect(path string) error {
	if runtime.GOOS != "windows" {
		return os.Chmod(path, 0700)
	}
	current, err := user.Current()
	if err != nil {
		return errors.New("Windows 사용자 확인 실패")
	}
	cmd := exec.Command(filepath.Join(os.Getenv("SystemRoot"), "System32", "icacls.exe"), path, "/inheritance:r", "/grant:r", current.Username+":(OI)(CI)F")
	if err := cmd.Run(); err != nil {
		return errors.New("연결 정보 폴더의 Windows 접근 권한 설정 실패")
	}
	return nil
}

func install(p Pairing, home string, client *http.Client) error {
	if err := validate(p); err != nil {
		return err
	}
	dir := filepath.Join(home, ".buzz-agents-web")
	config := filepath.Join(dir, "connection.json")
	if _, err := os.Stat(config); err == nil {
		return errors.New("이미 Windows 연결 정보가 있습니다. 기존 연결은 보존했습니다. 설정 화면의 연결 목록을 먼저 확인해 주세요.")
	} else if !os.IsNotExist(err) {
		return err
	}
	bin := filepath.Join(home, ".local", "bin")
	target := filepath.Join(bin, "buzz-backend-hostinger-https.exe")
	if old, err := os.ReadFile(target); err == nil && !bytes.Equal(old, provider) {
		return errors.New("다른 버전의 HTTPS 연결기가 있어 자동으로 덮어쓰지 않습니다.")
	} else if err != nil && !os.IsNotExist(err) {
		return err
	}
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	if err := protect(dir); err != nil {
		return err
	}
	if err := os.MkdirAll(bin, 0755); err != nil {
		return err
	}
	// Prepare executable before redeeming a one-use code. No global PATH edits.
	if err := os.WriteFile(target, provider, 0755); err != nil {
		return err
	}
	name, _ := os.Hostname()
	if name == "" {
		name = "Windows Buzz"
	}
	if len(name) > 80 {
		name = name[:80]
	}
	c, err := exchange(p, name, client)
	if err != nil {
		return err
	}
	data, _ := json.MarshalIndent(c, "", "  ")
	f, err := os.OpenFile(config, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return errors.New("연결 정보 저장 실패. 설정 화면에서 방금 만든 Windows 연결을 해제한 뒤 다시 시도하세요.")
	}
	_, writeErr := f.Write(data)
	closeErr := f.Close()
	if writeErr != nil || closeErr != nil {
		return errors.New("연결 정보 저장 실패. 설정 화면에서 해당 연결을 해제하세요.")
	}
	return nil
}

func main() {
	fmt.Println("Buzz VPS · Windows 연결\nroot 비밀번호나 SSH는 필요하지 않습니다.")
	in := bufio.NewReader(os.Stdin)
	defer func() { fmt.Println("\nEnter를 누르면 닫힙니다."); in.ReadString('\n') }()
	exe, err := os.Executable()
	if err != nil {
		fmt.Println("프로그램 경로 확인 실패")
		return
	}
	path := filepath.Join(filepath.Dir(exe), "buzz-pairing.json")
	if len(os.Args) == 2 {
		path = os.Args[1]
	}
	file, err := os.Open(path)
	if err != nil {
		fmt.Println("연결 ZIP의 압축을 모두 푼 뒤 실행해 주세요. buzz-pairing.json이 같은 폴더에 있어야 합니다.")
		return
	}
	raw, err := io.ReadAll(io.LimitReader(file, 4097))
	file.Close()
	var p Pairing
	if err != nil || len(raw) > 4096 || json.Unmarshal(raw, &p) != nil || validate(p) != nil {
		fmt.Println("연결 파일을 확인할 수 없습니다.")
		return
	}
	fmt.Println("\n연결할 서버: " + p.Endpoint + "\n본인의 설정 화면 주소가 맞으면 Enter, 취소하려면 n을 입력하세요.")
	answer, _ := in.ReadString('\n')
	if strings.TrimSpace(answer) != "" {
		fmt.Println("취소했습니다.")
		return
	}
	home, err := os.UserHomeDir()
	if err != nil {
		fmt.Println("사용자 폴더 확인 실패")
		return
	}
	client := &http.Client{Timeout: 30 * time.Second, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return errors.New("redirect refused") }}
	if err := install(p, home, client); err != nil {
		fmt.Println("완료되지 않음: " + err.Error())
		return
	}
	fmt.Println("\nWindows 연결을 저장했습니다.\n1. Buzz를 다시 실행하세요.\n2. 봇 실행 위치에서 Hostinger VPS — HTTPS를 선택하고 배포하세요.\n3. 서버 설정 화면에서 해당 봇의 Codex·Claude 계정에 로그인하세요.")
}
