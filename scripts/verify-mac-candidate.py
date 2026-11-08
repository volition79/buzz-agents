"""Verify packaged bytes, not macOS native behavior. Run after --with-macos."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zipfile


def verify(directory):
    manifest = json.loads((directory/'manifest.json').read_text())
    assert 'macos-arm64' in manifest['target']
    assert manifest['macos_native_verified'] is False
    for name, record in manifest['files'].items():
        raw = (directory/name).read_bytes()
        assert len(raw) == record['size'], name
        assert hashlib.sha256(raw).hexdigest() == record['sha256'], name
    provider = (directory/'buzz-backend-hostinger-https-macos-arm64').read_bytes()
    connector = (directory/'Buzz-VPS-Connect-macos-arm64').read_bytes()
    for raw in (provider, connector):
        assert struct.unpack('<II', raw[:8]) == (0xfeedfacf, 0x0100000c), 'not native arm64 Mach-O'
    assert provider in connector, 'wrong embedded provider'
    windows = (directory/'Buzz-VPS-Connect.exe').read_bytes()
    assert windows[:2] == b'MZ'
    assert (directory/'buzz-backend-hostinger-https.exe').read_bytes() in windows
    with zipfile.ZipFile(directory/'docker-build-context.zip') as archive:
        assert archive.read('connect/assets/macos/Buzz-VPS-Connect-macos-arm64') == connector
        assert archive.read('connect/assets/Buzz-VPS-Connect.exe') == windows
        assert 'buzz_agents/connection_bundle.py' in archive.namelist()
        assert not any('buzz-pairing.json' in name for name in archive.namelist())
    with zipfile.ZipFile(directory/'public-source.zip') as archive:
        for name in ('connect/platform_darwin_arm64.go', 'connect/platform_default.go',
                     'connect/provider-history-macos-arm64.json', 'buzz_agents/connection_bundle.py'):
            assert name in archive.namelist(), name
    print('PASS: manifest hashes, native arm64 format, embedded Mac/Windows providers, Docker context and source package. Native Mac execution NOT verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    verify(parser.parse_args().directory)
