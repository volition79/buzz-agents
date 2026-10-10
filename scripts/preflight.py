"""Build/runtime capability probes; never calls a model or authenticates a user."""
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from buzz_agents.common import bounded, ToolError, crypto


def run(argv):
    code, data, _ = bounded(argv, timeout=45, limit=2*1024*1024)
    if code:
        raise ToolError("capability_probe_failed")
    return data.decode("utf-8", "replace")


def main():
    # Guard cleanup pins process identities using Linux pidfds. Fail the image
    # capability probe rather than discovering missing support during a task.
    fd = os.pidfd_open(os.getpid())
    try:
        signal.pidfd_send_signal(fd, 0)
        Path("/proc/self/stat").read_text()
    finally:
        os.close(fd)
    native = run(["buzz-acp", "--help"])
    for flag in ("--agent-command", "--agent-args", "--respond-to", "--max-turn-duration", "--session-policy"):
        if flag not in native:
            raise ToolError("native_buzz_capability_missing")
    versions = {"node": run(["node", "--version"]).strip(),
        "codex_adapter": run(["codex-acp", "--version"]).strip(),
        "claude_adapter": run(["claude-agent-acp", "--version"]).strip(),
        "codex_cli": run(["codex-acp", "cli", "-V"]).strip(),
        "claude_cli": run(["claude-agent-acp", "--cli", "--version"]).strip()}
    key = crypto("keygen")
    if crypto("public", key["private_key"]) != key["public_key"]:
        raise ToolError("identity_probe_failed")
    del key
    inventory = json.loads(run(["npm", "ls", "--global", "--all", "--json"]))
    return {"schema": 2, "native_service": True, "versions": versions, "npm": inventory,
            "note": "Capability checks only; no live Relay, subscription, desktop provider, or VPS test."}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False, indent=2))
