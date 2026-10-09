# Buzz VPS 간편 연결 — Docker 설정 화면 개발 후보

각 사용자가 Windows Buzz에서 자신의 신원을 만들고, **자신의 공개키를 소유자로 지정한 Hostinger Buzz Relay**를 먼저 설치했다고 가정합니다. 기존 Relay와 Windows Buzz는 계속 사용합니다. nsec 개인키와 VPS root 비밀번호를 이 프로그램에 입력하지 않습니다.

## 현재 상태

v0.4 공개 개발 후보입니다. GitHub에서 이미지 빌드·임시 Compose 실행·비로그인 다운로드 검증을 통과했습니다. 실제 Hostinger 설치·공식 계정 인증·Windows 완전 종료 시험은 아직 남아 있습니다.

Docker Manager의 **컴포즈 → URL에서 Compose**에 입력할 주소:

```text
https://github.com/volition79/buzz-agents/releases/download/portal-candidate-8ae5df6d57c1-1-1/compose.install.yaml
```

가져온 설정에서 `BUZZ_SETUP_HOST`에 기존 Buzz 주소와 다른 설정 화면 호스트명을 지정하고, 해당 이름의 DNS가 VPS를 가리키는지 확인합니다. 이미지 3개는 이미 정확한 digest로 고정되어 있습니다. 로컬 `compose.hostinger.yaml`은 개발용 템플릿이며 위 공개 설치 파일과 다릅니다.

## 설치 및 실서버 검증 순서

1. Docker Manager에 위 Compose URL로 배포합니다. 기존 `traefik-proxy` 네트워크와 HTTPS 인증서 발급기 `letsencrypt`를 사용합니다. 해당 VPS를 가리키는 설정 화면 호스트명을 지정해야 합니다. 기존 Buzz 주소와는 다른 호스트명입니다.
2. 설정 화면을 엽니다. Docker Manager의 **portal 로그**에 나온 최초 설정 코드를 입력하고, 설정 화면용 비밀번호(12자 이상)를 정합니다. root 비밀번호와는 별개입니다. 최초 코드는 60분간 유효하며 사용 후 폐기됩니다. 만료 시 portal을 재시작하면 새 코드가 나옵니다.
3. 기존 Relay를 자동으로 찾습니다. 주소·소유자 공개키를 확인하고 연결합니다. 여러 개면 선택하고, 찾지 못하면 두 공개 정보만 직접 입력합니다. 소유권을 Nostr 서명으로 새로 증명하는 기능은 아닙니다. Docker 관리자만 읽을 수 있는 최초 코드와 기존 Relay 설정을 신뢰하며, 봇 권한은 기존 Relay가 검증합니다.
4. **Windows 연결 파일 받기** → ZIP 압축 풀기 → `Buzz-VPS-Connect.exe` 실행. 자기 서버 주소가 맞는지 확인합니다. 파일은 10분간 한 번만 사용 가능합니다.
5. Windows Buzz를 다시 열고 봇 실행 위치에서 **Hostinger VPS — HTTPS**를 선택해 배포합니다. 연결기가 보이지 않으면 현재 Buzz 버전의 외부 backend 검색 경로를 확인해야 합니다. 실제 Windows Buzz 발견/실행 시험은 아직 남아 있습니다.
6. 설정 화면에 나타난 해당 봇의 **계정 로그인**을 누릅니다. 공식 Codex/Claude 로그인 주소를 열어 승인합니다. Claude 등이 코드를 요청하면 설정 화면에 붙여넣습니다. 인증 정보는 그 봇의 VPS 홈에 남습니다. 로컬 Windows AI 인증 파일을 복사하지 않습니다.
7. Buzz에서 실제 답변을 확인합니다. 봇마다 격리된 홈을 사용하므로 봇을 추가하면 해당 봇도 로그인해야 합니다. 실행 중인 봇의 재인증은 먼저 Buzz에서 중지합니다.

설정 화면은 평소 닫아도 됩니다. 봇 생성·대화는 Windows Buzz에서 합니다. Windows 프로그램은 배포 시에만 서버에 연결하며 계속 켜놓는 중계기가 아닙니다. 다만 portal 컨테이너 자체를 중지하면 새 배포/상태 확인은 사용할 수 없습니다. 기존 봇·예약 컨테이너는 별도로 실행됩니다.

## 선택: Windows 종료 후 예약

설정 화면의 예약 항목에서 예약 봇 공개키를 확인합니다. 해당 신원을 Relay와 채널의 멤버로 승인하고, 대상 AI 봇의 허용 목록에 추가합니다. 채널 UUID·대상 봇·한국 시간·메시지를 입력하고 예약합니다. 이 권한 승인 단계는 자동으로 생략하지 않습니다.

**필수 합격 시험:** Windows를 완전히 끈 뒤 아직 시작되지 않았던 예약 작업이 VPS에서 시작되고, 두 AI가 작업 파일을 완성하는지 확인합니다. Relay에 메시지가 전달된 것만으로 작업 완료라고 판단하지 않습니다.

## 연결 해제와 복구

- 설정 화면에서 Windows 연결을 해제하면 해당 PC는 더 이상 새 배포를 요청할 수 없습니다. 실행 중인 봇·인증·파일은 삭제하지 않습니다.
- 설정 화면 로그인은 8시간 유효합니다. 다시 접속할 때 설정 화면용 비밀번호를 사용합니다. portal을 재시작하면 브라우저 세션과 미사용 연결 파일은 만료되지만, Windows 연결은 유지됩니다.
- 기존 v0.3 파일은 보존합니다. v0.4 연결기는 별도 이름이고 `~/.buzz-agents-web/connection.json`에 자기 연결 정보만 저장합니다. 다른 버전의 실행 파일이나 기존 연결 정보는 자동으로 덮어쓰지 않습니다.
- 재연결이 필요하면 설정 화면에서 기존 연결을 해제한 뒤 해당 PC의 위 연결 파일을 삭제하고 새 ZIP을 받습니다. 비밀번호 분실 복구·기존 설치 마이그레이션·이미지 자동 업그레이드는 별도 관리 절차가 필요합니다. 기존 데이터를 지워 재설치하지 마세요.

## 권한 구조

portal은 UID10002로 동작하며 Docker 소켓·봇 인증 폴더에 접근하지 않습니다. 네트워크가 없는 broker만 Docker 소켓과 정해진 데이터 폴더를 사용하고, private Unix socket으로 제한된 작업을 받습니다. **Docker 소켓을 가진 broker 자체는 서버 관리자에 준하는 권한**이 있으므로 신뢰한 이미지로만 배포해야 합니다. root 비밀번호가 필요 없다는 말은 내부 관리 권한까지 없다는 뜻이 아닙니다.

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

검토 후 지정 레지스트리에 공개하고 immutable digest로 `BUZZ_RUNTIME_IMAGE`, `BUZZ_BROKER_IMAGE`, `BUZZ_PORTAL_IMAGE`를 고정합니다. `BUZZ_SETUP_HOST`는 설정 화면 호스트명입니다. 아직 공개하지 않은 주소를 문서에 임의로 쓰지 않습니다.

공개 준비용 `.github/workflows/portal-images.yml`도 포함됩니다. 저장소에 올리는 것만으로 실행되지 않고, **수동 workflow_dispatch** 때만 동작합니다. Windows 빌드·테스트 → Docker 이미지 빌드 → 별도 CI 서버에서 Compose/권한 경계 스모크 → GHCR push → 익명 pull 확인 → digest가 고정된 설치 Compose를 후보 릴리스에 첨부하는 순서입니다. 최초 GHCR 패키지가 비공개이면 익명 확인 단계에서 멈추므로, 저장소 소유자가 각 패키지를 Public으로 바꾼 뒤 다시 실행해야 합니다. 첫 CI 실행은 성공했습니다.

공개 소스 준비본은 `public-source.zip`입니다. 개인 계정 정보·연결 파일·테스트 실행 로그·이전 ZIP을 포함하지 않습니다. 기존 v0.3 소스는 회귀 확인을 위해 보존하지만, 새 배포 경로는 `web-provider`, `connect`, `Dockerfile.portal`입니다.

기반: [Hostinger의 여러 Compose 프로젝트 Traefik 연결 안내](https://www.hostinger.com/support/connecting-multiple-docker-compose-projects-using-traefik-in-hostinger-docker-manager/), [Docker 소켓 권한 안내](https://docs.docker.com/engine/security/protect-access/).
