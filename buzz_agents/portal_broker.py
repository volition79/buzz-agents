"""Network-disabled broker. Only this role gets the Docker socket.

Fixed RPC vocabulary; untrusted callers cannot supply Docker commands, paths,
image references, container names, ports, mounts, or arbitrary terminal commands.
"""
import json
import os
from pathlib import Path
import pty
import re
import secrets
import socketserver
import subprocess
import termios
import threading
import time
from .common import ToolError
from .config import HEX, relay_url
from .host import Deployer, execute, inspect_container, check_ownership, container_name
from .bridge import bot_records
from .policy import atomic_json, read_json
from . import easy_schedule, portal_bootstrap, portal_compose

LIMIT = 512 * 1024
STATE = Path('/var/lib/buzz-agents-v2')
CONTROL = Path('/control')
SOCKET = '/rpc/broker.sock'


def discover_relays(containers):
    """Keep only public connection data. Never return raw inspect/environment."""
    found = []
    for container in containers:
        env = {}
        for entry in container.get('Config', {}).get('Env') or []:
            name, _, value = entry.partition('=')
            if name in ('RELAY_OWNER_PUBKEY', 'BUZZ_REQUIRE_RELAY_MEMBERSHIP'):
                env[name] = value
        owner = env.get('RELAY_OWNER_PUBKEY', '')
        if not HEX.fullmatch(owner):
            continue
        labels = container.get('Config', {}).get('Labels') or {}
        hosts = set()
        for key, value in labels.items():
            if key.startswith('traefik.http.routers.') and key.endswith('.rule'):
                hosts.update(re.findall(r'Host\(`([a-zA-Z0-9.-]+)`\)', value))
        for hostname in sorted(hosts):
            record = {'relay': 'wss://' + hostname, 'owner': owner,
                      'membership_required': env.get('BUZZ_REQUIRE_RELAY_MEMBERSHIP', '').lower() == 'true'}
            if record not in found:
                found.append(record)
    return found


class LoginSessions:
    def __init__(self, spawn=subprocess.Popen, command=execute, clock=time.monotonic):
        self.spawn, self.command, self.clock = spawn, command, clock
        self.items = {}
        self.lock = threading.RLock()

    def start(self, settings, pubkey):
        if not isinstance(pubkey, str) or not HEX.fullmatch(pubkey):
            raise ToolError('invalid_bot_public_key')
        registry = read_json(Path(settings['state_dir']) / 'registry.json', {})
        item = registry.get(pubkey)
        if not item or item.get('provider') not in ('codex', 'claude'):
            raise ToolError('unknown_bot')
        actual = inspect_container(container_name(pubkey))
        if not actual or not actual.get('State', {}).get('Running'):
            raise ToolError('bot_container_not_running')
        check_ownership(actual, item)
        with self.lock:
            self.expire()
            if any(v['pubkey'] == pubkey and v['process'].poll() is None for v in self.items.values()):
                raise ToolError('authentication_already_in_progress')
            if len(self.items) >= 8:
                raise ToolError('too_many_login_sessions')
            master, slave = pty.openpty()
            attributes = termios.tcgetattr(slave)
            attributes[3] &= ~termios.ECHO
            termios.tcsetattr(slave, termios.TCSANOW, attributes)
            job = secrets.token_hex(16)
            try:
                process = self.spawn(['docker', 'exec', '-it', '--user', '0:0', container_name(pubkey),
                                      'python', '-m', 'buzz_agents.portal_auth', 'run', item['provider'], job],
                                     stdin=slave, stdout=slave, stderr=slave, close_fds=True)
            except Exception:
                os.close(master)
                raise
            finally:
                os.close(slave)
            sid = secrets.token_urlsafe(32)
            self.items[sid] = {'pubkey': pubkey, 'fd': master, 'process': process, 'job': job,
                               'created': self.clock(), 'output': bytearray(), 'truncated': False}
            threading.Thread(target=self._read, args=(sid,), daemon=True).start()
            return {'ok': True, 'session': sid, 'expires_in': 600}

    def _read(self, sid):
        item = self.items[sid]
        try:
            while True:
                data = os.read(item['fd'], 4096)
                if not data:
                    break
                with self.lock:
                    item['output'].extend(data)
                    if len(item['output']) > 65536:
                        del item['output'][:-65536]
                        item['truncated'] = True
        except OSError:
            pass

    def expire(self):
        for sid, item in list(self.items.items()):
            if self.clock() - item['created'] > 660:
                self.cancel(sid)
                os.close(item['fd'])
                del self.items[sid]

    def get(self, sid):
        with self.lock:
            self.expire()
            if not isinstance(sid, str) or sid not in self.items:
                raise ToolError('login_session_expired')
            return self.items[sid]

    def poll(self, sid):
        with self.lock:
            item = self.get(sid)
            code = item['process'].poll()
            return {'ok': True, 'output': item['output'].decode('utf8', 'replace'),
                    'truncated': item['truncated'], 'done': code is not None,
                    'success': code == 0 if code is not None else False}

    def send(self, sid, text):
        if not isinstance(text, str) or len(text) > 4096 or any(ord(c) < 32 for c in text):
            raise ToolError('invalid_login_input')
        with self.lock:
            item = self.get(sid)
            if item['process'].poll() is not None:
                raise ToolError('login_already_finished')
            os.write(item['fd'], text.encode() + b'\n')
        return {'ok': True}

    def cancel(self, sid):
        with self.lock:
            item = self.items.get(sid)
            if not item:
                raise ToolError('login_session_expired')
            if item['process'].poll() is None:
                self.command(['docker', 'exec', '--user', '0:0', container_name(item['pubkey']),
                              'python', '-m', 'buzz_agents.portal_auth', 'cancel', item['job']], timeout=15)
                try:
                    item['process'].wait(timeout=5)
                except subprocess.TimeoutExpired:
                    item['process'].kill()
                    item['process'].wait()
            return {'ok': True}


class Broker:
    def __init__(self, image, root=STATE, control=CONTROL):
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._/:@-]{1,250}', image):
            raise ToolError('invalid_runtime_image')
        self.image, self.root, self.control = image, Path(root), Path(control)
        self.lock = threading.RLock()
        self.logins = LoginSessions()

    def reconcile_saved_route(self):
        # Broker-only upgrades need no portal restart. Previous activation already
        # passed DNS in portal; fresh discovery must still match that saved plan.
        saved = read_json(self.control / 'bootstrap.json', {})
        if not saved:
            return
        for _ in range(12):
            try:
                self.dispatch({'op': 'bootstrap-activate', 'fingerprint': saved['fingerprint']})
                print('Compose setup route ready', flush=True)
                return
            except Exception:
                print('Compose setup route awaiting reconciliation; existing settings retained', flush=True)
                time.sleep(10)


    def settings(self):
        data = read_json(self.control / 'settings.json', {})
        if not data:
            raise ToolError('configure_relay_first')
        return data

    def dispatch(self, request):
        if not isinstance(request, dict):
            raise ToolError('invalid_request')
        op = request.get('op')
        fields = {'bootstrap-plan': set(), 'bootstrap-activate': {'fingerprint'}, 'status': set(), 'discover': set(), 'configure': {'owner', 'relay'},
                  'deploy': {'request'}, 'auth-start': {'pubkey'}, 'auth-poll': {'session'},
                  'auth-input': {'session', 'text'}, 'auth-cancel': {'session'},
                  'schedule-init': set(), 'schedule-save': {'schedule'}, 'schedule-disable': set()}
        if op not in fields or set(request) != fields[op] | {'op'}:
            raise ToolError('unsupported_broker_operation')
        if op.startswith('bootstrap-'):
            with self.lock:
                ids = execute(['docker', 'container', 'ls', '-a', '--format', '{{.ID}}']).decode().split()
                if len(ids) > 100:
                    raise ToolError('too_many_containers_for_discovery')
                containers = json.loads(execute(['docker', 'inspect', *ids])) if ids else []
                data = portal_bootstrap.plan(containers, os.environ.get('HOSTNAME', ''))
                saved = read_json(self.control / 'bootstrap.json', {})
                data = portal_bootstrap.retain_verified_route(data, saved, containers)
                if op == 'bootstrap-plan':
                    return {'ok': True, **{key:data[key] for key in ('hostname','url','relay_hosts','fingerprint')}}
                if request['fingerprint'] != data['fingerprint']:
                    raise ToolError('bootstrap_plan_changed')
                old = read_json(self.control / 'bootstrap.json', {})
                if old and old.get('fingerprint') != data['fingerprint']:
                    raise ToolError('bootstrap_existing_route_requires_review')
                portal = next(c for c in containers if c.get('Name', '').lstrip('/') == data['upstream'])
                if data['network'] not in portal.get('NetworkSettings', {}).get('Networks', {}):
                    execute(['docker', 'network', 'connect', data['network'], portal['Id']])
                portal_compose.reconcile(containers, os.environ.get('HOSTNAME', ''), data)
                atomic_json(self.control / 'bootstrap.json', data)
                return {'ok': True, 'url': data['url']}
        if op == 'discover':
            ids = execute(['docker', 'container', 'ls', '--format', '{{.ID}}']).decode().split()
            if len(ids) > 100:
                raise ToolError('too_many_containers_for_discovery')
            data = json.loads(execute(['docker', 'inspect', *ids])) if ids else []
            return {'ok': True, 'relays': discover_relays(data)}
        if op.startswith('auth-') and op != 'auth-start':
            if op == 'auth-poll': return self.logins.poll(request['session'])
            if op == 'auth-input': return self.logins.send(request['session'], request['text'])
            return self.logins.cancel(request['session'])
        with self.lock:
            if op == 'configure':
                owner = request['owner']
                if not isinstance(owner, str) or not HEX.fullmatch(owner):
                    raise ToolError('owner_public_hex_required')
                relay = relay_url(request['relay'])
                old = read_json(self.control / 'settings.json', {})
                if old and (old['owner'] != owner or old['relay'] != relay):
                    raise ToolError('existing_relay_configuration_preserved')
                if read_json(self.root / 'registry.json', {}) and not old:
                    raise ToolError('existing_installation_requires_migration')
                image = json.loads(execute(['docker', 'image', 'inspect', self.image]))[0]
                labels = image.get('Config', {}).get('Labels') or {}
                if labels.get('org.opencontainers.image.title') != 'buzz-agents':
                    raise ToolError('runtime_image_identity_mismatch')
                settings = {'state_dir': str(self.root), 'owner': owner, 'relay': relay,
                            'image': self.image, 'image_id': image['Id'], 'memory_budget_mb': 5120, 'max_bots': 8}
                if old and old['image_id'] != settings['image_id']:
                    raise ToolError('image_upgrade_requires_review')
                atomic_json(self.control / 'settings.json', settings)
                return {'ok': True}
            if op == 'status':
                settings = read_json(self.control / 'settings.json', {})
                return {'ok': True, 'configured': bool(settings),
                        'relay': settings.get('relay'), 'owner': settings.get('owner'),
                        'bots': bot_records(settings) if settings else []}
            settings = self.settings()
            if op == 'deploy':
                payload = request['request']
                if not isinstance(payload, dict) or payload.get('op') != 'deploy' or 'agent' not in payload:
                    raise ToolError('only_deploy_is_allowed')
                return Deployer(settings).deploy(payload)
            if op == 'auth-start':
                return self.logins.start(settings, request['pubkey'])
            if op == 'schedule-init': return easy_schedule.initialize(settings)
            if op == 'schedule-save': return easy_schedule.configure(settings, request['schedule'])
            return easy_schedule.disable()


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(250)
        try:
            line = self.rfile.readline(LIMIT + 1)
            if len(line) > LIMIT:
                raise ToolError('request_too_large')
            answer = self.server.broker.dispatch(json.loads(line))
        except ToolError as exc:
            code = str(exc)
            answer = {'ok': False, 'error': code if re.fullmatch(r'[a-zA-Z0-9_]{1,160}', code) else 'broker_failed'}
        except Exception:
            answer = {'ok': False, 'error': 'broker_failed'}
        self.wfile.write(json.dumps(answer, ensure_ascii=False).encode() + b'\n')


def main():
    os.umask(0o077)
    for path in (STATE, CONTROL, easy_schedule.BASE):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    rpc = Path(SOCKET).parent
    rpc.mkdir(exist_ok=True)
    os.chown(rpc, 0, 10002)
    os.chmod(rpc, 0o750)
    Path(SOCKET).unlink(missing_ok=True)
    # A serialized RPC dispatcher bounds privileged concurrency; PTY reads are background only.
    with socketserver.UnixStreamServer(SOCKET, Handler) as server:
        os.chown(SOCKET, 0, 10002)
        os.chmod(SOCKET, 0o660)
        server.broker = Broker(os.environ['BUZZ_RUNTIME_IMAGE'])
        threading.Thread(target=server.broker.reconcile_saved_route, daemon=True).start()
        server.serve_forever()


if __name__ == '__main__': main()
