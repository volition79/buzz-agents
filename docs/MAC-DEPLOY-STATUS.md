# Mac connection deployment preparation — 2026-11-08

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
