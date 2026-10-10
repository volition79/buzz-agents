# Buzz VPS 간편 연결 — Docker 설정 화면 개발 후보

각 사용자가 Windows Buzz에서 자신의 신원을 만들고, **자신의 공개키를 소유자로 지정한 Hostinger Buzz Relay**를 먼저 설치했다고 가정합니다. 기존 Relay와 Windows Buzz는 계속 사용합니다. nsec 개인키와 VPS root 비밀번호를 이 프로그램에 입력하지 않습니다.

## Windows 연결 프로그램 업데이트

새 설정 화면에서 연결 파일을 내려받아 실행하면, 이전 공식 버전의 연결기도 자동 갱신합니다. 정상 연결은 유지하고, 서버에서 무효로 확인된 연결은 화면 안내에 따라 재연결합니다. 기존 파일을 직접 삭제하거나 이름을 바꿀 필요가 없습니다. Buzz를 먼저 종료하세요. 출처를 확인할 수 없는 파일은 덮어쓰지 않습니다.

기존 Docker 프로젝트를 직접 편집해 업데이트할 때는 `setup-route` 이미지를 변경하지 마세요. 검증된 기존 접속 경로를 유지하고 `portal`, `broker`, runtime 참조만 갱신합니다. 신규 설치는 아래 URL의 자동 구성을 사용합니다.

## 현재 상태

기존 봇 업데이트는 [기존 봇 업데이트 안내](EXISTING-BOT-UPDATE.md)를 따르세요. 최신 관리 서비스를 적용한 뒤 **열기 → 봇 계정 로그인 → 해당 봇의 업데이트·다시 시작**을 사용합니다. Windows Buzz의 `Deployed`는 실행 중이라는 보장이 아니며, Shutdown 후 재배포 버튼이 나타나지 않을 수 있습니다. 봇·프로젝트 삭제는 필요하지 않습니다.

v0.4 공개 개발 후보입니다. GitHub에서 이미지 빌드·임시 Compose 실행·비로그인 다운로드 검증을 통과했습니다. 기존 후보의 실제 Hostinger 설치와 공인 HTTPS 접속은 확인했습니다. 기존 「열기」 버튼에서 설정 화면 접속은 확인했습니다. 이번 후보는 최초 설정 HTTP400에 이어 로그인 직후 자동 조회와 안내 이미지 요청이 겹치는 문제도 수정했습니다. CI37942173881에서 실제 중계기를 거치는 느린 이미지·게이트웨이 오류·재시도·최초 설정·재로그인 및 신규 설치·업데이트 시험을 통과했습니다. Hostinger ‘열기’의 인증값 자동 전달은 사용하지 않습니다. 공식 계정 인증·Windows 완전 종료 시험은 아직 남아 있습니다.

캡처 기반 한국어·영어 안내, 실제 Relay 주소 복사와 Windows 연결 상태별 선택을 포함한 Docker Manager **컴포즈 → URL에서 Compose** 주소:

```text
https://raw.githubusercontent.com/volition79/buzz-agents/ebf871a23f6922cfdd8a45fc8ad4dc65436e5d08/docker-compose.yml
```

최초 설정에서 HTTP400을 보았다면 이번 URL로 업데이트한 뒤 Docker Manager의 **열기**로 다시 접속하세요. 주소 끝에 `?`가 남은 오류 페이지를 새로고침하지 마세요. portal 로그의 최신 최초 설정 코드를 사용합니다. 설정 버튼은 화면 준비가 끝나면 활성화됩니다.

로그인 직후 조회가 계속 실패하면 **서버 연결 다시 확인**을 누르세요. 커뮤니티 주소는 기다리기만 해서는 표시되지 않습니다. **01 / 내 Relay 연결 → 이 Relay로 연결**로 저장하면 Windows Buzz용 주소가 자동으로 표시됩니다. 안내 이미지는 초기 조회 후 순서대로 불러옵니다.

업데이트 후에는 설정 페이지에서 Windows 연결 ZIP을 새로 다운로드하세요. 예전에 내려받은 실행 파일에는 새 안내와 연결 선택 방식이 반영되지 않습니다.

도메인 환경변수를 요구하지 않는 자동 초기 설정 후보입니다. 기존 **Hostinger 기본 도메인의 Buzz Relay와 Traefik**이 먼저 실행되어 있어야 합니다.

시작한 broker가 기존 Relay 프로젝트의 소유자 공개키와 Traefik 호스트 라벨을 읽습니다. `srv숫자.hstgr.cloud` 기반 도메인이 하나로 확인되면 프로젝트별 `buzz-setup-고유값.srv숫자.hstgr.cloud` 주소를 구성합니다. portal이 DNS를 확인한 뒤, broker가 자기 프로젝트의 Compose 파일에 `setup-route` 서비스를 등록하고 실행합니다. 기존 Relay와 Traefik은 수정하지 않습니다. portal은 Docker 소켓 없이 실행됩니다.

`TRAEFIK_HOST`, `BUZZ_SETUP_HOST`, root 비밀번호, 사람의 nsec를 입력하지 않습니다. 최초 관리자 코드와 설정 비밀번호는 계속 필요합니다. Docker Manager의 portal 로그에서 최신 설정 코드를 복사해 입력합니다. DNS 조회는 연결 가능성 검사이며 사용자 소유권 인증을 대체하지 않습니다.

현재 자동 지원 범위는 Hostinger 기본 도메인입니다. 사용자 지정 도메인, 서로 다른 기본 도메인의 Relay 여러 개, DNS 미전파, 기존 라우팅 컨테이너 충돌은 `Buzz automatic setup waiting: 오류코드`로 대기합니다. 임의 주소로 실행하지 않습니다. 후보 선택/수동 도메인 입력 UI는 아직 제공하지 않습니다.

## 설치 및 실서버 검증 순서

1. Docker Manager에 위 Compose URL로 배포합니다. 먼저 Compose 기본 네트워크에서 시작한 뒤 기존 Relay·Traefik의 실제 네트워크와 HTTPS 라우터 설정을 검색합니다. 자기 portal만 발견한 네트워크에 연결하며, 기존 서비스의 네트워크는 바꾸지 않습니다. 환경값 추가 없이 배포합니다. 자동 구성 후 목록을 새로고침하고 **열기** 버튼으로 접속합니다. portal 로그의 `Buzz setup URL` 주소로도 접속할 수 있습니다.
2. 설정 화면을 열고 **Docker Manager → buzz-agents → 관리 → 로그**에서 portal의 최신 `Buzz first setup code`를 복사해 입력합니다. 설정 화면용 비밀번호(12자 이상)를 정합니다. 코드는 발급 후 60분간 한 번만 유효합니다. 설정 화면 비밀번호는 root 비밀번호와 별개입니다.
3. 기존 Relay를 자동으로 찾습니다. 주소·소유자 공개키를 확인하고 연결합니다. 여러 개면 선택하고, 찾지 못하면 두 공개 정보만 직접 입력합니다. 소유권을 Nostr 서명으로 새로 증명하는 기능은 아닙니다. Docker 관리자만 읽을 수 있는 최초 코드와 기존 Relay 설정을 신뢰하며, 봇 권한은 기존 Relay가 검증합니다.
4. **Windows 연결 파일 받기** → ZIP 압축 풀기 → `Buzz-VPS-Connect.exe` 실행. 자기 서버 주소가 맞는지 확인합니다. 파일은 10분간 한 번만 사용 가능합니다.
5. Windows Buzz를 다시 열고 봇 실행 위치에서 **Hostinger VPS — HTTPS**를 선택해 배포합니다. 연결기가 보이지 않으면 현재 Buzz 버전의 외부 backend 검색 경로를 확인해야 합니다. 실제 Windows Buzz 발견/실행 시험은 아직 남아 있습니다.
6. 설정 화면에 나타난 해당 봇의 **계정 로그인**을 누릅니다. 공식 Codex/Claude 로그인 주소를 열어 승인합니다. Claude 등이 코드를 요청하면 설정 화면에 붙여넣습니다. 인증 정보는 그 봇의 VPS 홈에 남습니다. 로컬 Windows AI 인증 파일을 복사하지 않습니다.
7. Buzz에서 실제 답변을 확인합니다. 봇마다 격리된 홈을 사용하므로 봇을 추가하면 해당 봇도 로그인해야 합니다. 실행 중인 봇의 재인증은 먼저 Buzz에서 중지합니다.

설정 화면은 평소 닫아도 됩니다. 봇 생성·대화는 Windows Buzz에서 합니다. Windows 프로그램은 배포 시에만 서버에 연결하며 계속 켜놓는 중계기가 아닙니다. 다만 portal 컨테이너 자체를 중지하면 새 배포/상태 확인은 사용할 수 없습니다. 기존 봇·예약 컨테이너는 별도로 실행됩니다.

## Windows Buzz 커뮤니티 연결 안내

설정 페이지의 **Windows Buzz에서 내 서버에 들어가기**에 실제 화면 캡처 3장과 한국어·영어 안내가 있습니다.

1. 연결 프로그램에서 저장 완료를 확인하고 Windows Buzz를 다시 실행합니다.
2. `Choose your model settings` 화면은 `Skip for now`를 누릅니다.
3. `Join or create a community`에서 맨 위 `Join a community`를 누릅니다.
4. 설정 페이지의 **Windows Buzz에 입력할 내 커뮤니티 주소 → 주소 복사**를 누릅니다. 주소는 저장된 Relay 설정에서 가져오며 서버마다 다릅니다.
5. Buzz의 `Invite link or community URL`에 붙여넣고 `Next`를 누릅니다.

`I already have a community → I own the community`는 관찰된 버전에서 Builderlab 로그인으로 이어집니다. 이 Hostinger 연결에는 사용하지 않습니다. `buzz-setup-…` 주소는 설정 도우미 주소이며 커뮤니티 주소가 아닙니다. 이미지의 화면 배치는 Buzz 버전에 따라 달라질 수 있습니다.

## 선택: Windows 종료 후 예약

설정 화면의 예약 항목에서 예약 봇 공개키를 확인합니다. 해당 신원을 Relay와 채널의 멤버로 승인하고, 대상 AI 봇의 허용 목록에 추가합니다. 채널 UUID·대상 봇·한국 시간·메시지를 입력하고 예약합니다. 이 권한 승인 단계는 자동으로 생략하지 않습니다.

**필수 합격 시험:** Windows를 완전히 끈 뒤 아직 시작되지 않았던 예약 작업이 VPS에서 시작되고, 두 AI가 작업 파일을 완성하는지 확인합니다. Relay에 메시지가 전달된 것만으로 작업 완료라고 판단하지 않습니다.

## 다시 시도·재시작·재설정

| 상황 | 할 일 | 유지되는 것 |
|---|---|---|
| 최초 코드가 없거나 만료됨 | buzz-agents 오른쪽 **⋮ → 다시 시작** 후 portal의 최신 로그에서 새 코드를 복사 | 기존 Relay·작업 데이터 |
| 설정 후 portal/VPS 재시작 | 기존 설정 비밀번호로 로그인. 미사용 연결 ZIP은 다시 받기 | 저장된 Windows 연결·봇·파일·AI 인증 |
| 연결 ZIP이 10분 경과/이미 사용됨 | 설정 화면에서 **새 Windows 연결 파일 받기**, 압축을 모두 풀고 실행 | 이미 완료된 연결 |
| 같은 PC에서 프로그램 재실행 | 정상: Enter로 유지. 서버가 연결 해제·무효를 확인: Enter로 재연결. 확인 실패: Enter로 확인 재시도 / `r`로 재연결 / `n`으로 취소. 재연결 전 Buzz 종료 | 새 연결 저장 성공까지 기존 연결 파일 |
| 다른 PC 추가 | 새 ZIP을 해당 PC에서 실행 | 다른 PC의 연결 |
| 저장 실패 | 프로그램 안내대로 재시도. 장치 ID가 나오면 설정 화면의 그 ID만 해제하고 새 ZIP 받기 | 기존 연결 파일·VPS 작업 데이터 |
| 비밀번호 분실 | 아래 접근 복구 절차 | 봇·파일·AI 인증·Windows 연결 |

**최신 코드 확인:** Docker Manager → buzz-agents → 관리 → 로그에서 portal 로그를 선택하거나 해당 줄을 찾습니다. 이전 코드가 남아 있어도 마지막으로 발급된 것만 사용하세요. 로그가 비어 있거나 불러오기에 실패하면 코드를 추측하지 말고 portal의 실행 상태부터 확인하세요.

**설정 완료 후 비밀번호 분실 시 접근 복구:** Docker Manager 목록에서 buzz-agents를 펼쳐 **portal 컨테이너의 터미널**을 엽니다. 아래 명령을 실행합니다. VPS root 비밀번호를 이 프로그램에 입력하지 않습니다.

```sh
python -m buzz_agents.portal_recover
```

- 최초 설정 전: 로그에 새 `Buzz first setup code`와 설정 링크가 나옵니다.
- 설정 후: 로그에 `Buzz recovery code`와 복구 링크가 나옵니다. 설정 화면의 **비밀번호를 잊었나요? · 접근 복구**에 코드를 입력하거나 복구 링크를 열고 새 비밀번호를 정합니다.
- 둘 다 60분·한 번 사용입니다. 재발급 또는 portal 재시작 시 이전 코드는 무효가 됩니다. 복구 코드는 재시작 후 자동으로 다시 발급되지 않습니다.
- 비밀번호 복구 성공 후 새 비밀번호로 로그인합니다. 기존 브라우저 세션과 미사용 연결 ZIP은 폐기됩니다. 일반 재시작은 비밀번호 초기화가 아닙니다.
- 코드와 링크는 인증 정보입니다. 다른 사람에게 공유하지 마세요. 공개 화면에서는 코드를 발급하지 않습니다.

Windows 연결 해제는 해당 장치의 새 배포 권한을 제거하며 VPS 봇·파일을 삭제하지 않습니다. 재연결 성공 후 이전 장치 ID가 목록에 남아 있으면 그 ID만 해제합니다. `~/.buzz-agents-web/connection.json`을 수동 삭제하는 절차는 필요하지 않습니다. 공개 후보의 해시와 소스 호환성이 확인된 기존 연결기는 그대로 재사용합니다. 알 수 없거나 수정된 실행 파일은 자동으로 덮어쓰지 않습니다.

## 설정 코드 입력과 화면 언어

Hostinger의 ‘열기’에서는 설정 코드 자동 전달을 지원하지 않는 것으로 안내합니다. Docker Manager → buzz-agents → 관리 → 로그에서 portal의 최신 `Buzz first setup code`를 복사해 입력하세요. 최초 설정 전 코드가 만료되었다면 buzz-agents 오른쪽 **⋮ → 다시 시작**을 누르고 재시작 완료 후 최신 로그에서 새 코드를 복사합니다. 터미널 명령은 최초 설정 재시도에 필요하지 않습니다. 이미 설정을 마친 서버는 재시작으로 비밀번호가 초기화되지 않습니다.

로그의 비밀 링크는 보조 기능으로 유지합니다. `/#setup_code=...` 또는 `/#recovery_code=...`를 입력한 뒤 즉시 주소창에서 제거하며 자동 제출하지 않습니다.

화면은 브라우저의 첫 번째 선호 언어가 한국어이면 한국어, 영어 또는 그 외 언어이면 영어로 표시합니다. 브라우저 언어를 변경한 뒤 페이지를 새로고침하세요. 봇 이름, 입력값, 공식 로그인 프로그램의 출력은 번역하지 않습니다. 예약 시각은 언어와 관계없이 한국 시간(UTC+9)입니다.

## 권한 구조

portal은 UID10002로 동작하며 Docker 소켓·봇 인증 폴더에 접근하지 않습니다. 네트워크가 없는 broker만 Docker 소켓·정해진 데이터 폴더·자기 `/docker/<프로젝트>` 설정 폴더를 사용하고, private Unix socket으로 제한된 작업을 받습니다. **Docker 소켓을 가진 broker 자체는 서버 관리자에 준하는 권한**이 있으므로 신뢰한 이미지로만 배포해야 합니다. root 비밀번호가 필요 없다는 말은 내부 관리 권한까지 없다는 뜻이 아닙니다.

봇은 기존처럼 별도 컨테이너·UID10001·봇별 인증 홈·자원 한도·작업 보호 정책을 사용합니다. AI 컨테이너에는 Docker 소켓을 제공하지 않습니다. 공식 로그인 화면은 최대 10분간만 열리며, 출력은 메모리에만 유지하고 로그/파일로 저장하지 않습니다.

## 개발자 빌드와 공개 전 준비

```bash
BUZZ_BUILD_GO=/usr/local/go/bin/go python3 scripts/build-portal.py
```

`dist/portal-v0.4/docker-build-context.zip`에는 필요한 Docker 빌드 소스와 Windows 연결 프로그램이 포함됩니다. 빌드 컨텍스트를 풀고 다음 세 이미지를 빌드/검증합니다.

```bash
docker build -t buzz-agents-runtime:0.4.0 .
docker build -f Dockerfile.portal --target broker -t buzz-agents-broker:0.4.0 .
docker build -f Dockerfile.portal --target portal -t buzz-agents-portal:0.4.0 .
```

검토 후 지정 레지스트리에 공개하고 immutable digest로 `BUZZ_RUNTIME_IMAGE`, `BUZZ_BROKER_IMAGE`, `BUZZ_PORTAL_IMAGE`를 고정합니다. 프로젝트 이름은 실제 컨테이너의 Compose 라벨에서 읽고 도메인은 기존 Relay에서 검색합니다. 루트 `docker-compose.yml`은 공개 URL 설치의 기준 파일입니다.

공개 준비용 `.github/workflows/portal-images.yml`도 포함됩니다. 저장소에 올리는 것만으로 실행되지 않고, **수동 workflow_dispatch** 때만 동작합니다. Windows 빌드·테스트 → Docker 이미지 빌드 → 별도 CI 서버에서 Compose/권한 경계 스모크 → GHCR push → 익명 pull 확인 → digest가 고정된 설치 Compose를 후보 릴리스에 첨부하는 순서입니다. 최초 GHCR 패키지가 비공개이면 익명 확인 단계에서 멈추므로, 저장소 소유자가 각 패키지를 Public으로 바꾼 뒤 다시 실행해야 합니다. 첫 CI 실행은 성공했습니다.

공개 소스 준비본은 `public-source.zip`입니다. 개인 계정 정보·연결 파일·테스트 실행 로그·이전 ZIP을 포함하지 않습니다. 기존 v0.3 소스는 회귀 확인을 위해 보존하지만, 새 배포 경로는 `web-provider`, `connect`, `Dockerfile.portal`입니다.

기반: [Hostinger의 여러 Compose 프로젝트 Traefik 연결 안내](https://www.hostinger.com/support/connecting-multiple-docker-compose-projects-using-traefik-in-hostinger-docker-manager/), [Docker 소켓 권한 안내](https://docs.docker.com/engine/security/protect-access/).


## URL 가져오기 합격 기준

- 공개 Raw URL만 입력해 설치하며 수동 YAML 붙여넣기나 SSH 보정을 사용하지 않습니다.
- 관리 화면을 다시 열어도 Compose 내용이 유지됩니다.
- broker·portal이 실행되고 runtime-image는 정상 종료합니다.
- HTTPS 설정 화면이 정상 응답합니다.
- 기존 Relay·Traefik은 계속 동작합니다.

공식 근거: [URL 설치](https://www.hostinger.com/support/12040815-how-to-deploy-your-first-container-with-hostinger-docker-manager/), [Raw URL 예시](https://www.hostinger.com/support/deploy-on-hostinger-button/), [Traefik 변수](https://www.hostinger.com/support/connecting-multiple-docker-compose-projects-using-traefik-in-hostinger-docker-manager/). 자동 초기 설정 CI는 도메인 환경값을 제거하고 Docker Relay 메타데이터와 DNS를 테스트용으로 구성합니다. 실제 hPanel importer·공인 DNS·TLS 발급은 별도로 확인해야 합니다.


## 자동 라우팅 컨테이너

초기 Compose 서비스 3개 외에 `setup-route`가 추가됩니다. 같은 portal 이미지의 제한된 HTTP 전달 프로그램이며, 별도 인증 데이터·Docker 소켓·호스트 볼륨이 없습니다. 사용자 요청은 고정된 자기 portal로만 전달합니다. 같은 구성으로 재시작하면 재사용합니다. portal 화면 이미지만 바뀐 경우에도 저장된 라우팅 정보·소유권·보안 설정이 모두 일치하면 기존 digest의 접속용 컨테이너를 재사용합니다. 다른 주소·네트워크·구성으로의 자동 변경은 거부합니다. 확인된 구버전 helper는 기존 URL을 유지하면서 정식 서비스로 전환합니다. 전환 후에는 Compose 조회와 종료에 포함됩니다. 다른 이미지 업그레이드는 별도 검토가 필요합니다.

네트워크 자동 탐색 수정은 CI37906214523 및 공개 URL 재실행 CI37906666736에서 통과했습니다. 기존 후보의 실제 Hostinger 설치와 공인 HTTPS는 확인했으며, 기존 Open 버튼 접속은 이후 사용자가 확인했습니다. 이번 복구 개선판 적용은 별도 확인합니다. 여러 네트워크/Traefik 후보가 남거나 HTTPS 라우터 설정을 확인할 수 없으면 안전하게 대기합니다. 아직 선택 화면은 없습니다. 공인 HTTPS 접속 확인 전에는 설치 성공으로 간주하지 마세요.


## 열기 버튼 수정 후보 검증

CI37912336094에서 134개 Python 검사와 실제 Docker 신규 설치·기존 helper 전환을 통과했습니다. 공개 URL 그대로 내려받은 배포 검사도 CI37912789643에서 통과했습니다. 접속용 서비스는 정식 Compose 목록과 종료 대상에 포함되며 기존 설정 화면 이미지·URL·인증 볼륨을 유지합니다. 이후 사용자가 기존 「열기」 클릭으로 설정 화면 접속을 확인했습니다. 「열기」가 인증값까지 전달하는지는 아직 확인되지 않았습니다.

기존 프로젝트의 단순 「업데이트」가 GitHub URL의 새 내용을 다시 가져온다고 가정하지 마세요. 이미지가 digest로 고정되어 있으므로 새 Compose 내용이 실제 저장됐는지 확인해야 합니다. 기존 프로젝트를 삭제하거나 이름을 바꾸면 현재 URL·볼륨과 달라질 수 있으므로, 기존 `buzz-agents` 구성을 보존한 적용 경로를 먼저 확인합니다.

## 이번 후보의 검증

- 이미지 소스: `b54f2212b70a55aeca8d9a2fd8778b88dc3e6745`, 후보 `portal-candidate-b54f2212b70a-15-1`.
- Python 142개, Linux Go race/vet, 실제 Windows 연결기 테스트 9개, 실제 Chrome의 자동 입력·만료·복구·모바일 표시 시험 통과.
- CI37929657380: 공유 네트워크/host 네트워크의 신규 설치, 구버전 broker 전환, 기존 계정·Windows 연결·접속용 컨테이너를 보존하는 portal 업데이트 통과. 익명 이미지 접근도 확인.
- Windows 실행 파일은 로컬 빌드와 공개 후보의 바이트가 일치합니다.
- 실제 사용자의 VPS는 변경하지 않았습니다. 기존 `buzz-agents` 프로젝트 이름·볼륨을 유지해 적용하세요. 프로젝트 삭제·새 이름으로 재생성하는 절차는 아닙니다.

공개 Raw URL의 실제 다운로드·이미지 pull·두 네트워크 모드의 HTTPS 설치 검증도 CI37930186525에서 통과했습니다. 실제 Hostinger의 인증값 전달은 이 시험에 포함되지 않습니다.
