# Runtime guard recovery verification — 2026-10-10

Approved scope: local implementation and validation, not publication or VPS changes.
Baseline: d1a887eb422ed0dcc24e37b700863670d0917866 with pre-existing mobile changes.
Authoring: Linux/WSL. Product: Ubuntu Docker with Codex/Claude ACP, Windows providers.

## Root cause and boundaries

The observed `turn_window_limit` was a permanent wrapper latch even after its
rolling window expired. Successful requests and upstream retries shared that
mandatory budget. Upstream already owns failure retry/backoff and idle/hard
limits. New budgets default to disabled; explicit budgets expire without killing
the bot. Quota accounting remains durable when enabled. Historical configuration
intent cannot be inferred, so existing values remain until explicit redeploy.

The observed generic `runtime_protocol_failed` did not retain enough information
to determine its historical cause. The wrapper's 4MiB cap differed from pinned
upstream's 10,000,000-byte cap and measured a read buffer before splitting frames.
Both defects are corrected; neither is claimed as the proven live root cause.
Distinct bounded JSON/shape/size/transport/backpressure/cleanup codes replace that
ambiguity without exposing raw prompts, credentials or adapter output.

## Evidence scope

- Whole local Python suite: 240 tests passed before final cleanup-watchdog addition.
- Final focused replay: 84 passed and one lock-cleanup failure; after the fix,
  all 35 native/host tests passed. Other focused tests remained unchanged.
- Both Go providers: `go test ./...` passed including public configuration schemas.
- Browser i18n check: Korean/English/fallback, desktop/mobile viewports, zero console errors.
- Real local guard processes use fake adapters for both supported command names:
  105 successful prompts, explicit quota rejection then expiry, 5MiB frames,
  malformed JSON redaction, child-group cleanup and safe slot reclamation.
- Deterministic replay covers legacy hold expiry, auth preservation, simultaneous
  workers, official-duration grace, and root cleanup-integrity fallback.

Tests proving permanent quota latching or bot-wide ordinary deadlines were updated
for the approved behavior. Auth, ownership, process-cleanup and quota-storage
failure protections remain. These are local fixtures, not actual provider runs.
CodeMap is navigation evidence; Sonol Test workflow used the project's existing
manual command fallback (empty registered lanes), not a managed gate receipt.
There is no project policy pack and no validator allow receipt is claimed.

## Remaining acceptance

Publish/rebuild runtime and provider artifacts, then update existing bots with
the administrator portal action documented in EXISTING-BOT-UPDATE.md. Existing configured limits need explicit review; see
DEPLOYMENT.md. Validate actual Claude/Codex tasks and Windows-off operation on
VPS. No such deployment, subscription login or paid inference occurred here.
