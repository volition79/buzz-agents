# Mac connector candidate — not released

## Scope and preserved contract

Apple Silicon macOS is the first candidate target. Intel is not advertised.
Existing Windows bundle requests, provider filename, connection schema, tokens,
one-use pairing, administrator/device authority and bot execution remain unchanged.
No runtime image, Compose URL, bot identity, workspace or AI credentials
are migrated by this feature. An explicit management-only release contract skips
automatic bot reconciliation; existing general releases retain their behavior. Native Mac acceptance is still required.

## Implementation rationale (task baseline 8de6b0e)

- connect platform assets: new reason MAC-CONNECT-01; choose a native embedded
  provider at build time, retain the verified Windows predecessor catalog and
  reject unknown installed files. Mac has no approved predecessors yet.
- portal bundle/UI: new reason MAC-CONNECT-01; explicit allowlisted target with
  Windows default; unsupported/missing artifacts fail before creating a grant.
  Capabilities describe packaged artifacts, not successful native execution.
- packaging: new reason MAC-CONNECT-01; Mac artifacts are opt-in local candidates,
  separate from default Windows publication. Never send personal pairing JSON to
  a public artifact store or signing/notarization service.
- tests: new reason MAC-CONNECT-01; exercise real local HTTP auth, expiry,
  persistence, mixed Windows/Mac revocation isolation and unchanged rollout
  decisions, plus native-format and ZIP permission checks.
- release/rollout: new reason MAC-CONNECT-PRESERVE-01; explicit optional boolean
  `management_only` skips all automatic bot updates, including stopped old bots.
  Absent/false retains existing reconciliation; unknown values fail closed.
  Management compatibility and unresolved earlier rollout checks remain required.
  Preserve current runtime digest; ordinary portal-images workflow
  rebuilds runtime and promotes stable, so MUST NOT be used for this candidate.

## Build and use in an isolated environment

Run `python3 scripts/build-portal.py --with-macos` with Go available. This only
builds local unsigned candidates. Default builds exclude Mac download artifacts.
Run the candidate portal with a temporary state directory and test broker; never
point a fixture or test installer at production. The Mac ZIP has a `.command`
launcher, native executable and adjacent personal `buzz-pairing.json`.
Extract the entire ZIP; close Buzz; open the launcher and confirm your own HTTPS
endpoint. Existing healthy connections can be kept; replacing one is explicit.
Do not disable Gatekeeper or remove quarantine indiscriminately. Release signing
and notarization must be completed/verified separately from personal bundles.

## Release acceptance (all pending until recorded)

1. Exact supported Buzz/macOS version, Apple Silicon machine and downloaded
   artifact hashes recorded. Browser download, Finder extraction and launch
   verified under normal macOS security settings; Terminal-only success is not
   sufficient for an advertised double-click flow.
2. Buzz discovers `hostinger-https`; a real VPS deployment and reply succeed;
   after Mac shutdown a new mobile request completes.
3. Legacy Windows download/install and already-connected provider still work
   against the candidate server. Windows and Mac device revoke/reconnect are
   independent. No AI re-login or bot update is required by this feature.
4. Candidate images are immutable and unpublished to stable. Broker release
   contract retains the EXACT approved runtime digest and sets `management_only`
   true. Generate build arguments with `render-unified-release.py --management-only`.
   Verify the built broker embeds that flag, and old stopped/running bots and
   explicit retry are preserved. Never use a general release contract for this feature.
5. Test management update and rollback on a disposable copy, preserving project
   name, volumes, device records, bot IDs, credentials, files and lifecycle.
   Store previous management digests. Verify the actual Hostinger update journey.
6. Publish the Mac option/manual only after native acceptance. The existing pinned
   compose.stable.yaml URL can remain only if its Compose schema is sufficient.

No live VPS, hPanel update, macOS native execution, code signing, notarization or
public release is implied by a successful cross-build or local test.
