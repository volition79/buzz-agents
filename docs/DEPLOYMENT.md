# 설치와 적용 — v0.2.0

## 0. 먼저 이해할 경계

Windows Buzz → 원격 제공자(.exe) → OpenSSH → VPS의 제한된 수신기 → 봇별 Docker 컨테이너.
배포 후 Windows 연결은 유지할 필요가 없습니다. 봇은 VPS에서 Relay와 직접 통신합니다.

이 구성은 `buzz-rpka`를 수정하지 않습니다. 운영체제 재설치, 새 VPS, Kubernetes도 필요하지 않습니다.
다만 **첫 준비까지 hPanel YAML 붙여넣기 하나로 끝나는 구성은 아닙니다.**
VPS에서 이미지 빌드·수신기 설치를 한 번 하고 Windows에 원격 제공자를 설치해야 합니다.

문서의 `<...>`는 자기 환경의 값으로 바꿉니다. 비밀번호·nsec·구독 토큰을 채팅이나 영상에 공개하지 마세요.

## 1. 기존 서버 확인과 백업

현재 Relay의 주소와 공개키를 기록합니다. 다음은 기존 설정의 점검 항목이지 변경 명령이 아닙니다.

- 기존 `RELAY_OWNER_PUBKEY`: 자신의 64자리 HEX 공개키.
- `BUZZ_REQUIRE_AUTH_TOKEN=true`, `BUZZ_REQUIRE_RELAY_MEMBERSHIP=true` 여부.
- 이 패키지의 봇은 Buzz가 보내는 소유자 위임 서명(`auth_tag`)을 사용합니다.
  Relay에서 NIP-OA 위임 인증을 허용하고 해당 소유자의 회원 상태가 유효해야 합니다.
- Relay 입장과 채널 참여는 별개입니다. 봇을 필요한 채널에 추가합니다.

현재 프로젝트 YAML·데이터·미디어·Relay 신원키의 백업과 복원 방법을 준비합니다.
기존 도메인·신원키를 바꾸지 않습니다. 스냅샷 보존 기간만 믿지 말고 실제 보관 상태를 확인합니다.

## 2. VPS에 소스 전달과 이미지 빌드

ZIP을 VPS의 새 디렉터리에 업로드하고 압축을 풉니다. 예: `/root/buzz-agents-v0.2.0/`.
현재 `buzz-rpka` 디렉터리에 덮어쓰지 마세요.

소스 폴더에서:

```bash
cd /root/buzz-agents-v0.2.0/buzz-agents
sha256sum -c SHA256SUMS
docker build -t buzz-agents:0.2.0 .
```

Dockerfile은 원본 패키지의 Buzz/Sprig 지문과 ACP 버전 지정을 유지합니다.
해당 이미지·npm 패키지를 현재 레지스트리에서 실제로 가져오고 실행하는 것은 이 빌드에서 최초 검증됩니다.
이 대화의 시험 환경에서는 Docker/외부 네트워크가 없어 빌드를 수행하지 못했습니다.

빌드 과정은 `scripts/preflight.py`로 공식 native 옵션·CLI 버전·키 생성/공개키 일치 여부를 검사합니다.
실패하면 검사 삭제나 `|| true`로 무시하지 말고 실패 원인을 확인하세요. 로그에 구독 인증 정보는 넣지 않습니다.

완료 후:

```bash
docker run --rm --network none --entrypoint cat buzz-agents:0.2.0 /opt/buzz-build/inventory.json
```

이는 설치된 구성 요소 목록입니다. 로그인이나 실제 AI 작업 성공 증명은 아닙니다.
최종 배포 시 호스트 수신기는 이 이미지의 실제 로컬 Image ID를 기록하고, 태그가 다른 이미지로 바뀌면 거부합니다.

## 3. 제한된 배포 수신기 설치

VPS 관리자(root) 터미널에서:

```bash
sh scripts/install-host.sh "$PWD" buzz-agents:0.2.0 \
  <자신의_64자리_HEX_공개키> \
  wss://<기존_Buzz_Relay_도메인>
```

생성되는 경로와 계정:

| 항목 | 용도 |
|---|---|
| `/opt/buzz-agents` | root만 변경 가능한 관리 코드·호스트 설정 |
| `/var/lib/buzz-agents-v2` | 봇 설정·인증 홈·실행 상태·생성된 Compose |
| `buzzdeploy` | 제한된 SSH 배포 전용 계정 |
| `/usr/local/sbin/buzz-agents-receive` | 고정 JSON 배포 요청만 받는 명령 |
| `/etc/sudoers.d/buzz-agents-receive` | 위 명령 하나만 허용하는 sudo 규칙 |

동일한 계정이나 설치 디렉터리가 이미 있으면 설치를 거부합니다. 기존 것을 지우고 강행하지 말고 확인하세요.
전체 파일 시스템이나 Docker 소켓을 AI 컨테이너에 제공하지 않습니다.

## 4. Windows 전용 SSH 연결 준비

Windows PowerShell에서 전용 키를 만듭니다.

```powershell
New-Item -ItemType Directory -Force "$HOME\.ssh" | Out-Null
ssh-keygen -t ed25519 -f "$HOME\.ssh\buzz_vps"
```

키 암호를 설정했다면 OpenSSH agent에 올려야 비대화형 배포가 됩니다.
`ssh-agent` 서비스가 사용 가능한 환경에서 `ssh-add "$HOME\.ssh\buzz_vps"`를 사용합니다.
이 개인키는 Windows에 보관하며 VPS에는 `.pub` 파일의 공개키만 전달합니다.

VPS `/home/buzzdeploy/.ssh/authorized_keys`에 **다음 제한을 붙인 한 줄**을 넣습니다.
아래 `AAA...` 부분은 Windows `buzz_vps.pub`의 실제 공개키 본문으로 바꿉니다.

```text
restrict,command="sudo -n /usr/local/sbin/buzz-agents-receive" ssh-ed25519 AAA... buzz-vps
```

VPS에서 권한을 맞춥니다.

```bash
chown buzzdeploy:buzzdeploy /home/buzzdeploy/.ssh/authorized_keys
chmod 600 /home/buzzdeploy/.ssh/authorized_keys
```

`restrict`와 `command=`를 빼지 마세요. 이 키로 일반 셸·포트 포워딩을 열기 위한 구성이 아닙니다.
수신기는 SSH가 요청한 임의 명령을 실행하지 않고 자신의 고정 JSON 배포 처리만 합니다.

Windows `$HOME\.ssh\config`에 추가:

```sshconfig
Host buzz-vps
    HostName <VPS_IP>
    User buzzdeploy
    IdentityFile ~/.ssh/buzz_vps
    IdentitiesOnly yes
    RequestTTY no
```

서버 호스트키도 검증해야 합니다. VPS 관리자 콘솔에서:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Windows에서 서버 키를 임시 파일로 읽고 같은 지문인지 **별도 콘솔 결과와 대조한 후에만** known_hosts에 추가합니다.

```powershell
ssh-keyscan -t ed25519 <VPS_IP> 2>$null | Set-Content -Encoding ascii "$env:TEMP\buzz-hostkey.txt"
ssh-keygen -lf "$env:TEMP\buzz-hostkey.txt"
# 위 지문이 VPS 콘솔과 일치하는 것을 직접 확인한 다음 실행:
Get-Content "$env:TEMP\buzz-hostkey.txt" | Add-Content -Encoding ascii "$HOME\.ssh\known_hosts"
```

제공자는 `BatchMode=yes`, `StrictHostKeyChecking=yes`를 사용합니다.
새 서버 키를 몰래 신뢰하거나 로그인 비밀번호를 채팅에서 받지 않습니다.

## 5. Windows 원격 제공자 설치

패키지의 `bin/buzz-backend-hostinger.exe`를 Windows에 복사합니다. x64용이며 코드 서명되지 않았습니다.
출처를 신뢰한 뒤 사용하세요. 원하면 `provider/`의 Go 소스를 직접 빌드할 수 있습니다.

공식 검색 경로 중 사용자 폴더를 사용하는 예:

```powershell
New-Item -ItemType Directory -Force "$HOME\.local\bin" | Out-Null
Copy-Item .\bin\buzz-backend-hostinger.exe "$HOME\.local\bin\buzz-backend-hostinger.exe"
'{"op":"info","request_id":"local-check"}' | & "$HOME\.local\bin\buzz-backend-hostinger.exe"
```

정상 응답에는 `ok: true`, `protocol_version: 1`이 있어야 합니다. 이 확인은 VPS 접속 검사가 아닙니다.
Buzz를 다시 열고 봇 편집 화면의 원격 실행 위치(`Run on` 또는 해당 버전의 실행 위치 메뉴)에서
**Hostinger VPS — Native Buzz**가 표시되는지 확인합니다.

앱 버전에 따라 검색 경로가 다르거나 원격 제공자 기능이 노출되지 않을 수 있습니다.
필요하면 이 폴더를 사용자 PATH에 추가한 뒤 앱을 완전히 다시 시작합니다.
제공자가 끝내 보이지 않거나 `desktop_launch_contract_required` 오류가 나오면 그 앱 버전은 여기서 요구하는
원격 계약과 맞지 않습니다. 이 상태를 성공으로 간주하거나 Local 실행으로 바꾸면 안 됩니다.

## 6. Buzz에서 원하는 봇 생성

Buzz의 기본 봇 생성/편집 UI에서 이름·역할·모델을 설정합니다.
지원하는 ACP 실행 명령은 `codex-acp`, `claude-agent-acp`입니다. 사용자 지정 셸 명령은 거부합니다.

원격 제공자 설정의 초기값:

| 필드 | 초기값 | 의미 |
|---|---:|---|
| `ssh_alias` | `buzz-vps` | Windows SSH config에서 정의한 이름 |
| `workspace` | `private` | 개별 작업 공간. 같은 문자열의 그룹을 쓰면 파일 공유 |
| `memory_mb` | 1536 | 봇 컨테이너 메모리 제한 |
| `cpus` | 0.75 | CPU 사용 상한 |
| `max_turn_seconds` | 7200 | 공식 실행기가 적용하는 작업당 최대 시간 (초) |
| `turn_limit` | 0 | 지정 시간 구간의 요청 시작 한도. 0은 제한 없음 |
| `window_seconds` | 3600 | 호출 수를 셀 시간 구간 |
| `daily_limit` | 0 | 최근 24시간 요청 시작 한도. 0은 제한 없음 |

Buzz의 봇별 동시 실행 설정(1~32, 기본값 10)을 VPS에서도 그대로 사용합니다. 사용자가 VPS의 CPU·메모리와 봇 수에 맞게 직접 조절하세요. 10은 동시 실행 상한이며 항상 10개 작업을 실행한다는 뜻은 아닙니다. 봇의 CPU·메모리 제한은 전체 작업이 공유하며, 작업 시작 횟수 제한도 봇 단위로 합산합니다.

VPS agents honor Buzz per-agent concurrency (1–32, default 10). Adjust the count yourself for available CPU, memory, and the number of bots. This is a maximum, not ten continuously running tasks. All workers share the bot container’s CPU/memory limits and aggregate start quotas.
`owner-only` 또는 명시적 `allowlist`를 사용합니다. 공개 `anyone` 모드는 이 패키지에서 거부합니다.

**주의:** 공식 Buzz의 같은 소유자 봇 취급은 런타임 버전에 따릅니다. `owner-only`를 사람만 허용하는 것으로
단정하지 마세요. 허용된 두 봇으로 실제 상호 멘션을 시험하고, 의도하지 않은 호출은 제한합니다.

같은 종류의 봇을 추가로 만들 수 있습니다. 봇마다 신원키와 인증 홈이 다릅니다.
기본 총 메모리 배정 예산은 5,120MiB이며, 봇별 기본값 1,536MiB로는 등록 3개까지 허용됩니다.
이는 성능 보증이 아니라 기존 Relay를 보호하려는 설정상 상한입니다. 먼저 두 봇으로 실측하세요.

## 7. 봇별 최초 구독 로그인

처음 배포된 봇은 `needs_login`으로 대기하며 모델 요청을 하지 않습니다.

생성된 프로젝트는 `buzz-agents-v2`, 컨테이너는 `buzz-native-<공개키 앞 20자리>`입니다.
hPanel에 이 외부 생성 프로젝트가 표시되는지 확인합니다. 표시되지 않으면 직접 만든 프로젝트의 자동 검색이
그 환경에서 지원되는지 확인해야 하며, 호스트 Docker 명령으로는 아래와 같이 접근할 수 있습니다.

Codex 봇의 컨테이너 터미널(root):

```bash
python -m buzz_agents.cli auth codex
```

Claude 봇의 컨테이너 터미널(root):

```bash
python -m buzz_agents.cli auth claude
```

공식 프로그램이 보여주는 기기 코드/브라우저 인증을 본인 계정으로 완료합니다.
관리 코드가 공식 로그인 성공을 기록하면 대기 중인 감독 프로세스가 컨테이너를 새로 시작하여 native 봇을 실행합니다.
성공 메시지는 로그인 명령의 정상 종료라는 뜻입니다. 반드시 실제 AI 응답을 추가로 확인하세요.

이미 실행 중인 봇을 재인증하려면 먼저 `!shutdown`으로 멈춥니다.
인증 파일을 다른 봇이나 Windows에서 복사해 공유하지 마세요. 각 봇이 공식 로그인으로 별도 상태를 갖습니다.
API 키·추가 과금 설정은 이 코드가 계정 차원에서 차단해 주지 않습니다.

## 8. 실제 메시지와 자유 협업 확인

두 봇을 같은 채널에 추가하고 `@` 자동완성에서 선택합니다.

예시: `@기획자 웹툰 소재를 제안하고, 작가에게 의견을 요청한 다음 차이를 정리해주세요.`

정해진 3단계를 실행하는 `/ba run`이 아닙니다. 프로그램에는 봇 순서나 역할 목록이 고정되어 있지 않습니다.
공식 Buzz가 봇의 멘션·대화·응답을 처리합니다. 상대 봇이 요청을 받을 접근 권한과 채널 참여가 필요합니다.

설정·역할·모델 변경은 실행 중 컨테이너에 자동 동기화하지 않습니다.
해당 봇에 소유자가 `!shutdown` → 변경 저장 → 다시 Deploy 순서로 반영합니다.
활성 봇의 설정을 바꾸려고 하면 `stop_native_bot_before_changing_settings`로 거부합니다.

## 9. 상태 확인과 중단

컨테이너 안에서:

```bash
python -m buzz_agents.cli status
python -m buzz_agents.cli security-check
```

두 번째 명령은 AI 사용자(10001)가 감독 프로그램의 설정·상태 파일을 읽지 못하는지 실제 경계 검사합니다.

호스트에서 전체 봇 상태:

```bash
cd /opt/buzz-agents
python3 -m buzz_agents.host status
```

`running`은 프로세스가 실행 중이라는 뜻이지 모델 건강 상태 보증은 아닙니다.
`needs_login`은 최초 로그인 대기, `stopped`는 의도적 종료, `held`는 정책/장애 중단입니다.
의도적으로 종료한 봇도 작은 감독 컨테이너는 hPanel에서 Running으로 보일 수 있습니다.
Buzz의 온라인 표시와 `cli status`를 함께 확인하세요.

`!shutdown`이 먹히지 않는 장애는 hPanel에서 해당 봇 컨테이너 Stop으로 멈춥니다.
친구 봇이나 기존 Relay 전체를 삭제하지 않습니다.

## 10. Windows 종료·서버 복구 시험

- Windows가 켜진 동안 파일 작업과 다른 봇에 대한 요청을 시작합니다.
- Windows를 완전히 종료한 뒤 생성된 파일 시각과 Buzz 결과를 확인합니다.
- 예약 실행은 `AUTOMATION.md`대로 따로 설정하여 Windows 종료 후 새 작업이 발동되는지 확인합니다.
- 정상적인 Docker/호스트 종료는 native 실행을 다시 준비할 수 있지만, **강제 재부팅·OOM 등 불확실한 중단은 held로 보류**합니다.
- 이미 시작된 작업의 자동 재실행·정확히 한 번 수행을 보증하지 않습니다.
- `!shutdown` 이후 재부팅해도 봇이 자동으로 깨어나지 않는지 시험합니다.

CPU·RAM·디스크·작업 시간·오류·계정 사용량을 함께 기록합니다. 이 시험 전에는 영상에서 실제 무인 운영 검증 완료로 소개하지 않습니다.

## 11. 봇 삭제와 용량 회수

원격 제공자 규약에는 undeploy가 없으므로 Buzz 화면에서 기록을 삭제하는 것만으로 VPS가 정리되지 않습니다.
먼저 봇을 `!shutdown` 또는 hPanel Stop으로 종료한 뒤 호스트에서:

```bash
cd /opt/buzz-agents
python3 -m buzz_agents.host retire <봇의_64자리_HEX_공개키> --confirm-stopped
```

활성 native 봇이나 소유권 표식이 다른 컨테이너는 거부합니다.
해당 컨테이너와 등록만 제거하고 파일·인증·작업 데이터는 삭제하지 않습니다. 총 등록 메모리 예산은 회수됩니다.
완전한 자료 삭제는 백업 및 계정 연결 회수를 확인한 뒤 운영자가 별도로 결정합니다.

동일 봇의 실행기를 Codex에서 Claude로 바꿀 경우에도 두 공급자의 인증 홈은 별도로 유지합니다.


## Local contract correction candidate — 2026-10-10

The candidate must include a newly built **runtime**, broker, portal and Windows connection tool. Existing canonical Compose still references the previously published images; it is intentionally unchanged until publication/testing is authorized. The publication workflow now builds all three images from one source revision.

Run the updated connection tool once to upgrade a recognized old HTTPS provider. Existing connection credentials are preserved. Unknown local provider binaries are not overwritten. For existing bots, stop them in Buzz before redeploying to the new runtime. A running old-image bot reports `stop_native_bot_before_image_upgrade` rather than being silently replaced.

Local regression coverage includes real validator errors, replay-floor identity and one-start consumption, fresh nonce, active cancellation, adapter EOF/crash isolation, safe diagnostic categories, graceful and forced process shutdown, host capacity budgeting and connection binary replacement. A prompt error no longer trips every worker. Quota/storage/deadline violations still hold the whole bot as a safety policy. Unknown adapter failures remain generic; classifier output is evidence of a message category, not a definitive cause.

Supported boundary: Codex ACP / Claude Agent ACP, owner-attested private Relay, empty custom argv. Model dropdown discovery belongs to Windows Buzz's local runtime, not this HTTPS provider. Model list recovery by waiting/reopening is a troubleshooting hint, not a proven root-cause fix. Live policy changes require stop/redeploy. VPS account login remains separate from local Windows login.

동시 실행 기본값은 10(1~32 선택)입니다. 사용자가 VPS 성능에 맞게 조절해야 하며 자동 성능 튜닝을 의미하지 않습니다. CPU/RAM은 실제 Docker host 용량으로 검증합니다. 기존 기본 5120MiB/8봇 제한은 host-v1 정책으로 이행하며, 사용자 지정 제한은 보존합니다. 같은 값을 수동으로 고정하려면 resource_policy=fixed를 사용합니다.

배포 후 필수 실제 검증: Claude·Codex 각각 로그인 → Buzz 메시지와 도구 실행 → 실패 분류 로그 확인 → 정상 중지/재배포 → Windows 완전 종료 후 VPS에서 **새 작업** 시작·완료 확인. 이 검증 전에는 24시간 무인 운용 완료로 소개하지 않습니다.

완료된 로그인은 동시 로그인 8개 한도에서 제외됩니다. 최근 완료 출력은 제한적으로 보관하며 오래된 화면의 세션이 사라지면 새 로그인을 시작합니다. 강제 종료된 AI 작업의 슬롯은 해당 프로세스 그룹이 모두 종료된 뒤 회수하고, 사용량 기록은 유지합니다.

Release pipeline: build-portal.py creates the artifact manifest; render-portal-release.py adds the final digest-pinned Compose and SHA256SUMS. Immediately before publication, run its --verify mode. Existing artifact hash mismatches fail the release.

로그인 만료 정리가 실패하면 `login_cleanup_pending`만 기록하고 다른 봇의 로그인은 계속 허용합니다. 실패한 실행의 종료를 확인하기 전에는 해당 봇의 중복 로그인을 막고 실행 한도도 유지합니다. 이후 요청에서 30초 간격으로 정리를 재시도합니다. 배포 파일 목록은 `render-portal-release.py --list-assets --output ...`의 검증 결과를 사용합니다.


## 정상 작업과 오류 복구 / Healthy work and failure recovery

새 배포의 기본값은 횟수 제한 없음(0), 활동이 없는 대기 시간 25분,
작업당 최대 2시간입니다. 공식 buzz-acp가 실패 유형별 재시도와 취소를
처리하며, 이 패키지는 자체 자동 재시도 루프를 추가하지 않습니다.
별도 안전 시간은 최대 시간 이후 120초이며 해당 작업 실행기만 종료합니다.
한 작업 실패로 다른 작업을 중단하지 않습니다. 다만 정리 실패·저장 오류 등
안전성을 확인할 수 없는 상태는 여전히 봇을 보류합니다.

기존 봇의 20/100회·30분·5분 설정은 자동 변경하지 않습니다. 최신 연결기와
런타임을 설치한 후 Buzz에서 봇을 중지하고, 제공자 설정의 `turn_limit`과
`daily_limit`을 0, `max_turn_seconds`를 7200으로 설정해 다시 배포하세요.
별도로 지정한 `BUZZ_ACP_IDLE_TIMEOUT`/`BUZZ_ACP_MAX_TURN_DURATION`도 확인하세요.
봇 삭제, 작업 파일 삭제, 재로그인은 필요하지 않습니다. 설정 화면이 아직
옛 기본값을 보여주면 최신 Windows 연결기를 설치하고 Buzz를 다시 여세요.

선택한 횟수 한도는 재시도 요청을 포함해 허용된 `session/prompt` 시작을 셉니다.
토큰 비용 제한이 아닙니다. 한도에 걸리면 해당 요청에 이유와 재시도까지의
초를 반환하고 봇은 유지합니다. 한도 종료 후 새 요청을 받을 수 있지만,
공식 실행기가 이미 포기한 요청을 자동으로 되살리지는 않습니다.
예전 버전의 횟수 제한 보류만 실제 사용 기록상 한도가 풀렸을 때 해제합니다.
로그인 필요, 사용자 중지, 비정상 종료, 정리 실패는 자동 해제하지 않습니다.

New deployments default to no prompt-count budget (0), 25 minutes of inactivity,
and a two-hour turn cap. Official buzz-acp owns retries and cancellation. A local
worker fallback allows a further 120 seconds for cleanup, then stops only that
worker. Storage/integrity/cleanup failures still hold the bot.
Existing values are preserved: stop the bot, set turn_limit/daily_limit to 0 and
max_turn_seconds to 7200, check explicit timeout environment settings, and redeploy
with the updated runtime/provider. Do not delete bots, files or credentials.
Optional budgets count admitted prompts, including retries, not tokens. Expiry
allows new requests; it does not replay requests already abandoned by upstream.
Only expired legacy quota holds self-rearm; other stop/auth/fault states remain.

작업 실행기의 안전 종료 뒤에도 30초 동안 티켓이 남으면
`worker_cleanup_timeout`으로 봇을 보류합니다. 정상 작업 횟수가 아니라
종료 확인 실패에 대한 최종 안전장치입니다. 의미 없는 대화가 성공 응답으로
반복되는지까지 자동 판별하는 기능은 아니므로, 필요하면 선택 한도를 설정하세요.
If a ticket remains for another 30 seconds after the worker watchdog, the supervisor
holds the bot with worker_cleanup_timeout. This is a cleanup-integrity fallback,
not a normal-work quota. Successful but unproductive conversations are not detected
semantically; optional budgets remain available.
