# Existing bot update candidate — 2026-10-10

Adds an administrator-only **Update / restart** action for existing Claude/Codex
bots, including ones left Deployed in Buzz after Shutdown. It preserves the last
deployed identity, role/model, authentication and work files, with optional explicit
removal of historical count budgets. See [update instructions](EXISTING-BOT-UPDATE.md).

Local verification: 257 Python regressions passed before final auth-lock and
retire-image tests; final focused update suite16 passed. Korean/English Chrome
checks cover confirmation, opt-in defaults, cancel, double-click, refresh, completion,
failure and interrupted jobs. Existing multilingual/viewport regression passed.
Current release CI runs the full current suite and real Docker replacement for both
providers before publishing. Synthetic account-file preservation does not prove
live provider tokens or replies. User VPS and Windows-off acceptance remain pending.

In-place management updates replace only broker/portal/runtime references; preserve
setup-route and all existing volumes, paths and project names. No VPS mutation is
performed by this publication.

## Previous release evidence (historical)

Published candidate `portal-candidate-06c848475608-33-1` from source
`06c8484756087803e04792af157ab1ee8a7cc76a`.
Candidate CI: https://github.com/volition79/buzz-agents/actions/runs/38052003782
passed 242 Python tests, provider/connector race and vet checks, browser tests,
four Docker startup/upgrade scenarios and anonymous image access.
Independent anonymous readback verified seven manifest assets, checksums, 39
runtime/web source files and both Windows binaries against local Go 1.26.5 builds.
Canonical Compose below adopts only the three reviewed image digests.
Exact Raw URL start verification is the remaining publication handoff check.

# Runtime recovery and mobile pairing candidate — 2026-10-10

New deployments use optional prompt budgets (0 = disabled), official 25-minute
idle / two-hour turn defaults, and per-worker deadline recovery. Enabled budgets
expire without permanently holding the bot. Existing stored settings are preserved;
stop and redeploy each bot with reviewed settings to adopt the runtime correction.
Cleanup/storage integrity faults still hold safely. Legacy expired budget holds
may recover; operator stops and login requirements do not auto-clear.

ACP framing matches the pinned official 10MB line limit; specific safe diagnostic
codes replace ambiguous protocol errors. Earlier runtime_protocol_failed cannot
be retrospectively attributed to one cause from the old logs.

Includes previously approved mobile pairing setup and Korean/English guidance.
Local Python regression, both provider schema tests and bilingual browser checks
passed. See docs/GUARD-RECOVERY.md and docs/MOBILE-PAIRING.md for evidence and limits.
CI must pass real Docker startup/upgrade tests and anonymous artifact access before
install handoff. Actual VPS installation, account login and Windows-off execution
remain user acceptance steps. No live VPS changes are performed by this release.

# Windows provider upgrade history — 2026-10-10

Fixes official previous-provider rejection during reconnect. The installer embeds a reviewed offline catalog of public provider hashes. The release workflow verifies completeness against all public candidate manifests and checks actual EXE bytes (including embedded backends in early installers); missing or changed releases block publication. Unknown or modified executables remain protected.

Release maintainers: run `python3 scripts/provider-history.py --write --download-dir /tmp/buzz-provider-history`, review and commit the catalog, then publish. CI uses `--check` before building and supplies verified binaries to real upgrade tests. No credential or installed-user configuration is changed by these tests. Live VPS/AI acceptance remains separate.

Published source `3126a43128b085f7d288e69934bd24f4b8d6d404`: [candidate CI38023046793](https://github.com/volition79/buzz-agents/actions/runs/38023046793) passed207 Python tests, Go race/vet and actual released-provider fixtures, browser route and Docker startup/upgrade checks. Local native Windows9 official providers ×2 upgrade paths passed. Anonymous7 assets,38 runtime/web files, embedded history and both Windows binaries matched reviewed bytes. Immutable install `ebf871a23f6922cfdd8a45fc8ad4dc65436e5d08` passed [exact URL CI38023462552](https://github.com/volition79/buzz-agents/actions/runs/38023462552); Compose SHA256 `4a7b03cd69522728ef008ac35779659c38b929591c869cc83d4673f6246c557c`. No live user configuration changed.

Previous evidence follows.

# PID/thread capacity candidate — 2026-10-10

This candidate replaces the fixed per-bot256 PID ceiling with a finite worker-scaled budget (10 workers:768). Existing running bots require explicit stop/redeploy when their limit differs. Login, workspace, identity and quota data are retained. Cgroup-v2 snapshots and safe diagnostic categories distinguish observed limit events from generic process-creation failures; ko/en setup shows last sampled usage.

Published source `289bc3946cbb873975cf06749123ae49354484af` passed [candidate CI38020017912](https://github.com/volition79/buzz-agents/actions/runs/38020017912): Python204, Go race/vet, browser route and four Docker startup/upgrade fixtures. All7 anonymous release assets passed hash/size readback;38 runtime/web source files and both Windows binaries match local reviewed builds. Immutable install `c31586e078dff3e7e8de69da5b1410cdfb13f909` passed [exact URL CI38020378322](https://github.com/volition79/buzz-agents/actions/runs/38020378322). Compose SHA256: `84ee40c57efa25c06e3abb0f4b4461c3b0dd252ef9abc618146c8fdee41cc0a3`. VPS installation remains user-operated. This is not proof of leak-free runtime, real Codex/Claude10-worker success or Windows-off scheduled completion. See [incident boundaries](process-limit-investigation.md).

Previous release evidence follows.

# Runtime and setup recovery candidate — 2026-10-10

Published source70dee396ee1f343b81929f69a0c9d7e1f65f5a53 passed candidate CI38015081911. Release portal-candidate-70dee396ee1f-26-1: all7 manifest assets downloaded anonymously and verified. Windows executables reproduced with Go1.26.5; native Windows connector tests and provider info smoke passed. Immutable install ee741f5e9be0f4cee88e476e4446337136287b1b passed exact public URL Docker CI38015539605. Compose SHA256 da2f545d95f2b31a184e9e41cc21d8c7aa2d7e271080ceddd103d16ef93d8ee7. VPS untouched; user performs real-account and Windows-off tests.

This candidate updates runtime, broker, portal and Windows connector together. It corrects shared Codex/Claude launch contracts, concurrency, worker cleanup and slot recovery, login retry isolation, safe diagnostics and provider upgrade handling. The bilingual setup guide now uses numbered screenshot panels; expired sign-in sessions can be retried without reloading. Release assets are derived from the verified manifest.

Local source, process, Windows and browser checks are recorded in docs/contract-fix-verification.json and TASK.md. The user authorized publication and will perform VPS installation and real-account testing. CI image/bootstrap checks and exact immutable Raw URL verification must finish before install handoff. Real provider account/model execution and a new task after Windows power-off remain unverified.

# Post-login automatic discovery regression — 2026-10-09

User confirmed manual Relay/HEX discovery works, while login followed by automatic loading displayed a non-JSON Bad Gateway error. Read-only unauthenticated probes did not capture the exact failed authenticated request. On source e0e6ccd, a real two-slot route with one-second guide-image latency reproduces a successful claim followed by missing automatic owner fill. This supports a request-overlap failure; it does not claim access to the user's authenticated Network history.

The page now serializes its API and guide-image requests, completes status/devices/discover before loading images and suppresses polling during initialization. Only read-only status/devices/discover retry transport or 502/503/504 errors, at most three attempts. Login/configuration/pairing/auth operations are never automatically retried. Non-JSON failures have localized messages; a failed initial load exposes an explicit retry button. No route, Relay, account or credential changes.

Real-route Chrome regression passes delayed images, transient and persistent gateway replies, automatic owner fill, explicit retry, existing-password login and exactly-one login attempt on gateway failure. The original e0e6ccd assets fail the same replay before owner fill. Logout assertions now wait for the actual visible logged-out page rather than stale hidden form state. Existing Korean/English guide/browser checks and portal HTTP26 passed. Publication is recorded below when complete; live user retest remains outstanding.

Published source `598e055f97eea93e938d2b578e1e1bfd105f0943`: [candidate CI37942173881](https://github.com/volition79/buzz-agents/actions/runs/37942173881) passed including the real-route browser incident checks. [Exact Raw CI37942744913](https://github.com/volition79/buzz-agents/actions/runs/37942744913) passed for install `daa506c4c993b720372ba96708d4f32cf8f4abc4`. Independent anonymous Compose SHA256 `ce850ff59e095b5afd78b9876096a15d47fc0ff929b9c525e26bff3ad285f13a`. Release manifest hashes and actual web/portal bytes match source. User installs; VPS unchanged.

# Initial setup HTTP400 regression — 2026-10-09

Observed on published source `daccc5f` through the real HTTPS setup URL: cold Chrome loads intermittently miss app.js or i18n.js; one captured runtime exception was missing BuzzI18n. Native form submission then requests /?, which the route correctly rejects. Public asset bytes matched the release. The retained route admits two concurrent connections while the page added a third parallel CSS/JS request. Direct-portal browser checks had omitted this bridge boundary.

Correction serves both scripts in dependency order as /setup.js, disables initial submission until hello succeeds, provides bilingual loading/reload text and blocks native form navigation via CSP. No auth, expiry, route image, persisted account or VPS settings are changed. The actual two-slot route browser regression passes five cold loads, invalid code, first claim, logout/password login and unavailable-script fail-closed behavior. The same regression rejects the original page at initialization. Portal HTTP tests26 and existing Korean/English guide/browser tests pass. Candidate publication evidence follows after CI; actual user initial setup remains to be retried.

Published source `d2ed537e1043c2531e12457994f5cf9ef3cdc890`: [candidate CI37939336330](https://github.com/volition79/buzz-agents/actions/runs/37939336330) passed including the new real-route Chrome setup gate. [Exact Raw CI37939809318](https://github.com/volition79/buzz-agents/actions/runs/37939809318) passed for install commit `21524ec79f7603a8f31633b2d34c24cfaabe75a0`. Anonymous downloaded Compose SHA256: `43c379f1056814bfab3b14997f68393fc4f9ab9a333bcdca7b28e5fd063e5934`. Published build-context changed source bytes and EXE/archive manifest hashes verified. No VPS write; user retries initial setup after installation.

# Screenshot guide and connection choices — 2026-10-09

This candidate adds three real Buzz onboarding captures with Korean/English instructions and a copy button for the installation's saved Relay URL. Browser tests checked both languages, image loading, clipboard success/denial, user-data preservation and desktop/mobile layouts. Portal tests: 25 passed. Windows connection choices now distinguish a healthy connection, an explicit server rejection and unknown status; Enter keeps, reconnects or retries respectively. Linux race/vet and 11 native Windows tests passed, including TLS classification, EOF cancellation and existing save/rollback checks. Both package archives contain the three screenshot assets. These are local results; publication CI is recorded separately. The user performs VPS installation.

Published source `c172f61333325111465314f72df3e48e36a5fcb2`: [candidate CI37936814573](https://github.com/volition79/buzz-agents/actions/runs/37936814573) passed scoped tests, four Docker startup/upgrade fixtures and anonymous image checks. [Exact Raw CI37937481478](https://github.com/volition79/buzz-agents/actions/runs/37937481478) passed on install commit `da9a4640dc2dbdcc6c2a9129b2074b1b0a838347`, including anonymous pulls and both Traefik network modes. Anonymous Compose SHA256: `a10ad79357aab2c25e7b500bd013cc62986a26849fb931a9bc3c7c43f76e9f4f`. Published EXE SHA256 `c15568b0db829e9642ab3f0286b06fd392a674b8e6ce0c7cd09c778a617af1bb` matches locally tested Windows bytes. Published web/portal sources and all three screenshots match local bytes. User installs; VPS unchanged. Real AI authentication, collaboration and Windows-off acceptance remain pending.

Earlier publication evidence follows.

# Browser language and restart-guide update — 2026-10-09

This candidate adds automatic Korean/English UI selection (132 entries), English fallback, and project-menu restart instructions for initial setup codes. Chrome locale tests cover Korean, US/UK English, French fallback, localized static/dynamic text, recovery and unmodified user/provider content. Desktop/mobile checks and the existing browser connection flow passed; portal unit tests: 25 passed. The new i18n script is served through the same protected static handler. These are local fixture results; live VPS update and original real-AI/Windows-off acceptance are separate.

Published source `4dda974a8239b2c21b1b7fd1c3c5ef7ebb4c81a2`: [candidate CI37933477258](https://github.com/volition79/buzz-agents/actions/runs/37933477258) passed 142 Python tests, scoped Go race/vet, four Docker startup/upgrade fixtures and anonymous image checks. [Exact Raw CI37933975910](https://github.com/volition79/buzz-agents/actions/runs/37933975910) passed on install commit `89f7ff848cbb250086a5e57146e174fcb89b073c`. Compose SHA256: `13e2d270b7d1897894ef6619c7ce4ae4f7a9b5461daccdfc253a70729454c3b8`. Published build-context bytes match the tested web sources. The user will install; no VPS configuration was changed.

The following sections describe earlier candidate evidence and history.

# v0.4 Docker portal — verification boundary

Published development candidate, 2026-10-09. No live Hostinger deployment was performed.

Published source: `8ae5df6d57c1c8a999bcebe3cd0b3517ef27f09a`. [CI run](https://github.com/volition79/buzz-agents/actions/runs/37896228009) passed all build, test, isolated Compose, image publication and anonymous-access steps. [Candidate release](https://github.com/volition79/buzz-agents/releases/tag/portal-candidate-8ae5df6d57c1-1-1).

## Passed

- Python: 107 tests (105-test suite plus 2 release-render tests), including all retained native/config/guard/scheduler/SSH tests and 19 new portal/broker/auth tests. Total with Go: 133.
- Go: 26 tests (legacy provider 9, legacy setup 7, HTTPS provider 6, HTTPS connect 4), with race detector; all four modules pass vet.
- JavaScript syntax; real Chrome 140 at 1440×1120 and 390×844, no captured runtime exceptions and no mobile horizontal overflow.
- Browser exercised real local HTTP claim, automatic Relay-prefill confirmation, connection ZIP download, one-use pairing, scoped device deploy request, bot list, login text input/cancel. **Docker broker / official login responses in browser test are explicit fixtures.**
- Real local PTY input/completion; login process-group timeout; cancellation before startup and wrong-session cancellation.
- Actual Windows x64 HTTPS provider executable answered `info` with protocol 1 and version 0.4.0. This does not prove Buzz discovery or Windows connection installation.
- Official Docker Compose 2.40.3 `config --quiet` accepted the template with test image/host values. CLI artifact SHA256 matched the Docker official image history.
- Docker CLI 28.5.1 manifest resolved and pinned to `sha256:9190b0613792e658a7783cf14b2d5ace5941bb68ede7276922ea36ee457d76ad`; image history confirms the copied Compose plugin path.
- Prepared manual-only CI publication workflow and digest-only Compose renderer; mutable tags/injected strings are rejected in renderer tests. The first GitHub workflow completed successfully.

## Evidence

`.sonol-test/runtime/portal-v04/checks.json` binds tested source hashes and command logs. Browser report, browser log and screenshots are in the same directory. `dist/portal-v0.4/manifest.json` and `SHA256SUMS` identify the new distribution; root/v0.3 manifests remain historical snapshots.

Source review checked current upstream desktop launch payload at `block/buzz` commit `e9269cbdf66b0e2fdb588aa20aad65bcba3ca622` (`desktop/src-tauri/src/commands/agents_deploy.rs`): resolved `launch` exists. The upstream remote-agent specification still contains historical draft caveats; the installed Windows app version has not been verified against that source.

## Publication verification

- All three images built on the GitHub Linux runner; disposable Compose stack started successfully. Portal UID10002, absent Docker socket, and broker RPC status were checked at runtime.
- Published release assets were downloaded without authentication; the EXE and build-context ZIP match the build manifest.
- All three digest-pinned image manifests were fetched anonymously and their SHA256 values matched the installation Compose.
- `published-assets.json` and `SHA256SUMS.published` cover the actual release downloads, including Compose. The original `manifest.json` describes the broader build output, some of which is embedded rather than separately uploaded.

## Not yet proven — release acceptance remains open

3. Existing VPS Traefik network/labels/DNS and live Relay auto-discovery.
4. Windows Buzz finds the provider, supplies the current launch contract, and deploys a real bot. Desktop subscription checks for selecting a provider must also be observed.
5. Real Codex/Claude official authentication and reauthentication through nested Docker PTYs; actual replies and persistent credentials after restart. Device-auth eligibility follows the official account settings.
6. Two AIs collaborating on one VPS workspace; no local Windows execution dependency.
7. **Windows fully powered off before a new scheduled task begins and completes**, verified by server-side timestamps/files and actual AI completion, not only Relay delivery.
8. KVM2 CPU/RAM behavior under the intended workload.

The public GitHub repository, GHCR images and candidate release were created with user approval. Existing VPS and Relay settings were not changed. No chat-supplied private key or root password was used or packaged. Web portal setup password is separate from VPS root credentials. No policy-gate receipt is claimed: the existing focused manual evidence route remains active.


## URL importer incident and correction

Observed 2026-10-09 with source 33161cd177066040304fd8fd98fa4bd3de09a9a0: Hostinger reported `Docker project not found`; project row existed with zero containers and blank YAML. No server logs were available. Exact hPanel failure cause is unknown.

Source correction removes the custom required BUZZ_SETUP_HOST and top-level project name, publishes a complete digest-pinned root docker-compose.yml at a Raw URL, and follows documented Hostinger Traefik variable/label conventions. The missing TRAEFIK_HOST case still fails explicitly; automatic platform injection is not assumed proven.

`tests/test_portal_release.py` covers canonical artifact/renderer parity and digest constraints. `scripts/verify-url-install.py` fetches exact public bytes, tests both missing and supplied platform hostname, project renaming, role boundaries, anonymous pull and ephemeral CI start. CI uses explicit fixture platform variables and is not live Hostinger importer evidence. Runtime image bytes remain unchanged from the first published candidate.

URL correction CI result: [https://github.com/volition79/buzz-agents/actions/runs/37898496077](https://github.com/volition79/buzz-agents/actions/runs/37898496077) succeeded for b841f7b670a54f66ee86022165384d2e717f6159. Downloaded Raw artifact SHA256 `5cb2294cb946e14214cd4e660a1bd94018e42128beb04975ec67976bceaf650d` (2927 bytes). Missing-platform-variable rejection, supplied/renamed platform-variable resolution, anonymous Docker image pulls, exact-artifact Compose startup, portal HTTP and broker RPC checks passed. No live Hostinger URL-import or TLS success is claimed. One independent read-only subagent review found no concrete source blocker and retained the platform-injection gap.


## Automatic bootstrap extension

User requested no domain environment input. New broker-only inspection derives a unique hostname from existing Relay metadata under one Hostinger srvNN.hstgr.cloud base. Portal checks DNS then activates a fingerprint-bound owned HTTP routing helper with the exact portal image ID. No existing Relay/Traefik is changed; custom/ambiguous/unresolved domains wait. Hostinger default-domain support only; there is no pre-bootstrap selection UI yet.

New tests cover split Relay services, missing/ambiguous metadata, wrong own identity, DNS mismatch/unavailability, activation fingerprint/foreign-container rejection, route security drift, retry and bounded actual proxy HTTP/ZIP/cookie/framing handling. Docker CI removes domain env and provisions explicitly artificial Relay/DNS metadata, exercises route creation and portal restart reuse. This does not prove hPanel import, actual TLS issuance or Windows-off AI operation.

Build CI [37901027761](https://github.com/volition79/buzz-agents/actions/runs/37901027761) passed source tests, all three image builds, zero-domain-env Docker startup, dynamic route HTTP and same-ID restart reuse; fixture Relay config was unchanged. Source image commit: 3518e79bc21afeb668edafc84ffd2baaff07be6e. Candidate images are published; exact public Raw promotion smoke follows.

Public-artifact CI [37901354005](https://github.com/volition79/buzz-agents/actions/runs/37901354005) passed for a3843e798c28ab5c78eb7418de697d0790d45ae4. Raw SHA256 `b0c0c67665c7dbb7e9e0b5fc99461a5052fa4589459ddae5024fdafd04b7216f`; exact renderer byte parity, no-env Compose resolution, anonymous pull, automatic startup/proxy/restart reuse and unchanged fixture Relay all passed. Initial image CI passed 118 Python tests plus scoped Go tests/vet. Independent reviewer identified timeout and route DNS override gaps; both were fixed with regressions before image build. Live Hostinger acceptance remains open.

## Network discovery correction

Source 9d6683aea6756fc559267805361927cc6ff656a9; CI37906214523 passed 121 Python tests and existing Go race/vet gates. Compose starts portal on its own default network without requiring any external network. Broker discovers the running official Traefik image, an unambiguous Relay routing network, entrypoints and certificate resolver from existing router labels; only own portal is connected. Shared-network and host-mode Traefik tests both pass real HTTPS forwarding with synthetic DNS/certificate. Existing services' IDs/config/network settings remain unchanged. Proxy recreation preserves route identity. Sole independent reviewer accepted this change after the proxy ID fix.

Limits: default-only TLS configuration without router labels, custom domains and ambiguous routing safely wait; no pre-bootstrap selector UI. Dynamic route lifecycle/upgrades still need separate management as documented. Public ACME validity, actual Hostinger importer, user logins and Windows-off task acceptance are not proven by CI.

Public artifact ee2ab42595318ad9e4b8c0bc46454573165c1ec3 passed CI37906666736: exact anonymous Raw byte parity, pinned image pulls, shared/host proxy HTTPS fixtures. SHA256 `0f99971770d71f9bea9c86772da2496d72b22551773284b18c86e1de9cc18956`. Independent anonymous manifest digest verification passed for all three images. This does not close the live acceptance gaps above.


## Open-button correction (current work)

The user's live Docker output and hPanel API response now confirm that the old URL
import started broker/portal and the raw routing helper. Public setup HTTPS was
also checked with normal certificate validation. This supersedes the earlier
unverified import/TLS notes for that installed candidate only. The hPanel API
still returns entrypoint_url=null for buzz-agents and excludes its raw helper;
the working Relay has a derived HTTPS entrypoint.

OPEN-01 registers setup-route through genuine Compose, using a project-named
Traefik router. Only broker changes; portal/runtime digests, URL and volumes are
preserved. Broker mounts only its own /docker/<project> directory, verifies the
canonical config_files label, parses without interpolation, compares resolved
existing services, and adds its route to that file. A checked legacy helper is
replaced with rollback and a private recovery journal. Existing Relay and Traefik
are not mutated. This is custom integration, not a claimed Hostinger builtin.

Acceptance still requires the real hPanel response to include setup-route and a
non-null entrypoint_url, then Open must reach the existing trusted HTTPS portal.
CI Compose visibility/TLS fixtures cannot prove hPanel's private selection logic.
AI authentication and the original Windows-off fresh task remain unverified.

Final broker image build [CI37912336094](https://github.com/volition79/buzz-agents/actions/runs/37912336094) passed image source a1f82117471dfbdf6d9ff0d5d413f13900da5c83: 134 Python tests, retained Go race/vet gates, new installs with shared and host-mode real Traefik, and legacy helper migration through broker-only replacement. Compose ps/down includes route; portal container identity, dollar-containing environment and existing Relay/Traefik remain unchanged. Portal/runtime image digests are retained. Sole auditor's rollback findings were corrected and regression-tested; final review found no further blocker. New broker digest: 56d45e699381baf6e79bc16934d24f64713be6b6e6a3bf21fef52f7a82df73c8. Final Raw-URL artifact smoke follows; actual hPanel Open remains unverified.


Exact public artifact ec2d9b08df3bb7e7d383eff9fa9ac3002bde4b06 passed [CI37912789643](https://github.com/volition79/buzz-agents/actions/runs/37912789643), including both real Traefik network modes, anonymous pulls and renderer byte parity. Raw SHA256: 17896cf3c0bc9a0f766f59257f9eeabefa702d06162adf3d6abece0021545f44. Independent anonymous readback hash-matched all three image manifests. Actual hPanel application/Open and Windows-off acceptance remain pending.

## Recovery/autofill candidate (2026-10-09)

Scope: fragment setup/recovery-code autofill, owner-only local control socket, retry/reconnect and state-aware Korean guidance. Tokens never come from a public issuer. The Hostinger Open URL's token delivery remains unverified; accepting a manually provided fragment is not proof of Hostinger integration.

New local evidence: 25 portal HTTP/broker tests passed, including expiring/single-use recovery, CSRF, concurrent redemption, persistence and failed-password-save preservation. Browser fixture passed fragment missing/malformed/duplicate/expired cases, immediate URL scrubbing, recovery and Windows-device state retention, desktop/mobile overflow and zero console exceptions. Docker/AI and Windows installer actions in that browser fixture are simulated, not live acceptance.

Portal-image upgrade retains only a verified same-project/same-security proxy and its immutable image. Existing configuration or identity changes are still refused. Full Docker upgrade fixture and candidate image publication must pass before the new Compose is promoted. Previous published Compose URLs do not contain these changes.

Final recovery candidate source b54f2212b70a55aeca8d9a2fd8778b88dc3e6745 passed CI37929657380. Python142, Go race/vet, real Docker new/shared and new/host proxy fixtures, legacy broker migration and portal image upgrade with persisted account/devices and unchanged proxy ID passed. The first CI failure (37928608283) was a fixture runner write to the broker's root-owned Compose file, fixed by replacing the file in the fixture-owned parent; product checks were not relaxed. CI37929001513 then passed; final candidate additionally preserves hash-verified previously published Windows providers and produces reproducible buildvcs=false binaries.

Native Windows executed 9 connect test cases (TLS fixture servers, real Windows file locking/atomic replacement/ACLs); all passed. Browser fixture and Python tests remain source-applicable. This does not prove real Buzz provider discovery, official AI authentication or Windows-off execution.

Release portal-candidate-b54f2212b70a-15-1: local and downloaded public Windows EXE bytes match, SHA256 d14af7ecf93a27a3d05fd2f89f09be08c957f6fb10422b602a8c2aec24a55c28. Install Compose renderer bytes match the release, SHA256 d31442d6109392b534a5fe1f000cca33980c4ab687c3a187fc24c83a0a0077a2. Immutable Raw source: 01d385829515df2870af5d6925e53c22a6d81183; exact-URL CI37930186525 passed anonymous download/renderer parity/image pulls and real HTTPS Compose startup in both supported proxy network modes. The source main branch can advance documentation without changing this immutable install URL.
