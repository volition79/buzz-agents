"""In-container setup/authentication/status; provider auth stays in the official CLI."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from .common import ToolError, crypto, clean_env
from .config import normalize, relay_url
from .native import load_config
from .policy import atomic_json, read_json


def auth(provider):
    if os.geteuid() != 0:
        raise ToolError("auth_requires_supervisor_terminal")
    with open('/native-state/auth.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ToolError('authentication_already_in_progress') from None
        return authenticate_locked(provider)


def authenticate_locked(provider):
    # Run from hPanel's root container terminal. It is ONLY the named bot's HOME.
    state = read_json(Path("/native-state/runtime.json"), {})
    if state.get("status") == "running":
        raise ToolError("stop_bot_before_authentication")
    config = load_config("/native-config/config.json")
    if provider != config["provider"]:
        raise ToolError("wrong_provider_for_this_bot")
    if os.geteuid() != 0:
        raise ToolError("auth_requires_supervisor_terminal")
    env = clean_env()
    env.update(HOME="/home/agent", USER="agent", LOGNAME="agent", NO_BROWSER="1")
    argv = (["codex-acp", "cli", "login", "--device-auth"] if provider == "codex" else
            ["claude-agent-acp", "--cli", "auth", "login", "--claudeai"])
    result = subprocess.run(argv, env=env, user=10001, group=10001, extra_groups=[], check=False)
    if result.returncode:
        raise ToolError("official_login_failed")
    atomic_json(Path("/native-state") / ("auth-" + provider + ".json"), {"official_login_returned_zero": True})
    atomic_json(Path("/native-state/runtime.json"), {"status": "ready", "reason": "explicit_login", "pubkey": config["pubkey"]})
    return {"ok": True, "note": "Native bot is rearmed after official login. Verify a real model reply."}


def security_probe():
    if os.geteuid() != 0:
        raise ToolError("security_probe_requires_container_root")
    fd, filename = tempfile.mkstemp(prefix="probe-", dir="/native-state")
    os.write(fd, b"disposable_probe_not_a_credential")
    os.close(fd)
    try:
        command = """import os,sys
assert os.geteuid()==10001
for p in [sys.argv[1], '/native-config/config.json', '/native-state/slots']:
 try:
  if os.path.isdir(p): os.listdir(p)
  else: open(p,'rb').close()
 except PermissionError: continue
 raise SystemExit(2)
print('uid_boundary_passed')
"""
        result = subprocess.run([sys.executable, "-c", command, filename], user=10001,
                                group=10001, extra_groups=[], capture_output=True, timeout=5)
        if result.returncode:
            raise ToolError("uid_boundary_failed")
        return {"ok": True, "check": "AI UID cannot read supervisor configuration/state/slot directory"}
    finally:
        Path(filename).unlink(missing_ok=True)


def automation_init(directory, relay):
    if os.geteuid() != 0:
        raise ToolError("automation_init_requires_root")
    base = Path(directory)
    if not base.is_dir() or base.is_symlink():
        raise ToolError("automation_directory_required")
    if any((base / n).exists() for n in ("config", "state")):
        raise ToolError("automation_exists_no_overwrite")
    keys = crypto("keygen")
    cfg = base / "config"
    cfg.mkdir(mode=0o700)
    state = base / "state"
    state.mkdir(mode=0o700)
    atomic_json(cfg / "config.json", {"enabled": False, "relay": relay_url(relay),
                "private_key_hex": keys["private_key"], "auth_tag": None, "schedules": []}, 0o600)
    for p in (cfg / "config.json", cfg, state):
        os.chown(p, 10001, 10001)
    return {"ok": True, "scheduler_pubkey": keys["public_key"],
            "note": "Register this identity as a Relay/channel member and explicitly allow it on target bots before enabling."}


def main():
    parser = argparse.ArgumentParser(description="Native Buzz VPS tools — no fixed workflow")
    sub = parser.add_subparsers(dest="op", required=True)
    sub.add_parser("validate")
    sub.add_parser("status")
    sub.add_parser("security-check")
    sub.add_parser("auth").add_argument("provider", choices=("codex", "claude"))
    init = sub.add_parser("automation-init")
    init.add_argument("directory")
    init.add_argument("--relay", required=True)
    args = parser.parse_args()
    if args.op == "validate":
        raw = sys.stdin.buffer.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024:
            raise ToolError("request_too_large")
        data = json.loads(raw)
        return normalize(data["agent"], data.get("provider_config", {}), data["owner"], data["relay"])
    if args.op == "status":
        return read_json(Path("/native-state/runtime.json"), {"status": "not_started"})
    if args.op == "auth":
        return auth(args.provider)
    if args.op == "security-check":
        return security_probe()
    if args.op == "automation-init":
        return automation_init(args.directory, args.relay)


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except ToolError as error:
        print(json.dumps({"ok": False, "error": str(error)}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({"ok": False, "error": "operation_failed"}))
        raise SystemExit(1)
