# v0.2.0 검증 결과

검증일: 2026-10-09. 실행 환경: 이 대화의 Linux 컨테이너. 사용자 Hostinger VPS가 아닙니다.

## 실제 실행 결과

| 검사 | 결과 |
|---|---|
| Python unittest | 73개 중 72개 통과, 1개 미실행, 실패 0 |
| Go 테스트 (`go test -race`) | 8개 통과 |
| 합계 | **81개 중 80개 통과, 1개 미실행** |
| Python 문법 검사 | 통과 |
| 설치 스크립트 셸 문법 검사 | 통과. 스크립트를 서버에 설치 실행한 것은 아님 |
| Go 정적 검사 (`go vet`) | 통과 |
| Windows x64 원격 제공자 교차 빌드 | 성공. Windows에서 실행한 검사는 아님 |
| Linux x64 원격 제공자 빌드 + info 호출 | 성공 |

실행 로그: `python-test-results.txt`, `go-test-results.txt`.

## 검사에 실제 사용한 것

- 실제 로컬 Unix socket으로 보호 정책 요청/응답.
- 실제 Python ACP 중계 프로세스와 가짜 ACP 프로그램의 JSON-lines 통신.
- 가짜 ACP 프로그램 종료와 실제 중계 프로세스 종료 상태 확인.
- 디스크에 기록한 호출 한도 유지와 시간 제한·상태 복구 규칙.
- 실제 SQLite 예약 회차 장부와 전송 실패/불확실성/중복 방지.
- 실제 Linux UID10001 강등과 root 전용 임시 파일 읽기 거부.
- 가짜 SSH 실행 파일을 통한 Go 모듈의 비밀 stdin 전달·오류 출력 제한 검사.
- 모의 Docker 호출로 배포 범위, 소유권 충돌, 이미지 변경 거부, 중지 후 변경, 다중 봇 구성 확인.
- Codex/Claude wrapper가 원래 실행기 basename을 유지하여 native 런타임 인식을 깨지 않는지 검사.

## 미실행 1개

`@noble/secp256k1` 실제 라이브러리를 사용하는 키 생성/공개키 도출 검사입니다.
이 시험 환경은 외부 네트워크 접근이 안 되고 node_modules가 없어 실행하지 않았습니다.
Docker 이미지 빌드에는 이 라이브러리 검사와 실제 native 옵션 검사를 **필수 preflight**로 넣었습니다.
실제 이미지가 없는데 해당 검사를 통과한 것처럼 표시하지 않습니다.

## 아직 검증하지 않은 것

- Docker build/pull, 전체 Compose를 실제 Docker daemon에서 실행.
- 유지한 upstream 이미지 지문/패키지의 현재 레지스트리 다운로드 가능성.
- 실제 컨테이너 cap_drop/no-new-privileges/마운트와 UID 경계의 조합.
- 실제 SSH 서버의 forced-command/sudo/키 에이전트/호스트키 확인.
- Windows Buzz 앱의 모듈 검색, Run on UI 표시와 실제 deploy 요청.
- 사용자의 설치 버전이 보내는 launch/env 형식과 전체 호환성.
- Hostinger hPanel에서 외부 생성 Compose 프로젝트가 표시되는지.
- 실제 OpenAI/Claude 구독 로그인, 모델 호출·갱신·한도.
- 기존 Relay의 회원/위임 인증·채널 접근·원격 봇 표시.
- 실제 여러 AI의 위임·멘션·공유 파일 협업.
- Windows 완전 종료 후 기존 작업 완료와 새 예약 작업 시작.
- 정상/강제 VPS 재부팅, 72시간/장기 유지, 자원 실측.

자동 검사 숫자는 운영 인증이나 보안 감사가 아닙니다.
원래 목표를 입증하려면 DEPLOYMENT.md 마지막의 실제 VPS 시험을 통과해야 합니다.

## 재현 명령

```bash
python -m unittest discover -s tests -v
python -m compileall -q buzz_agents scripts
sh -n scripts/install-host.sh
cd provider
go vet ./...
go test -race -v ./...
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -ldflags='-s -w' -o ../bin/buzz-backend-hostinger.exe .
```

실제 Nostr 라이브러리 검사를 포함하려면 호환 Node 환경에서 `npm install --ignore-scripts`를 수행한 뒤 Python 검사를 다시 실행합니다.
다만 설치된 전체 npm 의존성을 고정하는 lock 파일은 제공하지 않습니다. 이미지의 실제 Image ID를 배포 고정점으로 사용하며 재빌드마다 재검증합니다.
