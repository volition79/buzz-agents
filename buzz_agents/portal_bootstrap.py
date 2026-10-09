"""Server-derived installation plan. No user-provided host, image or Docker command."""
import hashlib
import json
import re
import socket
from .common import ToolError

BASE = re.compile(r'(?:^|\.)(srv[0-9]+\.hstgr\.cloud)$')
NAME = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z')
HEX = re.compile(r'[a-f0-9]{64}\Z')
MANAGED = 'buzz-setup-route-v1'


def labels(container):
    return container.get('Config', {}).get('Labels') or {}


def plan(containers, self_id):
    own = [c for c in containers if c.get('Id', '').startswith(self_id)]
    if len(own) != 1 or len(self_id) < 12:
        raise ToolError('bootstrap_broker_identity_missing')
    own = own[0]
    project = labels(own).get('com.docker.compose.project', '')
    if not NAME.fullmatch(project) or labels(own).get('com.docker.compose.service') != 'broker':
        raise ToolError('bootstrap_broker_identity_invalid')
    portals = [c for c in containers if labels(c).get('com.docker.compose.project') == project
               and labels(c).get('com.docker.compose.service') == 'portal']
    if len(portals) != 1:
        raise ToolError('bootstrap_own_portal_missing_or_ambiguous')
    portal = portals[0]
    upstream = portal.get('Name', '').lstrip('/')
    image = portal.get('Image', '')
    if not NAME.fullmatch(upstream) or not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise ToolError('bootstrap_own_portal_identity_invalid')
    # A Buzz template may split owner env and Traefik labels across services.
    relay_projects = set()
    for c in containers:
        env = dict(item.split('=', 1) for item in c.get('Config', {}).get('Env') or [] if '=' in item)
        key = labels(c).get('com.docker.compose.project')
        if key and key != project and HEX.fullmatch(env.get('RELAY_OWNER_PUBKEY', '')):
            relay_projects.add(key)
    bases = {}
    routers = []
    for c in containers:
        if labels(c).get('com.docker.compose.project') not in relay_projects or not c.get('State', {}).get('Running'):
            continue
        for key, value in labels(c).items():
            if key.startswith('traefik.http.routers.') and key.endswith('.rule'):
                for host in re.findall(r'Host\(`([a-zA-Z0-9.-]+)`\)', value):
                    match = BASE.search(host.lower())
                    if match:
                        bases.setdefault(match[1], set()).add(host.lower())
                        routers.append((c, key[:-5]))
    if not bases:
        raise ToolError('bootstrap_hostinger_relay_domain_not_found')
    if len(bases) != 1:
        raise ToolError('bootstrap_relay_domains_ambiguous')
    base, hosts = next(iter(bases.items()))
    routing = discover_routing(containers, routers)
    ident = 'buzz-setup-' + hashlib.sha256(project.encode()).hexdigest()[:12]
    hostname = ident + '.' + base
    result = {'project': project, 'hostname': hostname, 'url': 'https://' + hostname,
              'relay_hosts': sorted(hosts), 'route_name': ident, 'upstream': upstream, 'image': image, **routing}
    result['fingerprint'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def retain_verified_route(data, saved, containers):
    """A portal UI upgrade may reuse its unchanged, previously verified proxy image.

    Never migrate routing/security settings or replace a proxy through this path.
    """
    if not saved or saved.get('fingerprint') == data['fingerprint']:
        return data
    previous = {k: v for k, v in saved.items() if k != 'fingerprint'}
    if hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest() != saved.get('fingerprint'):
        raise ToolError('bootstrap_saved_route_invalid')
    same = lambda value: {k: v for k, v in value.items() if k not in ('image', 'fingerprint')}
    if same(data) != same(saved):
        raise ToolError('bootstrap_existing_route_requires_review')
    existing = [c for c in containers if c.get('Name', '').lstrip('/') == saved['route_name']]
    if len(existing) != 1:
        raise ToolError('bootstrap_previous_route_missing')
    check_route(existing[0], saved, compose=True)
    return saved


def networks(container):
    return set(container.get('NetworkSettings', {}).get('Networks', {})) - {'host', 'none', 'bridge'}


def discover_routing(containers, routers):
    """Use existing HTTPS router settings, never assume network or TLS names."""
    proxies = []
    for c in containers:
        image = c.get('Config', {}).get('Image', '').split('@')[0].split(':')[0]
        if image in ('traefik', 'library/traefik', 'docker.io/library/traefik', 'docker.io/traefik') and c.get('State', {}).get('Running'):
            proxies.append(c)
    candidates = set()
    for relay, prefix in routers:
        tags = labels(relay)
        entrypoints = tags.get(prefix + '.entrypoints', '')
        resolver = tags.get(prefix + '.tls.certresolver', '')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+(?:,[a-zA-Z0-9_-]+)*', entrypoints) or not re.fullmatch(r'[a-zA-Z0-9_-]+', resolver):
            continue
        for proxy in proxies:
            shared = networks(relay)
            if proxy.get('HostConfig', {}).get('NetworkMode') != 'host':
                shared &= networks(proxy)
            explicit = tags.get('traefik.docker.network')
            if explicit:
                shared &= {explicit}
            for network in shared:
                if NAME.fullmatch(network):
                    candidates.add((proxy['Id'], network, entrypoints, resolver))
    if len(candidates) != 1:
        raise ToolError('bootstrap_proxy_route_missing' if not candidates else 'bootstrap_proxy_route_ambiguous')
    proxy_id, network, entrypoints, resolver = candidates.pop()
    return {'network': network, 'entrypoints': entrypoints, 'resolver': resolver}


def verify_dns(data, resolver=socket.getaddrinfo):
    def addresses(host):
        try:
            return {item[4][0] for item in resolver(host, 443, type=socket.SOCK_STREAM)}
        except OSError:
            raise ToolError('bootstrap_dns_not_ready') from None
    candidate = addresses(data['hostname'])
    references = [addresses(host) for host in data['relay_hosts']]
    if not candidate or not references or not all(candidate == value for value in references):
        raise ToolError('bootstrap_dns_mismatch')


def route_command(data, compose=False):
    ident = data['project'] if compose else data['route_name']
    tag = {
        'io.buzz-agents.managed': MANAGED + ('-compose' if compose else ''),
        'io.buzz-agents.bootstrap': data['fingerprint'],
        'com.docker.compose.project': data['project'],
        'com.docker.compose.service': 'setup-route',
        'traefik.enable': 'true', 'traefik.docker.network': data['network'],
        'traefik.http.routers.'+ident+'.rule': 'Host(`'+data['hostname']+'`)',
        'traefik.http.routers.'+ident+'.entrypoints': data['entrypoints'],
        'traefik.http.routers.'+ident+'.tls.certresolver': data['resolver'],
        'traefik.http.routers.'+ident+'.service': ident,
        'traefik.http.services.'+ident+'.loadbalancer.server.port': '8080',
    }
    command = ['docker', 'create', '--name', data['route_name'], '--network', data['network'],
               '--user', '10002:10002', '--read-only', '--cap-drop', 'ALL',
               '--security-opt', 'no-new-privileges:true', '--init',
               '--restart', 'unless-stopped', '--memory', '256m', '--cpus', '0.25',
               '--pids-limit', '48', '--log-opt', 'max-size=5m', '--log-opt', 'max-file=2',
               '--env', 'BUZZ_ROUTE_HOST='+data['hostname'], '--env', 'BUZZ_ROUTE_UPSTREAM='+data['upstream']]
    for key, value in tag.items():
        command += ['--label', key+'='+value]
    return command + [data['image'], 'python', '-m', 'buzz_agents.portal_route']


def check_route(existing, data, compose=False):
    tag = labels(existing)
    if (tag.get('io.buzz-agents.managed') != MANAGED + ('-compose' if compose else '')
            or tag.get('io.buzz-agents.bootstrap') != data['fingerprint']
            or tag.get('com.docker.compose.project') != data['project']
            or existing.get('Image') != data['image']):
        raise ToolError('bootstrap_existing_route_requires_review')
    config = existing.get('Config', {})
    host = existing.get('HostConfig', {})
    env = config.get('Env') or []
    expected_labels = {}
    command = route_command(data, compose=compose)
    for index, item in enumerate(command[:-1]):
        if item == '--label':
            key, value = command[index+1].split('=', 1)
            expected_labels[key] = value
    if (config.get('User') != '10002:10002'
            or config.get('Cmd') != ['python','-m','buzz_agents.portal_route']
            or config.get('Entrypoint') not in (None, [])
            or not host.get('ReadonlyRootfs') or host.get('Privileged')
            or host.get('CapDrop') != ['ALL'] or host.get('CapAdd')
            or host.get('Memory') != 256*1024*1024
            or host.get('NanoCpus') != 250000000 or host.get('PidsLimit') != 48
            or host.get('RestartPolicy', {}).get('Name') != 'unless-stopped'
            or 'no-new-privileges:true' not in (host.get('SecurityOpt') or [])
            or existing.get('Mounts') or host.get('PortBindings')
            or any(host.get(key) for key in ('ExtraHosts','Dns','DnsSearch','DnsOptions','Links'))
            or set(existing.get('NetworkSettings', {}).get('Networks', {})) != {data['network']}
            or 'BUZZ_ROUTE_HOST='+data['hostname'] not in env
            or 'BUZZ_ROUTE_UPSTREAM='+data['upstream'] not in env
            or any(tag.get(key) != value for key, value in expected_labels.items())):
        raise ToolError('bootstrap_existing_route_requires_review')
