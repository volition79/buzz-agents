"""One-bot, admin-consented reauthentication; persisted hold survives broker loss."""
import fcntl
import os
from pathlib import Path
import re
import threading
import time

from .bot_update import ExistingBotUpdater
from .common import ToolError
from .host import container_name, check_ownership
from .policy import atomic_json, read_json

HOLD = 'reauth-hold.json'
CAPABILITY = 'io.buzz-agents.reauth'


def pending(root, pubkey):
    return (Path(root) / 'bots' / pubkey / 'state' / HOLD).exists()


def require_unheld(root, pubkey):
    if pending(root, pubkey):
        raise ToolError('bot_reauthentication_pending')


def inspect_bot(deployer, pubkey):
    config, actual, revision = ExistingBotUpdater(deployer).inspect(pubkey)
    if actual and (actual.get('Config', {}).get('Labels') or {}).get('io.buzz-agents.fingerprint') != config['fingerprint']:
        raise ToolError('saved_bot_configuration_changed')
    return config, actual, revision


class Reauthentication:
    def __init__(self, control, logins, root):
        self.path = Path(control) / 'reauth.json'
        self.root = Path(root)
        self.logins = logins
        self.lock = threading.RLock()
        self.running = False
        self.session = None  # Only the authenticated admin endpoint can read this.

    def status(self):
        with self.lock:
            job = read_json(self.path, {})
            if job.get('state') in ('preparing', 'authenticating') and not self.running:
                completed = read_json(self.root / 'bots' / job['pubkey'] / 'state' / 'reauth-result.json', {})
                if completed.get('request_id') == job['id'] and completed.get('success') is True and not pending(self.root, job['pubkey']):
                    job = {**job, 'state': 'succeeded'}
                else:
                    job = {**job, 'state': 'interrupted', 'error': 'reauth_interrupted'}
            result = {'ok': True, 'reauth': job}
            if self.running and self.session:
                result['session'] = self.session
            return result

    def start(self, deployer, pubkey, request_id):
        if not isinstance(request_id, str) or not re.fullmatch('[0-9a-f]{32}', request_id):
            raise ToolError('invalid_reauth_request')
        with self.lock:
            previous = self.status()['reauth']
            if previous.get('id') == request_id:
                if previous.get('pubkey') != pubkey:
                    raise ToolError('invalid_reauth_request')
                return self.status()
            if self.running:
                raise ToolError('authentication_already_in_progress')
            config, actual, _ = inspect_bot(deployer, pubkey)
            if not actual or (actual.get('Config', {}).get('Labels') or {}).get(CAPABILITY) != '1':
                raise ToolError('reauth_runtime_update_required')
            with self.logins.lock:
                self.logins.expire()
                if any(v['process'].poll() is None for v in self.logins.items.values()):
                    raise ToolError('authentication_already_in_progress')
            job = {'id': request_id, 'pubkey': pubkey, 'name': config['name'], 'state': 'preparing'}
            atomic_json(self.path, job)
            self.running, self.session = True, None
            try:
                threading.Thread(target=self._work, args=(deployer, job), daemon=True).start()
            except RuntimeError:
                self.running = False
                atomic_json(self.path, {**job, 'state': 'failed', 'error': 'reauth_failed'})
                raise ToolError('reauth_failed') from None
            return {'ok': True, 'reauth': job}

    def prepare(self, d, job):
        inspect_bot(d, job['pubkey'])
        folder = d.root / 'bots' / job['pubkey'] / 'state'
        auth_locks = []
        try:
            if not (folder / HOLD).exists():
                for name in ('portal-auth.lock', 'auth.lock'):
                    fd = os.open(folder / name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                    auth_locks.append(fd)
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        raise ToolError('authentication_already_in_progress') from None
            self._prepare_locked(d, job, bool(auth_locks))
        finally:
            for fd in auth_locks:
                os.close(fd)
        return self.logins.start(d.settings, job['pubkey'])

    def _prepare_locked(self, d, job, auth_locked):
        """Caller owns deploy.lock until authentication and cleanup finish."""
        pubkey = job['pubkey']
        config, actual, _ = inspect_bot(d, pubkey)
        if not actual or (actual.get('Config', {}).get('Labels') or {}).get(CAPABILITY) != '1':
            raise ToolError('reauth_runtime_update_required')
        folder = d.root / 'bots' / pubkey / 'state'
        # No active auth may be interrupted by a new request. A durable marker
        # from our own interrupted operation is recoverable by stopping the same
        # container (which kills its auth process too), then checking both locks.
        if (folder / 'portal-auth.json').exists() and not (folder / HOLD).exists():
            raise ToolError('authentication_already_in_progress')
        atomic_json(folder / HOLD, {'request_id': job['id']})
        d.run(['docker', 'stop', '--time', '70', actual['Id']], timeout=80)
        stopped = d.inspect(container_name(pubkey))
        if (not stopped or stopped.get('Id') != actual['Id']
                or stopped.get('State', {}).get('Running')
                or stopped.get('State', {}).get('Restarting')
                or stopped.get('State', {}).get('Pid', 0) != 0):
            raise ToolError('reauth_stop_unconfirmed')
        check_ownership(stopped, config)
        locks = []
        try:
            for name in (('runtime.lock',) if auth_locked else ('runtime.lock', 'portal-auth.lock', 'auth.lock')):
                fd = os.open(folder / name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                locks.append(fd)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ToolError('reauth_cleanup_unconfirmed') from None
            state = read_json(folder / 'runtime.json', {})
            atomic_json(folder / 'runtime.json', {**state, 'status': 'needs_login',
                        'reason': 'explicit_reauthentication', 'pubkey': pubkey})
            # Only stale process metadata after a proven full container stop.
            for name in ('portal-auth.json', 'portal-auth-cancel.json'):
                (folder / name).unlink(missing_ok=True)
        finally:
            for fd in locks:
                os.close(fd)
        d.run(['docker', 'start', actual['Id']], timeout=30)
        started = d.inspect(container_name(pubkey))
        if not started or started.get('Id') != actual['Id'] or not started.get('State', {}).get('Running'):
            raise ToolError('reauth_start_unconfirmed')
        check_ownership(started, config)

    def _work(self, d, job):
        fd = None
        result = {**job, 'state': 'failed', 'error': 'reauth_failed'}
        try:
            fd = os.open(d.root / 'deploy.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ToolError('bot_update_busy') from None
            login = self.prepare(d, job)
            with self.lock:
                self.session = login['session']
                atomic_json(self.path, {**job, 'state': 'authenticating'})
            while True:
                reply = self.logins.poll(login['session'])
                if reply['done']:
                    # A successful CLI alone is insufficient: wrapper must
                    # release the durable hold after its process-group cleanup.
                    completed = read_json(d.root / 'bots' / job['pubkey'] / 'state' / 'reauth-result.json', {})
                    success = completed.get('request_id') == job['id'] and completed.get('success') is True and not pending(d.root, job['pubkey'])
                    result = {**job, 'state': 'succeeded' if success else 'failed'}
                    if not success:
                        result['error'] = 'reauth_login_incomplete'
                    break
                time.sleep(.5)
        except ToolError as exc:
            if re.fullmatch('[a-zA-Z0-9_]{1,160}', str(exc)):
                result['error'] = str(exc)
        except Exception:
            pass
        finally:
            # Failed login/cleanup retains the durable hold; no old credential
            # marker can wake this bot, even after a VPS/broker restart.
            if fd is not None:
                os.close(fd)
            with self.lock:
                atomic_json(self.path, result)
                self.running = False
                self.session = None
            print('Buzz reauthentication: ' + result['state'] + ' ' + result.get('error', 'verified'), flush=True)
