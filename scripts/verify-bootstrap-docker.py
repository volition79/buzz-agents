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
    parser.add_argument('--host-proxy',action='store_true')
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
        network='buzz-fixture-relay_default'
        run(['docker','network','create',network])
        proxy='buzz-ci-traefik-fixture'
        relay='buzz-ci-relay-fixture'
        try:
            # Actual Traefik, renamed entrypoint/resolver/network; no external ACME request.
            proxy_network=['--network','host'] if args.host_proxy else ['--network',network,'--publish','127.0.0.1:19443:19443']
            run(['docker','run','-d','--name',proxy,*proxy_network,
                 '--volume','/var/run/docker.sock:/var/run/docker.sock:ro',
                 'traefik:v3.5.0','--providers.docker=true','--providers.docker.exposedbydefault=false',
                 '--entrypoints.fixture-secure.address=:19443',
                 '--certificatesresolvers.fixture-acme.acme.email=test@example.invalid',
                 '--certificatesresolvers.fixture-acme.acme.storage=/tmp/acme.json',
                 '--certificatesresolvers.fixture-acme.acme.tlschallenge=true',
                 '--certificatesresolvers.fixture-acme.acme.caserver=https://127.0.0.1:9/directory'])
            proxy_before=json.loads(run(['docker','inspect',proxy]))[0]
            run(['docker','run','-d','--name',relay,'--network',network,
                 '--label','com.docker.compose.project=ci-relay',
                 '--label','com.docker.compose.service=relay',
                 '--label','traefik.http.routers.fixture.rule=Host(`buzz.srv12345.hstgr.cloud`)',
                 '--label','traefik.http.routers.fixture.entrypoints=fixture-secure',
                 '--label','traefik.http.routers.fixture.tls.certresolver=fixture-acme',
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
            # Real HTTPS -> Traefik -> route -> portal. Only this synthetic certificate is untrusted.
            for attempt in range(30):
                tls=subprocess.run(['curl','--silent','--show-error','--fail','--insecure',
                    '--noproxy','*','--resolve',host+':19443:127.0.0.1',
                    '--header','Host: '+host,'https://'+host+':19443/api/hello'],capture_output=True)
                if tls.returncode==0: break
                time.sleep(2)
            assert tls.returncode==0, 'real Traefik TLS routing failed: '+tls.stderr.decode()
            run(cmd+['restart','portal'],env=env)
            ready()
            assert json.loads(run(['docker','inspect',route]))[0]['Id']==route_state['Id']
            after=json.loads(run(['docker','inspect',relay]))[0]
            assert before['Id']==after['Id'] and before['Config']==after['Config'] and after['State']['Running']
            proxy_after=json.loads(run(['docker','inspect',proxy]))[0]
            assert proxy_before['Id']==proxy_after['Id'] and proxy_before['Config']==proxy_after['Config']
            assert proxy_before['NetworkSettings']['Networks']==proxy_after['NetworkSettings']['Networks']
            assert before['NetworkSettings']['Networks']==after['NetworkSettings']['Networks']
            print(json.dumps({'no_domain_environment':True,'auto_route_running':True,'route_restart_reused':True,'fixture_relay_unchanged':True,'fixture_dns_only':True,'live_hostinger_verified':False,'real_traefik_tls_fixture':True,'host_proxy':args.host_proxy}))
        finally:
            subprocess.run(['docker','rm','-f',route],capture_output=True)
            subprocess.run(cmd+['down'],env=env,capture_output=True)
            subprocess.run(['docker','rm','-f',relay],capture_output=True)
            subprocess.run(['docker','rm','-f',proxy],capture_output=True)
            subprocess.run(['docker','network','rm',network],capture_output=True)


if __name__=='__main__':main()
