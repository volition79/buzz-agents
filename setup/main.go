// A local console wizard; it never reads Windows Codex/Claude credentials.
package main

import (
	"bufio"
	"bytes"
	"context"
	"crypto/sha256"
	"embed"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/url"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"time"
)

//go:embed assets/server.zip assets/easy-bootstrap.py assets/buzz-backend-hostinger.exe
var assets embed.FS

const version = "0.3.0-candidate"

type Connection struct {
	Host  string `json:"host"`
	Port  int    `json:"port"`
	Owner string `json:"owner"`
	Relay string `json:"relay"`
}
type Bot struct {
	Pubkey   string `json:"pubkey"`
	Name     string `json:"name"`
	Provider string `json:"provider"`
	Status   string `json:"status"`
	Running  bool   `json:"container_running"`
}
type Status struct {
	OK    bool   `json:"ok"`
	Error string `json:"error"`
	Bots  []Bot  `json:"bots"`
}

var hexKey = regexp.MustCompile(`^[0-9a-f]{64}$`)
var dnsName = regexp.MustCompile(`^[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?$`)

func (c Connection) validate() error {
	if net.ParseIP(c.Host) == nil && !dnsName.MatchString(c.Host) {
		return errors.New("VPS 주소에는 IP 또는 호스트 이름만 입력하세요")
	}
	if c.Port < 1 || c.Port > 65535 {
		return errors.New("SSH 포트는 1~65535입니다")
	}
	if !hexKey.MatchString(c.Owner) {
		return errors.New("소유자 공개키는 64자리 HEX여야 합니다. nsec 개인키를 입력하지 마세요")
	}
	u, err := url.Parse(c.Relay)
	if err != nil || u.Scheme != "wss" || u.Hostname() == "" || u.User != nil || (u.Path != "" && u.Path != "/") || u.RawQuery != "" || u.Fragment != "" {
		return errors.New("Buzz Relay 주소는 wss://호스트 형식이어야 합니다")
	}
	return nil
}

func safeDisplay(s string) string {
	return strings.Map(func(r rune) rune {
		if r < 32 || r == 127 {
			return ' '
		}
		return r
	}, s)
}

func shellQuote(s string) string { return "'" + strings.ReplaceAll(s, "'", "'\"'\"'") + "'" }
func configPath(p string) (string, error) {
	if strings.ContainsAny(p, "\r\n\x00\"%") {
		return "", errors.New("설정 경로에 지원하지 않는 문자가 있습니다")
	}
	return `"` + filepath.ToSlash(p) + `"`, nil
}

func sshConfig(c Connection, dir string) (string, error) {
	if err := c.validate(); err != nil {
		return "", err
	}
	key, err := configPath(filepath.Join(dir, "vps_ed25519"))
	if err != nil {
		return "", err
	}
	known, err := configPath(filepath.Join(dir, "known_hosts"))
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("Host buzz-vps\n    HostName %s\n    Port %d\n    User buzzdeploy\n    IdentityFile %s\n    UserKnownHostsFile %s\n    IdentitiesOnly yes\n    BatchMode yes\n    StrictHostKeyChecking yes\n    ConnectTimeout 15\n    ServerAliveInterval 15\n    ServerAliveCountMax 3\n", c.Host, c.Port, key, known), nil
}

func exclusiveOrSame(path string, data []byte, mode os.FileMode) error {
	old, err := os.ReadFile(path)
	if err == nil {
		if bytes.Equal(old, data) {
			return nil
		}
		return fmt.Errorf("기존 파일을 보존했습니다: %s (다른 버전/설정의 자동 덮어쓰기는 지원하지 않습니다)", path)
	}
	if !os.IsNotExist(err) {
		return err
	}
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, mode)
	if err != nil {
		return err
	}
	_, err = f.Write(data)
	closeErr := f.Close()
	if err != nil {
		return err
	}
	return closeErr
}

type Wizard struct {
	input  *bufio.Reader
	dir    string
	ssh    string
	keygen string
	// Inject the process boundary in tests; real auth inherits the terminal.
	run func(string, []string, io.Reader, io.Writer, io.Writer) error
}

func runProcess(name string, args []string, input io.Reader, out, diagnostic io.Writer) error {
	ctx := context.Background()
	var cancel context.CancelFunc
	if len(args) > 0 && args[len(args)-1] == "buzz-agents-status" {
		ctx, cancel = context.WithTimeout(ctx, 45*time.Second)
		defer cancel()
	}
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = input, out, diagnostic
	return cmd.Run()
}
func (w *Wizard) ask(label, fallback string) (string, error) {
	fmt.Print(label)
	if fallback != "" {
		fmt.Printf(" [%s]", fallback)
	}
	fmt.Print(": ")
	line, err := w.input.ReadString('\n')
	if err != nil {
		return "", err
	}
	line = strings.TrimSpace(line)
	if line == "" {
		line = fallback
	}
	return line, nil
}
func (w *Wizard) adminArgs(c Connection, strict string) []string {
	return []string{"-F", "none", "-p", strconv.Itoa(c.Port), "-o", "StrictHostKeyChecking=" + strict,
		"-o", "UserKnownHostsFile=" + filepath.ToSlash(filepath.Join(w.dir, "known_hosts")),
		"-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15", "root@" + c.Host}
}
func (w *Wizard) remoteArgs(command string, tty bool) []string {
	flag := "-T"
	if tty {
		flag = "-tt"
	}
	return []string{flag, "-F", filepath.Join(w.dir, "ssh_config"), "buzz-vps", command}
}

func (w *Wizard) install(c Connection) error {
	if err := c.validate(); err != nil {
		return err
	}
	c.Relay = strings.TrimRight(c.Relay, "/")
	home, err := os.UserHomeDir()
	if err != nil {
		return err
	}
	provider, err := assets.ReadFile("assets/buzz-backend-hostinger.exe")
	if err != nil {
		return err
	}
	bin := filepath.Join(home, ".local", "bin")
	if old, e := os.ReadFile(filepath.Join(bin, "buzz-backend-hostinger.exe")); e == nil && !bytes.Equal(old, provider) {
		return errors.New("기존 Buzz 연결기 버전이 다릅니다. 서버 변경 전에 기존 연결기 백업·교체 검토가 필요합니다")
	} else if e != nil && !os.IsNotExist(e) {
		return e
	}
	if err := os.MkdirAll(w.dir, 0700); err != nil {
		return err
	}
	configuration, err := sshConfig(c, w.dir)
	if err != nil {
		return err
	}
	// Reject conflicting local installs before contacting a server.
	if old, err := os.ReadFile(filepath.Join(w.dir, "ssh_config")); err == nil && string(old) != configuration {
		return errors.New("기존 VPS 연결 설정이 달라 자동 교체하지 않았습니다")
	}
	key := filepath.Join(w.dir, "vps_ed25519")
	if _, err := os.Stat(key); os.IsNotExist(err) {
		if _, err := os.Stat(key + ".pub"); !os.IsNotExist(err) {
			return errors.New("공개키만 남아 있습니다. 키 상태를 먼저 확인하세요")
		}
		if err := w.run(w.keygen, []string{"-t", "ed25519", "-N", "", "-C", "buzz-agents-easy", "-f", key}, os.Stdin, os.Stdout, os.Stderr); err != nil {
			return err
		}
	} else if err != nil {
		return err
	}
	if runtime.GOOS == "windows" {
		u, err := user.Current()
		if err != nil {
			return err
		}
		acl := filepath.Join(os.Getenv("SystemRoot"), "System32", "icacls.exe")
		if err := w.run(acl, []string{key, "/inheritance:r", "/grant:r", u.Username + ":F"}, nil, os.Stdout, os.Stderr); err != nil {
			return err
		}
	}
	pub, err := os.ReadFile(key + ".pub")
	if err != nil {
		return err
	}
	fmt.Println("\n최초 연결: Hostinger 콘솔에서 확인한 서버 SSH 지문과 일치할 때만 yes를 입력하세요.")
	if err := w.run(w.ssh, append(w.adminArgs(c, "ask"), "true"), os.Stdin, os.Stdout, os.Stderr); err != nil {
		return errors.New("관리자 SSH 연결 실패: 서버 주소·포트·접속 권한을 확인하세요")
	}
	payload, err := assets.ReadFile("assets/server.zip")
	if err != nil {
		return err
	}
	bootstrap, err := assets.ReadFile("assets/easy-bootstrap.py")
	if err != nil {
		return err
	}
	digest := sha256.Sum256(payload)
	request, err := json.Marshal(map[string]string{"archive": base64.StdEncoding.EncodeToString(payload), "sha256": hex.EncodeToString(digest[:]), "public_key": strings.TrimSpace(string(pub)), "owner": c.Owner, "relay": c.Relay})
	if err != nil {
		return err
	}
	fmt.Println("\n서버 구성과 이미지 빌드를 시작합니다. 최초 실행은 다운로드 때문에 오래 걸릴 수 있습니다. 기존 Relay는 수정하지 않습니다.")
	if err := w.run(w.ssh, append(w.adminArgs(c, "yes"), "python3 -c "+shellQuote(string(bootstrap))), bytes.NewReader(request), os.Stdout, os.Stderr); err != nil {
		return errors.New("서버 설치가 완료되지 않았습니다. 위 오류를 확인하세요. 성공으로 처리하지 않습니다")
	}
	if err := exclusiveOrSame(filepath.Join(w.dir, "ssh_config"), []byte(configuration), 0600); err != nil {
		return err
	}
	encoded, _ := json.MarshalIndent(c, "", "  ")
	if err := exclusiveOrSame(filepath.Join(w.dir, "connection.json"), encoded, 0600); err != nil {
		return err
	}
	if err := os.MkdirAll(bin, 0755); err != nil {
		return err
	}
	if err := exclusiveOrSame(filepath.Join(bin, "buzz-backend-hostinger.exe"), provider, 0755); err != nil {
		return err
	}
	if _, err := w.status(); err != nil {
		return fmt.Errorf("설치는 진행됐지만 전용 연결 확인 실패: %w", err)
	}
	fmt.Println("\n연결 준비 완료. Buzz를 완전히 종료하고 다시 여세요.")
	fmt.Println("봇 실행 위치: Hostinger VPS — Native Buzz / ssh_alias: buzz-vps / workspace: team")
	fmt.Println("Codex와 Claude 봇을 각각 배포한 뒤 이 도우미의 2번에서 VPS 로그인을 진행하세요.")
	fmt.Println("이는 연결 확인입니다. 실제 AI 응답과 Windows 종료 시험은 아직 필요합니다.")
	return nil
}

func decodeStatus(raw []byte) ([]Bot, error) {
	if len(raw) > 1024*1024 {
		return nil, errors.New("서버 상태 응답이 너무 큽니다")
	}
	var status Status
	if err := json.Unmarshal(raw, &status); err != nil || !status.OK {
		return nil, errors.New("서버 상태 조회 실패")
	}
	for _, b := range status.Bots {
		if !hexKey.MatchString(b.Pubkey) || (b.Provider != "codex" && b.Provider != "claude") {
			return nil, errors.New("잘못된 봇 상태 응답")
		}
	}
	return status.Bots, nil
}

type limitedBuffer struct{ bytes.Buffer }

func (b *limitedBuffer) Write(p []byte) (int, error) {
	if b.Len()+len(p) > 1024*1024 {
		return 0, errors.New("서버 응답 제한 초과")
	}
	return b.Buffer.Write(p)
}
func (w *Wizard) status() ([]Bot, error) {
	var output limitedBuffer
	err := w.run(w.ssh, w.remoteArgs("buzz-agents-status", false), nil, &output, os.Stderr)
	if err != nil {
		return nil, err
	}
	return decodeStatus(output.Bytes())
}
func (w *Wizard) login() error {
	bots, err := w.status()
	if err != nil {
		return err
	}
	if len(bots) == 0 {
		fmt.Println("아직 봇이 없습니다. 먼저 Windows Buzz에서 원격 봇을 배포하세요.")
		return nil
	}
	for i, b := range bots {
		fmt.Printf("%d. %s (%s, %s)\n", i+1, safeDisplay(b.Name), b.Provider, safeDisplay(b.Status))
	}
	s, err := w.ask("로그인할 봇 번호", "")
	if err != nil {
		return err
	}
	i, err := strconv.Atoi(s)
	if err != nil || i < 1 || i > len(bots) {
		return errors.New("목록의 번호를 입력하세요")
	}
	b := bots[i-1]
	if !b.Running {
		return errors.New("컨테이너가 실행 중이 아닙니다. 서버 상태를 확인하세요")
	}
	if b.Status == "running" {
		return errors.New("실행 중인 봇입니다. 재인증이 필요하면 Buzz에서 !shutdown 후 다시 선택하세요")
	}
	fmt.Println("\n로그인은 VPS 안에서 실행됩니다. 출력된 공식 주소를 Windows 브라우저에서 열어 승인하세요.")
	fmt.Println("코드 입력을 요청하면 이 창에 입력하세요. 완료 전 창을 닫지 마세요. 화면을 녹화하지 마세요.")
	err = w.run(w.ssh, w.remoteArgs("buzz-agents-auth "+b.Provider+" "+b.Pubkey, true), os.Stdin, os.Stdout, os.Stderr)
	if err != nil {
		return errors.New("VPS 로그인 실패 또는 중단. 다시 상태를 확인하세요")
	}
	fmt.Println("VPS 로그인 명령이 완료되었습니다. Buzz에서 실제 응답을 확인하세요.")
	return nil
}

func (w *Wizard) schedule() error {
	bots, err := w.status()
	if err != nil {
		return err
	}
	if len(bots) == 0 {
		return errors.New("먼저 Buzz에서 봇을 배포하세요")
	}
	var out limitedBuffer
	if err = w.run(w.ssh, w.remoteArgs("buzz-agents-schedule-init", false), nil, &out, os.Stderr); err != nil {
		return err
	}
	var identity struct {
		OK     bool   `json:"ok"`
		Pubkey string `json:"pubkey"`
	}
	if json.Unmarshal(out.Bytes(), &identity) != nil || !identity.OK || !hexKey.MatchString(identity.Pubkey) {
		return errors.New("예약 신원 생성 실패")
	}
	fmt.Println("예약 발신자 공개키:", identity.Pubkey)
	fmt.Println("최초 1회: Buzz에서 이 공개키를 Relay 회원과 대상 채널에 추가하고, 대상 봇의 allowlist에 허용한 뒤 봇을 재배포하세요.")
	fmt.Println("같은 채널의 다른 봇과 협업하려면 그 봇들의 공개키도 서로 허용해야 합니다.")
	answer, err := w.ask("위 권한 설정이 완료되면 확인 입력 (다른 입력은 취소)", "")
	if err != nil {
		return err
	}
	if answer != "확인" {
		return nil
	}
	for i, b := range bots {
		fmt.Printf("%d. %s (%s)\n", i+1, safeDisplay(b.Name), b.Provider)
	}
	selected, err := w.ask("예약을 받을 봇 번호", "")
	if err != nil {
		return err
	}
	i, err := strconv.Atoi(selected)
	if err != nil || i < 1 || i > len(bots) {
		return errors.New("잘못된 봇 번호")
	}
	channel, err := w.ask("Buzz 대상 채널 ID (UUID)", "")
	if err != nil {
		return err
	}
	time, err := w.ask("매일 실행 시각 (한국 시간 HH:MM)", "09:00")
	if err != nil {
		return err
	}
	prompt, err := w.ask("봇에게 전달할 작업", "")
	if err != nil {
		return err
	}
	fmt.Printf("%s, 매일 %s 한국 시간에 작업을 예약합니다. 기존 도우미 예약 1개는 교체됩니다.\n", safeDisplay(bots[i-1].Name), safeDisplay(time))
	answer, err = w.ask("저장하려면 예약 입력", "")
	if err != nil {
		return err
	}
	if answer != "예약" {
		return nil
	}
	data, _ := json.Marshal(map[string]any{"channel_id": channel, "bot_pubkey": bots[i-1].Pubkey, "prompt": prompt, "time": time, "membership_confirmed": true})
	return w.run(w.ssh, w.remoteArgs("buzz-agents-schedule-save", false), bytes.NewReader(data), os.Stdout, os.Stderr)
}

func main() {
	if len(os.Args) == 2 && os.Args[1] == "--version" {
		fmt.Println(version)
		return
	}
	if runtime.GOOS != "windows" {
		fmt.Fprintln(os.Stderr, "이 연결 도우미는 Windows x64용입니다.")
		os.Exit(1)
	}
	home, err := os.UserHomeDir()
	if err != nil {
		fmt.Println(err)
		return
	}
	system := filepath.Join(os.Getenv("SystemRoot"), "System32", "OpenSSH")
	w := Wizard{input: bufio.NewReader(os.Stdin), dir: filepath.Join(home, ".buzz-agents"), ssh: filepath.Join(system, "ssh.exe"), keygen: filepath.Join(system, "ssh-keygen.exe"), run: runProcess}
	if _, err := os.Stat(w.ssh); err != nil {
		fmt.Println("Windows 선택적 기능에서 OpenSSH 클라이언트를 설치한 뒤 다시 실행하세요.")
		w.ask("Enter를 누르면 종료", "")
		return
	}
	fmt.Println("Buzz VPS 연결 도우미 " + version + " — 시험용, 실제 VPS 검증 전")
	for {
		fmt.Println("\n1. 최초 서버 설치·연결\n2. VPS의 Codex / Claude 로그인\n3. 봇 상태 확인\n4. 매일 예약 설정 (선택)\n5. 예약 중지\n0. 종료")
		choice, err := w.ask("선택", "")
		if err != nil {
			return
		}
		switch choice {
		case "0":
			return
		case "1":
			var c Connection
			c.Host, err = w.ask("VPS IP 또는 호스트 이름", "")
			if err != nil {
				return
			}
			port, e := w.ask("SSH 포트", "22")
			if e != nil {
				return
			}
			c.Port, _ = strconv.Atoi(port)
			c.Relay, err = w.ask("Windows Buzz에서 사용하는 wss:// Relay 주소", "")
			if err != nil {
				return
			}
			c.Owner, err = w.ask("소유자 HEX 공개키 (nsec 아님)", "")
			if err != nil {
				return
			}
			fmt.Println("선택한 VPS에 전용 계정·키·실행 이미지를 설치합니다. 기존 Relay는 유지합니다.")
			answer, e := w.ask("진행하려면 설치 입력", "")
			if e != nil {
				return
			}
			if answer != "설치" {
				continue
			}
			err = w.install(c)
		case "2":
			err = w.login()
		case "3":
			var bots []Bot
			bots, err = w.status()
			if err == nil {
				for _, b := range bots {
					fmt.Printf("%s: %s, container=%t\n", safeDisplay(b.Name), safeDisplay(b.Status), b.Running)
				}
				fmt.Println("running은 프로세스 상태입니다. 모델의 실제 응답 성공을 뜻하지 않습니다.")
			}
		case "4":
			err = w.schedule()
		case "5":
			var answer string
			answer, err = w.ask("예약을 중지하려면 중지 입력", "")
			if err == nil && answer == "중지" {
				err = w.run(w.ssh, w.remoteArgs("buzz-agents-schedule-disable", false), nil, os.Stdout, os.Stderr)
			}
		default:
			fmt.Println("메뉴 번호를 입력하세요.")
		}
		if err != nil {
			fmt.Println("\n완료되지 않음:", safeDisplay(err.Error()))
		}
	}
}
