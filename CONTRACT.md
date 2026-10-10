# v0.2 native execution contract

- Native conversational `buzz-acp` is the runtime. No `run --task` execution path, stage list, fixed role order or provider pool.
- A desktop v1 info/deploy backend transports the full resolved launch payload over OpenSSH stdin.
- Require launch.command in {codex-acp,claude-agent-acp}, empty args, correct owner/Relay, nonempty bot identity and matching public key.
- Unknown environment and provider configuration keys are errors. No alternate provider API keys/base URLs or arbitrary shell commands.
- The human secret is never needed. The trusted desktop signs a bot owner attestation; Relay validates that attestation cryptographically.
- Host owns Docker access. No Docker socket/host namespaces/management TCP port in agent containers.
- Each bot gets an independent container, protected root config/state and a UID10001 auth home.
- Initially needs_login. Official login as UID10001 returns; root records authorization to start.
- Agent credentials remain with official CLI; no credential copying among bots or custom OAuth refresh implementation.
- First boot starts native service after auth. Intentional native exit remains stopped. Integrity/cleanup faults remain held; expired legacy quota holds may self-rearm.
- An idle stopped/held supervisor is not equivalent to an online model. Native presence and explicit status must be distinguished.
- Same-key/same-live-config deploy is no-op. Live different config/image requires prior stop. Full pubkey ownership label fences collisions.
- Use generated project buzz-agents-v2. Do not rewrite buzz-rpka or old project/volumes. Do not use --remove-orphans.
- Each native prompt obtains one root-owned ticket, which persists enabled rolling time-window/24h budgets before forwarding; disabled budgets do not accumulate starts.
- A prompt response releases its ticket. An application error releases only that worker; a failed adapter releases tickets after it dies. Budget rejection affects only that request and expires automatically. Storage/cleanup integrity violations still hold the bot. Official turn deadlines run first; a monotonic guard-local watchdog allows an additional 120 seconds before stopping only that worker.
- Per-bot ticket lock only. No global prompt lock that would deadlock agent-to-agent delegation.
- Guard copies ACP messages without changing their content or choosing a target coworker.
- Counters do not claim hard cost/token caps or cover every CLI internal retry/sub-agent/background command.
- Child process group receives TERM/KILL on supervisor exit. Container exit is the last cleanup for detached descendants.
- The default workspace group is team, matching the desktop schema; choose distinct group names for separate files. Shared files have no automatic writer locking.
- Optional scheduler posts one native mention, records prepared before send, and never labels Relay delivery as task completion.
- Duplicate occurrence delivery is avoided; ambiguous sends are held unknown, not automatically retried with new events.
- Source/unit/proxy/SSH-mock tests are not an end-to-end Hostinger deployment proof.

## v0.4 portal transport addition

- Each person first creates their own Windows Buzz identity and private Relay with their public owner key. Do not request/import the human nsec or root password.
- HTTPS desktop backend carries the same complete launch payload. Existing SSH backend remains a separate legacy path.
- Initial portal claim requires a random expiring code from Docker logs and creates a separate hashed settings password.
- Browser administrator sessions, one-use expiring pairing grants, and persistent revocable deploy-only Windows credentials have separate authority.
- Only the network-disabled broker gets Docker socket authority; broker is still host-equivalent trusted infrastructure. No socket/host-management access in portal or AI containers.
- Broker receives a closed RPC operation set. Image reference, mount paths and process argv are not client-controlled.
- Login uses a bounded process group in the named bot. Input/output are admin-only, memory-only; credentials remain in official CLI home. Cancellation is bound to one login generation, including cancellation before process startup.
- Detection of existing owner public key is configuration discovery, not a new cryptographic proof of human ownership. Relay still validates bot owner attestations.
- A current upstream draft is not proof of an installed Buzz version. Real Windows discovery/deploy remains an acceptance gate.

## 2026-10-10 launch contract corrections

- Reference desktop source: block/buzz 326e2301cb4b1edcb8a72d01ac4b19a83545365f. Bundled runtime remains 4db7bb0e7f904b2f0ea232aacae6cd7f6b8a3b39; this is not proof of every installed desktop version.
- Preserve explicit dedup/steering settings; leave absent values to native defaults. Safe locale fields LANG/LC_ALL/TZ and BUZZ_ACP_MEMORY are supported. Arbitrary executable/provider credential environment is still refused.
- Replay floor is invocation-only, excluded from config fingerprint, and consumed before first process spawn. Login preserves the consumption marker. Graceful restart does not reapply it; forced or nonzero shutdown remains held; abnormal restart remains held. Each native spawn gets a fresh start nonce.
- Active cancellation retains its ticket until the final ACP response. Control, steering, permissions and session notifications pass unchanged.
- Native shutdown allows up to 60 seconds while draining output, followed by process-group cleanup; Docker provides 75 seconds. No guarantee that a remote model honors cancellation.
- Logs contain fixed diagnostic categories and runtime exit state, never raw prompts, credentials, model IDs or adapter output. Categories are hints from observed output, not proof of root cause. Unknown failures remain generic.
- Live access-policy/model/launch changes require stopping the bot before redeploy. Official automatic access refresh may be refused until that stop; hot policy updates are not supported.
- Only codex-acp and claude-agent-acp with empty custom argv are supported. Relay mesh, public anyone mode and missing owner attestation remain deliberately refused.
- Build the runtime alongside portal/broker when publishing this change. A portal-only release with the old runtime digest cannot deliver these runtime corrections.
- End-to-end acceptance still requires real remote login, task completion and a new task after Windows is fully off. Local test results do not replace that acceptance.

- Resource policy host-v1 reads Docker daemon capacity on each deployment. Reserve max(2048MiB, 25% RAM) for OS/Relay; registered memory limits must fit the remainder. This reserve is a conservative allowance, not measurement of all other workloads. Per-bot CPU cannot exceed host CPU; aggregate CPU time-sharing is allowed.
- New installations have no fixed eight-bot cap. Custom memory/bot limits remain honored. Legacy settings with exactly 5120MiB and 8 bots migrate as old generated defaults unless resource_policy=fixed. Historical files cannot distinguish a manually chosen identical pair.
- Broker may select an updated runtime image after title/ID validation. Existing running bot containers are not automatically replaced. Stop and redeploy each bot to adopt the candidate image.

## 2026-10-10 pre-deployment review corrections

- Keep each adapter and its ordinary descendants in the guard process group created by upstream Buzz. Upstream group SIGKILL must reach all of them; finally handlers cannot protect against SIGKILL. Standalone guard invocation first isolates its own group.
- For ordinary adapter failure, Linux /proc group inspection and pidfd signaling clean only that guard's remaining peers before ticket release. Cleanup failure holds the bot; arbitrary processes that deliberately escape the group still require container cleanup. Image preflight checks pidfd capability.
- Preserve the last categorical diagnosis on held/stopped/needs-login restarts. Clear it only at a new native launch, so old errors do not falsely describe a new attempt.

- Broker binds worker tickets to Unix peer credentials and pidfds. After abrupt worker death, reclaim only once its process group has no live members; charged starts remain durable. Live descendants retain the slot until verified cleanup.
- Login capacity counts only running sessions (maximum eight); completed output history is bounded and evicted PTY readers are stopped. Both supported providers share this behavior.
- Release rendering verifies existing artifacts, adds final compose.install.yaml to manifest and SHA256SUMS, and verifies all listed files again before publication.

- Failed expired-login cancellation retains that running session and its capacity; never infer remote termination from a Docker error. Other sessions proceed; later requests retry cleanup after 30 seconds. Expired sessions refuse input.
- Candidate publication derives every asset argument from the verified manifest and includes manifest/SHA256SUMS themselves; no separately maintained upload list.

- Browser login expiry resets only the matching session on an explicit server expiry response. Transient errors preserve the session, old responses cannot clear a newer session, and cancellation of an absent session is idempotent.


## Runtime recovery revision (2026-10-10)

Default prompt budgets are opt-in (0 disables), idle timeout is 1500s and hard
turn duration is 7200s. Stored legacy configuration is preserved, not guessed.
Only held turn_window_limit/daily_start_limit states may self-rearm when their
stored allowance permits and the clock has not rolled back; auth checks still run.
Never replay a discarded upstream request or auto-reset other stop/fault states.
ACP frame size matches pinned buzz-acp: 10,000,000 bytes per newline-delimited
frame. Combined reads do not count as one frame. Bounded output and classified
JSON/shape/size/transport/cleanup failures keep raw content out of logs.

A ticket remaining 30s after the guard-local watchdog deadline is a cleanup
integrity failure (worker_cleanup_timeout), which retains the whole-container
safety hold. It is not charged as normal-work exhaustion. Clock rollback and
storage faults remain explicit; successful semantic loops are not inferred.
