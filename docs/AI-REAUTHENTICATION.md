# AI sign-in recovery / AI 재로그인

## 한국어

인증 오류가 발생하면 Buzz의 원래 오류 안내 뒤에 Docker Manager → 사용 중인 buzz-agents 프로젝트 → **열기** → 해당 봇의 **재로그인** 안내가 붙습니다. 사용량·요청 속도 제한은 소유하신 AI 플랜의 사용량과 초기화 시간을 확인하라는 안내를 붙입니다. 재로그인으로 사용량 한도가 초기화되지는 않습니다. 공식 Buzz의 재시도 횟수와 간격은 변경하지 않습니다.

1. 설정 화면에 로그인하고 해당 봇의 **재로그인**을 누릅니다. 실행 중이어도 사용할 수 있습니다.
2. 선택한 봇의 작업 중단을 확인합니다. 다른 봇, 역할, 모델, 로그인 저장 폴더, 작업 파일과 실행 제한은 유지합니다.
3. 표시되는 공식 Claude/Codex 로그인 링크와 안내를 따릅니다.
4. 로그인 명령이 성공하고 이전 로그인 프로세스 정리가 확인되면 같은 봇이 자동으로 시작됩니다. Buzz에서 중단했던 요청을 다시 보내 실제 답변을 확인하세요. 이전 요청을 자동으로 다시 보내지는 않습니다.

실패·취소·시간 만료 후에는 해당 봇을 대기 상태로 유지합니다. **재로그인**을 다시 누르면 처음부터 시도할 수 있습니다. 새로고침은 진행 중인 로그인 화면을 복원하며 새 로그인을 중복 실행하지 않습니다. 관리 서비스가 재시작돼 진행 상태를 잃었으면 다시 재로그인하세요. 기존 프로세스 종료를 확인하지 못하면 새 로그인을 시작하지 않습니다.

예전 봇 실행 이미지에는 안전한 재로그인 대기 기능이 없습니다. 이번 broker/portal/runtime 업데이트 후 각 기존 봇의 **업데이트·다시 시작**을 한 번 실행해야 합니다. 기존 제한을 유지하려면 제한 변경 옵션을 선택하지 마세요. 최신 실행 버전 적용 전 재로그인은 차단하고 업데이트 안내를 표시합니다. 프로젝트나 봇을 삭제할 필요가 없습니다.

`실행 중`은 서버 프로세스 상태이며 구독 인증과 잔여 사용량을 보증하지 않습니다. 오류가 분류되지 않으면 기존 Buzz 오류와 Harness Log를 확인하세요.

## English

Recognized authentication failures keep the original Buzz notice and append directions to Docker Manager → your buzz-agents project → **Open** → **Re-login** for the affected bot. Usage/rate-limit failures append a reminder to check your AI plan’s usage and reset time. Re-login does not reset usage limits. Official Buzz retry counts and delays are unchanged.

1. Sign in to the setup portal and select **Re-login** on the affected bot, including a running bot.
2. Confirm interruption of that bot’s active work. Other bots, identity, role, model, credential home, work files and resource limits are retained.
3. Follow the official Claude/Codex login link and instructions.
4. Successful CLI login plus verified process cleanup releases the hold and automatically starts the same bot. Resend the interrupted request in Buzz and verify a real reply. Work is not automatically resent.

Failure, cancellation or expiry keeps the bot waiting. Select **Re-login** to retry. Refreshing restores an active login without launching another one. If the management service restarted and lost its session, retry reauthentication. Unverified cleanup blocks a new login.

Update broker, portal and runtime images, then use **Update / restart** once on each existing bot; leave the optional limit changes unchecked to preserve them. Legacy runtimes cannot provide the durable reauthentication hold and are refused with an update hint. Do not delete the project or bots.

`Running` describes the server process, not valid subscription authentication or available quota. Unclassified failures retain the original Buzz error; check Harness Log.

## Implementation boundary and validation

The runtime compiles `buzz-acp` from official commit `4db7bb0e7f904b2f0ea232aacae6cd7f6b8a3b39`, applying `patches/apply.py` to the exact SHA256-verified source. The only upstream behavior change is appended failure-notice guidance; queue/auth classification/retry/dispatch remain unchanged. All other sprig tools retain the pinned official binary. Rust toolchain/base and source archive are digest-pinned in Dockerfile; the original Buzz license remains included. This is a buzz-agents addition, not a Hostinger or Buzz built-in feature.

Lifecycle state is persisted separately from bot configuration. `reauth-hold.json` prevents startup even with an old successful-login marker. Deploy/update/retire cannot bypass this hold. The global deploy lock spans stop, container identity/state readback and login completion. The portal endpoint requires a same-origin administrator session; device credentials do not grant lifecycle operations or access to login sessions. No auth transcript, token or credential is added to diagnostic logs. The original official notice is retained unchanged before the suffix.

Focused unit tests cover lifecycle refusals, data retention, both providers, restart holds, idempotency, child cleanup and cancellation. Browser fixtures cover Korean/English, running bots, confirmation, refresh, retry and success. The real Docker CI test uses explicitly synthetic CLI/AI programs to verify process lifecycle without real accounts or external Relay access. Real subscription login and a subsequent model reply remain user acceptance checks.
