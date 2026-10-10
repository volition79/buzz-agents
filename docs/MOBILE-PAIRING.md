# Mobile pairing / 휴대폰 페어링

## 한국어

최신 기능이 포함된 broker/portal 이미지로 설치한 뒤 설정 페이지에서 내 Relay를
저장하면 휴대폰 페어링을 자동 준비합니다. Windows Buzz의 Settings → Mobile에서
QR 코드를 표시하고, 휴대폰 Buzz의 Scan QR code로 스캔한 뒤 Windows에 표시된
6자리 코드를 휴대폰에 입력하세요. 실제 UI는 Buzz 버전에 따라 다를 수 있습니다.

오류가 나타나면 먼저 Try again을 누르세요. 계속 실패하면 Docker Manager에서
**설치한 buzz-agents 프로젝트**의 다시 시작을 누른 뒤 재시도하세요. 설치 프로젝트
이름을 변경했다면 그 이름을 사용합니다. Relay나 AI 봇을 삭제하지 마세요.
broker 로그의 `Mobile pairing: pending (...)`은 준비 확인이 필요하다는 뜻입니다.
재시작해도 계속되면 다음 조건을 확인해야 하며, 반복 재시작으로 해결되지 않을 수 있습니다.

- `mobile_pairing_binary_missing`: 기존 Relay 이미지에 공식 페어링 실행 파일이
  없거나 컨테이너 내 확인이 실패했습니다. Relay 이미지/상태 확인이 필요합니다.
- `mobile_existing_*_preserved`: 기존 서비스/라우팅과 충돌합니다. 자동 덮어쓰기를
  하지 않습니다. 기존 설정을 검토해야 합니다.
- `mobile_custom_pairing_preserved`: 운영자가 별도 페어링 URL을 지정했습니다.
  그 구성을 유지하며 여기서 변경하지 않습니다.
- `mobile_relay_missing_or_ambiguous` / `mobile_relay_unsupported`: 자동 지원 범위와
  다른 Relay 구성입니다. 사용자 지정 프록시/경로는 별도 확인이 필요합니다.

`available`은 마지막 검사에서 HTTPS WebSocket 연결이 가능했다는 뜻이며,
휴대폰의 실제 페어링 완료나 AI 작업 성공을 뜻하지 않습니다. 휴대폰에서 채널과
메시지가 보이는지 확인한 뒤 Windows를 끄고 새 메시지에 VPS 봇이 응답하는지 확인하세요.

## English

With broker/portal images containing this feature, saving your Relay settings
automatically prepares mobile pairing. In Windows Buzz, open Settings → Mobile.
Scan the QR code with Scan QR code in mobile Buzz and enter the six-digit code
shown on Windows. The exact UI can vary by Buzz version.

On an error, select Try again first. If it persists, restart **your buzz-agents
installation project** in Docker Manager and retry; use its actual project name.
Do not delete your Relay or AI bots. Check `Mobile pairing: pending (...)` in
broker logs if restarting does not help. Missing binaries, ambiguous/custom
routing and conflicting existing services require review; restarting cannot
repair every unsupported configuration. Custom pairing URLs are preserved.

`available` records a successful HTTPS WebSocket handshake at the last setup
check, not completed mobile pairing or successful AI execution. Verify channels
and messages on your phone, then turn Windows off and test a new message to a VPS bot.

## Implementation and support boundary

- Runs at first Relay configuration and on broker bootstrap/restart using saved
  settings. No new root password, SSH key, phone credential or human nsec input.
- Selects one running Relay by configured owner and exact Traefik Host rule;
  derives network, HTTPS entrypoint and certificate resolver from Docker.
- Supports a root `wss://` Relay on port 443, an official `block/buzz` image
  containing `/usr/local/bin/buzz-pair-relay`, and the existing supported Traefik
  bootstrap topology. Does not claim every self-hosted or split-proxy layout.
- Uses the locally installed Relay image ID, without pulling a mutable tag or
  restarting/upgrading the Relay. The image remains available while Relay runs.
- Healthy existing `/pair` is reused, including a manually created `buzz-pairing`
  project. Unhealthy conflicting routing is retained for review, never shadowed.
- New service belongs to the installation Compose as `mobile-pairing`, with a
  relay-host-derived container name. Declared in Compose for restart/deletion
  lifecycle. Concurrent installations cannot create the same named container.
- No host port, Docker socket, mounts, added capabilities or persistent pairing
  data. Read-only filesystem, UID 1000, 128 MiB, 0.25 CPU, 64 PIDs, two Tokio
  workers, bounded logs and unless-stopped restart. Only exact `/pair` is routed.
- Only the mobile service/network may change. A failed creation retains its
  declaration for retry. Existing unrelated services and volumes are preserved.
- Relay image changes or custom modifications to this managed service require
  review rather than silently replacing a running pairing service.
- `mobile-pairing.json` stores only a coarse result, sanitized reason and last
  check time. Optional pairing failures do not cancel ordinary AI configuration.
- Publication must build both broker and portal images and update the release
  Compose digests. Editing source alone does not update an existing install URL.

References: [official pairing deployment](https://github.com/block/buzz/blob/main/deploy/charts/buzz/templates/pairing-relay.yaml),
[official image](https://github.com/block/buzz/blob/main/Dockerfile),
[Relay configuration](https://github.com/block/buzz/blob/main/crates/buzz-relay/src/config.rs).

Local checks cover Compose generation/reconciliation, preservation, failure and
retry, broker integration, and Korean/English UI. Automated release deployment,
Android identity transfer, and Windows-off task execution remain live acceptance
checks; the earlier manual VPS repair is not proof of this new installer path.
