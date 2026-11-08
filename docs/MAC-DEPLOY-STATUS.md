# Mac connection deployment status — 2026-11-08

## Current result (supersedes the historical preparation notes below)

The user repeated the production request after the native GUI limitation was
reported. Production management images and the public manual are now deployed.
Mac is explicitly trial support for Apple Silicon; Finder/Gatekeeper and the
actual Mac Buzz-to-VPS end-to-end journey remain unverified. Intel Mac is not
provided. Do not describe the GUI journey as passed.

- Release source: `31aed4aaae2f38d11552232e9e150f3f0944694e`.
- Passed CI: https://github.com/volition79/buzz-agents/actions/runs/42473193845
  (package, Apple Silicon native tests, real old/new management update and
  rollback, candidate anonymous pull, management-only stable publication).
- Release: `mac-connect-31aed4aaae2f-42473193845`; its `rollback.json` records
  immutable previous/current broker and portal digests. Runtime stays exactly
  `sha256:0f50d422ba8992cd23461a4901c73d52580a6801ea2e50177fd1f0d95465871b`.
- Actual Hostinger `buzz-agents` broker and portal updated with existing compose
  and volumes, using `up -d --no-deps broker portal`. No bot update was invoked.
  All three AI container IDs, images and start times remained identical.
  Account/device JSON hashes remained identical. The pre-existing Windows
  credential passed live `/api/device/check` with HTTP 200 and `ok:true`.
- Expected adjacent behavior: the existing swap manager replaces its owned
  helper when the broker image changes (`swap_manager.reconcile` image comparison).
  The initial blanket assertion that *every* non-management container would stay
  identical therefore failed. Direct source/current-state comparison identified
  only `buzz-agents-swap-v1` as changed; bots, route, Relay and other services
  remained identical. Active swap was verified. No source assertion was weakened.
- Live portal contains both Windows and macOS-arm64 executables; memory-only
  dummy-data ZIP inspection verified Mac launcher and Unix executable modes.
  An initial probe used the wrong `/app/connect/assets` path; Dockerfile confirms
  `/artifacts`, and the corrected probe passed. No real pairing grant was created.
- Public https://zooo.kr/buzz-manual/#chapter-5 now shows Windows(Mac) 연결,
  separate OS steps, Mac trial limitation and existing-user update instructions.
  Live Chrome verified all 12 chapters, navigation, progress persistence, desktop
  width and no JS errors. Existing noindex metadata and file ACL/owner/mode were
  preserved; no site menus were linked. The install URL remains unchanged.
- Private backups exist on each server outside the web root. No credentials are
  committed. The pre-existing local manual ZIP was not republished by this task.

### Final scope and rationale reconciliation

`MAC-MANAGEMENT-RELEASE-01` covers the workflow/rollback helper changes; its
historical planned status is retained, with the actual CI result above as the
current evidence. `MAC-CONNECT-HISTORY-01` covers the provider catalog addition.
Documentation changes report verified state, rather than introducing runtime
behavior. Manual changes preserve chapter IDs/progress keys, installation URL,
Windows path and security-stop instructions; screenshots remain Windows-labeled.
Management deployment preserves the bot runtime and persistent data. The swap
helper replacement is reviewed existing behavior, not a new bot migration.
Selected policy mode is search-check: no full policy-pack certification is
claimed. Existing source/fixture results are not relabeled as native GUI proof.

## Historical preparation record

The user authorized production deployment and zooo.kr manual chapter 05 changes,
with Windows/bot preservation and native Mac acceptance retained as prerequisites.
This document does not claim production deployment.

## This request's actual delta

- `.dockerignore` / Docker context: MAC-CONNECT-DOCKER-CONTEXT-01. The previous
  allowlist excluded `connect/assets/macos` even though build-portal put it in the
  archive. Reinclude only that directory, preserving other exclusions. Actual
  container inspection is required; archive membership alone is insufficient.
- `.github/workflows/mac-connection-check.yml`: isolated candidate verification.
  GitHub contents are read-only; no image push, stable promotion, host mounts or
  production access. Inspect actual built portal bytes and broker contract while
  retaining the public stable broker's runtime digest. This does not prove live
  lifecycle/rollback, Finder security or native Buzz behavior.
- Local manual `index.html`: chapter 05 and its menu become Windows(Mac) 연결;
  distinguish Windows EXE and Apple Silicon command launcher, one-use expiry,
  security stops, existing Windows preservation and no unnecessary bot updates.
  Screenshots remain explicitly identified as Windows examples. Installation URL,
  12 chapter IDs and existing local progress keys remain unchanged. No site menu
  link or public publication has occurred.

## Observations

- GitHub main remains baseline `8de6b0e`; public releases are prereleases, so a
  releases/latest 404 is not proof of missing assets.
- Live manual fetched successfully. Before editing, its text matched the local
  manual; HTML differed only by non-content formatting/metadata.
- Local Chrome chapter navigation, persistence, title, Mac content and no
  horizontal overflow passed. Screenshot inspected at 1920x1080.
- Windows Docker CLI exists, but neither desktop-linux nor default daemon is
  reachable. `docker desktop start` reports already running. No reset/restart or
  deletion was performed. Candidate Docker verification is assigned to CI.
- A Mac availability question is pending. Native download/extraction/Gatekeeper,
  official Buzz discovery, VPS deployment/reply and mobile continuation remain
  unverified. Do not publish Mac as a supported working path before acceptance.

## Production boundary

Do not run the old `portal-images.yml` for this connector-only update: it rebuilds
runtime and promotes stable. Keep the exact approved runtime digest and use
`management_only=true`. Real update/rollback acceptance must precede stable
promotion. Then verify candidate downloads and Windows compatibility before
publishing the prepared manual. Retain remote backups and current digests.

## Verified follow-up

- Candidate source branch: `mac-connect-review-20261108`, CI commit `a209fd4`.
  Main and stable were not updated. CI run:
  https://github.com/volition79/buzz-agents/actions/runs/42472261491
- Linux package job passed 63 Python tests, Go tests, actual Docker portal byte
  inspection and real broker management-only contract with unchanged runtime.
- Apple Silicon `macos-15` job passed native connector/provider tests and vet.
  These use temporary fixtures, not a downloaded Finder-launched Buzz connection.
- Earlier CI run 42472156414 failed because ownership-changing lifecycle fixtures
  ran unprivileged. The corrected run uses the same sudo environment convention
  as the existing release workflow; application protection was not weakened.
- Public provider history was retrieved through authenticated GitHub CLI after
  direct downloads returned HTTP 504. All 23 manifest records and 10 distinct
  binaries were hash/size checked. Missing tag e0b542dc9d9f-59-2 reuses an already
  approved executable hash; only its catalog entry was added locally.
- Current remaining blockers: native downloaded ZIP/Finder/Gatekeeper and actual
  Buzz/VPS journey; management update/rollback acceptance. Public Mac support and
  zooo.kr publication remain pending. Local chapter 05 is ready for review.
