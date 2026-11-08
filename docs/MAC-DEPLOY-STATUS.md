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
