"""Optional mobile pairing sidecar; only the broker may reconcile Docker state."""
import fcntl
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

from .common import ToolError
from .host import execute, inspect_container
from . import portal_bootstrap as boot, portal_compose as compose

SERVICE = 'mobile-pairing'
MANAGED = 'buzz-mobile-pairing-v1'
BINARY = '/usr/local/bin/buzz-pair-relay'

# Run in our network-enabled portal, not the network-disabled broker. No human
# keys, cookies or account tokens. TLS and redirects remain strictly checked.
PROBE = """
import base64,json,os,socket,ssl,sys
host=sys.argv[1]
key=base64.b64encode(os.urandom(16)).decode()
with socket.create_connection((host,443),4) as raw:
 with ssl.create_default_context().wrap_socket(raw,server_hostname=host) as s:
  s.settimeout(4)
  s.sendall(('GET /pair HTTP/1.1\\r\\nHost: '+host+'\\r\\nUpgrade: websocket\\r\\nConnection: Upgrade\\r\\nSec-WebSocket-Version: 13\\r\\nSec-WebSocket-Key: '+key+'\\r\\n\\r\\n').encode())
  data=b''
  while b'\\r\\n\\r\\n' not in data and len(data)<16384:
   chunk=s.recv(1024)
   if not chunk: break
   data+=chunk
  import hashlib
  headers=data.split(b'\\r\\n\\r\\n')[0].decode('latin1').split('\\r\\n')
  fields={k.strip().lower():v.strip() for line in headers[1:] if ':' in line for k,v in [line.split(':',1)]}
  accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
  print(json.dumps({'reachable':len(headers[0].split())>1 and headers[0].split()[1]=='101' and fields.get('sec-websocket-accept')==accept}))
"""


def reachable(portal, host):
    try:
        return json.loads(execute(['docker', 'exec', portal, 'python', '-c', PROBE, host], timeout=12)).get('reachable') is True
    except (ToolError, ValueError, AttributeError):
        return False


def plan(containers, settings, bootstrap):
    url = urlsplit(settings['relay'])
    host = url.hostname or ''
    if (url.scheme != 'wss' or url.port not in (None, 443) or url.path not in ('', '/')
            or url.query or url.fragment or url.username or url.password
            or not re.fullmatch(r'[a-zA-Z0-9.-]+', host)):
        raise ToolError('mobile_relay_unsupported')
    candidates = []
    for c in containers:
        env = dict(v.split('=', 1) for v in c.get('Config', {}).get('Env') or [] if '=' in v)
        if env.get('RELAY_OWNER_PUBKEY') != settings['owner'] or not c.get('State', {}).get('Running'):
            continue
        if env.get('BUZZ_PAIRING_RELAY_URL'):
            raise ToolError('mobile_custom_pairing_preserved')
        for k, v in boot.labels(c).items():
            if k.startswith('traefik.http.routers.') and k.endswith('.rule') and v == f'Host(`{host}`)':
                candidates.append((c, k[:-5]))
    if len(candidates) != 1:
        raise ToolError('mobile_relay_missing_or_ambiguous')
    relay, prefix = candidates[0]
    routing = boot.discover_routing(containers, [(relay, prefix)])
    image = relay.get('Image', '')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise ToolError('mobile_relay_image_invalid')
    name = 'buzz-pair-' + hashlib.sha256(host.encode()).hexdigest()[:16]
    return dict(routing, host=host, image=image, relay_id=relay['Id'], name=name,
                project=bootstrap['project'], portal=bootstrap['upstream'])


def service(data):
    ident = data['name']
    labels = {'io.buzz-agents.managed': MANAGED,
              'io.buzz-agents.mobile-host': data['host'],
              'traefik.enable': 'true', 'traefik.docker.network': data['network'],
              f'traefik.http.routers.{ident}.rule': f'Host(`{data["host"]}`) && Path(`/pair`)',
              f'traefik.http.routers.{ident}.entrypoints': data['entrypoints'],
              f'traefik.http.routers.{ident}.tls.certresolver': data['resolver'],
              f'traefik.http.routers.{ident}.service': ident,
              f'traefik.http.services.{ident}.loadbalancer.server.port': '5000'}
    return {'image': data['image'], 'container_name': ident, 'pull_policy': 'never',
            'entrypoint': [BINARY], 'command': [], 'user': '1000:1000',
            'environment': {'BUZZ_PAIR_RELAY_BIND_ADDR': '0.0.0.0:5000', 'TOKIO_WORKER_THREADS': '2'},
            'init': True, 'restart': 'unless-stopped', 'read_only': True,
            'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
            'mem_limit': '128m', 'cpus': 0.25, 'pids_limit': 64,
            'networks': ['buzz_mobile_pairing'], 'labels': labels,
            'logging': {'driver': 'json-file', 'options': {'max-size': '5m', 'max-file': '2'}}}


def check_owned(c, data, path):
    labels = boot.labels(c)
    required = {**service(data)['labels'], 'com.docker.compose.project': data['project'],
                'com.docker.compose.service': SERVICE,
                'com.docker.compose.project.config_files': str(path)}
    if any(labels.get(k) != v for k, v in required.items()) or c.get('Image') != data['image']:
        raise ToolError('mobile_existing_container_preserved')
    config, host = c.get('Config', {}), c.get('HostConfig', {})
    if (config.get('Entrypoint') != [BINARY] or config.get('User') != '1000:1000'
            or config.get('Cmd') not in (None, []) or c.get('Mounts')
            or host.get('Privileged') or host.get('PortBindings')
            or not host.get('ReadonlyRootfs') or host.get('CapDrop') != ['ALL']
            or host.get('CapAdd') or 'no-new-privileges:true' not in (host.get('SecurityOpt') or [])
            or host.get('Memory') != 128*1024*1024 or host.get('PidsLimit') != 64
            or host.get('NanoCpus') != 250000000
            or host.get('RestartPolicy', {}).get('Name') != 'unless-stopped'
            or set(c.get('NetworkSettings', {}).get('Networks', {})) != {data['network']}
            or 'BUZZ_PAIR_RELAY_BIND_ADDR=0.0.0.0:5000' not in (config.get('Env') or [])):
        raise ToolError('mobile_existing_container_preserved')


def service_semantics(spec):
    # Compose's no-normalize JSON still omits empty command and expands network
    # lists to maps. Compare those equivalent forms without allowing extra fields.
    spec = dict(spec)
    if spec.get('command') in (None, []):
        spec.pop('command', None)
    if isinstance(spec.get('networks'), list):
        spec['networks'] = {name: None for name in spec['networks']}
    return spec


def reconcile(containers, self_id, settings, bootstrap):
    data = plan(containers, settings, bootstrap)
    path = compose.project_file(containers, self_id, data['project'])
    fd = os.open(path.parent / '.buzz-route.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _reconcile(containers, path, data)


def _reconcile(containers, path, data):
    # Already supplied by the relay operator or an earlier installation. Do not
    # adopt/rewrite another project's service, even when its name looks familiar.
    existing = inspect_container(data['name'])
    healthy = reachable(data['portal'], data['host'])
    if existing:
        try:
            check_owned(existing, data, path)
        except ToolError:
            if healthy:
                return {'state': 'available'}
            raise
    if healthy and not existing:
        return {'state': 'available'}
    for c in containers:
        if existing and c.get('Id') == existing.get('Id'):
            continue
        for key, rule in boot.labels(c).items():
            if (key.startswith('traefik.http.routers.') and key.endswith('.rule')
                    and data['host'] in rule and ('Path' in rule or '/pair' in rule)):
                raise ToolError('mobile_existing_route_preserved')
    image = json.loads(execute(['docker', 'image', 'inspect', data['image']]))[0]
    if (image.get('Id') != data['image']
            or image.get('Config', {}).get('Cmd') not in (None, [])
            or image.get('Config', {}).get('Labels', {}).get('org.opencontainers.image.source') != 'https://github.com/block/buzz'):
        raise ToolError('mobile_official_relay_image_required')
    try:
        execute(['docker', 'exec', data['relay_id'], 'test', '-x', BINARY])
    except ToolError:
        raise ToolError('mobile_pairing_binary_missing') from None
    cmd = compose.command(path, data['project'])
    original = path.read_bytes()
    before = compose.normalized(path, data['project'])
    raw = json.loads(execute(cmd + ['config', '--format', 'json', '--no-interpolate',
                                   '--no-env-resolution', '--no-path-resolution', '--no-normalize']))
    expected = service(data)
    old = raw.get('services', {}).get(SERVICE)
    if old and service_semantics(old) != service_semantics(expected):
        raise ToolError('mobile_existing_service_preserved')
    network = {'name': data['network'], 'external': True}
    old_net = raw.get('networks', {}).get('buzz_mobile_pairing')
    if old_net and old_net != network:
        raise ToolError('mobile_existing_network_preserved')
    raw['services'][SERVICE] = expected
    raw.setdefault('networks', {})['buzz_mobile_pairing'] = network
    proposed = (json.dumps(raw, indent=2) + '\n').encode()
    fd, name = tempfile.mkstemp(prefix='.buzz-mobile-', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(proposed)
        after = compose.normalized(Path(name), data['project'])
        for model in (before, after):
            model.get('services', {}).pop(SERVICE, None)
            model.setdefault('networks', {}).pop('buzz_mobile_pairing', None)
        if before != after:
            raise ToolError('mobile_existing_compose_would_change')
    finally:
        Path(name).unlink(missing_ok=True)
    # Keep the declaration on failure: Compose can recover a partial creation on
    # the next restart. Never remove containers or roll back a possibly live route.
    compose.replace_if_unchanged(path, original, proposed)
    execute(cmd + ['up', '-d', '--no-deps', '--pull', 'never', SERVICE])
    created = inspect_container(data['name'])
    if not created:
        raise ToolError('mobile_container_missing')
    check_owned(created, data, path)
    if not created.get('State', {}).get('Running'):
        raise ToolError('mobile_container_not_running')
    for attempt in range(5):
        if reachable(data['portal'], data['host']):
            return {'state': 'available'}
        if attempt < 4:
            time.sleep(1)
    return {'state': 'pending'}
