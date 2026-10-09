"""Root-owned loop/time guards. No content decisions and no provider token quota claim."""
import fcntl
import json
import os
from pathlib import Path
import secrets
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


class Policy:
    """Each native prompt consumes a durable ticket; faults never auto-reset it."""
    def __init__(self, directory, slots, limits, concurrency=1, clock=time.time, monotonic=time.monotonic):
        self.directory, self.slots = Path(directory), Path(slots)
        self.limits, self.concurrency = limits, concurrency
        self.clock, self.monotonic = clock, monotonic
        self.lock = threading.RLock()
        self.active = None
        self.tripped = ""
        self.data = read_json(self.directory / "quota.json", {"starts": [], "last": 0})

    def acquire(self):
        with self.lock:
            if self.tripped:
                return {"ok": False, "error": self.tripped}
            if self.active:
                return {"ok": False, "error": "busy"}
            now = self.clock()
            if now + 2 < self.data["last"]:
                return self.trip("clock_moved_backwards")
            starts = [v for v in self.data["starts"] if v >= now - 86400]
            if sum(v >= now - self.limits["window_seconds"] for v in starts) >= self.limits["turn_limit"]:
                return self.trip("turn_window_limit")
            # A rolling 24-hour allowance, not midnight reset bursts.
            if len(starts) >= self.limits["daily_limit"]:
                return self.trip("daily_start_limit")
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
                self.data = {"starts": starts + [now], "last": now}
                atomic_json(self.directory / "quota.json", self.data)
                self.active = (token, slot, self.monotonic() + self.limits["max_turn_seconds"])
                return {"ok": True, "ticket": token}
            except Exception:
                os.close(slot)
                return self.trip("quota_storage_failed")

    def release(self, token):
        with self.lock:
            if not self.active or not isinstance(token, str) or not secrets.compare_digest(self.active[0], token):
                return {"ok": False, "error": "invalid_ticket"}
            os.close(self.active[1])
            self.active = None
            return {"ok": True}

    def trip(self, reason):
        with self.lock:
            self.tripped = reason
            return {"ok": False, "error": reason}

    def check(self):
        with self.lock:
            if self.active and self.monotonic() >= self.active[2]:
                self.trip("turn_deadline")
            return self.tripped

    def close(self):
        with self.lock:
            if self.active:
                os.close(self.active[1])
                self.active = None


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
