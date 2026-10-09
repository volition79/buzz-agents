"""Bounded subprocess and secret-file helpers; no provider protocol implementation."""

import json
import os
import selectors
import signal
import stat
import subprocess
import time
from pathlib import Path


class ToolError(RuntimeError):
    """Only fixed diagnostic codes cross a user-visible boundary."""


def secret(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 512:
            raise ToolError("secret_permissions")
        value = os.read(fd, 513).decode("ascii").strip()
        if not 16 <= len(value) <= 256:
            raise ToolError("secret_invalid")
        return value
    finally:
        os.close(fd)


def clean_env():
    allowed = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "SSL_CERT_FILE", "SSL_CERT_DIR")
    return {k: os.environ[k] for k in allowed if k in os.environ}


def bounded(argv, *, data=b"", env=None, timeout=20, limit=8 * 1024 * 1024):
    """Drain all pipes without unbounded buffering or a blocking stdin write."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=env, start_new_session=True,
                               close_fds=True)
    selector = selectors.DefaultSelector()
    output, diagnostic = bytearray(), bytearray()
    pending = memoryview(data)
    deadline = time.monotonic() + timeout
    for stream, name in ((process.stdout, "out"), (process.stderr, "err")):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    if pending:
        os.set_blocking(process.stdin.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE, "in")
    else:
        process.stdin.close()
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                raise ToolError("subprocess_timeout")
            for key, _ in selector.select(min(0.2, max(0, deadline - time.monotonic()))):
                if key.data == "in":
                    try:
                        pending = pending[os.write(key.fd, pending[:65536]):]
                    except BrokenPipeError:
                        pending = memoryview(b"")
                    if not pending:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                else:
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    target = output if key.data == "out" else diagnostic
                    if len(target) + len(chunk) > limit:
                        raise ToolError("subprocess_output_limit")
                    target.extend(chunk)
        code = process.wait(timeout=max(0.01, deadline - time.monotonic()))
        return code, bytes(output), bytes(diagnostic)
    except subprocess.TimeoutExpired:
        raise ToolError("subprocess_timeout") from None
    finally:
        selector.close()
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
        process.wait()


def crypto(operation, value=None):
    helper = Path(__file__).with_name("nostr.mjs")
    code, out, _ = bounded(["node", str(helper), operation],
                          data=json.dumps(value, ensure_ascii=False).encode(),
                          env=clean_env(), timeout=15)
    if code:
        raise ToolError("nostr_helper_failed")
    try:
        return json.loads(out)
    except (ValueError, UnicodeError):
        raise ToolError("nostr_helper_invalid") from None
