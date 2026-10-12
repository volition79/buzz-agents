# Swap helper seccomp profile

Upstream: https://raw.githubusercontent.com/moby/profiles/c936cc7b4074219137bc0bee45670f5e4618d462/seccomp/default.json

Moby profiles seccomp/v0.1.0, matching Docker28.5.1 vendor.mod.
Original SHA256: `01536f1d1df938ae611eba20d6349e0de7a99b6ecdee1549427a0b01b8301e28`

Apache-2.0; see ../buzz_agents/SWAP-SECCOMP-LICENSE. Modified for buzz-agents:
add only swapon; remove CAP_SYS_ADMIN conditional allow group (mount,
namespaces, bpf etc). Ordinary restricted clone and clone3 ENOSYS fallback
also apply with SYS_ADMIN. Default deny and other restrictions retained; no
swapoff grant. Docker CLI reads this file in the broker image.
Actual supported-host Docker execution is a pre-publication gate.
