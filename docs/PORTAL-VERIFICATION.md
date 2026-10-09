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
