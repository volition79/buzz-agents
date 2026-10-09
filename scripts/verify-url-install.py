"""Validate the exact public URL artifact using Docker; never contacts a VPS.

CI supplies documented Hostinger variables explicitly. Their injection by the
Hostinger URL importer is a separate, unproven live acceptance requirement.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--start', action='store_true')
    args = parser.parse_args()
    with urllib.request.urlopen(args.url, timeout=30) as response:
        raw = response.read()
    assert raw == (ROOT/'docker-compose.yml').read_bytes(), 'public URL bytes differ from checkout'
    env = {k:v for k,v in os.environ.items() if not k.startswith(('BUZZ_', 'COMPOSE_', 'TRAEFIK_'))}
    env['COMPOSE_PROJECT_NAME'] = 'buzz-url-check'
    with tempfile.TemporaryDirectory(prefix='buzz-url-') as tmp:
        compose = Path(tmp)/'docker-compose.yml'
        compose.write_bytes(raw)
        command = ['docker', 'compose', '--env-file', '/dev/null', '-f', str(compose)]
        missing = subprocess.run(command+['config','--format','json'], cwd=tmp, env=env, capture_output=True, text=True)
        assert missing.returncode != 0 and 'TRAEFIK_HOST' in missing.stderr, 'missing platform hostname must fail explicitly'
        env['TRAEFIK_HOST'] = 'fixture.example.invalid'
        config = json.loads(subprocess.check_output(command+['config','--format','json'],cwd=tmp,env=env))
        assert config['name'] == 'buzz-url-check'
        services = config['services']
        assert set(services) == {'runtime-image','broker','portal'}
        portal = services['portal']
        host = 'buzz-url-check.fixture.example.invalid'
        assert portal['environment']['BUZZ_PUBLIC_URL'] == 'https://'+host
        assert portal['labels']['traefik.http.routers.buzz-url-check-setup.rule'] == 'Host(`'+host+'`)'
        assert portal['labels']['traefik.http.routers.buzz-url-check-setup.service'] == 'buzz-url-check-setup'
        assert portal['labels']['traefik.http.services.buzz-url-check-setup.loadbalancer.server.port'] == '8080'
        renamed = json.loads(subprocess.check_output(command+['config','--format','json'],cwd=tmp,env={**env,'COMPOSE_PROJECT_NAME':'another-project'}))
        assert renamed['name'] == 'another-project'
        assert renamed['services']['portal']['environment']['BUZZ_PUBLIC_URL'] == 'https://another-project.fixture.example.invalid'
        assert renamed['services']['portal']['labels']['traefik.http.routers.another-project-setup.service'] == 'another-project-setup'
        assert all('@sha256:' in service['image'] for service in services.values())
        assert services['broker']['network_mode'] == 'none'
        assert not any(v.get('source')=='/var/run/docker.sock' for v in portal['volumes'])
        if args.start:
            # Only an ephemeral GitHub runner may execute --start.
            assert os.environ.get('GITHUB_ACTIONS') == 'true', 'runtime smoke is restricted to CI'
            subprocess.run(['docker','network','create','traefik-proxy'],check=True)
            try:
                subprocess.run(command+['pull'],cwd=tmp,env=env,check=True)
                subprocess.run(command+['up','-d'],cwd=tmp,env=env,check=True)
                check = "import os,urllib.request; from pathlib import Path; from buzz_agents.portal import broker_call; assert os.geteuid()==10002; assert not Path('/var/run/docker.sock').exists(); assert broker_call({'op':'status'})['configured'] is False; request=urllib.request.Request('http://127.0.0.1:8080/',headers={'Host':'buzz-url-check.fixture.example.invalid','X-Forwarded-Proto':'https'}); assert urllib.request.urlopen(request).status==200"
                for attempt in range(20):
                    result=subprocess.run(command+['exec','-T','portal','python','-c',check],cwd=tmp,env=env,capture_output=True)
                    if result.returncode==0:break
                    time.sleep(1)
                else:raise SystemExit('published URL runtime check failed')
            finally:
                subprocess.run(command+['down'],cwd=tmp,env=env,check=True)
                subprocess.run(['docker','network','rm','traefik-proxy'],check=True)
    print(json.dumps({'url_sha256':hashlib.sha256(raw).hexdigest(),'public_bytes_match':True,'platform_env_fixture':True,'hostinger_import_verified':False,'runtime_smoke':args.start}))


if __name__ == '__main__':main()
