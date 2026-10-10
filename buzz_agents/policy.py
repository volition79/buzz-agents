"""Root-owned loop/time guards. No content decisions and no provider token quota claim."""
import fcntl
import json
import math
import os
from pathlib import Path
import secrets
import select
import socket
import struct
import socketserver
import threading
import time
from .common import ToolError


def read_json(path, default=None):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return default
    with os.fdopen(fd, "rb") as stream:
        data = stream.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ToolError("state_too_large")
    return json.loads(data)


def atomic_json(path, value, mode=0o600):
    path = Path(path)
    tmp = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def budget_wait(limits, data, now):
    """Optional rolling admission budgets, separate from upstream failure retries."""
    blocked = []
    for key, window, reason in (("turn_limit", limits.get("window_seconds", 3600), "turn_window_limit"),
                                ("daily_limit", 86400, "daily_start_limit")):
        limit = limits.get(key, 0)
        if not limit:
            continue
        starts = sorted(v for v in data.get("starts", []) if v > now - window)
        if len(starts) >= limit:
            blocked.append((starts[-limit] + window, reason))
    if not blocked:
        return None
    retry_at, reason = max(blocked)
    return {"ok": False, "error": reason, "retry_after_seconds": max(1, math.ceil(retry_at - now))}


class Policy:
    """Durable optional budgets and secure worker slots; only integrity faults latch."""
    def __init__(self, directory, slots, limits, concurrency=1, clock=time.time, monotonic=time.monotonic):
        if type(concurrency) is not int or not 1 <= concurrency <= 32:
            raise ToolError("invalid_parallelism")
        self.directory, self.slots = Path(directory), Path(slots)
        self.limits, self.concurrency = limits, concurrency
        self.clock, self.monotonic = clock, monotonic
        self.lock = threading.RLock()
        self.active = {}
        self.owners = {}
        self.tripped = ""
        self.data = read_json(self.directory / "quota.json", {"starts": [], "last": 0})

    def acquire(self, owner=None):
        # owner is kernel-derived (pidfd, process group), never request JSON.
        with self.lock:
            try:
                self.reap_dead_owners()
                result = self._acquire()
                if result.get("ok") and owner is not None:
                    self.owners[result["ticket"]] = owner
                    owner = None
                return result
            finally:
                if owner is not None:
                    os.close(owner[0])

    def reap_dead_owners(self):
        for token, (fd, group) in list(self.owners.items()):
            if not select.select([fd], [], [], 0)[0]:
                continue
            # A dead guard alone is insufficient: ordinary adapter descendants
            # must also be gone before a slot can be reused. Never kill by a
            # potentially recycled PID/PGID here; uncertain cleanup stays held.
            live = False
            for entry in Path("/proc").iterdir():
                if not entry.name.isdigit():
                    continue
                try:
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                    if int(fields[2]) == group and fields[0] != "Z":
                        live = True
                        break
                except (FileNotFoundError, ProcessLookupError):
                    continue
            if not live:
                self.release(token)

    def _acquire(self):
        with self.lock:
            if self.tripped:
                return {"ok": False, "error": self.tripped}
            if len(self.active) >= self.concurrency:
                return {"ok": False, "error": "busy"}
            now = self.clock()
            if now + 2 < self.data["last"]:
                return self.trip("clock_moved_backwards")
            denied = budget_wait(self.limits, self.data, now)
            if denied:
                return denied
            # With budgets disabled there is no unbounded history of healthy turns.
            retention = (86400 if self.limits.get("daily_limit") else
                         self.limits.get("window_seconds", 3600) if self.limits.get("turn_limit") else 0)
            starts = [v for v in self.data["starts"] if v > now - retention] if retention else []
            slot = None
            for number in range(self.concurrency):
                fd = os.open(self.slots / f"slot-{number}", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    slot = fd
                    break
                except BlockingIOError:
                    os.close(fd)
            if slot is None:
                return {"ok": False, "error": "busy"}
            token = secrets.token_hex(24)
            try:
                self.data = {"starts": starts + [now] if retention else [], "last": now}
                atomic_json(self.directory / "quota.json", self.data)
                # Guard watchdog runs at +120s and gets 30s to verify cleanup.
                # A remaining ticket after that is an integrity/cleanup failure,
                # not a normal turn timeout. Never leave orphan workers unbounded.
                self.active[token] = (slot, self.monotonic() + self.limits["max_turn_seconds"] + 150)
                return {"ok": True, "ticket": token,
                        "watchdog_seconds": self.limits["max_turn_seconds"] + 120}
            except Exception:
                os.close(slot)
                return self.trip("quota_storage_failed")

    def release(self, token):
        with self.lock:
            if not isinstance(token, str) or token not in self.active:
                return {"ok": False, "error": "invalid_ticket"}
            owner = self.owners.pop(token, None)
            if owner is not None:
                os.close(owner[0])
            slot, _ = self.active.pop(token)
            os.close(slot)
            return {"ok": True}

    def trip(self, reason):
        with self.lock:
            self.tripped = reason
            return {"ok": False, "error": reason}

    def check(self):
        with self.lock:
            try:
                self.reap_dead_owners()
            except (OSError, ValueError, IndexError):
                self.trip("worker_lifetime_check_failed")
            # buzz-acp owns turn deadlines. A guard-local fallback bounds only
            # that worker after upstream cancellation/cleanup has had time to run.
            if any(self.monotonic() >= deadline for _, deadline in self.active.values()):
                self.trip("worker_cleanup_timeout")
            return self.tripped

    def close(self):
        with self.lock:
            for slot, _ in self.active.values():
                os.close(slot)
            self.active.clear()
            for fd, _ in self.owners.values():
                os.close(fd)
            self.owners.clear()


class Broker(socketserver.UnixStreamServer):
    def __init__(self, address, policy):
        self.policy = policy
        super().__init__(str(address), BrokerHandler)


class BrokerHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(1)
        try:
            raw = self.rfile.readline(8193)
            if len(raw) > 8192:
                raise ValueError()
            request = json.loads(raw)
            if request.get("op") == "acquire":
                pid, _, _ = struct.unpack("3i", self.connection.getsockopt(
                    socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i")))
                fd = os.pidfd_open(pid)
                try:
                    group = os.getpgid(pid)
                except BaseException:
                    os.close(fd)
                    raise
                if group == pid:
                    result = self.server.policy.acquire((fd, group))
                else:
                    # Legacy/manual clients have no privately owned worker group.
                    os.close(fd)
                    result = self.server.policy.acquire()
            elif request.get("op") == "release":
                result = self.server.policy.release(request.get("ticket"))
            elif request.get("op") == "trip":
                result = self.server.policy.trip("adapter_or_guard_fault")
            else:
                result = {"ok": False, "error": "invalid_operation"}
            self.wfile.write(json.dumps(result).encode() + b"\n")
        except (ValueError, OSError, AttributeError):
            return
