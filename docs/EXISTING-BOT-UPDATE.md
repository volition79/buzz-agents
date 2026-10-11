# 기존 봇 업데이트 / Update existing bots

## 이번 배포로 전환 / Enable button-based updates

검증된 배포: [portal-candidate-396648e39341-49-1](https://github.com/volition79/buzz-agents/releases/tag/portal-candidate-396648e39341-49-1).
[실제 Docker 검증](https://github.com/volition79/buzz-agents/actions/runs/38105165263).

**처음 한 번만**, 작업을 마친 후 기존 **buzz-agents → 관리 → Compose 편집**에서 다음 두 값만 바꾸고 배포하세요.

| 항목 / Field | 값 / Value |
|---|---|
| `services.broker.image` | `ghcr.io/volition79/buzz-agents-broker:stable` |
| `services.portal.image` | `ghcr.io/volition79/buzz-agents-portal:stable` |

프로젝트 이름·볼륨·경로·네트워크·기존 `setup-route`와 나머지 값은 유지합니다.
기존 `BUZZ_RUNTIME_IMAGE`와 `runtime-image` 항목이 남아 있어도 됩니다.
새 broker에 내장된 검증된 실행 버전이 우선하며 기존 봇은 별도로 적용합니다.
**이후에는 buzz-agents → ⋯ → 업데이트**를 사용합니다. 이어서 **열기**에서
필요한 봇별로 **업데이트·다시 시작**을 눌러 적용합니다. Windows 재연결은 필요하지 않습니다.
관리 서비스 버전이 다르다는 안내가 나오면 Docker Manager의 업데이트를 다시 실행하세요.
설정 화면의 적용 재시도만으로 관리 이미지가 교체되지는 않습니다.

**One-time migration:** finish work, edit the existing buzz-agents Compose, replace
only the two image values above, and deploy. Preserve the project name, volumes,
paths, networks, entire setup-route, and all other values. The old runtime preload
and environment reference may remain; the embedded broker contract selects the
reviewed runtime. For later releases, use **buzz-agents → ⋯ → Update**, then
**Open → Update / restart** for each bot needing the installed runtime. No Windows
re-pairing is needed. If management versions differ, run Docker Manager Update again;
the portal's application retry cannot replace management images.

New installations / 신규 설치: [Compose URL](https://raw.githubusercontent.com/volition79/buzz-agents/main/compose.stable.yaml).
This URL uses the verified management update channel; its image versions can change.
아래 digest 참조는 특정 버전을 고정하려는 경우에 사용합니다.
The digest references below are an alternative for installations that pin a release.

## 업데이트 전 주의 / Before updating

**진행 중인 작업과 대기 메시지는 자동 재개를 보장하지 않습니다.** 로그인 정보와
작업 파일 보존은 실행 중인 작업의 연속성을 의미하지 않습니다.

1. Buzz에서 작업 완료와 결과 저장을 확인합니다. 팀원에게 새 요청을 보내지 않도록
   알리고, 예약 작업이 업데이트 시간과 겹치지 않는지 확인합니다.
2. **통합 업데이트로 전환된 설치에 한해** Docker Manager → **buzz-agents → ⋯ → 업데이트**를
   사용합니다. 아래 검증된 릴리스처럼 이미지가 digest로 고정된 기존 설치는 버튼만으로
   새 릴리스로 바뀌지 않습니다. 해당 릴리스의 이미지 참조 변경 안내를 따르세요.
3. 완료 후 **열기** → 봇별 상태를 확인합니다. 실행 중인 봇은 자동 교체하지 않습니다.
   적용이 필요한 봇마다 **업데이트·다시 시작**을 한 번씩 누르고 완료를 기다립니다.
   작업 중이라면 버튼을 누르기 전에 마무리하세요. 중지 상태로 유지된 봇은 별도로 시작합니다.
4. 로그인 상태와 실제 답변을 확인한 뒤 작업을 재개합니다. 중단된 작업은 결과와
   파일을 확인한 후 필요한 부분만 다시 지시합니다.

프로젝트·봇을 삭제하거나 신규 설치로 대체하지 마세요. **buzz-agents-v2**는 별도로
업데이트할 필요가 없습니다. 오류가 나거나 완료 여부가 불분명하면 현재 상태부터 확인합니다.
설정 화면의 **업데이트 적용 재시도**는 실패한 적용을 다시 시도합니다. 중지된 봇에는 서버에 설치된 릴리스의 실행 버전을 적용할 수 있으며, 실행 중인 봇은 계속 사용자 확인을 기다립니다. 새 릴리스를 검색하는 버튼은 아닙니다.

통합 업데이트의 [동작과 검증 범위](UNIFIED-UPDATE.md)를 참고하세요.

**Pending messages and active work are not guaranteed to resume automatically.**
Retaining sign-in data and work files does not preserve an in-progress task.

1. Confirm completion and saved results in Buzz. Ask teammates to pause new requests
   and check that scheduled tasks will not overlap maintenance.
2. **Only after migration to unified updates**, use Docker Manager → **buzz-agents → ⋯ → Update**.
   Existing installations pinned to image digests, including the verified release
   below, need the documented image-reference changes to select a newer release.
3. Return through **Open** and check each bot. Running bots are not replaced automatically.
   Use **Update / restart** for each bot needing the installed runtime, one at a time.
   Finish its work first. Bots kept stopped need to be started separately.
4. Verify sign-in state and an actual reply before resuming work. Review results and
   files before requesting only the unfinished parts of an interrupted task.

Do not delete projects or bots, or replace them with a new installation.
**buzz-agents-v2** needs no separate update. After an error or uncertain completion,
check the current state first. **Retry update application** retries failed application of the installed release.
Stopped bots may receive its runtime; running bots still wait for explicit confirmation.
It does not discover newly published releases.

See [unified update behavior and verification limits](UNIFIED-UPDATE.md).

## Verified release references / 검증된 릴리스 참조

Release: `portal-candidate-396648e39341-49-1` · [CI verification](https://github.com/volition79/buzz-agents/actions/runs/38105165263).

In the **existing** project, replace only these values. 기존 프로젝트에서 아래 값만 변경하세요.

`broker.image`

```text
ghcr.io/volition79/buzz-agents-broker@sha256:3414b920a93c4763c3b8bf8b09ed2326edd5540cdd4ea682c102995daedc88b5
```

`broker.environment.BUZZ_RUNTIME_IMAGE and runtime-image.image`

```text
ghcr.io/volition79/buzz-agents-runtime@sha256:ea420bf321cf73b03aa9234df7a26fc56af22830b1c4778a03aa78fd16eef496
```

`portal.image`

```text
ghcr.io/volition79/buzz-agents-portal@sha256:f5dddde38b1e06c0f6f398a2e9625ce940870e5ea5873ece044d5898c9245c2a
```

## 버전을 고정하는 경우 / Digest-pinned alternative

아래 절차는 stable 채널 대신 특정 릴리스에 고정하려는 설치용입니다.
업데이트 버튼을 사용하려면 문서 맨 위의 두 이미지 전환 방법을 사용하세요.

The following procedure pins a specific release. For button-based updates, use
the two-image migration at the top of this document instead.

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
