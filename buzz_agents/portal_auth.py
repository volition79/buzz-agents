"""Bounded official-login process group inside ONE bot, never a general terminal."""
import fcntl
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from .common import ToolError
from .policy import atomic_json, read_json

BASE = Path('/native-state')


def process_start(pid):
    # comm may contain spaces/parentheses; fields after its final ')' start at #3.
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


def validate_session(session):
    if not isinstance(session, str) or not re.fullmatch(r'[a-f0-9]{32}', session):
        raise ToolError('invalid_auth_session')


def cancel(session):
    validate_session(session)
    # Persist intent BEFORE reading PID, covering cancellation during startup.
    atomic_json(BASE / 'portal-auth-cancel.json', {'session': session})
    record = read_json(BASE / 'portal-auth.json', {})
    if record and record.get('session') == session:
        pid = record.get('pid')
        if type(pid) is not int or pid <= 1:
            raise ToolError('invalid_auth_process')
        try:
            if process_start(pid) == record['start']:
                os.killpg(pid, signal.SIGTERM)
        except (FileNotFoundError, ProcessLookupError):
            pass


def run(provider, session, timeout=600):
    validate_session(session)
    if provider not in ('codex', 'claude') or os.geteuid() != 0:
        raise ToolError('invalid_auth_request')
    with open(BASE / 'portal-auth.lock', 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ToolError('authentication_already_in_progress') from None
        if read_json(BASE / 'portal-auth-cancel.json', {}).get('session') == session:
            (BASE / 'portal-auth-cancel.json').unlink(missing_ok=True)
            return 130
        child = subprocess.Popen([sys.executable, '-m', 'buzz_agents.cli', 'auth', provider],
                                 start_new_session=True)
        try:
            atomic_json(BASE / 'portal-auth.json', {'pid': child.pid, 'start': process_start(child.pid), 'session': session})
            if read_json(BASE / 'portal-auth-cancel.json', {}).get('session') == session:
                return 130
            try:
                return child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                return 124
        finally:
            try:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            (BASE / 'portal-auth.json').unlink(missing_ok=True)
            if read_json(BASE / 'portal-auth-cancel.json', {}).get('session') == session:
                (BASE / 'portal-auth-cancel.json').unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        if len(sys.argv) == 3 and sys.argv[1] == 'cancel' and os.geteuid() == 0:
            cancel(sys.argv[2])
        elif len(sys.argv) == 4 and sys.argv[1] == 'run':
            sys.exit(run(sys.argv[2], sys.argv[3]))
        else:
            raise ToolError('invalid_auth_operation')
    except Exception:
        print('authentication_session_failed', flush=True)
        sys.exit(1)
