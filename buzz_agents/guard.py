"""Transparent ACP JSON-lines proxy; protects prompt starts, never chooses coworkers."""
import json
import os
import selectors
import socket
import subprocess
import sys
import time
from .common import clean_env

MAX_LINE = 4 * 1024 * 1024


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
    def __init__(self, send_agent, send_host, call=broker):
        self.to_agent, self.to_host, self.call = send_agent, send_host, call
        self.waiting = []
        self.active = {}
        self.stopped = False

    def fail(self, message, code=-32000, text="buzz-agents guard stopped this request"):
        self.to_host({"jsonrpc": "2.0", "id": message.get("id"), "error": {"code": code, "message": text}})

    def from_host(self, message):
        if message.get("method") == "session/prompt" and "id" in message:
            if len(self.waiting) >= 4:
                self.call({"op": "trip"})
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
        if self.stopped or self.active or not self.waiting:
            return
        answer = self.call({"op": "acquire"})
        if answer.get("error") == "busy":
            return
        message = self.waiting.pop(0)
        if not answer.get("ok"):
            self.fail(message)
            self.stopped = True
            return
        self.active[request_id(message)] = answer["ticket"]
        self.to_agent(message)

    def from_agent(self, message):
        # Notifications or tool permission requests must not consume reply tickets.
        if "method" not in message and "id" in message and ("result" in message or "error" in message):
            ticket = self.active.pop(request_id(message), None)
            if ticket:
                self.call({"op": "release", "ticket": ticket})
                if "error" in message:
                    self.call({"op": "trip"})
                    self.stopped = True
        self.to_host(message)


def main():
    command = os.environ.get("BUZZ_NATIVE_COMMAND")
    if command not in ("codex-acp", "claude-agent-acp"):
        return 2
    # These are the bot's own credentials and native settings, never host SSH keys.
    env = {k: v for k, v in os.environ.items() if not k.startswith("BUZZ_GUARD_") and k != "BUZZ_NATIVE_COMMAND"}
    child = subprocess.Popen([command], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, env=env, close_fds=True, bufsize=0)
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
            raise ValueError("output_limit")
        pending[label].extend(raw)
    proxy = Proxy(lambda m: enqueue("to_agent", m), lambda m: enqueue("to_host", m))
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
                if proxy.active or proxy.waiting:
                    broker({"op": "trip"})
                return 3
            for event, _ in selector.select(0.05):
                chunk = os.read(event.fd, 65536)
                if not chunk:
                    if event.data == "host":
                        return 0
                    broker({"op": "trip"})
                    return 3
                buffer = buffers[event.data]
                buffer.extend(chunk)
                if len(buffer) > MAX_LINE:
                    raise ValueError("line_limit")
                while b"\n" in buffer:
                    raw, _, rest = buffer.partition(b"\n")
                    buffer[:] = rest
                    message = json.loads(raw)
                    if not isinstance(message, dict):
                        raise ValueError("invalid_frame")
                    (proxy.from_host if event.data == "host" else proxy.from_agent)(message)
            proxy.tick()
    except (OSError, ValueError, KeyError):
        try:
            broker({"op": "trip"})
        except Exception:
            pass
        return 3
    finally:
        selector.close()
        child.kill()
        child.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
