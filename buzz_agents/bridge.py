"""Forced SSH command boundary. Never execute an arbitrary SSH command."""
import json
import fcntl
import os
from pathlib import Path
import re
import subprocess
import sys
from .common import ToolError
from .host import load_settings, inspect_container, check_ownership, container_name, main as deploy
from .policy import read_json


def parse_command(command):
    if command == "buzz-agents-receive":
        return ("deploy",)
    if command == "buzz-agents-status":
        return ("status",)
    if command in ("buzz-agents-schedule-init", "buzz-agents-schedule-save", "buzz-agents-schedule-disable"):
        return (command.removeprefix("buzz-agents-"),)
    match = re.fullmatch(r"buzz-agents-auth (codex|claude) ([0-9a-f]{64})", command)
    if match:
        return ("auth", *match.groups())
    raise ToolError("unsupported_ssh_operation")


def bot_records(settings):
    root = Path(settings["state_dir"])
    registry = read_json(root / "registry.json", {})
    records = []
    for pubkey, item in sorted(registry.items()):
        if not re.fullmatch(r"[0-9a-f]{64}", pubkey):
            raise ToolError("invalid_registry")
        state = read_json(root / "bots" / pubkey / "state" / "runtime.json", {})
        actual = inspect_container(container_name(pubkey))
        if actual:
            check_ownership(actual, item)
        records.append({"pubkey": pubkey, "name": item["name"], "provider": item["provider"],
                        "status": state.get("status", "unknown"),
                        "container_running": bool(actual and actual.get("State", {}).get("Running"))})
    return records


def authenticate(settings, provider, pubkey):
    registry = read_json(Path(settings["state_dir"]) / "registry.json", {})
    item = registry.get(pubkey)
    if not item or item.get("provider") != provider:
        raise ToolError("unknown_bot_or_wrong_provider")
    actual = inspect_container(container_name(pubkey))
    if not actual or not actual.get("State", {}).get("Running"):
        raise ToolError("bot_container_not_running")
    check_ownership(actual, item)
    # This is the only permitted exec command. No user-controlled path or argv.
    if not sys.stdin.isatty():
        raise ToolError("authentication_requires_terminal")
    result = subprocess.run(["docker", "exec", "-it", "--user", "0:0", container_name(pubkey),
                             "python", "-m", "buzz_agents.cli", "auth", provider], check=False)
    if result.returncode:
        raise ToolError("remote_authentication_failed")
    return {"ok": True, "note": "Login completed on VPS; verify an actual model reply in Buzz."}


def main(command=None):
    operation = parse_command(command if command is not None else (sys.argv[1] if len(sys.argv) == 2 else ""))
    if os.geteuid() != 0:
        raise ToolError("bridge_requires_restricted_sudo")
    if operation[0] == "deploy":
        # host.main understands only a JSON deploy on stdin, not bridge argv.
        sys.argv = [sys.argv[0]]
        return deploy()
    settings = load_settings()
    if operation[0] == "status":
        return {"ok": True, "version": "0.3.0", "bots": bot_records(settings)}
    if operation[0].startswith("schedule-"):
        from . import easy_schedule
        with open('/run/buzz-agents-easy-schedule.lock', 'w') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ToolError('scheduler_setup_in_progress') from None
            if operation[0] == "schedule-init":
                return easy_schedule.initialize(settings)
            if operation[0] == "schedule-disable":
                return easy_schedule.disable()
            raw = sys.stdin.buffer.read(32769)
            if len(raw) > 32768:
                raise ToolError("schedule_request_too_large")
            return easy_schedule.configure(settings, json.loads(raw))
    return authenticate(settings, *operation[1:])


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except ToolError as error:
        code = str(error)
        print(json.dumps({"ok": False, "error": code if re.fullmatch(r"[a-zA-Z0-9_]{1,160}", code) else "bridge_failed"}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({"ok": False, "error": "bridge_failed_check_server"}))
        raise SystemExit(1)
