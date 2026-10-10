Candidate publication passed: source 06c8484756087803e04792af157ab1ee8a7cc76a,
CI38052003782, tag portal-candidate-06c848475608-33-1. Seven public assets and
39 source files verified anonymously; both Windows binaries match local bytes.
242 Python tests pass in CI. Canonical Compose update changes only image digests;
no runtime source changes after that CI. Exact URL installation check follows.

## 2026-10-10 Publication approved

User requested publication of the completed guard recovery implementation.
Retain CodeMap scoped navigation, focused Sonol Test with project manual fallback,
and validator off (no pack). Build/publish runtime, broker, portal and Windows
HTTPS connector through existing manual GitHub workflow. Refresh predecessor
provider history from verified public release bytes. Include prior approved
mobile pairing source; exclude unrelated untracked files and local evidence/cache.
After candidate checks, review immutable image refs and publish canonical Compose;
verify anonymous downloads and exact-commit URL installation. No direct VPS writes.

## 2026-10-10 Runtime guard recovery (approved local implementation)

Verification outcome: whole Python suite 240 PASS before the final integrity
fallback; final focused suite 84 PASS/1 error exposed a retained file lock on
same-process supervisor reentry. Fixed with finally-close on held-state exit;
focused native/host rerun: 35 PASS. Both Go provider suites PASS.
The browser i18n scenario passed Korean/English/fallback and both viewports;
rerun after the last reason-to-message mapping. Added process fixtures exercise
both adapters with 105 healthy prompts, >4MiB frames, budget expiry and cleanup.
No registered Sonol Test lanes exist: manual command fallback and explicit
assertion review, no managed verification receipt claimed. Canonical rationale
GUARD-RECOVERY / ACP-FRAMING captured; README behavior unchanged. Provider/schema,
UI explanation, tests, docs and .gitignore (generated CodeMap only) are within
these decisions. Existing mobile source hashes preserved outside shared TASK/UI.
Root cleanup fallback at hard cap+150s remains only for missing worker cleanup;
ordinary worker timeout is handled at hard cap+120s and never latches the bot.


Scope: default budgets, per-request failure isolation, bounded ACP framing and
safe diagnostics, expired legacy quota holds, provider schemas, tests and docs.
No publication, VPS changes, account access, or arbitrary restart recovery.
Authoring: Linux/WSL Python/Go. Targets: Ubuntu Docker Claude/Codex ACP workers;
Windows SSH/HTTPS provider configuration schema. Existing mobile/UI edits retained.
CodeMap first full strict build passed; index daemon absent, direct verified impact
queries used. LSP available but fast static profile chosen; source is authority.
Rationale mode ON, no prior records mapped. New reason GUARD-RECOVERY: upstream
buzz-acp owns retry/idle/hard deadlines; wrapper budgets are optional, never a
bot-wide latch; worker fallback deadline must allow upstream cleanup first.
Preserve secure slots, cleanup-before-release, credentials and operator stops.
Legacy config intent is unknown: preserve explicit stored limits, only resume old
quota holds once their actual allowance permits; require redeploy/settings to
choose new defaults. No auto-replay of previous side effects by our supervisor.
New reason ACP-FRAMING: official pinned codec accepts 10,000,000-byte lines;
match limit, measure per frame, classify errors without logging raw content.
Tests: config/schema defaults/explicit values; quota expiry across restart; >100
healthy prompts; repeated failures; worker cleanup/concurrency; malformed/large
frames; safe diagnostics; state persistence. Old latch/deadline tests require
updates under approved behavior change; ownership/auth tests remain unchanged.
Evidence: deterministic local fixtures, not live accounts or Windows-off proof.
Policy validator OFF: no project policy pack. Existing manual test fallback retained.

## 2026-10-10 Mobile pairing automatic installation

Approved: local code and focused tests; CodeMap off, Sonol Test focused,
Policy Validator off (no pack). No publication or live server change in this task.
Authoring Linux/WSL; target Ubuntu Docker/Traefik with an existing private Buzz
Relay and Python portal. Windows/Android pairing remains a manual acceptance.
MOBILE-01 new broker-owned reconciliation: derive the selected relay, image,
network and HTTPS labels from Docker; add only a managed mobile-pairing service
in this installation's Compose. Preserve Relay/AI services, secrets and volumes.
MOBILE-02 reuse an already reachable /pair endpoint; refuse competing routes,
foreign service/container names, unsupported relay images and ambiguous discovery.
Bound commands, immutable image IDs, resource caps, no host ports or mounts.
MOBILE-03 bootstrap/configure trigger reconciliation; a mobile failure cannot
fail ordinary AI setup. Persist a sanitized status and offer restart instructions.
MOBILE-04 focused tests cover derivation, collision, restart/reinstall, preservation,
failed deployment and broker status. UI guidance is bilingual; no new UI framework.
Existing untracked files are outside this task; no global skill changes.

Local result: 17 mobile regression tests and 58 existing portal tests passed.
Actual Compose v2.40.3 (official checksum verified) config/round-trip checks passed
for initial and repeated reconciliation. That check found omitted empty command /
expanded network syntax; service_semantics now handles only those equivalent
representations and rejects extra service fields. Regression retained.
Real headless Chrome passed ko-KR/en-US/en-GB/fallback locale checks, 1440/390
viewport checks, expanded mobile guidance and zero console exceptions. JS syntax
and git diff whitespace checks passed. Negative-control test fails when the
broker's first-configure mobile hook is removed. No existing assertion weakened.
Dockerfile.portal copies the entire buzz_agents tree; both broker and portal
must be rebuilt for release. No live Docker daemon available locally: actual
sidecar creation/TLS routing by this installer, Android pairing, and Windows-off
response remain release/manual acceptance gaps. Earlier manual VPS sidecar is
separate evidence. No image/URL publication or VPS mutation in this task.
Direct focused evidence follows this project's existing manual test fallback;
no managed validator/CodeMap receipt claimed. Existing untracked files untouched.

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

CONNECT-CHOICE-01: distinguish authenticated healthy check, explicit401 connection_revoked_or_invalid, and uncertain network/HTTP/parse/device mismatch. Healthy Enter keeps; rejected/damaged Enter reconnects; unknown Enter rechecks with r/R reconnect or n/N cancel. EOF cancels without consuming a grant. Local Windows program/source change only; saved credentials remain until successful replacement. TLS response and scripted decision tests cover transport errors, generic401/404/503, malformed/oversized responses, retries and EOF; retain existing atomic-save/rollback tests.

GUIDE-01: user requests screenshot-based Windows Buzz community onboarding in Korean and English. Reuse two observed non-secret onboarding screenshots; fresh region capture for join address excludes personal public key. Guide follows Skip for now -> Join a community -> configured Relay URL -> Next, not Builderlab owner flow. Fixed allowlist serves PNGs; public source/build context include them. Copy uses stored Relay config, never hardcoded developer hostname or setup host; clipboard denial selects address with localized Ctrl+C instruction. Real Chrome checks Korean/English images, alt text, correct URL, copy success/failure and both viewports passed. Local code/package only, no live VPS changes.

GUIDE-01 publication: source c172f61333325111465314f72df3e48e36a5fcb2 passed candidate CI37936814573, including scoped tests, four Docker startup/upgrade fixtures and anonymous image checks. Release portal-candidate-c172f6133332-19-1 EXE matches locally tested native Windows bytes; all web assets and portal source match anonymous build-context download. Root promotion changes only broker/portal digests. Exact Raw verification follows. User installs; VPS unchanged.

GUIDE-01 publication complete: exact Raw CI37937481478 passed anonymous downloads and actual Docker fixtures for both Traefik network modes. Install commit da9a4640dc2dbdcc6c2a9129b2074b1b0a838347; independent anonymous Compose SHA256 a10ad79357aab2c25e7b500bd013cc62986a26849fb931a9bc3c7c43f76e9f4f. New Windows EXE hash c15568b0db829e9642ab3f0286b06fd392a674b8e6ce0c7cd09c778a617af1bb matches local native test artifact. Install docs updated; user downloads a fresh connection ZIP. VPS unchanged; original real-AI/Windows-off acceptance remains open.

SETUP-LOAD-01 incident: user sees native Chrome HTTP400 at /? after initial setup submit. Author WSL; targets browser through retained two-slot portal_route on Hostinger. Current public HTML/app/i18n bytes match published source. Read-only cold Chrome checks and local real route reproduce i18n available but app boot undefined; direct-portal browser tests missed route concurrency. New reason: combine dependent scripts into one served asset, disable login until API readiness, forbid native form navigation and provide bilingual loading/reload guidance. Preserve JSON auth, setup expiry, origin/host validation and retained route identity; no credential or VPS mutation. Existing approved route remains CodeMap off, focused direct Sonol Test fallback, validator off. Add real-route browser initial-claim/login plus unavailable-script regression, retain existing locale/HTTP tests. Publish corrected candidate through existing CI and immutable URL; user installs.

SETUP-LOAD-01 local evidence: actual live read-only Chrome reproduced missing scripts and BuzzI18n TypeError; no credentials submitted. Real local two-slot bridge regression passes cold loads, invalid code, first claim, existing-password login and blocked-script/native-submit refusal. Same replay rejects daccc5f web assets. Existing locale/browser suite and portal HTTP26 pass. New browser gate added to candidate CI; existing required checks preserved.

SETUP-LOAD-01 candidate CI37939336330 passed including new real-route Chrome regression and existing Docker installation/upgrade checks. Anonymous release portal-candidate-d2ed537e1043-21-1 hashes and changed source bytes verified. Promoting immutable broker/portal images; runtime retained. Exact Raw smoke next. No VPS write.

SETUP-LOAD-01 published: exact Raw CI37939809318 passed on install21524ec79f7603a8f31633b2d34c24cfaabe75a0. Anonymous bytes SHA25643c379f1056814bfab3b14997f68393fc4f9ab9a333bcdca7b28e5fd063e5934. Docs direct user to new URL, Open without stale /?, latest portal code. Live endpoint read-only reported claimed=false before update; no account/password reset needed. User installs; live corrected initial claim remains user verification, not claimed complete.

LOGIN-LOAD-01: user confirms manual Relay discovery/HEX works after automatic post-login Bad Gateway. Current source e0e6ccd; WSL author, browser+retained two-slot route target. One-second guide-image latency fixture reproduces successful claim followed by missing auto-filled owner, unlike prior fast-loopback fixture. New reason: serialize page-owned API/image traffic; finish initial status/devices/discover before revealing/loading guide; bounded retry only explicitly read-only status/devices/discover on transport/502/503/504; never retry login/configure/auth/pair writes. Handle non-JSON errors with localized text and explicit initial-load retry. Preserve auth, secrets, Relay and route identity. Existing route CodeMap off/focused direct tests/validator off. Regression must replay delayed images, transient/persistent gateway errors, and demonstrate non-idempotent login is sent once; prior real bridge/browser/locale checks retained. Publish corrected images via existing CI, user installs, no live VPS mutation.

LOGIN-LOAD-01 verified: delayed-image replay fails original e0e6ccd at owner autofill and passes fixed source. Extended real-route fixture covers transient read retry, persistent three-attempt limit, manual retry, exactly-one login request on injected502, initial claim and password login. Test logout readiness strengthened because serialized image queue exposed stale-page predicate. Existing i18n and portal HTTP26 passed. No authenticated live session or VPS mutation.

LOGIN-LOAD-01 candidate CI37942173881 passed all required tests including delayed-guide/gateway real-route Chrome and Docker upgrade preservation. Release portal-candidate-598e055f97ee-23-1 public manifest hashes and source/image bytes verified. Promote only broker/portal digests; exact Raw check follows. Latest user capture shows broken join-address image and unsaved community address placeholder; saved Relay config is still required before address display. No VPS mutation.

LOGIN-LOAD-01 publication complete: exact Raw CI37942744913 passed on daa506c4c993b720372ba96708d4f32cf8f4abc4. Independent anonymous SHA256ce850ff59e095b5afd78b9876096a15d47fc0ff929b9c525e26bff3ad285f13a. All source/web image bytes verified. User-facing install guide explains saved-Relay prerequisite, sequential images and explicit retry; actual VPS update/user acceptance remains pending.

GUIDE-READY-01: remove confusing setup-host warning; add user-authorized actual Welcome capture as step4, bilingual community-connection success text and AI-agent next step. Completion is scoped to community join, not VPS AI execution. Existing sequential image loader and fixed static allowlist retained. Local content change; no VPS update.

GUIDE-TABS-01 (approved): local source/UI only, no publication or VPS writes. CodeMap off; Sonol Test focused direct browser/route fallback; validator off. Author WSL; targets desktop/mobile browsers in ko/en and Windows Buzz v0.5.27 observed screens. New reason: replace long onboarding with six keyboard-accessible numbered panels, reuse reviewed community/address copy and sequential image queue, preserve all auth/config/device controls. Add actual adapter/model/Run-on/error screenshots; never label failed provider deployment as success. Evidence: extend locale browser assertions for navigation/hidden panels/keyboard/Relay copying/images/mobile overflow, retain real two-slot route regression. Existing dirty work preserved.

GUIDE-TABS-01 verification: six panels with roving keyboard focus, previous/next boundaries, ko/en copy and image alt text, saved Relay clipboard success/denial, all eight PNGs, and desktop1440/mobile390 overflow checks passed in real headless Chrome. Initial concurrently executed locale run hit its 12-second image readiness deadline; diagnostic rerun in isolation passed, so no claim about that transient cause. Retained two-slot route test passed cold loads, delayed images, gateway retries, and single-submit login behavior. Portal HTTP26 passed; JS syntax and diff whitespace passed. Rendered ko desktop step4 and en mobile step5 inspected. Existing 150ms button transition can appear between colors in immediate test captures; selected tab semantics are asserted independently. Local source complete, no release/push/VPS mutation; real provider deployment error and Windows-off AI execution remain unresolved.

PROVIDER-ERROR-01 approved source investigation/fix, no installation/publication/VPS writes. CodeMap off, focused direct Sonol Test fallback, validator off. WSL author, Windows provider and Linux VPS target. Observed local managed record: Claude VPS backend hostinger-https, agent_command claude-agent-acp, args [], parallelism10, last_error provider failed (exit code1, empty stderr). No private keys read/exported; connection file shape only inspected. Official source326e2301cb4b1edcb8a72d01ac4b19a83545365f backend.rs rejects nonzero before parsing stdout; agents_deploy.rs emits resolved launch and effective parallelism; types.rs default10. v0.5.27 tag unavailable through GitHub API, so main source corroborates installed behavior but is not claimed exact binary source. New reason: bounded allowlisted stderr diagnostics and end-to-end provider failure fixture, keep stdout JSON/exit1 and no secret/raw request logging. New reason: accept valid desktop concurrency1..32, honor user-selected concurrency and default10 instead of rejecting it; preserve identity/env/args/memory/time/guard boundaries and resolved model authority. Captured stored metadata is not original transmitted payload; original live root cause remains unconfirmed until user redeploy with diagnostics. Tests must replay synthetic version-pinned official shape with parallelism10 through normalize, and verify stderr from actual provider process on Windows plus TLS failure forwarding/redaction.

PROVIDER-ERROR-01 user steering: preserve Buzz concurrency1..32, default10; no forced single-worker cap or automatic resource-based adjustment. Shared broker now tracks independent active tickets/deadlines with aggregate durable quotas; each adapter remains sequential while multiple adapters run concurrently. No publication or VPS mutation.

PROVIDER-ERROR-01 local verification: config23, policy/guard19, host/native22, process5 tests passed (69 total). Real Unix socket tests hold 1/2/10/32 independent tickets, reject excess without consuming quota, release exactly once and persist aggregate starts; staggered deadlines checked. Go race suite passed. Cross-built Windows diagnostic executable ran on Windows: failure exit1 with parseable stdout and safe nonempty stderr, secret marker absent; info exit0 valid JSON/no stderr. Installed provider untouched. No live Claude success or Windows-off acceptance claim; publication and VPS update not performed.

CONTRACT-FIX-02 user-approved local implementation and broader upstream audit with one subagent; no push/publication/install/VPS mutation. Existing dirty guide/provider changes preserved as baseline. CodeMap off, focused direct Sonol Test fallback (project has no validator registry), Policy Validator off. Author WSL/Linux, targets Windows provider/connector and Linux Docker VPS. New reasons: preserve safe validator diagnostics across subprocess/RPC/HTTPS; relay replay-floor pass-through without durable stale replay; preserve explicit Buzz event/dedup/session settings; runtime-local failure isolation and grace-bounded cleanup; physical-host resource limits instead of fixed KVM2 ceilings; migrate only exact reviewed Windows provider binaries; observable categorical runtime diagnostics without raw secret-bearing output. Reviewed invariants: identity/owner/member checks, two supported adapters, no host path/secret env override, durable aggregate quotas, intentional-stop persistence, previous unknown binaries/credentials/data preservation. Additional official gaps will be recorded and repaired within these same boundaries. Tests: contract reproductions first, native process/Unix socket/HTTPS/Windows upgrade regression; release artifacts and actual VPS/Windows-off proof remain separate.

CONTRACT-FIX-02 outcome: local corrections implemented; independent one-agent review and targeted re-review completed. Full Python172 passed; final diagnostic changes process9+contract13 passed. Go web-provider/connect/provider race+vet passed. Native Windows connect tests and provider info/error smoke passed. Docker unavailable locally, so new image build/live VPS/auth/Windows-off acceptance remain unverified. No publication, install or live mutation. Dedicated dist/contract-fix-20261010 avoids old compose.install.yaml from earlier builds. Contract/support boundaries and legacy resource-default migration documented.

CONTRACT-FIX-03 approved two review findings: retain upstream-owned guard process group so official group SIGKILL also kills adapters/ordinary descendants; preserve categorical diagnostic across held/stopped/login-only restarts and reset at actual launch. CodeMap off, focused Sonol Test direct fallback, Policy Validator off, no new delegation/publication/install/VPS actions. Author Linux/WSL, runtime target Linux Docker. Process cleanup must preserve per-worker isolation, kill/reap before ticket release and fail closed if cleanup cannot be verified; normal guarded shutdown must still retain diagnostic drain. New regressions reproduce upstream group kill and native main state persistence before product edits. Existing dirty source preserved. Generated package will be refreshed after tests; actual Docker image/live acceptance remain outside this local proof.

CONTRACT-FIX-03 outcome: before-fix upstream process-group SIGKILL regression failed with surviving AI descendant; restart-state test failed in held/stopped/needs-login cases. Corrected adapter group inheritance, own-group cleanup uses pidfd identity pinning and bounded /proc scan before releasing tickets; failure holds bot. Native previous diagnostic preserved until real new spawn. Focused tests process10 + native diagnostic2 (including ready-without-login and real launch state writes) + contract13 + host/native25 + guard/policy20 =70 pass. WSL pidfd/proc probe pass; Docker capability probe added to image preflight, actual Docker/VPS not run. Build candidate refreshed locally and byte/hash readback required; no publication/install.

CONTRACT-FIX-04 approved three follow-up fixes, same local-only route (CodeMap off, focused Sonol Test, validator off): kernel-authenticated guard lifetime tracking reclaims slots only after owner and group are dead, preserves charged quota and live-worker deadlines; completed login sessions no longer consume running-session capacity while bounded output/history remains; render release Compose before regenerating/verifying manifest+SHA256SUMS. Applies equally to Codex and Claude Linux adapters; real provider login/model and Docker release remain unverified. Regression tests must cover both adapter names, active guard SIGKILL and next acquire, live siblings, repeated finished logins versus eight running logins, final Compose tamper detection. No external deployment/install authorized.

CONTRACT-FIX-04 outcome: kernel peer/pidfd owner tracking reclaims a dead worker slot only after its group dies, without refunding quota; live-child regression retains the slot. Completed login attempts no longer exhaust active cap8; history and duplicated PTY reader descriptors are bounded. Release Compose now enters final manifest/SHA256SUMS and publication verifies hashes. Focused tests: process20 (both fake adapter names), policy21, login2 (both providers), portal26, release4, diagnostic2, host25, contract13 =113 passed. Local package refresh only; real Docker/AI login/VPS/Windows-off acceptance not run.

CONTRACT-FIX-05: user authorized fixing the two follow-up findings. Same local scope: CodeMap off, focused direct Sonol Test, validator off, no publication/install/VPS writes. Linux author; Linux broker and release CI affected, both Codex/Claude auth. Expiry cleanup failures retain running session/capacity and same-bot exclusion; unrelated sessions proceed; retry on subsequent requests after 30 seconds, expired input denied. Fixed-category log only. Release asset arguments now derive from verified manifest, including checksum/manifest metadata, with Bash array quoting. Regression: login3 (both providers, cleanup failure/recovery/backoff), release4, portal26 =33 passed. CLI-to-Bash asset handoff with Korean/spaced filenames and sha256sum readback passed. Existing dirty changes preserved. Refresh local package; no live Docker/AI or Windows-off proof.

LOGIN-EXPIRY-01: user approved UI retry correction, existing local scope retained (CodeMap off, focused Sonol Test, validator off). Linux author; ko/en browsers target. Clear matching active UI session only on explicit login_session_expired for poll/input/cancel; preserve sessions on transport/transient errors and ignore older-session expiry for newer UI state. Clear terminal/input/links and show existing localized retry guidance. Expired cancel is idempotent, permitting logout. Real Chrome/HTTP browser and i18n suites passed with both fake providers, all three expiry operations, transient preservation, stale response and re-login checks. Docker unavailable; actual provider accounts/VPS/Windows-off acceptance remain unverified. No publication or installation.

PUBLICATION-20261010: user explicitly authorizes deployment for user testing. Publish reviewed source, three GHCR images, Windows connector and immutable Compose through existing GitHub Actions; user installs/tests. Keep existing focused route; no VPS mutations or user credential use. Source main matches origin before publication. CI Docker fixtures provide unavailable local environment checks; exact Raw verification and anonymous asset hash/source readback required before handoff.

Publication readback found GitHub renamed Korean release basename to default.md, invalidating manifest download names despite pre-upload checks. Use ASCII START-HERE.ko.md for the external asset; Korean guide contents unchanged. First candidate not promoted. Repeat publication and anonymous exact-name/hash readback before handoff.

Publication candidate70dee396ee1f passed CI38015081911 including real Docker install/upgrade and anonymous images. All7 manifest assets downloaded anonymously under exact names and passed SHA256/size checks;37 runtime/web source files match checkout. Local Go1.23 versus CI1.26.5 explained binary mismatch; rebuilt with Go1.26.5 and both Windows binaries match published bytes exactly. Native Windows HTTPS provider info smoke passed. Promoting only the four image references in canonical Compose; exact Raw CI next. No VPS writes.

Publication complete: immutable install ee741f5e9be0f4cee88e476e4446337136287b1b passed CI38015539605 (both proxy network modes, exact public bytes and anonymous image pulls). Independent anonymous Raw SHA256 da2f545d95f2b31a184e9e41cc21d8c7aa2d7e271080ceddd103d16ef93d8ee7. Go1.26.5 native Windows connector tests passed. User installs/tests; no VPS or credentials changed.

PID-POOL-01 (approved): CodeMap off, Sonol Test focused direct fallback, Policy Validator off. Exactly one subagent owns native/guard/bridge diagnostics. Root owns finite worker-scaled PID budget, explicit stopped migration/readback, bilingual health display and tests. Preserve default10/range1..32, Guardian approvals, identities/auth/workspaces/quota. New reasons: cgroup limit256 exhausted with observed251 threads; do not classify one sample as leak. Resource snapshots every5s with baseline/delta and safe allowlisted diagnostics; no raw model content/secrets. Local source only, no deployment/VPS mutation. WSL author; Linux Docker and Windows provider/browser targets. Real Docker/AI and Windows-off acceptance remain pending.

PID-POOL-01 verification: full Python suite201 passed before final three host additions; final host31 and native diagnostic3 passed; Go provider tests passed. Chrome ko/en/en-GB/fr fallback, desktop/mobile and new health text/unknown-code nonexposure passed with zero console exceptions. Subagent independently reviewed host drift/migration (no blockers); added numeric mismatch, invalid workers, retained auth/workspace/quota/other registry regressions. Corrected final resource sample to run even after stream EOF. Process-limit diagnosis is sourced from cgroup event delta, not arbitrary log text. Docker unavailable locally: no real10-worker model acceptance, sustained leak test or Windows-off completion claimed. No push/deploy/VPS mutation performed.

PID-POOL-01 publication authorized by user: publish reviewed source, candidate images/Windows assets and immutable Compose via existing GitHub Actions, then anonymous readback. Reuse CodeMap off, focused Sonol Test/direct CI fallback, validator off. User installs VPS; no live VPS mutation. New publication reasons: ship host resource policy plus supervisor health together; verify artifacts contain runtime_health.py; preserve previous install URL until CI passes. Existing local regression evidence reused, Docker install/upgrade checks delegated to standard CI (no additional subagent).

Publication preflight corrected an unreachable Go hint case (moved from safeErrorCode to errorHint, concrete Windows Buzz stop guidance), plus stale packaged install-guide URL. New regression checks safe code identity and actual hint. Cancelled first build before publication and rebuild corrected source; live user settings untouched.

PID-POOL-01 candidate289bc3946cbb passed CI38020017912: Python204, Go race/vet, browser route and four Docker startup/upgrade fixtures. Anonymous7 release assets passed manifest SHA256/size;38 runtime/web sources match checkout. Both Windows binaries match local Go1.26.5 build; provider info ran on Windows. Promote immutable image references only; exact public Raw verification next.

PID-POOL-01 publication complete: immutable installc31586e078dff3e7e8de69da5b1410cdfb13f909 passed exact public URL Docker CI38020378322. Independent anonymous Raw SHA25684ee40c57efa25c06e3abb0f4b4461c3b0dd252ef9abc618146c8fdee41cc0a3 matched. Candidate releaseportal-candidate-289bc3946cbb-29-1 available; user performs VPS install, bot stop/redeploy and live acceptance. No VPS/credential mutations.

CONNECT-UPGRADE-02 user authorizes root fix and republication. Reuse router: CodeMap off, Sonol Test focused direct fallback plus existing release CI, validator off. No subagents or VPS/local installed configuration mutation. Linux author, native Windows installer target. New reason: replace manually maintained predecessor hash list with checked-in verified public-release catalog and pre-publication completeness gate; real released EXEs must upgrade in temp homes for healthy/reconnect paths. Preserve unknown-file refusal, failed-write credentials, locking and pairing semantics. Public release manifests plus independently hashed bytes bind trust; build embeds offline catalog, no client runtime download trust. Existing provider/runtime behavior and process budgets unchanged. Publish only after focused tests and existing CI/anonymous artifact readback. Documentation corrects manual-update route image retention; live accounts/Windows-off remain user acceptance.
CONNECT-UPGRADE-02 evidence: exact previous70dee provider regression failed before fix. Enumerated14 public releases, independently hashed9 unique providers; early embedded providers extracted only with exact manifest size/SHA256 match. Linux Go race suite and history validation tests passed. Native Windows9 providers × healthy/reconnect18 paths passed, along with locked-write/unknown-target preservation. First Windows test invocation lacked WSL environment propagation and skipped fixture test; corrected via process-local PowerShell environment and literal arguments, final run passed18 paths. Public source archive explicitly includes embedded catalog. Release gate blocks missing/changed history, runs actual predecessor upgrades before publishing; no user installation changes.

CONNECT-UPGRADE-02 candidate3126a43128b0 passed CI38023046793: release history14/9 verified, Python207, Go race/vet with real release fixtures, browser and Docker install/upgrade checks. Anonymous7 assets passed exact hashes;38 runtime/web sources, provider catalog and both Windows executables match local reviewed bytes. Promote verified image references; exact Raw CI next. No user file/VPS changes.

CONNECT-UPGRADE-02 publication complete: install ebf871a23f6922cfdd8a45fc8ad4dc65436e5d08 passed CI38023462552 exact anonymous URL Docker run; independent Raw SHA2564a7b03cd69522728ef008ac35779659c38b929591c869cc83d4673f6246c557c. Release portal-candidate-3126a43128b0-31-1 verified. User updates VPS and downloads a fresh pairing bundle; existing provider file need not be renamed/deleted. Unknown builds remain protected.


UPDATE-01 (2026-10-10), user approved implementation and publication, with broader source verification. No live VPS mutation. Author WSL/Linux; targets Linux Docker broker/runtime and Korean/English browser UI; existing Windows/SSH deploy contract retained. CodeMap scoped (verified sync required due stale source; LSP off for this profile); Sonol Test focused direct incident and regression tests plus release CI; validator off because no project policy pack. Upstream reference 326e2301: runtime.rs remote status remains deployed after !shutdown; AgentRuntimeAvatarControl hides start for active bookkeeping; no provider undeploy. This explains the observed UI path but is not proof of installed binary identity.
New reason across host/update module, broker, portal and web: administrator-only existing-bot update with explicit running-work interruption consent, immutable broker-selected image, preserved bot key/owner/Relay/workspace/provider/account, explicit opt-in default budgets, saved normalized settings revalidated in the selected runtime, no replay-floor reuse. Async operation state avoids holding a browser request through Docker recreation; no automatic retry of mutation. Same global deploy lock fences desktop deployment, refuse overlapping authentication, target only one owned container, verify actual image/labels/limits after recreation. Other services retain their current pinned image. Failure is visible and never causes deletion of credentials/workspace.
Tests/new docs: incident regression for stopped/deployed UI mismatch, both providers, old budgets, data retention, image readback, concurrent updates/login, identity collision, malformed input, stale preview, failed stop/up, request loss and admin/device isolation; real browser ko/en controls and release Docker validation. New rationale capture follows stable implementation. Existing unrelated untracked files preserved.

UPDATE-01 local outcome: final update16 tests passed (both auth locks, stop/up failures, foreign identity, image readback, preserved other-image mapping including retire); portal27 and full257 prior to two final additions passed. Real Chrome ko/en desktop/mobile update controls passed including failure/interruption, no automatic mutation retries; existing i18n regression passed. CodeMap verified changed sync passed with existing LSP-off profile, rationale EXISTING-BOT-UPDATE captured. Actual Docker unavailable locally; real Docker both-provider replacement added before publication in CI. User VPS untouched.
UPDATE-01 publication gate found the immediately previous public release missing from the checked-in connector history. Anonymous manifest and executable readback verified16 releases/10 unique providers; added only the missing06c848 release record with exact SHA256/size. Gate remains fail-closed. Re-run candidate from corrected source; no images from the failed run were published.

UPDATE-01 candidate4581d501a9e3 passed CI38056923464: Python259, Go race/vet, browser route/update checks, four real Docker bootstrap/upgrade fixtures and both-provider existing-bot replacement. Synthetic identity/role/model/auth-file/quota/workspace/other-image retention passed; actual AI subscriptions remain untested. Anonymous7 assets,40 runtime/build files,125 source archive files and both Windows binaries matched reviewed local bytes. CodeMap parity initially invalidated by the concurrent history/docs correction; stable replay passed21 outputs with zero differences. Promote only verified image references and publish exact four-field existing-install instructions; exact Raw CI next. No live VPS mutations.
UPDATE-01 publication complete: immutable install50d89dc494662d90727a0ce350b8cc127a2febd7 passed exact anonymous Raw startup CI38057440414. Independent Raw SHA256134e4b16953da9fe9982855ed1ba05a5a371dd10ec53bc086b4ea9a52d6ea0f1 matched. Releaseportal-candidate-4581d501a9e3-36-1 includes tested images and binaries; release notes link exact four-field in-place update guide. User installs and checks real provider replies; no VPS or installed user settings modified. Headless local Chrome used only loopback test server and terminated; no public-network access required and the user's Windows firewall prompt was not directly observed.

AUTH-LINK-01 approved: scoped CodeMap, focused Sonol Test direct fallback, policy validator off (no project policy pack); implementation and publication, user installs, no live VPS/authentication changes. Baseline f4aaf752d10d3265d7397f6b54d0fd5c1f2224ba. WSL author; ko/en desktop/mobile browsers target, both provider login flows preserved. CodeMap verified refresh and exact app.js/broker query: app link rendering unmapped, broker's EXISTING-BOT-UPDATE does not require mutation. New reason: official SDK0.3.293 Linux-x64 binary SHA2568968405e26db478af44eabc4635ab5ca557057b702a54460a59c13e1b253e978 contains https://claude.com/cai/oauth/authorize, absent in current allowlist. User raw login transcript not collected; matching endpoint failure will be reproduced with sanitized fixture. Add exact new login endpoint, preserve full query parameters, retain OSC8 hyperlinks before stripping terminal control sequences, show open/copy with manual fallback, keep existing Codex links and refuse untrusted hosts/schemes/credentials. No automatic browser navigation or token logging. Source/test/UI evidence and release image/URL checks required. Existing unrelated untracked files preserved.

AUTH-LINK-01 local evidence: original renderer accepted Codex and failed current Claude endpoint; fixed parser fixture passed. Actual Chrome/HTTP ko desktop and en mobile passed plain/ANSI/OSC8 links, real clipboard readback, denied-copy selection and poll focus, input/cancel, Codex and hostile hosts; rendered mobile inspected. Existing four-locale i18n suite passed. Browser harness now waits for startup button and emulates focused headless document for clipboard; no production behavior changed to satisfy tests. Public history refreshed with verified17 releases/10 providers before release. No real account authentication performed.

AUTH-LINK-01 first candidate CI38059019403 stopped before image publication: new browser clipboard assertion failed. Harness could inspect previous locale document immediately after Page.navigate and retain its clipboard-denial override. Require a new document marker and exact successful-copy feedback before readback; do not weaken clipboard equality or change application behavior.
