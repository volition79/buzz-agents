"""Check package bytes and declared container boundaries, not live Docker behavior."""
import hashlib
import json
from pathlib import Path
import struct
import zipfile
import yaml

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist/portal-v0.4'


def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    for name, record in manifest['files'].items():
        raw=(OUT/name).read_bytes()
        assert len(raw)==record['size'] and hashlib.sha256(raw).hexdigest()==record['sha256'], name
        if name.endswith('.exe'):
            assert raw[:2]==b'MZ', name
            offset=struct.unpack_from('<I',raw,0x3c)[0]
            assert raw[offset:offset+4]==b'PE\0\0' and struct.unpack_from('<H',raw,offset+4)[0]==0x8664,name
    with zipfile.ZipFile(OUT/'docker-build-context.zip') as archive:
        for info in archive.infolist():
            path=Path(info.filename)
            assert not path.is_absolute() and '..' not in path.parts
            assert '.env' not in path.parts and '__pycache__' not in path.parts
            assert archive.read(info.filename)==(ROOT/path).read_bytes(),info.filename
        assert archive.read('connect/assets/Buzz-VPS-Connect.exe')==(OUT/'Buzz-VPS-Connect.exe').read_bytes()
        for required in ['buzz_agents/portal.py','buzz_agents/portal_broker.py','buzz_agents/portal_auth.py',
                         'buzz_agents/web/index.html','buzz_agents/web/app.js','buzz_agents/web/style.css',
                         'Dockerfile','Dockerfile.portal','scripts/preflight.py','package-lock.json']:
            assert required in archive.namelist(),required
    config=yaml.safe_load((OUT/'compose.hostinger.yaml').read_text())
    assert set(config['services'])=={'portal','broker','runtime-image'}
    portal,broker=config['services']['portal'],config['services']['broker']
    assert portal['user']=='10002:10002' and broker['network_mode']=='none'
    assert not any('docker.sock' in x for x in portal['volumes'])
    assert any('docker.sock' in x for x in broker['volumes'])
    assert not any('buzz-rpka' in x for x in broker['volumes'])
    for name,service in config['services'].items():
        assert not service.get('privileged') and not service.get('ports'),name
        assert service['read_only'] is True and service['cap_drop']==['ALL'],name
    with zipfile.ZipFile(OUT/'public-source.zip') as archive:
        for name in archive.namelist():
            assert '__pycache__' not in name and '/assets/' not in name and '.sonol-test/runtime/' not in name,name
            assert not name.endswith(('.exe','.zip','.sqlite')),name
            assert archive.read(name)==(ROOT/name).read_bytes(),name
        for required in ['.github/workflows/portal-images.yml','connect/main.go','web-provider/main.go',
                         'scripts/render-portal-release.py','scripts/build-portal.py','tests/test_portal.py','connect/provider-history.json']:
            assert required in archive.namelist(),required
    workflow=yaml.safe_load((ROOT/'.github/workflows/portal-images.yml').read_text())
    trigger=workflow.get('on',workflow.get(True)) # PyYAML YAML 1.1 parses 'on' as bool.
    assert set(trigger)=={'workflow_dispatch'},'publication must never auto-run on push'
    print(json.dumps({'status':'passed','manifest_files':len(manifest['files']),
                      'windows_pe':'amd64','archive_source_match':True,
                      'docker_socket':'network-disabled broker only','live_docker_test':False}))


if __name__=='__main__':main()
