"""Verify source/bundle/manifest correspondence; does not execute Windows code."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    assets = ROOT/'setup/assets'
    checked = 0
    with zipfile.ZipFile(assets/'server.zip') as z:
        for name in z.namelist():
            assert z.read(name) == (ROOT/name).read_bytes(), 'stale embedded source: '+name
            checked += 1
        for required in ['buzz_agents/bridge.py','buzz_agents/easy_schedule.py','package-lock.json']:
            assert required in z.namelist(), required
    assert (assets/'easy-bootstrap.py').read_bytes() == (ROOT/'scripts/easy-bootstrap.py').read_bytes()
    manifest = json.loads((ROOT/'dist/build-manifest.json').read_text())
    for name, record in manifest['files'].items():
        path = ROOT/'dist'/name if name=='Buzz-VPS-Setup.exe' else assets/name
        data=path.read_bytes()
        assert hashlib.sha256(data).hexdigest()==record['sha256'],name
        assert len(data)==record['size'],name
        if name.endswith('.exe'):
            assert data[:2]==b'MZ',name
            offset=int.from_bytes(data[60:64],'little')
            assert data[offset:offset+6]==b'PE\x00\x00\x64\x86',name
    with zipfile.ZipFile(ROOT/'dist/buzz-agents-easy-v0.3.0-candidate.zip') as z:
        for name in z.namelist():
            assert z.read(name)==(ROOT/'dist'/name).read_bytes(),name
        assert {'시작하기.md','LICENSE','THIRD_PARTY_GO_LICENSE.txt'} <= set(z.namelist())
    for line in (ROOT/'dist/SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1)
        assert hashlib.sha256((ROOT/'dist'/name).read_bytes()).hexdigest()==digest,name
    print(json.dumps({'status':'passed','embedded_source_files':checked,
                      'assurance':'local artifact integrity and PE x64 format only; not native/live execution'}))


if __name__=='__main__':main()
