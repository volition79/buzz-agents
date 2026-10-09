"""Fetch exact public Compose bytes and verify no-env Docker bootstrap in CI."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',required=True)
    parser.add_argument('--start',action='store_true')
    args=parser.parse_args()
    with urllib.request.urlopen(args.url,timeout=30) as response:raw=response.read()
    assert raw==(ROOT/'docker-compose.yml').read_bytes(),'public URL bytes differ from checkout'
    env={k:v for k,v in os.environ.items() if not k.startswith(('BUZZ_','TRAEFIK_','COMPOSE_'))}
    with tempfile.TemporaryDirectory(prefix='buzz-url-') as tmp:
        compose=Path(tmp)/'docker-compose.yml';compose.write_bytes(raw)
        cmd=['docker','compose','--env-file','/dev/null','-p','buzz-url-check','-f',str(compose)]
        config=json.loads(subprocess.check_output(cmd+['config','--format','json'],env=env,cwd=tmp))
        spec=importlib.util.spec_from_file_location('release',ROOT/'scripts/render-portal-release.py')
        renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
        images={role:config['services'][name]['image'] for role,name in [('runtime','runtime-image'),('broker','broker'),('portal','portal')]}
        assert raw.decode()==renderer.render(images),'public artifact differs from reviewed template'
        assert config['name']=='buzz-url-check'
        assert set(config['services'])=={'runtime-image','broker','portal'}
        assert all('@sha256:' in s['image'] for s in config['services'].values())
        assert 'BUZZ_PUBLIC_URL' not in config['services']['portal'].get('environment',{})
        assert config['services']['portal']['labels']['traefik.enable']=='false'
        assert config['services']['broker']['network_mode']=='none'
        if args.start:
            assert os.environ.get('GITHUB_ACTIONS')=='true','CI only'
            subprocess.run(cmd+['pull'],env=env,cwd=tmp,check=True)
            subprocess.run(['python3',str(ROOT/'scripts/verify-bootstrap-docker.py'),'--compose',str(compose)],env=env,check=True)
            subprocess.run(['python3',str(ROOT/'scripts/verify-bootstrap-docker.py'),'--compose',str(compose),'--host-proxy'],env=env,check=True)
    print(json.dumps({'url_sha256':hashlib.sha256(raw).hexdigest(),'public_bytes_match':True,
                      'no_domain_environment':True,'fixture_dns_only':True,
                      'hostinger_import_verified':False,'runtime_smoke':args.start}))


if __name__=='__main__':main()
