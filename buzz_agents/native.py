"""One native buzz-acp process per container. Clean stops persist across restarts."""
import fcntl
import json
import logging
import os
from pathlib import Path
import selectors
import secrets
import signal
import stat
import subprocess
import threading
import time
from .common import ToolError, clean_env
from .policy import Policy, Broker, atomic_json, read_json
from .diagnostics import RuntimeDiagnostics

UID = 10001


def load_config(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if info.st_uid != 0 or info.st_mode & 0o077 or not stat.S_ISREG(info.st_mode):
            raise ToolError("private_config_permissions")
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ToolError("config_too_large")
    return json.loads(data)


def runtime_parallelism(config):
    # Existing configs without an explicit pool size retain their old limit.
    value = config["env"].get("BUZZ_ACP_AGENTS", "1")
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 32:
        raise ToolError("invalid_parallelism")
    return int(value)


def runtime_env(config, socket_path, startup_consumed=True):
    env = clean_env()
    env.update(config["env"])
    env.pop("BUZZ_ACP_REPLAY_FLOOR", None)
    if not startup_consumed:
        env.update(config.get("startup_env", {}))
    env["BUZZ_MANAGED_AGENT_START_NONCE"] = secrets.token_hex(16)
    env.update(BUZZ_ACP_AGENTS=str(runtime_parallelism(config)), HOME="/home/agent", USER="agent", LOGNAME="agent", PYTHONPATH="/app",
               NO_BROWSER="1", BUZZ_ACP_AGENT_COMMAND="/app/guard-bin/" + config["command"],
               BUZZ_ACP_AGENT_ARGS="", BUZZ_NATIVE_COMMAND=config["command"],
               BUZZ_GUARD_SOCKET=str(socket_path), PYTHONDONTWRITEBYTECODE="1")
    return env


def stop_group(process, grace=60, drain=None):
    """Allow native shutdown to finish while draining its bounded output pipes."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + grace
    while process.poll() is None and time.monotonic() < deadline:
        if drain:
            drain()
        else:
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
    # Reap remaining descendants even when the group leader has already exited.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)


def state_on_start(previous):
    if previous is None or previous.get("status") == "ready":
        return "ready", ""
    if previous.get("status") == "running":
        return "held", "unexpected_container_restart"
    return previous.get("status", "held"), previous.get("reason", "operator_action_required")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if os.geteuid() != 0:
        raise ToolError("supervisor_requires_limited_container_root")
    state_dir = Path(os.environ.get("NATIVE_STATE", "/native-state"))
    config = load_config(os.environ.get("NATIVE_CONFIG", "/native-config/config.json"))
    lock = os.open(state_dir / "runtime.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    stopping = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopping.set())
    previous = read_json(state_dir / "runtime.json")
    status, reason = state_on_start(previous)
    startup_consumed = bool((previous or {}).get("startup_consumed", False))
    latest_diagnostic = (previous or {}).get("diagnostic", "")
    def save(status, reason=""):
        atomic_json(state_dir / "runtime.json", {"status": status, "reason": reason,
                    "pubkey": config["pubkey"], "updated_at": time.time(),
                    "startup_consumed": startup_consumed, "diagnostic": latest_diagnostic})
    if status == "ready" and not (state_dir / ("auth-" + config["provider"] + ".json")).is_file():
        status, reason = "needs_login", "first_subscription_login_required"
    save(status, reason)
    if status != "ready":
        logging.info("native_not_started:%s", reason or status)
        while not stopping.wait(2):
            # Only the root-owned auth helper/operator may rearm the service.
            if read_json(state_dir / "runtime.json", {}).get("status") == "ready":
                return 0
        return 0
    # These directories were created on the host with known ownership.
    for path in (state_dir, state_dir / "slots"):
        st = path.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
            raise ToolError("supervisor_directory_permissions")
    socket_path = Path("/tmp/buzz-guard.sock")
    socket_path.unlink(missing_ok=True)
    policy = Policy(state_dir, state_dir / "slots", config["policy"], concurrency=runtime_parallelism(config))
    broker = Broker(socket_path, policy)
    os.chown(socket_path, 0, UID)
    os.chmod(socket_path, 0o660)
    thread = threading.Thread(target=broker.serve_forever, daemon=True)
    thread.start()
    process = None
    selector = selectors.DefaultSelector()
    diagnostic_streams = {}
    def drain():
        nonlocal latest_diagnostic
        for event, _ in selector.select(0.05):
            chunk = os.read(event.fd, 65536)
            if not chunk:
                selector.unregister(event.fileobj)
                continue
            for code in diagnostic_streams[event.fd].feed(chunk):
                latest_diagnostic = code
                logging.warning("native_diagnostic:%s", code)
    try:
        launch_env = runtime_env(config, socket_path, startup_consumed)
        startup_consumed = True
        latest_diagnostic = ""  # A new launch owns a new diagnostic generation.
        save("running")  # Never resurrect if the supervisor dies before it can record a safe stop.
        process = subprocess.Popen(["buzz-acp", "--agent-args", ""], cwd="/workspace",
                    env=launch_env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
                    user=UID, group=UID, extra_groups=[], umask=0o077, close_fds=True)
        for stream in (process.stdout, process.stderr):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
            diagnostic_streams[stream.fileno()] = RuntimeDiagnostics()
        logging.info("native_started:%s:%s", config["pubkey"], config["provider"])
        while process.poll() is None and not stopping.is_set() and not policy.check():
            drain()
        # Collect final initialization/error bytes after fast native exit.
        for _ in range(5):
            if not selector.get_map():
                break
            drain()
        if stopping.is_set():
            # Normal Docker/host stop: native conversations may restart on host boot,
            # but incomplete model actions are not reissued by this package.
            stop_group(process, drain=drain)
            if process.returncode == 0:
                save("ready", "external_graceful_stop")
            else:
                save("held", "external_stop_incomplete")
        elif policy.tripped:
            save("held", policy.tripped)
        elif process.returncode == 0:
            save("stopped", "native_clean_exit")
        else:
            save("held", "native_process_failed")
    except Exception:
        save("held", "supervisor_fault")
        logging.error("native_supervisor_fault")
    finally:
        if process is not None:
            stop_group(process, drain=drain)
        policy.close()
        broker.shutdown()
        broker.server_close()
        selector.close()
        os.close(lock)
    # Docker starts a fresh PID namespace, then sees stopped/held and does not run the bot.
    # Remaining detached descendants die when this container exits.
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ToolError, OSError, ValueError):
        logging.error("native_boot_refused")
        raise SystemExit(2)
