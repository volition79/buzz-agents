"""Build the Windows candidate from reviewed local sources; never publish it."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def archive(paths):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(paths):
            name = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(name, (2026, 10, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, path.read_bytes())
    return stream.getvalue()


def prepare():
    assets = ROOT / 'setup/assets'
    assets.mkdir(parents=True, exist_ok=True)
    paths = [ROOT / n for n in ['Dockerfile', '.dockerignore', 'LICENSE', 'package.json', 'package-lock.json'] if (ROOT / n).exists()]
    paths += list((ROOT / 'buzz_agents').glob('*.py')) + list((ROOT / 'buzz_agents').glob('*.mjs'))
    paths += list((ROOT / 'guard-bin').glob('*'))
    paths += [ROOT / 'scripts' / n for n in ['install-host.sh', 'preflight.py']]
    (assets / 'server.zip').write_bytes(archive(paths))
    shutil.copyfile(ROOT / 'scripts/easy-bootstrap.py', assets / 'easy-bootstrap.py')
    env = {**os.environ, 'CGO_ENABLED':'0', 'GOOS':'windows', 'GOARCH':'amd64'}
    subprocess.run(['go','build','-trimpath','-ldflags=-s -w','-o', str(assets/'buzz-backend-hostinger.exe'),'.'],cwd=ROOT/'provider',env=env,check=True)
    return assets, env


def main():
    assets, env = prepare()
    out = ROOT/'dist'
    out.mkdir(exist_ok=True)
    exe = out/'Buzz-VPS-Setup.exe'
    subprocess.run(['go','build','-trimpath','-ldflags=-s -w','-o',str(exe),'.'],cwd=ROOT/'setup',env=env,check=True)
    manifest = {'version':'0.3.0-candidate','status':'local-build-not-live-verified','target':'windows-amd64',
                'files':{p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size} for p in [exe,assets/'server.zip',assets/'buzz-backend-hostinger.exe']}}
    (out/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    guide = ROOT/'docs/EASY-INSTALL.ko.md'
    if guide.exists(): shutil.copyfile(guide,out/'시작하기.md')
    shutil.copyfile(ROOT/'LICENSE',out/'LICENSE')
    shutil.copyfile(ROOT/'docs/THIRD_PARTY_GO_LICENSE.txt',out/'THIRD_PARTY_GO_LICENSE.txt')
    with zipfile.ZipFile(out/'buzz-agents-easy-v0.3.0-candidate.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name in ['Buzz-VPS-Setup.exe','build-manifest.json','시작하기.md','LICENSE','THIRD_PARTY_GO_LICENSE.txt']:
            if (out/name).exists(): z.write(out/name,name)
    package = out/'buzz-agents-easy-v0.3.0-candidate.zip'
    (out/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in [exe,package]))
    print(json.dumps(manifest,indent=2))


if __name__ == '__main__': main()
