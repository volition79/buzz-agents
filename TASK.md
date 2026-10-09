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

AUTO-01..04 public artifact verification: CI37901354005 passed for a3843e798c28ab5c78eb7418de697d0790d45ae4; immutable Raw URL https://raw.githubusercontent.com/volition79/buzz-agents/a3843e798c28ab5c78eb7418de697d0790d45ae4/docker-compose.yml. No-domain-env startup and route reuse verified against published images; fixture DNS only. Main promotion contains the same verified artifact bytes. Live Hostinger import/TLS and original Windows-off AI goal remain open.

NETWORK-01 (2026-10-09): confirmed live screenshot has no traefik-proxy and no agents containers. New reason: start portal on Compose default network, discover unique running Traefik and Relay router network/TLS labels. Attach only own portal, never alter existing services. Author Linux/WSL; target Hostinger Ubuntu Docker, host-mode or shared-network Traefik. Ambiguous/custom unsupported cases fail closed with reason; no selection UI claimed. Existing AUTO hostname, DNS, ownership and auth invariants retained. Tests must cover absent external network, renamed networks and TLS names, host-mode proxy, missing/ambiguous selection, own-only network mutation. Public images must be rebuilt before promoting root install artifact; actual TLS/Hostinger/Windows-off remain open.

NETWORK-01 review: proxy container ID remains a current-discovery ambiguity key, excluded from durable routing fingerprint so harmless Traefik recreation does not prevent portal restart. Added same-settings proxy-recreation regression.

NETWORK-01 candidate CI37906214523 passed source9d6683aea6756fc559267805361927cc6ff656a9: 121 Python tests, Go race/vet, three image builds, actual Traefik HTTPS bridge and host-network fixtures, unchanged existing Relay/proxy IDs/config/networks, restart reuse, anonymous image pulls. Synthetic DNS and untrusted fixture certificate are explicit; no real ACME/Hostinger or AI acceptance. Sole reviewer found no further blocker. Promote digest-pinned root file then verify exact public Raw bytes and both network fixtures.

NETWORK-01 completion: exact public Raw artifact ee2ab42595318ad9e4b8c0bc46454573165c1ec3 passed CI37906666736 including anonymous pulls and both actual Traefik network-mode fixtures. Independent readback SHA256 0f99971770d71f9bea9c86772da2496d72b22551773284b18c86e1de9cc18956; all three anonymous manifest digests verified. Sole subagent audit complete, no further source blocker. Live VPS unchanged. Actual hPanel URL import, public trusted TLS and Windows-off AI task are outstanding acceptance conditions, not claimed complete.

OPEN-01 (2026-10-09): user-provided live hPanel response has entrypoint_url=null and excludes the raw setup helper; existing trusted HTTPS setup works. Approved scope retained (CodeMap off, focused tests, validator off, one read-only auditor). Author WSL; target Hostinger /docker/<project>/docker-compose.yml with existing Relay/Traefik. Register setup-route through actual Compose, use project-named Traefik router, preserve URL and portal/runtime digests. Broker receives only its own project-directory bind; reject foreign paths/symlinks/multiple config files. Preserve variable expressions with non-interpolating Compose parse and compare resolved preexisting configuration before any write; atomic compare-before-write/rollback. Validate legacy route before rename/replacement, restore it on failure, never change Relay/Traefik or existing volumes. Saved-plan startup reconciliation handles broker-only upgrades. Tests cover preservation, ownership, migration/rollback, genuine Compose visibility and both actual Traefik fixtures. Actual hPanel entrypoint_url and Open click remain required live acceptance; no internal Hostinger algorithm claimed known.

OPEN-01 candidate verification: CI37912336094 passed image source a1f82117471dfbdf6d9ff0d5d413f13900da5c83, 134 Python tests and existing Go race/vet gates. Genuine Compose ps/down, unchanged portal ID on broker-only legacy migration, dollar-variable preservation, retained portal/runtime digests, actual Traefik HTTPS with shared and host networks all passed. Sole auditor's rollback findings fixed and regression-tested; final review found no blocker. Published broker digest 56d45e699381baf6e79bc16934d24f64713be6b6e6a3bf21fef52f7a82df73c8. Install template additionally rejects an absent built-in COMPOSE_PROJECT_NAME rather than mounting all /docker. Exact public Raw installation smoke follows. Real hPanel Open and Windows-off acceptance remain open.


OPEN-01 public artifact ec2d9b08df3bb7e7d383eff9fa9ac3002bde4b06 passed exact Raw URL CI37912789643: anonymous image pulls, byte/renderer parity, zero-domain-env install, Compose-managed route lifecycle, HTTPS through shared and host-mode Traefik. Anonymous readback SHA256 17896cf3c0bc9a0f766f59257f9eeabefa702d06162adf3d6abece0021545f44; all three manifests hash-matched. Evidence: /tmp/buzz-open-final-ci.log, /tmp/buzz-open-public-readback.json, GitHub CI37912336094 and CI37912789643. No live VPS mutation performed. Actual hPanel entrypoint_url/Open click remains pending user application; optional question about existing-project URL import UI is pending. Original Windows-off AI goal remains unproven.

RECOVERY-01 (2026-10-09), approved implementation plan: CodeMap off, focused Sonol Test direct fallback, validator off. Author WSL/Linux; targets Windows amd64 helper and Linux Docker portal. Existing OPEN/AUTO transport, origin, membership and own-project isolation invariants remain applicable. New reasons: fragment-only setup autofill without public secret issuance; local portal control socket issues expiring recovery codes without resetting persistent bots/devices; atomic Windows reconnect preserves the old connection until commit, with explicit user selection and cleanup of orphaned pairing. Screens, ZIP instructions and documentation must agree on restart/expiry/recovery behavior. Tests cover real HTTP and Unix socket boundaries, concurrent/replayed recovery, real browser fragment/no-value/recovery flows, Go TLS reconnect/save-failure and native Windows smoke where available. No claim that hPanel supplies a token, no invented platform labels, no VPS deployment. Existing untracked files are not task changes.

RECOVERY-02 upgrade compatibility: source inspection found old bootstrap fingerprints include the portal image ID. To deliver UI/auth updates without removing existing data, retain only the exact verified existing Compose proxy when every non-image plan field matches and its complete security/ownership checks pass. Do not silently replace proxy images. HTTP/browser/native Windows tests have passed; four Docker fixture paths (new/shared, new/host, legacy broker, portal upgrade with persisted account/devices) are required before publishing the new install Compose.

RECOVERY-03 packaging compatibility: native binary inspection/build review found Go VCS metadata changes web-provider bytes despite unchanged source, triggering the existing unknown-binary guard. Exact prior public manifest SHA256s (8ae5df6d57c1,3518e79bc21a,9d6683aea675,a404be735bc9,a1f82117471d) with unchanged web-provider source are now accepted for reuse without overwriting them. Unknown/modified binaries still fail before pairing. Future portal builds use buildvcs=false with trimpath. Regression covers recognized binary retention and modified-byte refusal.

RECOVERY completion: source b54f2212b70a55aeca8d9a2fd8778b88dc3e6745 passed CI37929657380 (Python142, Go race/vet, four real Docker fixtures including retained accounts/devices/proxy on upgrade, anonymous image access). Native Windows connect tests9 and Chrome desktop/mobile interaction fixtures passed locally. Candidate portal-candidate-b54f2212b70a-15-1 public EXE equals local reproducible bytes, SHA256 d14af7ecf93a27a3d05fd2f89f09be08c957f6fb10422b602a8c2aec24a55c28. Canonical immutable install 01d385829515df2870af5d6925e53c22a6d81183 passed exact-URL CI37930186525; anonymous Raw readback SHA256 d31442d6109392b534a5fe1f000cca33980c4ab687c3a187fc24c83a0a0077a2. Root Compose promotion retains runtime and changes only broker/portal image digests. User VPS not changed. Actual Hostinger secret-URL delivery, Windows Buzz/official AI acceptance and Windows-off fresh-task goal remain unverified. New local APIs are /api/recover, /api/device/check and self-only /api/device/revoke-self; issuance is local Unix socket only. Existing source guards and prior untracked files remain preserved.

I18N-01 (2026-10-09): browser primary language selects Korean or English (other languages fall back to English). 132 catalog entries cover marked static text, attributes, errors and dynamic state; user names/provider output remain untouched. New static asset uses the existing same-origin security headers. Restart guidance uses buzz-agents project menu, not initial-setup terminal commands. Focused source checks passed: portal unittest25; existing real-Chrome flow; i18n Chrome ko-KR/en-US/en-GB/fr-FR with secondary Korean, recovery, dynamic text and desktop/mobile. Existing scope: CodeMap off, direct focused test fallback, validator off. User now authorizes publication/deployment for testing; do not reset data or alter Relay/Traefik. Full publication CI and exact Raw smoke still required before release handoff.

I18N-01 deployment clarification: user will install on VPS. Assistant scope is publication of reviewed GHCR images and immutable Raw Compose URL only. No hPanel configuration or VPS restart was performed.

I18N-01 publication: source4dda974a8239b2c21b1b7fd1c3c5ef7ebb4c81a2; candidate CI37933477258 passed all tests, four actual-Docker startup/upgrade fixtures, GHCR publication and anonymous access. Release portal-candidate-4dda974a8239-17-1 build-context SHA25686511399b53501523b4458d8d0e2420c618afdad944e19ea4fd0d6fe63ca7cf9 matches published manifest and all changed application sources. Promotion changes only broker/portal image digests; runtime unchanged. Exact Raw check pending. No VPS mutation.

I18N-01 complete: exact public Raw CI37933975910 passed anonymous downloads and both actual-Traefik network modes. Immutable install89f7ff848cbb250086a5e57146e174fcb89b073c; Compose SHA25613e2d270b7d1897894ef6619c7ce4ae4f7a9b5461daccdfc253a70729454c3b8. Local browser results and publication record: .sonol-test/runtime/portal-i18n/. Candidate CI passed142 Python tests and scoped Go race/vet. User performs installation; VPS unchanged.
