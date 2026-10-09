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
- First boot starts native service after auth. Intentional native exit remains stopped. Faults and guard trips remain held.
- An idle stopped/held supervisor is not equivalent to an online model. Native presence and explicit status must be distinguished.
- Same-key/same-live-config deploy is no-op. Live different config/image requires prior stop. Full pubkey ownership label fences collisions.
- Use generated project buzz-agents-v2. Do not rewrite buzz-rpka or old project/volumes. Do not use --remove-orphans.
- Each native prompt obtains one root-owned ticket, which persists rolling time-window and rolling 24h starts before forwarding.
- A prompt response releases its ticket. Error response trips this bot. Deadline uses monotonic elapsed time.
- Per-bot ticket lock only. No global prompt lock that would deadlock agent-to-agent delegation.
- Guard copies ACP messages without changing their content or choosing a target coworker.
- Counters do not claim hard cost/token caps or cover every CLI internal retry/sub-agent/background command.
- Child process group receives TERM/KILL on supervisor exit. Container exit is the last cleanup for detached descendants.
- Workspaces are private by default; an explicit group shares files without automatic writer locking.
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
