"""Local candidate packaging. Does not upload, publish, deploy, or embed credentials."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--with-macos', action='store_true',
                        help='Build unsigned Apple Silicon candidates; not native acceptance or publication')
    args = parser.parse_args()
    output = Path(os.environ.get('BUZZ_BUILD_OUTPUT', str(ROOT / 'dist/portal-v0.4')))
    output.mkdir(parents=True, exist_ok=True)
    assets = ROOT / 'connect/assets'
    assets.mkdir(parents=True, exist_ok=True)
    mac_assets = assets / 'macos'
    mac_assets.mkdir(exist_ok=True)
    (mac_assets / '.keep').write_text('Candidate assets only. No personal pairing codes.\n')
    # Default publication cannot accidentally include a previous Mac candidate.
    mac_connector = mac_assets / 'Buzz-VPS-Connect-macos-arm64'
    if not args.with_macos:
        mac_connector.unlink(missing_ok=True)
        for name in ('Buzz-VPS-Connect-macos-arm64', 'buzz-backend-hostinger-https-macos-arm64'):
            (output / name).unlink(missing_ok=True)
    env = {**os.environ, 'CGO_ENABLED': '0', 'GOOS': 'windows', 'GOARCH': 'amd64'}
    go = os.environ.get('BUZZ_BUILD_GO', 'go')
    for module, destination in [('web-provider', assets/'buzz-backend-hostinger-https.exe'),
                                ('connect', assets/'Buzz-VPS-Connect.exe')]:
        subprocess.run([go, 'build', '-buildvcs=false', '-trimpath', '-ldflags=-s -w', '-o', str(destination), '.'],
                       cwd=ROOT/module, env=env, check=True)
    for filename in ('Buzz-VPS-Connect.exe', 'buzz-backend-hostinger-https.exe'):
        shutil.copyfile(assets/filename, output/filename)
    if args.with_macos:
        mac_env = {**os.environ, 'CGO_ENABLED': '0', 'GOOS': 'darwin', 'GOARCH': 'arm64'}
        for module, destination in [('web-provider', assets/'buzz-backend-hostinger-https-macos-arm64'),
                                    ('connect', mac_connector)]:
            subprocess.run([go, 'build', '-buildvcs=false', '-trimpath', '-ldflags=-s -w',
                            '-o', str(destination), '.'], cwd=ROOT/module, env=mac_env, check=True)
            shutil.copyfile(destination, output/destination.name)
    shutil.copyfile(ROOT/'compose.portal.yaml', output/'compose.hostinger.yaml')
    shutil.copyfile(ROOT/'docs/PORTAL-INSTALL.ko.md', output/'START-HERE.ko.md')
    paths = [ROOT/n for n in ('Dockerfile', 'Dockerfile.portal', '.dockerignore', 'LICENSE',
                              'package.json', 'package-lock.json', 'compose.portal.yaml')]
    for folder in ('buzz_agents', 'guard-bin', 'patches'):
        paths.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    paths.extend([ROOT/'scripts/preflight.py', assets/'Buzz-VPS-Connect.exe'])
    paths.extend(p for p in mac_assets.iterdir() if p.is_file())
    with zipfile.ZipFile(output/'docker-build-context.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), (2026,10,9,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if path.parent.name == 'guard-bin' else 0o100644) << 16
            archive.writestr(info, path.read_bytes())
    # A concrete reviewable publication payload, selected from source only.
    source = [ROOT/n for n in ('Dockerfile', 'Dockerfile.portal', '.dockerignore', '.gitignore',
                               'LICENSE', 'README.md', 'CONTRACT.md', 'TASK.md', 'package.json',
                               'package-lock.json', 'compose.portal.yaml', 'compose.automation.yaml', 'docker-compose.yml')]
    for folder in ('buzz_agents', 'guard-bin', 'patches', 'scripts', 'tests', 'web-provider', 'connect', 'provider', 'setup', '.github'):
        source.extend(p for p in (ROOT/folder).rglob('*') if p.is_file()
                      and '__pycache__' not in p.parts and 'assets' not in p.parts
                      and p.suffix in ('.rs', '.py', '.mjs', '.go', '.mod', '.sh', '.html', '.css', '.js', '.yml', '.yaml', '.png'))
    source.extend(p for p in (ROOT/'guard-bin').iterdir() if p.is_file())
    source.extend((ROOT/'docs').glob('*.md'))
    source.append(ROOT/'docs/THIRD_PARTY_GO_LICENSE.txt')
    source.append(ROOT/'connect/provider-history.json')
    source.append(ROOT/'connect/provider-history-macos-arm64.json')
    source.extend([ROOT/'buzz_agents/swap-seccomp.json', ROOT/'buzz_agents/SWAP-SECCOMP-LICENSE'])
    with zipfile.ZipFile(output/'public-source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(source)):
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), (2026,10,9,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if path.parent.name == 'guard-bin' else 0o100644) << 16
            archive.writestr(info, path.read_bytes())
    files = {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size': p.stat().st_size}
             for p in output.iterdir() if p.is_file() and p.name not in ('manifest.json', 'SHA256SUMS')}
    manifest = {'version': '0.4.0-candidate', 'status': 'local-build-not-live-verified',
                'target': ['windows-amd64', 'linux-amd64-docker'] + (['macos-arm64'] if args.with_macos else []),
                'macos_native_verified': False, 'files': files}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (output/'SHA256SUMS').write_text(''.join(v['sha256']+'  '+k+'\n' for k,v in sorted(files.items())))
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__': main()
