"""Reconcile only this install's route through genuine Compose lifecycle metadata."""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from .common import ToolError
from . import portal_bootstrap as boot
from .host import execute, inspect_container
from .policy import atomic_json, read_json


def project_file(containers, self_id, project):
    own = [c for c in containers if c.get('Id', '').startswith(self_id)]
    expected = Path('/docker') / project / 'docker-compose.yml'
    if (len(self_id) < 12 or len(own) != 1
            or boot.labels(own[0]).get('com.docker.compose.service') != 'broker'
            or boot.labels(own[0]).get('com.docker.compose.project') != project
            or boot.labels(own[0]).get('com.docker.compose.project.config_files') != str(expected)):
        raise ToolError('bootstrap_compose_path_requires_review')
    for path in (expected.parent.parent, expected.parent, expected):
        if path.is_symlink():
            raise ToolError('bootstrap_compose_symlink_refused')
    if not expected.is_file() or expected.stat().st_size > 1024 * 1024:
        raise ToolError('bootstrap_compose_file_unavailable')
    return expected


def command(path, project):
    # Do not inherit broker env or the historical temporary hPanel working_dir.
    return ['docker', 'compose', '--project-directory', str(path.parent),
            '-p', project, '-f', str(path)]


def service(data):
    argv = boot.route_command(data, compose=True)
    tags = {}
    for i, value in enumerate(argv[:-1]):
        if value == '--label':
            key, val = argv[i+1].split('=', 1)
            if not key.startswith('com.docker.compose.'):
                tags[key] = val
    return {'image': data['image'], 'container_name': data['route_name'],
            'command': ['python', '-m', 'buzz_agents.portal_route'],
            'user': '10002:10002', 'read_only': True, 'init': True,
            'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
            'restart': 'unless-stopped', 'mem_limit': '256m', 'cpus': 0.25,
            'pids_limit': 48, 'environment': {'BUZZ_ROUTE_HOST': data['hostname'],
                                            'BUZZ_ROUTE_UPSTREAM': data['upstream']},
            'networks': ['buzz_setup_route'], 'labels': tags,
            'logging': {'driver': 'json-file', 'options': {'max-size': '5m', 'max-file': '2'}}}


def normalized(path, project):
    return json.loads(execute(command(path, project) + ['config', '--format', 'json']))


def preserved(before, after):
    """Allow only our one service/network to differ. Compare actual resolved semantics."""
    before, after = copy.deepcopy(before), copy.deepcopy(after)
    for model in (before, after):
        model.get('services', {}).pop('setup-route', None)
        model.setdefault('networks', {}).pop('buzz_setup_route', None)
    if before != after:
        raise ToolError('bootstrap_existing_compose_would_change')


def replace_if_unchanged(path, expected, replacement):
    if path.is_symlink() or path.read_bytes() != expected:
        raise ToolError('bootstrap_compose_changed_concurrently')
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, name = tempfile.mkstemp(prefix='.buzz-compose-', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        if path.is_symlink() or path.read_bytes() != expected:
            raise ToolError('bootstrap_compose_changed_concurrently')
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def check_owned_replacement(existing, data, path):
    tags = boot.labels(existing)
    required = {'io.buzz-agents.managed': boot.MANAGED+'-compose',
                'io.buzz-agents.bootstrap': data['fingerprint'],
                'com.docker.compose.project': data['project'],
                'com.docker.compose.service': 'setup-route',
                'com.docker.compose.project.config_files': str(path)}
    if (not tags.get('com.docker.compose.config-hash')
            or any(tags.get(key) != value for key, value in required.items())
            or existing.get('Image') != data['image']):
        raise ToolError('bootstrap_compose_route_identity_mismatch')


def check_current(existing, data, path):
    check_owned_replacement(existing, data, path)
    boot.check_route(existing, data, compose=True)


def reconcile(containers, self_id, data):
    path = project_file(containers, self_id, data['project'])
    lock = path.parent / '.buzz-route.lock'
    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _reconcile(path, data)


def _reconcile(path, data):
    cmd = command(path, data['project'])
    original = path.read_bytes()
    before = normalized(path, data['project'])
    raw = json.loads(execute(cmd + ['config', '--format', 'json', '--no-interpolate',
                                    '--no-env-resolution', '--no-path-resolution', '--no-normalize']))
    if set(raw.get('services', {})) - {'broker', 'portal', 'runtime-image', 'setup-route'}:
        raise ToolError('bootstrap_unexpected_compose_services')
    expected_service = service(data)
    current = raw.get('services', {}).get('setup-route')
    if current and current.get('labels', {}).get('io.buzz-agents.bootstrap') != data['fingerprint']:
        raise ToolError('bootstrap_existing_compose_route_requires_review')
    network = {'name': data['network'], 'external': True}
    old_network = raw.get('networks', {}).get('buzz_setup_route')
    if old_network and old_network != network:
        raise ToolError('bootstrap_existing_compose_network_requires_review')
    raw['services']['setup-route'] = expected_service
    raw.setdefault('networks', {})['buzz_setup_route'] = network
    proposed = (json.dumps(raw, indent=2) + '\n').encode()
    fd, name = tempfile.mkstemp(prefix='.buzz-validate-', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(proposed)
        after = normalized(Path(name), data['project'])
        preserved(before, after)
    finally:
        Path(name).unlink(missing_ok=True)
    route = data['route_name']
    backup_name = route + '-previous'
    existing = inspect_container(route)
    backup = inspect_container(backup_name)
    journal_path = path.parent / '.buzz-route-transaction.json'
    if journal_path.is_symlink():
        raise ToolError('bootstrap_compose_symlink_refused')
    journal = read_json(journal_path, {})
    # Recover a process interruption after rename. Never discard an unchecked backup.
    if backup:
        boot.check_route(backup, data)
        if journal.get('legacy_id') != backup['Id'] or journal.get('fingerprint') != data['fingerprint']:
            raise ToolError('bootstrap_route_recovery_requires_review')
        if existing:
            check_current(existing, data, path)
            if not existing.get('State', {}).get('Running'):
                raise ToolError('bootstrap_route_recovery_requires_review')
            # Already committed replacement; old cleanup cannot roll it back.
            try:
                execute(['docker', 'rm', backup['Id']])
                journal_path.unlink(missing_ok=True)
            except ToolError:
                pass
        else:
            execute(['docker', 'rename', backup['Id'], route])
            existing = backup
            if journal.get('was_running'):
                execute(['docker', 'start', backup['Id']])
                existing = inspect_container(route)
    legacy = existing and boot.labels(existing).get('io.buzz-agents.managed') == boot.MANAGED
    if existing:
        if legacy:
            boot.check_route(existing, data)
        else:
            check_current(existing, data, path)
    was_running = bool(existing and existing.get('State', {}).get('Running'))
    if legacy and journal:
        if journal.get('legacy_id') != existing['Id'] or journal.get('fingerprint') != data['fingerprint']:
            raise ToolError('bootstrap_route_recovery_requires_review')
        # A crash can occur after stop but before rename; canonical name is
        # still present then, so backup-name recovery alone is insufficient.
        was_running = bool(journal.get('was_running'))
    # Persist backup bytes privately, retaining first original for manual recovery.
    backup_path = path.parent / '.buzz-compose-before-route'
    try:
        fd = os.open(backup_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'wb') as file:
            file.write(original)
    changed = original != proposed
    renamed = False
    if legacy:
        atomic_json(journal_path, {'legacy_id': existing['Id'], 'was_running': was_running,
                                  'fingerprint': data['fingerprint'],
                                  'before_sha256': hashlib.sha256(original).hexdigest(),
                                  'after_sha256': hashlib.sha256(proposed).hexdigest()})
    try:
        if changed:
            replace_if_unchanged(path, original, proposed)
        elif path.read_bytes() != original:
            raise ToolError('bootstrap_compose_changed_concurrently')
        if legacy:
            if was_running:
                execute(['docker', 'stop', '--time', '10', existing['Id']])
            execute(['docker', 'rename', existing['Id'], backup_name])
            renamed = True
        execute(cmd + ['up', '-d', '--no-deps', '--pull', 'never', 'setup-route'])
        created = inspect_container(route)
        if not created:
            raise ToolError('bootstrap_compose_route_missing')
        check_current(created, data, path)
        if not created.get('State', {}).get('Running'):
            raise ToolError('bootstrap_compose_route_not_running')
        execute(['docker', 'exec', created['Id'], 'python', '-c',
                 "import socket,time\nfor n in range(20):\n try:\n  socket.create_connection(('127.0.0.1',8080),1).close();break\n except OSError:\n  if n==19: raise\n  time.sleep(0.25)"])
    except Exception:
        if renamed:
            created = inspect_container(route)
            if created:
                # A failed new route may violate readiness/security checks, but
                # rollback may remove only our exact newly created identity.
                check_owned_replacement(created, data, path)
                if created['Id'] == existing['Id']:
                    raise ToolError('bootstrap_route_recovery_requires_review')
                execute(['docker', 'rm', '-f', created['Id']])
            execute(['docker', 'rename', existing['Id'], route])
        if legacy and was_running:
            execute(['docker', 'start', existing['Id']])
        if changed and path.read_bytes() == proposed:
            replace_if_unchanged(path, proposed, original)
        if legacy:
            journal_path.unlink(missing_ok=True)
        raise

    # Commit point: a valid, running Compose route now owns the original URL.
    # Losing a cleanup response must never destroy the healthy replacement.
    if renamed:
        try:
            execute(['docker', 'rm', existing['Id']])
            journal_path.unlink(missing_ok=True)
        except ToolError:
            pass
    return created
