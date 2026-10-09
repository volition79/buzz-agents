"""Ephemeral Docker bootstrap fixture. No real Hostinger DNS/Relay/authentication."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time


def run(argv, **kwargs):
    return subprocess.check_output(argv, **kwargs)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--compose',required=True)
    args=parser.parse_args()
    assert os.environ.get('GITHUB_ACTIONS')=='true', 'CI fixture only'
    project='buzz-auto-ci'
    route='buzz-setup-'+hashlib.sha256(project.encode()).hexdigest()[:12]
    host=route+'.srv12345.hstgr.cloud'
    source=Path(args.compose).resolve()
    env={k:v for k,v in os.environ.items() if k not in ('BUZZ_PUBLIC_URL','BUZZ_SETUP_HOST','TRAEFIK_HOST','COMPOSE_PROJECT_NAME')}
    with tempfile.TemporaryDirectory() as tmp:
        override=Path(tmp)/'fixture.json'
        override.write_text(json.dumps({'services':{'portal':{'extra_hosts':{host:'192.0.2.1','buzz.srv12345.hstgr.cloud':'192.0.2.1'}}}}))
        cmd=['docker','compose','--env-file','/dev/null','-p',project,'-f',str(source),'-f',str(override)]
        config=json.loads(run(cmd+['config','--format','json'],env=env))
        assert 'BUZZ_PUBLIC_URL' not in config['services']['portal'].get('environment',{})
        run(['docker','network','create','traefik-proxy'])
        relay='buzz-ci-relay-fixture'
        try:
            # Metadata fixture splits owner and host across services, as templates can.
            run(['docker','run','-d','--name',relay,'--network','none',
                 '--label','com.docker.compose.project=ci-relay',
                 '--label','com.docker.compose.service=relay',
                 '--label','traefik.http.routers.fixture.rule=Host(`buzz.srv12345.hstgr.cloud`)',
                 '--env','RELAY_OWNER_PUBKEY='+'a'*64,
                 config['services']['portal']['image'],'python','-c','import time; time.sleep(600)'])
            before=json.loads(run(['docker','inspect',relay]))[0]
            run(cmd+['up','-d'],env=env)
            check="import os,urllib.request; from pathlib import Path; from buzz_agents.portal import broker_call; assert os.geteuid()==10002; assert not Path('/var/run/docker.sock').exists(); assert broker_call({'op':'status'})['configured'] is False; r=urllib.request.Request('http://127.0.0.1:8080/',headers={'Host':'"+host+"','X-Forwarded-Proto':'https'}); assert urllib.request.urlopen(r).status==200"
            def ready():
                for _ in range(30):
                    result=subprocess.run(cmd+['exec','-T','portal','python','-c',check],env=env,capture_output=True)
                    if result.returncode==0:return
                    time.sleep(2)
                raise AssertionError('automatic bootstrap failed in Docker fixture')
            ready()
            route_state=json.loads(run(['docker','inspect',route]))[0]
            assert route_state['State']['Running']
            assert route_state['Config']['User']=='10002:10002' and not route_state['Mounts']
            assert route_state['HostConfig']['ReadonlyRootfs'] and route_state['HostConfig']['CapDrop']==['ALL']
            # Exercise actual newly created route -> own portal, including expected TLS headers.
            proxy_check="import urllib.request; r=urllib.request.Request('http://127.0.0.1:8080/api/hello',headers={'Host':'"+host+"','X-Forwarded-Proto':'https'}); assert urllib.request.urlopen(r).status==200"
            run(['docker','exec',route,'python','-c',proxy_check])
            run(cmd+['restart','portal'],env=env)
            ready()
            assert json.loads(run(['docker','inspect',route]))[0]['Id']==route_state['Id']
            after=json.loads(run(['docker','inspect',relay]))[0]
            assert before['Id']==after['Id'] and before['Config']==after['Config'] and after['State']['Running']
            print(json.dumps({'no_domain_environment':True,'auto_route_running':True,'route_restart_reused':True,'fixture_relay_unchanged':True,'fixture_dns_only':True,'live_hostinger_verified':False}))
        finally:
            subprocess.run(['docker','rm','-f',route],capture_output=True)
            subprocess.run(cmd+['down'],env=env,capture_output=True)
            subprocess.run(['docker','rm','-f',relay],capture_output=True)
            subprocess.run(['docker','network','rm','traefik-proxy'],capture_output=True)


if __name__=='__main__':main()
