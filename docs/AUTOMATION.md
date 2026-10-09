# 선택 기능: 예약 시각에 native 봇 멘션

예약을 쓰지 않는 경우 이 문서는 건너뜁니다. 기본 멀티 봇 실행과 별도입니다.
이 기능도 같은 VPS에서 실행되므로 Windows에 스케줄러를 설치하지 않습니다.

이 스케줄러는 고정 작업 흐름을 실행하지 않습니다.
특정 시각에 `@대상봇 + 사용자가 정한 문장`을 Buzz에 게시할 뿐입니다.
그다음 협업과 결과 응답은 native Buzz/AI가 담당합니다.

## 최초 준비

호스트 관리자 터미널에서:

```bash
install -d -m 0700 /var/lib/buzz-agents-automation
docker run --rm -u 0:0 --network none \
  -v /var/lib/buzz-agents-automation:/bootstrap \
  --entrypoint python buzz-agents:0.2.0 \
  -m buzz_agents.cli automation-init /bootstrap --relay wss://<기존_Relay_도메인>
```

이 명령은 **새 스케줄러 신원**을 만들고 공개키만 출력합니다. 기존 파일이 있으면 거부합니다.
사람의 nsec나 다른 봇의 로그인 정보를 복사하지 않습니다.

출력된 공개키를 기존 Relay 회원과 원하는 채널 구성원으로 등록합니다.
대상 봇의 Buzz allowlist에 이 스케줄러 공개키를 명시적으로 허용하고 변경된 봇을 다시 배포합니다.
직접 회원으로 등록하는 구성에서는 scheduler의 auth_tag는 null로 둡니다.
Relay/채널/봇 접근 모두 성공해야 예약 멘션이 실행으로 이어집니다.

## 설정

호스트의 `/var/lib/buzz-agents-automation/config/config.json`을 수정합니다.
이 파일에 이미 들어 있는 private_key_hex는 유지하고 화면에 노출하지 않습니다.
공개 예제는 `examples/schedules.json`의 schedules 목록입니다.

예:

```json
{
  "id": "webtoon-morning",
  "enabled": true,
  "kind": "daily",
  "time": "09:00",
  "timezone": "Asia/Seoul",
  "channel_id": "<대상_채널_UUID>",
  "bot_pubkey": "<기획자_봇의_64자리_HEX_공개키>",
  "prompt": "오늘의 웹툰 소재를 기획하고 작가와 검토자에게 필요한 의견을 요청하세요. 목표를 만족하면 종료하고 결과를 알려주세요."
}
```

설정 파일 최상위 enabled를 true로 변경합니다.
파일은 UID10001 소유, 권한0600, 디렉터리0700을 유지합니다.
편집기가 다른 파일로 교체했다면 소유권/권한도 다시 확인합니다.

패키지 폴더에서:

```bash
BUZZ_AGENTS_IMAGE=buzz-agents:0.2.0 docker compose -f compose.automation.yaml up -d
```

설정은 시작할 때 읽으므로 변경 뒤 scheduler 컨테이너를 재시작합니다.
시간대는 Asia/Seoul 또는 UTC, 일정은 daily HH:MM 또는 once의 명시적 UTC offset 시각을 지원합니다.
이 예약 편집은 아직 Buzz 기본 설정 UI에 통합하지 않았습니다. 선택적인 파일 기반 기능입니다.

## 정확한 보장 범위

- 발송 전에 해당 회차를 SQLite 장부에 기록합니다.
- 120초 넘게 늦은 회차는 건너뛰며 몰아서 실행하지 않습니다.
- 전송 성공 여부가 불확실하면 unknown으로 남기고 자동으로 새 메시지를 만들어 재시도하지 않습니다.
- `delivered_not_completion`은 Relay가 메시지를 받았다는 뜻입니다. AI 실행·협업 완료라는 뜻이 아닙니다.
- 대상 봇이 offline/held이면 멘션이 실제 작업으로 이어지지 않을 수 있습니다. 다시 깨어날 때 과거 예약을 반드시 실행하는 구조가 아닙니다.
- 이 기능만으로 작업의 정확히 한 번 실행, 외부 게시 중복 방지 또는 품질 완료를 보증하지 않습니다.
- 하나의 예약 ID는 같은 시각 회차를 중복 발송하지 않습니다. 내용을 바꾸어 같은 회차를 다시 보내려면 사람이 새 ID와 의도를 결정해야 합니다.

## 필수 확인

먼저 사람이 보고 있는 상태에서 일회성 예약을 검사합니다.
회원·멘션·응답을 확인한 후, Windows를 끈 뒤 새 일회성 예약이 실제로 발동하는지 따로 확인합니다.
