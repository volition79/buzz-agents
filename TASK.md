# Easy native Buzz installation (v0.3 candidate)

## Current task: Docker portal (v0.4 candidate)

User approved the Docker + first-run setup portal direction and local development.
Root SSH/password bootstrap is superseded for new users; retain the v0.3 sources and artifacts.
Route retained: CodeMap off, Sonol Test focused, Policy Validator off (no pack).
No credentials from chat are copied to files, code, fixtures, logs, or artifacts.
Publication approved in the subsequent user turn: create public `volition79/buzz-agents`,
build/test/publish runtime/broker/portal GHCR images, and create the installation Compose URL.
No live VPS mutation, third-party AI account login, or Relay replacement is included.
Retain CodeMap off / focused Sonol Test / Policy Validator off. Scope binding and publication
receipts are private runtime files outside the source archive. New reason PORTAL-PUBLISH:
publish only the reviewed explicit source list; fix demonstrated CI/build blockers, verify
anonymous artifact/image access and digest readback, preserve remaining KVM2 acceptance gaps.

Authoring: Linux/WSL; Windows x64 helper cross-build and available native smoke.
Targets: Windows Buzz backend v1; Ubuntu Docker VPS, existing Traefik HTTPS and Buzz Relay.
New boundary reasons before edits:
- PORTAL-01 web portal: first claim protected by a random Docker-log setup code; administrator password hashes and scoped, revocable device credentials; HTTPS + origin/CSRF checks. No root password field.
- PORTAL-02 broker: network-disabled Docker controller, fixed operations over a private Unix socket. Only broker has Docker socket and host state binds. This remains host-equivalent authority inside broker; web/AI containers never get the socket. Preserve existing per-bot UID, resources, ownership labels, quota and stopped/held behavior.
- PORTAL-03 browser login: bounded PTY sessions run the official login in the selected bot, credentials stay there. Authentication needs a bot created in Buzz first. No custom OAuth token implementation, no transcript persisted or returned to unpaired devices.
- PORTAL-04 Windows: HTTPS provider installed under a distinct name; short-lived one-use pairing bundle, protected local credential file, strict TLS and redirect refusal. No SSH required; preserve old connection files.
- PORTAL-05 Compose/build: separate image roles, existing traefik-proxy network, no ports 80/443 conflict. Build local distribution first; no invented published image or Compose URL.
- PORTAL-06 tests/docs: actual HTTP contract, failed auth/CSRF/replay/permission boundaries, PTY lifecycle and restart, Windows protocol and artifact checks. Local fixtures are not real provider authentication or Windows-off acceptance.

Open release obligations: actual Linux Docker image build/start, published immutable images/Compose,
native Buzz provider discovery, official Codex/Claude login, two AI collaborators,
fresh task begins/completes after Windows is fully off, KVM2 resource observation.

Local v0.4 result (2026-10-09): portal, network-disabled broker, bounded/cancellable official-login PTY,
HTTPS Windows provider and one-use pairing installer, Compose, source/build packages implemented.
107 Python tests (105 suite + 2 release-render tests) and 26 Go tests pass; all Go vet and JS syntax pass.
Real Chrome first-claim/discovery/download/pair/bot/login-UI flows pass with explicitly simulated Docker
and official-login responses. Native Windows provider info passes; no actual account authentication used.
Compose 2.40.3 schema validation passes, no local Docker daemon available for image/start verification.
Manual-only GitHub workflow prepared to build/test images and anonymous-pull-check before issuing a
digest-pinned release Compose. It has not run. Publication payload: dist/portal-v0.4/public-source.zip.
Current GitHub session was read-only checked; no repository, package, release, or external setting changed.
Legacy rationale below applies to retained SSH path only.

Approved: local implementation and tests. No website manager. Preserve original ZIP and existing Relay. No public publishing, actual VPS access, subscription login or deployment performed by the development agent.

Authoring: Linux container, Go/Python/Node available, no Docker daemon or Windows runtime.
Targets: Windows x64 with OpenSSH client; Ubuntu Linux x64 VPS with Docker Compose and existing private Buzz Relay.
Route: CodeMap off; Sonol Test focused; Policy Validator off (no policy pack).

New decisions before changes:
- EASY-01 setup/*: standalone console wizard automates archive transfer, server bootstrap and native provider installation. SSH verifies host keys; never accept an unknown key automatically. Root SSH is needed only for bootstrap. Do not read local AI credential stores.
- EASY-02 buzz_agents/bootstrap.py, bridge.py: restricted SSH key for deploy/status/login operations. Validate remote operations before root Docker access; no general shell, path or arbitrary container exec. Existing Relay untouched. Repeated same-source bootstrap idempotent; different source refused pending explicit upgrade design.
- EASY-03 native/auth state: credentials remain in each bot's persistent VPS home. Authentication is after native Buzz bot creation. A successful login exit is not actual model health. Preserve stopped/held policy.
- EASY-04 tests/*, setup/*_test.go: preserve baseline tests; add negative transport/bootstrap cases and wizard protocol tests. Linux tests and Windows cross-build do not prove native Windows or VPS behavior.
- EASY-05 docs and packaging: ship reproducible local candidate, checksums and Korean walkthrough. No fake public installation URL. Publication and real KVM 2 Windows-off acceptance remain explicit obligations.

Implementation scope: preserve native Buzz UI and per-bot identity. Default shared workspace team for easy provider. Scheduling remains on VPS and requires explicit Relay/channel membership and allowlist; do not claim scheduling is automatic merely from relay installation.

Completion acceptance: fresh Windows setup; official logins and real replies; two bots collaborate on one file; Windows fully off before a fresh scheduled task begins and completes; KVM 2 resource measurement. These require real environment access.

Local implementation result:
- Windows console helper, embedded bootstrap/source archive, dedicated provider config, restricted remote auth/status and daily scheduler implemented.
- Final focused run: Python 86 + provider Go 9 + setup Go 7 = 102 passed; vet/syntax/PE/archive integrity passed. See docs/EASY-VERIFICATION.md.
- No policy pack was created. Automated plan/verify depends on an absent policy registry, so direct command evidence is retained without a managed receipt.
- Final reviewed boundaries: bootstrap, bridge, schedule, auth lock, provider config/default, Windows helper, packaging/lockfile, tests and user docs. Existing native/guard/quota behavior retained. No CodeMap capture because approved route is off; no invented rationale records.
- Existing ZIP and external Relay untouched. Local candidate is complete enough for live pilot; the project acceptance objective remains unproven until Windows/VPS trials.
- User-facing simplification: the single Windows helper performs server installation too. No unpublished Compose URL is promised. Initial SSH trust verification and Buzz membership/allowlist remain explicit.


Publication result, 2026-10-09: public repository volition79/buzz-agents created. Source 8ae5df6d57c1c8a999bcebe3cd0b3517ef27f09a; CI run 37896228009 succeeded including image builds, isolated Compose role-boundary smoke and anonymous access. Candidate release portal-candidate-8ae5df6d57c1-1-1 published. Independent anonymous asset/manifest hash readback passed. This supersedes earlier pre-publication snapshots above; actual VPS deployment, authentication and Windows-off acceptance remain open.


URL import correction (2026-10-09), baseline 33161cd177066040304fd8fd98fa4bd3de09a9a0.
Approved existing scope retained; one user-requested read-only reviewer. No live VPS changes.
URL-01 Compose/renderer: remove hardcoded project name; use official COMPOSE_PROJECT_NAME/TRAEFIK_HOST routing, no proprietary required hostname. Missing platform hostname remains explicit failure, never insecure fallback. Target Hostinger Linux Docker; built-in variable injection on URL imports remains unproven.
URL-02 root docker-compose.yml: publish digest-pinned complete config as raw GitHub source, preserve runtime image digests and security roles.
URL-03 workflow/regression: fetch exact published Raw bytes, validate missing-env failure and supplied Hostinger-env resolution, pull/start exact remote artifact in disposable CI; this is not Hostinger importer evidence.
URL-04 docs/build: replace failed release-asset install guidance with Raw URL and acceptance boundaries; include canonical install source in packages.
Focused manual test fallback remains due absent project policy registry. No changes to AI/auth implementations or legacy SSH path.

URL-01..04 verification: three release regressions passed; independent reviewer accepted source with explicit live gap. CI 37898496077 passed public Raw byte parity, platform-env negative/rename checks, anonymous image pulls, exact Compose runtime/portal HTTP/broker RPC. Canonical artifact SHA256 5cb2294cb946e14214cd4e660a1bd94018e42128beb04975ec67976bceaf650d. Only config/source/docs/verification changed; runtime images reused. Real Hostinger importer and TLS remain unproven.


Automatic bootstrap extension (2026-10-09). Explicit user request adds no-env first install; existing local/publication/CI scope retained. No live VPS mutation.
AUTO-01 startup: portal waits for fixed broker discovery, verifies candidate DNS against an existing Relay, binds activation to a plan fingerprint. Never weakens HTTPS/origin/auth or uses supplied nsec/root credentials. Unknown/custom/ambiguous bases wait with a safe reason.
AUTO-02 broker: inspect own Docker identity/project and one own portal; derive a unique setup hostname only under discovered Hostinger srvNN.hstgr.cloud; create only an owned routing helper using exact own portal image ID, fixed command/network/limits, no mounts/socket. Preserve all existing Relay/Traefik containers. Plan and existing helper identity fences prevent overwrite.
AUTO-03 route: bounded HTTP proxy preserves exact Host and forwards to the fixed own portal container, never a caller-specified target; caps request/response/concurrency; no raw request logs.
AUTO-04 Compose/CI/docs: no domain variables before startup. Test absent discovery, DNS mismatch, ownership collision, plan drift and restart; real Docker fixture lifecycle before publication and anonymous exact-artifact smoke afterward. Platform fixture is not real Hostinger acceptance. Existing public Compose remains old verified candidate until new image validation/promotion.

Independent review found and fixed AUTO-03 upstream timeout mismatch (now250s vs existing245s RPC) and AUTO-02 existing route DNS overrides (ExtraHosts/Dns/DnsSearch/DnsOptions/Links refused). Regression assertions added.

AUTO-01..04 build verification passed in CI37901027761, source3518e79bc21afeb668edafc84ffd2baaff07be6e. No hostname env was injected; artificial Relay metadata and hosts-file DNS were fixtures. Dynamic route/startup/restart identity and unchanged Relay verified. Promoting newly published image digests only after exact Raw smoke.
