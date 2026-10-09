"""Sent by the Windows setup helper over authenticated admin SSH. No HTTP installer."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import zipfile

ROOT = Path('/opt/buzz-agents')
MARKER = ROOT / 'host/easy-install.json'
VERSION = '0.3.0'


def validate(request):
    if not isinstance(request, dict) or set(request) != {'archive', 'sha256', 'public_key', 'owner', 'relay'}:
        raise ValueError('invalid_setup_request')
    if not re.fullmatch(r'[0-9a-f]{64}', request['owner']):
        raise ValueError('owner_must_be_hex_public_key')
    relay = urlsplit(request['relay'])
    if (relay.scheme != 'wss' or not relay.hostname or relay.username or relay.password
            or relay.path not in ('', '/') or relay.query or relay.fragment):
        raise ValueError('relay_must_be_wss_url')
    if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}(?: [A-Za-z0-9_.@-]+)?', request['public_key']):
        raise ValueError('invalid_dedicated_public_key')
    data = base64.b64decode(request['archive'], validate=True)
    if len(data) > 4 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != request['sha256']:
        raise ValueError('setup_archive_checksum_mismatch')
    return data


def unpack(data, target):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set()
        total = 0
        for item in archive.infolist():
            name = PurePosixPath(item.filename)
            if (name.is_absolute() or '..' in name.parts or '\\' in item.filename
                    or item.filename in names or item.is_dir()
                    or (item.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('unsafe_setup_archive')
            if not (item.filename in ('Dockerfile', '.dockerignore', 'LICENSE', 'package.json', 'package-lock.json')
                    or re.fullmatch(r'(?:buzz_agents|guard-bin|scripts)/[a-zA-Z0-9_.-]+', item.filename)):
                raise ValueError('unexpected_setup_file')
            names.add(item.filename)
            total += item.file_size
            if total > 8 * 1024 * 1024:
                raise ValueError('setup_archive_too_large')
        for required in ('Dockerfile', 'scripts/install-host.sh', 'buzz_agents/bridge.py'):
            if required not in names:
                raise ValueError('incomplete_setup_archive')
        for item in archive.infolist():
            path = target / item.filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(item))


def run(argv):
    # All output is setup diagnostics only. No cloud credentials are present.
    subprocess.run(argv, check=True, stdin=subprocess.DEVNULL)


def install_bridge(public_key):
    # Called only for this install identity, after marker/source checks.
    forced = Path('/usr/local/bin/buzz-agents-ssh')
    forced.write_text('#!/bin/sh\nexec sudo -n /usr/local/sbin/buzz-agents-easy-bridge "${SSH_ORIGINAL_COMMAND:-}"\n')
    forced.chmod(0o755)
    entry = Path('/usr/local/sbin/buzz-agents-easy-bridge')
    entry.write_text('#!/bin/sh\ncd /opt/buzz-agents\nexec /usr/bin/env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root PYTHONPATH=/opt/buzz-agents /usr/bin/python3 -m buzz_agents.bridge "$@"\n')
    entry.chmod(0o755)
    rule = 'buzzdeploy ALL=(root) NOPASSWD: /usr/local/sbin/buzz-agents-easy-bridge *\n'
    # Validate a private candidate before installing any sudoers fragment.
    with tempfile.NamedTemporaryFile(mode='w', dir='/etc/sudoers.d', prefix='.buzz-easy-') as f:
        f.write(rule); f.flush()
        run(['visudo', '-cf', f.name])
        dest = Path('/etc/sudoers.d/buzz-agents-easy')
        dest.write_text(rule); dest.chmod(0o440)
    folder = Path('/home/buzzdeploy/.ssh')
    folder.mkdir(mode=0o700, exist_ok=True)
    keys = folder / 'authorized_keys'
    line = 'restrict,pty,command="/usr/local/bin/buzz-agents-ssh" ' + public_key
    existing = keys.read_text() if keys.exists() else ''
    # Never append a weaker or duplicate authorization for the same key.
    blob = public_key.split()[1]
    entries = existing.splitlines()
    if any(blob in s and s != line for s in entries):
        raise ValueError('key_already_has_different_authorization')
    if line not in entries:
        entries.append(line)
    keys.write_text('\n'.join(entries) + '\n')
    keys.chmod(0o600)
    os.chown(keys, 0, 0)


def main():
    if os.geteuid() != 0:
        raise ValueError('initial_setup_requires_root_ssh')
    raw = sys.stdin.buffer.read(6 * 1024 * 1024 + 1)
    if len(raw) > 6 * 1024 * 1024:
        raise ValueError('setup_request_too_large')
    request = json.loads(raw)
    data = validate(request)
    expected = {'version': VERSION, 'source_sha256': request['sha256'], 'owner': request['owner'],
                'relay': request['relay'].rstrip('/')}
    if ROOT.exists():
        if not MARKER.is_file() or json.loads(MARKER.read_text()) != expected:
            raise ValueError('existing_installation_preserved_manual_upgrade_required')
        install_bridge(request['public_key'])
        print('BUZZ_SETUP_OK: existing matching installation')
        return
    if Path('/var/lib/buzz-agents-v2').exists():
        raise ValueError('existing_bot_data_preserved_manual_review_required')
    for tool in ('docker', 'sudo', 'visudo', 'useradd'):
        if not shutil.which(tool):
            raise ValueError('missing_server_tool_' + tool)
    run(['docker', 'compose', 'version'])
    run(['docker', 'info', '--format', '{{.OSType}}/{{.Architecture}}'])
    # Concurrent initial setup must not race account/config/key installation.
    import fcntl
    with open('/run/buzz-agents-easy-install.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if ROOT.exists():
            raise ValueError('setup_changed_retry_after_review')
        with tempfile.TemporaryDirectory(prefix='buzz-agents-build-') as directory:
            stage = Path(directory)
            unpack(data, stage)
            run(['docker', 'build', '-t', 'buzz-agents:' + VERSION, str(stage)])
            run(['sh', str(stage / 'scripts/install-host.sh'), str(stage), 'buzz-agents:' + VERSION,
                 request['owner'], request['relay']])
            # Marker records source identity before key setup; same-source retry is safe.
            MARKER.write_text(json.dumps(expected)); MARKER.chmod(0o600)
            install_bridge(request['public_key'])
    print('BUZZ_SETUP_OK: server installed; create bots in Windows Buzz, then authenticate here')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        message = str(error)
        print('BUZZ_SETUP_FAILED: ' + (message if re.fullmatch(r'[a-zA-Z0-9_]+', message) else 'inspect_previous_setup_output'), file=sys.stderr)
        raise SystemExit(1)
