# v0.4 Docker portal — verification boundary

Local development candidate, 2026-10-09. No live Hostinger deployment or publication was performed.

## Passed

- Python: 107 tests (105-test suite plus 2 release-render tests), including all retained native/config/guard/scheduler/SSH tests and 19 new portal/broker/auth tests. Total with Go: 133.
- Go: 26 tests (legacy provider 9, legacy setup 7, HTTPS provider 6, HTTPS connect 4), with race detector; all four modules pass vet.
- JavaScript syntax; real Chrome 140 at 1440×1120 and 390×844, no captured runtime exceptions and no mobile horizontal overflow.
- Browser exercised real local HTTP claim, automatic Relay-prefill confirmation, connection ZIP download, one-use pairing, scoped device deploy request, bot list, login text input/cancel. **Docker broker / official login responses in browser test are explicit fixtures.**
- Real local PTY input/completion; login process-group timeout; cancellation before startup and wrong-session cancellation.
- Actual Windows x64 HTTPS provider executable answered `info` with protocol 1 and version 0.4.0. This does not prove Buzz discovery or Windows connection installation.
- Official Docker Compose 2.40.3 `config --quiet` accepted the template with test image/host values. CLI artifact SHA256 matched the Docker official image history.
- Docker CLI 28.5.1 manifest resolved and pinned to `sha256:9190b0613792e658a7783cf14b2d5ace5941bb68ede7276922ea36ee457d76ad`; image history confirms the copied Compose plugin path.
- Prepared manual-only CI publication workflow and digest-only Compose renderer; mutable tags/injected strings are rejected in renderer tests. Workflow execution is not yet verified.

## Evidence

`.sonol-test/runtime/portal-v04/checks.json` binds tested source hashes and command logs. Browser report, browser log and screenshots are in the same directory. `dist/portal-v0.4/manifest.json` and `SHA256SUMS` identify the new distribution; root/v0.3 manifests remain historical snapshots.

Source review checked current upstream desktop launch payload at `block/buzz` commit `e9269cbdf66b0e2fdb588aa20aad65bcba3ca622` (`desktop/src-tauri/src/commands/agents_deploy.rs`): resolved `launch` exists. The upstream remote-agent specification still contains historical draft caveats; the installed Windows app version has not been verified against that source.

## Not yet proven — release acceptance remains open

1. Docker image builds and actual Compose start on Linux: authoring environment has no Docker daemon. Compose schema validation is not an image build or privilege-boundary runtime test.
2. Published immutable image digests and a public Compose installation URL.
3. Existing VPS Traefik network/labels/DNS and live Relay auto-discovery.
4. Windows Buzz finds the provider, supplies the current launch contract, and deploys a real bot. Desktop subscription checks for selecting a provider must also be observed.
5. Real Codex/Claude official authentication and reauthentication through nested Docker PTYs; actual replies and persistent credentials after restart. Device-auth eligibility follows the official account settings.
6. Two AIs collaborating on one VPS workspace; no local Windows execution dependency.
7. **Windows fully powered off before a new scheduled task begins and completes**, verified by server-side timestamps/files and actual AI completion, not only Relay delivery.
8. KVM2 CPU/RAM behavior under the intended workload.

No external settings were changed. No chat-supplied private key or root password was used or packaged. Web portal setup password is separate from VPS root credentials. No policy-gate receipt is claimed: the existing focused manual evidence route remains active.
