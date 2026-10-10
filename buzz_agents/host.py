"""Restricted SSH receiver on the VPS host. It alone uses Docker, never the AI."""
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
from .common import ToolError
from .config import HEX, normalize
from .diagnostics import validation_error
from .policy import atomic_json, read_json

SETTINGS = Path("/opt/buzz-agents/host/settings.json")
MANAGED = "buzz-agents-native-v2"


def execute(argv, data=None, timeout=90, validation_response=False):
    try:
        result = subprocess.run(argv, input=None if data is None else json.dumps(data).encode(),
                                capture_output=True, timeout=timeout, check=False,
                                env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root"})
    except (OSError, subprocess.TimeoutExpired):
        raise ToolError("host_command_failed_or_timed_out") from None
    if result.returncode:
        code = validation_error(result.stdout) if validation_response and len(result.stdout) <= 512 * 1024 else None
        raise ToolError(code or "host_command_failed")
    if len(result.stdout) > 2 * 1024 * 1024:
        raise ToolError("host_response_too_large")
    return result.stdout


def host_capacity(runner=execute):
    """Docker daemon capacity, not the broker container's cgroup allowance."""
    try:
        value = json.loads(runner(["docker", "info", "--format", "{{json .}}"], timeout=20))
        cpus, memory = value["NCPU"], value["MemTotal"]
        if type(cpus) is not int or cpus < 1 or type(memory) is not int or memory < 1:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise ToolError("host_capacity_unavailable") from None
    memory_mb = memory // (1024 * 1024)
    reserve_mb = max(2048, (memory_mb + 3) // 4)
    return {"cpus": cpus, "memory_mb": memory_mb,
            "reserve_mb": reserve_mb, "budget_mb": max(0, memory_mb - reserve_mb)}


def check_resources(config, registry, settings, capacity):
    max_bots = settings.get("max_bots")
    if max_bots is not None:
        if type(max_bots) is not int or max_bots < 1:
            raise ToolError("invalid_host_settings")
        if config["pubkey"] not in registry and len(registry) >= max_bots:
            raise ToolError("registered_bot_limit")
    if config["cpus"] > capacity["cpus"]:
        raise ToolError("requested_cpu_exceeds_host")
    budget = settings.get("memory_budget_mb", capacity["budget_mb"])
    if type(budget) is not int or budget < 1:
        raise ToolError("host_memory_reserve_exhausted" if budget == 0 else "invalid_host_settings")
    # Explicit budgets are preserved, but never promise more than physical RAM
    # minus the documented OS/Relay reserve after a host downgrade.
    budget = min(budget, capacity["budget_mb"])
    memory = config["memory_mb"] + sum(c["memory_mb"] for k, c in registry.items() if k != config["pubkey"])
    if memory > budget:
        raise ToolError("aggregate_memory_budget_exceeded")


def inspect_container(name):
    # Missing container is expected. A daemon error must not be treated as absence.
    raw = execute(["docker", "container", "ls", "-a", "--filter", "name=^/" + name + "$", "--format", "{{.ID}}"])
    if not raw.strip():
        return None
    data = execute(["docker", "inspect", "--type", "container", name])
    return json.loads(data)[0]


def private_directory(path, uid=0):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    st = path.lstat()
    if not stat.S_ISDIR(st.st_mode) or path.is_symlink():
        raise ToolError("unsafe_host_directory")
    os.chown(path, uid, uid)
    os.chmod(path, 0o700)


def labels(config):
    return {"io.buzz-agents.managed": MANAGED, "io.buzz-agents.pubkey": config["pubkey"],
            "io.buzz-agents.fingerprint": config["fingerprint"]}


def container_name(pubkey):
    return "buzz-native-" + pubkey[:20]


def service_name(pubkey):
    return "bot-" + pubkey[:20]


def process_limit(config):
    """Finite headroom for eager ACP workers, review agents and child commands.

    128 shared + 64 per worker is a conservative initial policy, not a measured
    guarantee for arbitrary workloads. Legacy registry entries keep their 256
    until explicitly redeployed with normalized worker settings.
    """
    workers = config.get("parallelism")
    if "env" in config:
        workers = config["env"].get("BUZZ_ACP_AGENTS", "1")
    if workers is None:
        return 256
    if isinstance(workers, str) and workers.isascii() and workers.isdigit():
        workers = int(workers)
    if type(workers) is not int or not 1 <= workers <= 32:
        raise ToolError("invalid_agent_parallelism")
    return max(256, 128 + 64 * workers)


def process_limit_matches(container, config):
    actual = container.get("HostConfig", {}).get("PidsLimit")
    return type(actual) is int and actual == process_limit(config)


def service(config, settings):
    root = Path(settings["state_dir"])
    folder = root / "bots" / config["pubkey"]
    def bind(source, target, readonly=False):
        return {"type": "bind", "source": str(source), "target": target,
                "read_only": readonly, "bind": {"create_host_path": False}}
    return {
        "image": settings["image"], "pull_policy": "never",
        "container_name": container_name(config["pubkey"]), "labels": labels(config),
        "command": ["python", "-m", "buzz_agents.native"], "user": "0:0",
        "init": True, "restart": "unless-stopped", "read_only": True,
        "cap_drop": ["ALL"], "cap_add": ["SETUID", "SETGID", "KILL", "CHOWN", "DAC_OVERRIDE"],
        "security_opt": ["no-new-privileges:true"], "stop_grace_period": "75s",
        "cpus": config["cpus"], "mem_limit": f"{config['memory_mb']}m",
        "memswap_limit": f"{config['memory_mb']}m", "pids_limit": process_limit(config),
        "tmpfs": ["/tmp:size=128m,mode=1777,nosuid,nodev"],
        "environment": {"PYTHONPATH": "/app", "PYTHONDONTWRITEBYTECODE": "1"},
        "volumes": [bind(folder / "config", "/native-config", True),
                    bind(folder / "state", "/native-state"),
                    bind(folder / "home" / config["provider"], "/home/agent"),
                    bind(root / "workspaces" / config["workspace"], "/workspace")],
        "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
        # No ports, Docker socket, host PID/network, privileged mode or existing Relay volumes.
    }


def compose_document(registry, settings):
    return {"name": "buzz-agents-v2", "services": {
        service_name(c["pubkey"]): service(c, settings) for c in registry.values()}}


def check_ownership(container, config):
    actual = container.get("Config", {}).get("Labels") or {}
    if actual.get("io.buzz-agents.managed") != MANAGED or actual.get("io.buzz-agents.pubkey") != config["pubkey"]:
        raise ToolError("container_name_collision_no_changes_made")


def public_record(config):
    record = {k: config[k] for k in ("schema", "name", "pubkey", "provider", "workspace", "memory_mb", "cpus", "policy", "fingerprint")}
    record["parallelism"] = int(config["env"].get("BUZZ_ACP_AGENTS", "1"))
    return record


class Deployer:
    def __init__(self, settings, runner=execute, inspector=inspect_container, normalizer=None):
        self.settings, self.run, self.inspect = settings, runner, inspector
        self.root = Path(settings["state_dir"])
        self.normalizer = normalizer or self.normalize_in_image

    def normalize_in_image(self, request):
        raw = self.run(["docker", "run", "--rm", "--network", "none", "--read-only",
                        "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "-i",
                        "--entrypoint", "python", self.settings["image"], "-m", "buzz_agents.cli", "validate"],
                        {"agent": request["agent"], "provider_config": request.get("provider_config", {}),
                         "owner": self.settings["owner"], "relay": self.settings["relay"]}, validation_response=True)
        # This reply contains the agent's secret: it is NEVER sent to the desktop/logs.
        value = json.loads(raw)
        if value.get("ok") is False:
            raise ToolError(value.get("error", "invalid_payload"))
        return value

    def deploy(self, request):
        image = json.loads(self.run(["docker", "image", "inspect", self.settings["image"]]))[0]
        if image["Id"] != self.settings["image_id"]:
            raise ToolError("image_changed_revalidate_before_deploy")
        config = self.normalizer(request)
        if not HEX.fullmatch(config.get("pubkey", "")):
            raise ToolError("invalid_normalized_identity")
        private_directory(self.root)
        lock = os.open(self.root / "deploy.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            return self._deploy_locked(config)
        finally:
            os.close(lock)

    def retire(self, pubkey):
        if not HEX.fullmatch(pubkey):
            raise ToolError("invalid_bot_public_key")
        lock = os.open(self.root / "deploy.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            registry = read_json(self.root / "registry.json", {})
            config = registry.get(pubkey)
            if config is None:
                raise ToolError("bot_not_registered")
            actual = self.inspect(container_name(pubkey))
            if actual:
                check_ownership(actual, config)
                state = read_json(self.root / "bots" / pubkey / "state" / "runtime.json", {})
                if actual.get("State", {}).get("Running") and state.get("status") not in ("stopped", "held", "needs_login"):
                    raise ToolError("stop_native_bot_before_retiring")
                self.run(["docker", "stop", "--time", "70", container_name(pubkey)], timeout=80)
                self.run(["docker", "rm", container_name(pubkey)])
            del registry[pubkey]
            atomic_json(self.root / "registry.json", registry)
            atomic_json(self.root / "compose.yaml", compose_document(registry, self.settings))
            return {"ok": True, "retired": pubkey, "data_preserved": True}
        finally:
            os.close(lock)

    def _deploy_locked(self, config):
        registry = read_json(self.root / "registry.json", {})
        pubkey = config["pubkey"]
        folder = self.root / "bots" / pubkey
        name = container_name(pubkey)
        actual = self.inspect(name)
        if actual:
            check_ownership(actual, config)
            state = read_json(folder / "state" / "runtime.json", {})
            running = actual.get("State", {}).get("Running", False)
            if running and state.get("status") not in ("stopped", "held", "needs_login"):
                if actual.get("Image") != self.settings["image_id"]:
                    raise ToolError("stop_native_bot_before_image_upgrade")
                if not process_limit_matches(actual, config):
                    raise ToolError("stop_native_bot_before_resource_upgrade")
                if pubkey in registry and registry[pubkey]["fingerprint"] == config["fingerprint"]:
                    return {"ok": True, "agent_id": name, "action": "already_deployed"}
                raise ToolError("stop_native_bot_before_changing_settings")
        check_resources(config, registry, self.settings, host_capacity(self.run))
        if actual:
            # Previous container must fully stop before state/config can be replaced.
            self.run(["docker", "stop", "--time", "70", name], timeout=80)
        for path in (folder, folder / "config", folder / "state", folder / "state" / "slots"):
            private_directory(path)
        private_directory(folder / "home")
        private_directory(folder / "home" / config["provider"], 10001)
        private_directory(self.root / "workspaces" / config["workspace"], 10001)
        atomic_json(folder / "config" / "config.json", config, 0o400)
        # Keep quota counters across explicit redeploys; no silent budget reset.
        atomic_json(folder / "state" / "runtime.json", {"status": "ready", "reason": "explicit_deploy", "pubkey": pubkey})
        registry[pubkey] = public_record(config)
        atomic_json(self.root / "registry.json", registry)
        manifest = compose_document(registry, self.settings)
        atomic_json(self.root / "compose.yaml", manifest)
        self.run(["docker", "compose", "-p", "buzz-agents-v2", "-f", str(self.root / "compose.yaml"),
                  "up", "-d", "--no-deps", "--force-recreate", service_name(pubkey)], timeout=180)
        actual = self.inspect(name)
        if actual is None or not actual.get("State", {}).get("Running"):
            raise ToolError("deployment_not_running_inspect_host")
        check_ownership(actual, config)
        if not process_limit_matches(actual, config):
            raise ToolError("deployment_resource_limit_mismatch")
        return {"ok": True, "agent_id": name, "action": "deployed",
                "note": "Deployment is not proof of subscription authentication or model health."}


def load_settings(path=SETTINGS):
    st = path.lstat()
    if st.st_uid != 0 or st.st_mode & 0o022 or not stat.S_ISREG(st.st_mode):
        raise ToolError("host_settings_permissions")
    settings = read_json(path)
    if not HEX.fullmatch(settings.get("owner", "")) or not re.fullmatch(r"sha256:[0-9a-f]{64}", settings.get("image_id", "")):
        raise ToolError("invalid_host_settings")
    if settings.get("state_dir") != "/var/lib/buzz-agents-v2":
        raise ToolError("unexpected_state_directory")
    return settings


def main():
    if os.geteuid() != 0:
        raise ToolError("host_receiver_requires_root_via_restricted_sudo")
    settings = load_settings()
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        registry = read_json(Path(settings["state_dir"]) / "registry.json", {})
        return {key: {**value, "runtime": read_json(Path(settings["state_dir"]) / "bots" / key / "state" / "runtime.json", {})}
                for key, value in registry.items()}
    if len(sys.argv) == 4 and sys.argv[1] == "retire" and sys.argv[3] == "--confirm-stopped":
        return Deployer(settings).retire(sys.argv[2])
    raw = sys.stdin.buffer.read(512 * 1024 + 1)
    if len(raw) > 512 * 1024:
        raise ToolError("request_too_large")
    request = json.loads(raw)
    if not isinstance(request, dict) or request.get("op") != "deploy" or "agent" not in request:
        raise ToolError("only_deploy_is_allowed")
    return Deployer(settings).deploy(request)


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except ToolError as exc:
        # Only fixed codes originate from our validator; do not dump Docker stderr.
        code = str(exc)
        if not re.fullmatch(r"[a-zA-Z0-9_]{1,160}", code):
            code = "host_request_failed"
        print(json.dumps({"ok": False, "error": code}))
        raise SystemExit(1)
    except Exception:
        print(json.dumps({"ok": False, "error": "host_request_failed_check_local_state"}))
        raise SystemExit(1)
