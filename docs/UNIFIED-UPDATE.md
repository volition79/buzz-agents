# Unified update candidate / 통합 업데이트 후보

Verified release: [portal-candidate-d798dd4a17b5-51-1](https://github.com/volition79/buzz-agents/releases/tag/portal-candidate-d798dd4a17b5-51-1).
[CI verification](https://github.com/volition79/buzz-agents/actions/runs/38107825503)
passed Python292, browser flows, actual Docker bootstrap, legacy upgrade,
contract broker configuration, stopped-state preservation and reauthentication.
The stable management tags were promoted only after those gates passed.
Anonymous release assets and stable tag digests were independently checked.
Live Hostinger and real AI subscription acceptance remain user tests.

기존 설치는 [한 번만 전환하는 방법](EXISTING-BOT-UPDATE.md)을 따르세요.
새 설치는 `compose.stable.yaml`을 사용합니다. 버전 고정용 `docker-compose.yml`도 유지합니다.

## Implemented boundaries

A broker built with `BUZZ_RELEASE`, `BUZZ_RELEASE_RUNTIME` and
`BUZZ_RELEASE_PORTAL` embeds a closed v1 release contract. Runtime and portal
references must be immutable images in this repository. Without a contract the
legacy explicit update route remains active. An old BUZZ_RUNTIME_IMAGE environment
value cannot override the embedded release.

The background coordinator checks the actual portal image, obtains the exact
runtime before stopping anything and persists per-bot progress. A physically
stopped bot can be replaced while remaining stopped. Running containers wait:
this pinned official Buzz version has an in-memory queue and startup-time replay
floor, so empty guard slots do not prove a lossless handoff. No drain capability
or automatic continuation is advertised. The user selected option 1 instead
of the previously proposed durable queue extension. Finish work and verify saved
results, select Shutdown for each VPS bot in Buzz and confirm stopped status on
the setup page before updating management, then explicitly apply the installed runtime
to each running bot through Update / restart. This interrupts any active work;
pending messages and active tasks are not guaranteed to resume. Check scheduled
tasks and coordinate with channel members before starting maintenance.
Stopped bots remain stopped. No automatic latest-release discovery is implemented:
the portal reports application of the release already installed on the server.
See [the operator instructions](EXISTING-BOT-UPDATE.md).

Administrator-only endpoints: `/api/release/status`, `/api/release/retry`.
Retries are durable requests, not automatic replays of uncertain mutations.
Existing device APIs cannot invoke these actions. Portal text is Korean/English.

An accidental v2 update retains pinned images and bind-mounted configuration,
auth homes and workspace files. Process memory and `/tmp` are not durable. An
unclean stop can leave a protective hold. An explicit Re-login now recovers stale
ordinary authentication metadata only after live locks and exact-container stop
are verified. Active authentication and unknown cleanup are never bypassed.

## Release and migration requirements

Prepare a candidate using `scripts/render-unified-release.py` with reviewed
immutable image references. Build the broker with the emitted BUILD-ARGS.json.
The generated Compose is for a new installation only. It does not include or
replace an existing route. Existing installs must keep the project name, volumes,
paths, network and full setup-route; switch the management images once to a
verified stable release. Embedded runtime selection supersedes the old environment
reference. The obsolete runtime-image preload service and its broker dependency
can be removed together after the contract-enabled broker is available.

Before publishing stable, run actual Docker lifecycle/route/recovery checks on
the contract-enabled broker, anonymous digest pulls, English/Korean browser flows,
and source/package parity. Promote portal then broker; a transient mixed pair
must defer mutations and leave existing bots intact. Keep rollback digests.
A publisher must serialize promotion; this candidate does not publish tags.

실제 Hostinger 업데이트 버튼, 유료 AI 응답, PC 종료 상태에서의 실행은 별도
수락 테스트입니다. 로컬 모의 테스트 성공을 실서버 확인으로 표시하지 않습니다.
