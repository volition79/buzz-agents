# 기존 봇 업데이트 / Update existing bots

## 한국어

Docker Manager에서 관리 서비스만 업데이트해도 이미 실행 중인 봇의 이미지는 바뀌지 않습니다. 또한 Windows Buzz의 `Deployed`는 배포 등록 상태이므로 Shutdown 후에도 남을 수 있습니다. 그 상태에서 봇을 삭제하거나 새로 만들 필요는 없습니다.

1. 기존 **buzz-agents → 관리 → Compose 편집**에서 검증된 새 릴리스의 네 참조만 갱신하고 배포합니다: `broker.image`, `broker.environment.BUZZ_RUNTIME_IMAGE`, `portal.image`, `runtime-image.image`.
2. 프로젝트 이름, 볼륨, 경로, 네트워크 및 기존 `setup-route` 전체를 유지합니다. 새 프로젝트나 신규 설치 URL로 대체하지 않습니다.
3. **열기**로 기존 설정 비밀번호를 사용해 로그인합니다. **봇 계정 로그인** 단계에서 기존 봇을 찾고 **업데이트·다시 시작**을 누릅니다.
4. 이름과 현재 제한을 확인합니다. 기본적으로 기존 제한을 보존합니다. 과거 횟수 제한을 없애려면 명시적으로 **횟수 제한 해제·작업당 최대 2시간 적용**을 선택합니다. 기존 유휴 시간 제한과 동시 실행 수는 유지됩니다.
5. 실행을 확인하면 선택한 봇의 현재 작업이 중단되고, 저장된 설정으로 새 runtime 컨테이너를 만듭니다. 완료가 표시될 때까지 기다립니다. 다른 봇은 하나씩 같은 과정을 진행합니다.
6. 로그인 상태와 실제 응답을 확인합니다. 필요한 경우 해당 봇 계정만 다시 로그인합니다. 중단된 작업이 자동으로 이어진다고 보장하지 않으므로, 상태를 확인한 후 Buzz에서 이어 할 일을 지시합니다.

보존 대상은 VPS에 **마지막으로 배포된** 봇의 신원, 역할, 모델, 로그인 파일, 작업 파일, 사용량 기록입니다. Windows에서만 편집하고 배포하지 않은 내용은 반영하지 않습니다. 로그인 파일 보존은 제공사의 토큰 유효성을 보장하지 않습니다. 완료 표시는 Docker 이미지·소유권·프로세스 제한 확인이며 실제 AI 응답의 증명은 아닙니다.

진행 중 페이지를 새로고침해도 진행 상태를 다시 표시하고 작업을 자동 재시도하지 않습니다. 요청 응답을 받지 못하면 창을 닫고 상태를 먼저 확인하세요. 관리 서비스 재시작으로 결과가 불명확하면 **완료 여부 확인 필요**로 표시합니다. 실제 봇 상태를 확인한 뒤 새 확인창에서 다시 시도할 수 있습니다. 오류로 파일을 삭제하거나 봇을 새로 만들지 않습니다. 인증 중이면 인증을 끝내거나 취소한 뒤 시도하세요. 오래된 인증 표시가 남으면 관리자 진단이 필요할 수 있습니다.

이 기능은 설정 화면 관리자 로그인에만 허용됩니다. Windows 연결기의 일반 배포 권한은 실행 중인 봇의 교체를 허용하지 않습니다.

## English

Updating the management project alone does not replace existing bot containers. Buzz's `Deployed` describes its deployment registration, which may remain after Shutdown. Keep the existing bot identity.

1. Edit the existing **buzz-agents** Compose project. Replace only four references from a verified release: `broker.image`, `broker.environment.BUZZ_RUNTIME_IMAGE`, `portal.image`, and `runtime-image.image`.
2. Preserve the project name, volumes, paths, networks and the entire existing `setup-route`. Do not create a replacement project.
3. Click **Open**, sign in with the existing setup password, then find the bot under **Bot account sign-in** and click **Update / restart**.
4. Review the bot and its limits. Existing limits are kept unless you explicitly select removal of prompt-count limits with a two-hour maximum turn duration. Idle timeout and parallelism are preserved.
5. Confirm interruption of that bot's current work. Wait for completion, then update other bots individually.
6. Check login status and a real reply. Resume interrupted work with a new instruction after checking its state; automatic continuation is not guaranteed.

The action keeps the configuration last deployed to the VPS, including identity, role, model, account files, work files and quota history. Unpublished Windows edits are not included. Retained credentials can still expire. Success verifies the Docker image, ownership and PID limit, not an actual provider reply.

Reloading the page reads the existing job; it never resubmits an update automatically. After a missing response, close the dialog and check status. A management restart during the operation reports an uncertain outcome. Check the bot before starting another explicit attempt. Failures do not delete account/work files. Finish or cancel active login first; stale login markers may require administrator diagnosis.

Only the signed-in setup administrator can use this action. The Windows device deployment API retains its existing live-replacement restrictions.

## Evidence and limits

Pinned official Buzz source `326e2301cb4b1edcb8a72d01ac4b19a83545365f`:
- `desktop/src-tauri/src/managed_agents/runtime.rs`: provider registration can retain deployed status after presence goes offline.
- `provider_deploy.rs`: deployment protocol does not expose an undeploy acknowledgement.
- `AgentRuntimeAvatarControl.tsx`: deployment bookkeeping affects available start controls.

This explains the observed UI route; it does not identify the user's installed binary. Local tests cover both provider configurations, failures, concurrency, administrator authorization and real Korean/English browser controls. CI also exercises real Docker replacement for Claude and Codex with synthetic credentials and no paid inference. Live subscription login, actual replies and Windows-off work remain user acceptance checks.
