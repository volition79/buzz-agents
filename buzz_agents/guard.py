"""Transparent ACP JSON-lines proxy; protects prompt starts, never chooses coworkers."""
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import subprocess
import sys
import time
from .diagnostics import RuntimeDiagnostics, structured_diagnostic

# Match the pinned official buzz-acp LinesCodec limit (bytes excluding newline).
MAX_LINE = 10_000_000


class ProtocolFault(ValueError):
    """Only fixed public codes, never the failing frame or exception text."""


def decode_frames(buffer, chunk):
    buffer.extend(chunk)
    while b"\n" in buffer:
        end = buffer.index(b"\n")
        if end > MAX_LINE:
            raise ProtocolFault("runtime_frame_too_large")
        raw = bytes(buffer[:end])
        del buffer[:end + 1]
        try:
            message = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise ProtocolFault("runtime_frame_invalid_json") from None
        if not isinstance(message, dict):
            raise ProtocolFault("runtime_frame_invalid_shape")
        yield message
    if len(buffer) > MAX_LINE:
        raise ProtocolFault("runtime_frame_too_large")


def broker(request, path=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(2)
        conn.connect(path or os.environ["BUZZ_GUARD_SOCKET"])
        conn.sendall(json.dumps(request).encode() + b"\n")
        with conn.makefile("rb") as stream:
            return json.loads(stream.readline(8193))


def request_id(message):
    return json.dumps(message.get("id"), sort_keys=True)


class Proxy:
    def __init__(self, send_agent, send_host, call=broker, monotonic=time.monotonic):
        self.to_agent, self.to_host, self.call = send_agent, send_host, call
        self.waiting = []
        self.active = {}
        self.stopped = False
        self.monotonic = monotonic
        self.deadline = None
        self.active_message = None

    def fail(self, message, code=-32000, text="buzz-agents guard stopped this request"):
        self.to_host({"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": code, "message": text}})

    def from_host(self, message):
        if message.get("method") == "session/prompt" and "id" in message:
            if len(self.waiting) >= 4:
                self.fail(message)
                self.stopped = True
            else:
                self.waiting.append(message)
        elif message.get("method") == "session/cancel":
            session = message.get("params", {}).get("sessionId")
            keep = []
            for pending in self.waiting:
                if pending.get("params", {}).get("sessionId") == session:
                    self.to_host({"jsonrpc": "2.0", "id": pending["id"], "result": {"stopReason": "cancelled"}})
                else:
                    keep.append(pending)
            self.waiting = keep
            self.to_agent(message)
        else:
            self.to_agent(message)

    def tick(self):
        if self.stopped:
            return
        if self.active and self.deadline is not None and self.monotonic() >= self.deadline:
            self.fail(self.active_message, text="Worker exceeded upstream deadline and cleanup grace; this request stopped")
            print("buzz-agents-diagnostic:runtime_worker_deadline", file=sys.stderr, flush=True)
            self.stopped = True
            return  # Keep the slot until stop_adapter verifies cleanup.
        if self.active or not self.waiting:
            return
        answer = self.call({"op": "acquire"})
        if answer.get("error") == "busy":
            return
        message = self.waiting.pop(0)
        if not answer.get("ok"):
            reason = answer.get("error")
            if reason in ("turn_window_limit", "daily_start_limit"):
                delay = answer["retry_after_seconds"]
                self.fail(message, text=f"Configured prompt budget reached ({reason}); retry after {delay} seconds")
                print("buzz-agents-diagnostic:runtime_budget_wait", file=sys.stderr, flush=True)
            else:
                self.fail(message)
                self.stopped = True
            return
        self.active[request_id(message)] = answer["ticket"]
        self.active_message = message
        self.deadline = self.monotonic() + answer.get("watchdog_seconds", 7320)
        self.to_agent(message)

    def from_agent(self, message):
        code = structured_diagnostic(message)
        if code:
            print("buzz-agents-diagnostic:" + code, file=sys.stderr, flush=True)
        # Notifications or tool permission requests must not consume reply tickets.
        if "method" not in message and "id" in message and ("result" in message or "error" in message):
            ticket = self.active.pop(request_id(message), None)
            if ticket:
                self.call({"op": "release", "ticket": ticket})
                self.deadline = None
                self.active_message = None
                if "error" in message:
                    print("buzz-agents-diagnostic:runtime_prompt_failed", file=sys.stderr, flush=True)
        self.to_host(message)


def stop_adapter(child, timeout=3):
    """Kill only peers in this guard's upstream-owned Linux process group.

    Keeping the adapter in this group is essential: Buzz kills this group with
    SIGKILL, which cannot run our finally block. For an ordinary adapter failure
    the guard stays alive to verify cleanup and release its own prompt tickets.
    """
    group = os.getpgrp()
    if group != os.getpid():
        raise RuntimeError("guard_process_group_not_owned")
    deadline = time.monotonic() + timeout
    while True:
        live = False
        child.poll()  # Reap the direct child; orphan zombies need no more signal.
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit() or int(entry.name) == os.getpid():
                continue
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if int(fields[2]) != group or fields[0] == "Z":
                    continue
                live = True
                pid = int(entry.name)
                # Pin the process identity before signaling, avoiding PID reuse.
                fd = os.pidfd_open(pid)
                try:
                    if os.getpgid(pid) == group:
                        signal.pidfd_send_signal(fd, signal.SIGKILL)
                finally:
                    os.close(fd)
            except (FileNotFoundError, ProcessLookupError):
                continue
        if not live:
            child.wait(timeout=1)
            return
        if time.monotonic() >= deadline:
            raise RuntimeError("adapter_cleanup_incomplete")
        time.sleep(0.01)


def main():
    command = os.environ.get("BUZZ_NATIVE_COMMAND")
    if command not in ("codex-acp", "claude-agent-acp"):
        return 2
    # Upstream already makes the guard a group leader. Standalone invocation
    # must not share the caller's group either. Never move the adapter out.
    if os.getpgrp() != os.getpid():
        os.setpgid(0, 0)
    # These are the bot's own credentials and native settings, never host SSH keys.
    env = {k: v for k, v in os.environ.items() if not k.startswith("BUZZ_GUARD_") and k != "BUZZ_NATIVE_COMMAND"}
    child = subprocess.Popen([command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=env, close_fds=True, bufsize=0)
    selector = selectors.DefaultSelector()
    buffers = {"host": bytearray(), "agent": bytearray()}
    pending = {"to_agent": bytearray(), "to_host": bytearray()}
    for stream, label in ((sys.stdin.buffer, "host"), (child.stdout, "agent")):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, label)
    for stream in (child.stdin, sys.stdout.buffer):
        os.set_blocking(stream.fileno(), False)
    def enqueue(label, message):
        raw = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"
        if len(pending[label]) + len(raw) > 2 * MAX_LINE:
            raise ProtocolFault("runtime_output_backpressure")
        pending[label].extend(raw)
    proxy = Proxy(lambda m: enqueue("to_agent", m), lambda m: enqueue("to_host", m))
    selector.register(child.stderr, selectors.EVENT_READ, "diagnostic")
    os.set_blocking(child.stderr.fileno(), False)
    diagnostics = RuntimeDiagnostics()
    def terminate(*_):
        raise SystemExit(0)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, terminate)
    stop_at = None
    try:
        while True:
            for label, stream in (("to_agent", child.stdin), ("to_host", sys.stdout.buffer)):
                if pending[label]:
                    try:
                        size = os.write(stream.fileno(), pending[label][:65536])
                        del pending[label][:size]
                    except BlockingIOError:
                        pass
            if proxy.stopped and stop_at is None:
                stop_at = time.monotonic() + 0.5
            if stop_at and (not pending["to_host"] or time.monotonic() >= stop_at):
                return 3
            if child.poll() is not None:
                # Even an exit0 is not a complete ACP conversation if it breaks mid-turn.
                print("buzz-agents-diagnostic:runtime_adapter_exited", file=sys.stderr, flush=True)
                return 3
            for event, _ in selector.select(0.05):
                chunk = os.read(event.fd, 65536)
                if event.data == "diagnostic":
                    if not chunk:
                        selector.unregister(event.fileobj)
                    for code in diagnostics.feed(chunk):
                        print("buzz-agents-diagnostic:" + code, file=sys.stderr, flush=True)
                    continue
                if not chunk:
                    if event.data == "host":
                        return 0
                    print("buzz-agents-diagnostic:runtime_adapter_exited", file=sys.stderr, flush=True)
                    return 3
                buffer = buffers[event.data]
                for message in decode_frames(buffer, chunk):
                    (proxy.from_host if event.data == "host" else proxy.from_agent)(message)
            proxy.tick()
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as error:
        code = (str(error) if isinstance(error, ProtocolFault) else
                "runtime_transport_failed" if isinstance(error, OSError) else "runtime_frame_invalid_shape")
        print("buzz-agents-diagnostic:" + code, file=sys.stderr, flush=True)
        return 3
    finally:
        selector.close()
        cleaned = False
        try:
            stop_adapter(child)
            cleaned = True
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            print("buzz-agents-diagnostic:runtime_adapter_cleanup_failed", file=sys.stderr, flush=True)
            try:
                broker({"op": "trip"})
            except (OSError, ValueError):
                pass
        # A fast failing adapter may exit before the selector observes stderr.
        # Nonblocking and byte bounded even if an escaped child holds the pipe.
        for _ in range(4):
            try:
                chunk = os.read(child.stderr.fileno(), 65536)
            except (BlockingIOError, OSError):
                break
            if not chunk:
                break
            for code in diagnostics.feed(chunk):
                print("buzz-agents-diagnostic:" + code, file=sys.stderr, flush=True)
        # Release slots only after the failed adapter is dead. Starts stay charged.
        for ticket in (proxy.active.values() if cleaned else ()):
            try:
                broker({"op": "release", "ticket": ticket})
            except (OSError, ValueError):
                pass


if __name__ == "__main__":
    raise SystemExit(main())
