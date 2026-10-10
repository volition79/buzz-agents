// Installs a scoped HTTPS backend from a one-use pairing bundle. Never SSHs.
package main

import (
	"bufio"
	"bytes"
	"crypto/sha256"
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

// Offline catalog of verified official releases. CI checks completeness against
// published manifests and hashes every distinct executable before publication.
//
//go:embed provider-history.json
var providerHistory []byte

var compatibleProviders = loadProviderHistory()

func loadProviderHistory() map[string]bool {
	var history struct {
		Schema   int `json:"schema"`
		Releases []struct {
			Tag    string `json:"tag"`
			SHA256 string `json:"sha256"`
			Size   int64  `json:"size"`
		} `json:"releases"`
	}
	if json.Unmarshal(providerHistory, &history) != nil || history.Schema != 1 || len(history.Releases) == 0 {
		panic("invalid embedded provider history")
	}
	result := map[string]bool{}
	for _, r := range history.Releases {
		if !regexp.MustCompile(`^[a-f0-9]{64}$`).MatchString(r.SHA256) || r.Size < 1 || r.Size > 32*1024*1024 {
			panic("invalid embedded provider record")
		}
		result[r.SHA256] = true
	}
	return result
}

func compatibleProvider(data []byte) bool {
	return bytes.Equal(data, provider) || compatibleProviders[fmt.Sprintf("%x", sha256.Sum256(data))]
}

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

func readConnection(home string) (Connection, []byte, error) {
	path := filepath.Join(home, ".buzz-agents-web", "connection.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		return Connection{}, nil, err
	}
	var c Connection
	if len(raw) > 4096 || json.Unmarshal(raw, &c) != nil || validate(Pairing{1, c.Endpoint, c.Token}) != nil || !regexp.MustCompile(`^[a-f0-9]{24}$`).MatchString(c.DeviceID) {
		return Connection{}, raw, errors.New("기존 연결 파일을 읽지 못했습니다. 재연결을 선택하면 성공 시에만 교체합니다.")
	}
	return c, raw, nil
}

func deviceRequest(c Connection, action string, client *http.Client) bool {
	if validate(Pairing{1, c.Endpoint, c.Token}) != nil {
		return false
	}
	req, err := http.NewRequest("POST", c.Endpoint+"/api/device/"+action, strings.NewReader("{}"))
	if err != nil {
		return false
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+c.Token)
	resp, err := client.Do(req)
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	var value struct {
		OK       bool   `json:"ok"`
		DeviceID string `json:"device_id"`
	}
	if resp.StatusCode != 200 || json.NewDecoder(io.LimitReader(resp.Body, 4096)).Decode(&value) != nil || !value.OK {
		return false
	}
	return action != "check" || value.DeviceID == c.DeviceID
}

// Called with the installation lock held. Stage beside the executable and use
// MoveFileEx on Windows: a running/locked target fails without deleting it.
func installProvider(home string, commit func(string, string, bool) error) error {
	bin := filepath.Join(home, ".local", "bin")
	if err := os.MkdirAll(bin, 0755); err != nil {
		return err
	}
	target := filepath.Join(bin, "buzz-backend-hostinger-https.exe")
	info, err := os.Lstat(target)
	existed := err == nil
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if existed && !info.Mode().IsRegular() {
		return errors.New("연결기 파일이 일반 파일이 아닙니다. 기존 파일을 보존했습니다.")
	}
	var before []byte
	if existed {
		before, err = os.ReadFile(target)
		if err != nil {
			return err
		}
		if bytes.Equal(before, provider) {
			return nil
		}
		if !compatibleProvider(before) {
			return errors.New("알 수 없는 HTTPS 연결기가 있어 덮어쓰지 않습니다. 기존 연결기를 확인해 주세요.")
		}
	}
	f, err := os.CreateTemp(bin, ".buzz-provider-*.tmp")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	defer f.Close()
	if _, err = f.Write(provider); err != nil {
		return err
	}
	if err = f.Chmod(0755); err != nil {
		return err
	}
	if err = f.Sync(); err != nil {
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	// Recheck after staging so another actor's changed file is never knowingly
	// replaced. The installation lock serializes our own concurrent installers.
	current, err := os.ReadFile(target)
	if existed {
		currentInfo, statErr := os.Lstat(target)
		if err != nil || statErr != nil || !currentInfo.Mode().IsRegular() || !bytes.Equal(current, before) {
			return errors.New("설치 중 연결기 파일이 변경되었습니다. 다시 실행해 주세요.")
		}
	} else if !os.IsNotExist(err) {
		return errors.New("설치 중 연결기 파일이 생성되었습니다. 다시 실행해 주세요.")
	}
	if err := commit(f.Name(), target, existed); err != nil {
		return errors.New("연결기를 업데이트하지 못했습니다. Buzz를 종료한 뒤 다시 실행하세요. 기존 연결 정보는 보존했습니다.")
	}
	return nil
}

func upgradeConnectedProvider(home string) error {
	dir := filepath.Join(home, ".buzz-agents-web")
	unlock, err := lockInstall(filepath.Join(dir, "connect.lock"))
	if err != nil {
		return errors.New("다른 연결 프로그램을 닫은 뒤 다시 실행하세요.")
	}
	defer unlock()
	return installProvider(home, commitFile)
}

func install(p Pairing, home string, client *http.Client) error {
	return installConnection(p, home, client, false, commitFile)
}

func installConnection(p Pairing, home string, client *http.Client, replace bool, commit func(string, string, bool) error) error {
	if err := validate(p); err != nil {
		return err
	}
	dir := filepath.Join(home, ".buzz-agents-web")
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	if err := protect(dir); err != nil {
		return err
	}
	unlock, err := lockInstall(filepath.Join(dir, "connect.lock"))
	if err != nil {
		return errors.New("다른 연결 프로그램이 실행 중이거나 폴더에 접근할 수 없습니다. 다른 창을 닫고 다시 시도하세요.")
	}
	defer unlock()
	config := filepath.Join(dir, "connection.json")
	old, before, readErr := readConnection(home)
	existed := !os.IsNotExist(readErr)
	if existed && !replace {
		return errors.New("이미 Windows 연결 정보가 있습니다. 기존 연결을 보존했습니다. 프로그램에서 재연결을 직접 선택하세요.")
	}
	if readErr != nil && before == nil && existed {
		return errors.New("기존 연결 파일에 접근하지 못했습니다. 파일을 변경하지 않았습니다.")
	}
	if err := installProvider(home, commitFile); err != nil {
		return err
	}
	// Open a protected staging file BEFORE consuming the one-use grant.
	f, err := os.CreateTemp(dir, ".connection-*.tmp")
	if err != nil {
		return errors.New("연결 정보를 저장할 수 없습니다. 연결 파일은 사용하지 않았습니다.")
	}
	defer os.Remove(f.Name())
	defer f.Close()
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
	fail := func() error {
		if deviceRequest(c, "revoke-self", client) {
			return errors.New("연결 정보 저장 실패. 새 서버 연결은 해제했고 기존 연결은 보존했습니다. 새 연결 파일로 다시 시도하세요.")
		}
		return fmt.Errorf("연결 정보 저장 실패. 기존 연결은 보존했습니다. 설정 화면에서 장치 ID %s 를 해제한 뒤 새 연결 파일로 재시도하세요.", c.DeviceID)
	}
	data, _ := json.MarshalIndent(c, "", "  ")
	if _, err := f.Write(data); err != nil {
		return fail()
	}
	if err := f.Sync(); err != nil {
		return fail()
	}
	if err := f.Close(); err != nil {
		return fail()
	}
	current, err := os.ReadFile(config)
	if existed {
		if err != nil || !bytes.Equal(current, before) {
			return fail()
		}
	} else if !os.IsNotExist(err) {
		return fail()
	}
	if err := commit(f.Name(), config, existed); err != nil {
		return fail()
	}
	// Revoke only the previous credential after the new local file is committed.
	if readErr == nil && old.Endpoint == c.Endpoint && old.DeviceID != c.DeviceID {
		deviceRequest(old, "revoke-self", client)
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
	answer, inputErr := in.ReadString('\n')
	if inputErr != nil || strings.TrimSpace(answer) != "" {
		fmt.Println("취소했습니다.")
		return
	}
	home, err := os.UserHomeDir()
	if err != nil {
		fmt.Println("사용자 폴더 확인 실패")
		return
	}
	client := &http.Client{Timeout: 30 * time.Second, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return errors.New("redirect refused") }}
	replace := false
	old, raw, oldErr := readConnection(home)
	if oldErr == nil || raw != nil {
		if oldErr == nil {
			fmt.Println("기존 서버: " + old.Endpoint + "\n기존 장치 ID: " + old.DeviceID)
		}
		fmt.Println("재연결할 서버: " + p.Endpoint)
		choice := chooseConnection(in, os.Stdout, func() connectionState {
			if oldErr != nil {
				return connectionDamaged
			}
			return checkConnection(old, client)
		})
		switch choice {
		case connectionKeep:
			if err := upgradeConnectedProvider(home); err != nil {
				fmt.Println("완료되지 않음: " + err.Error())
				return
			}
			fmt.Println("정상인 기존 연결을 유지하고 연결기를 확인·업데이트했습니다. Buzz를 다시 실행하세요.")
			return
		case connectionCancel:
			fmt.Println("취소했습니다. 기존 연결 정보는 변경하지 않았습니다.")
			return
		case connectionReconnect:
			replace = true
		}
	}
	if err := installConnection(p, home, client, replace, commitFile); err != nil {
		fmt.Println("완료되지 않음: " + err.Error())
		return
	}
	if replace && oldErr == nil {
		fmt.Println("이전 장치 ID: " + old.DeviceID + " — 이전 서버 목록에 남아 있다면 이 ID의 연결만 해제하세요.")
	}
	fmt.Println("\nWindows 연결을 저장했습니다.\n1. Buzz를 다시 실행하세요.\n2. 봇 실행 위치에서 Hostinger VPS — HTTPS를 선택하고 배포하세요.\n3. 서버 설정 화면에서 해당 봇의 Codex·Claude 계정에 로그인하세요.")
}
