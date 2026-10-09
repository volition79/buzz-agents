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
    parser.add_argument('--legacy-upgrade',action='store_true')
    parser.add_argument('--portal-upgrade',action='store_true')
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
        # Match Hostinger's actual config_files path, including a single file.
        actual=Path('/docker')/project/'docker-compose.yml'
        run(['sudo','mkdir','-p',str(actual.parent)])
        run(['sudo','chown',str(os.getuid())+':'+str(os.getgid()),str(actual.parent)])
        target_broker=config['services']['broker']['image']
        target_portal=config['services']['portal']['image']
        if args.portal_upgrade:
            config['services']['broker']['image']='ghcr.io/volition79/buzz-agents-broker@sha256:56d45e699381baf6e79bc16934d24f64713be6b6e6a3bf21fef52f7a82df73c8'
            config['services']['portal']['image']='ghcr.io/volition79/buzz-agents-portal@sha256:844f142608f887dc314c4c810a40136d031a087d6619a7363b624966dd42bc81'
            for role in ('broker','portal'): run(['docker','pull',config['services'][role]['image']])
        config['services']['portal'].setdefault('environment',{})['BUZZ_FIXTURE_LITERAL']='a$$b'
        if args.legacy_upgrade:
            config['services']['broker']['image']='ghcr.io/volition79/buzz-agents-broker@sha256:00c183b8e229e5f0627fa9fcb43eecc3c9bb7c97c42104078f90004ee8126145'
            run(['docker','pull',config['services']['broker']['image']])
        actual.unlink(missing_ok=True)
        actual.write_text(json.dumps(config))
        cmd=['docker','compose','--env-file','/dev/null','-p',project,'-f',str(actual)]
        normalized_before=json.loads(run(cmd+['config','--format','json'],env=env))
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
            portal_before=json.loads(run(['docker','inspect',project+'-portal-1']))[0]
            if args.portal_upgrade:
                # Claim and pair through actual old HTTP API; keep fixture credentials in memory.
                logs=run(['docker','logs',project+'-portal-1']).decode()
                code=next(line.split(': ',1)[1] for line in logs.splitlines() if line.startswith('Buzz first setup code'))
                seed="""import io,json,urllib.request,zipfile
from pathlib import Path
base='http://127.0.0.1:8080'
headers={'Host':HOST,'X-Forwarded-Proto':'https','Origin':'https://'+HOST,'Content-Type':'application/json'}
def post(path,data):
 return urllib.request.urlopen(urllib.request.Request(base+path,json.dumps(data).encode(),headers))
r=post('/api/login',{'setup_code':CODE,'password':'ci-upgrade-password'})
headers['Cookie']=r.headers['Set-Cookie'].split(';')[0]
with zipfile.ZipFile(io.BytesIO(post('/api/pair/bundle',{}).read())) as z: pairing=json.loads(z.read('buzz-pairing.json'))
device=json.load(post('/api/pair/exchange',{'pairing_code':pairing['pairing_code'],'name':'ci-upgrade-device'}))
print(json.dumps({'account':Path('/portal/account.json').read_text(),'devices':Path('/portal/devices.json').read_text(),'token':device['token']}))
""".replace('HOST',repr(host)).replace('CODE',repr(code))
                preserved=json.loads(run(cmd+['exec','-T','portal','python','-c',seed],env=env))
                route_before_upgrade=route_state['Id']
                config['services']['broker']['image']=target_broker
                config['services']['portal']['image']=target_portal
                actual.write_text(json.dumps(config))
                run(cmd+['up','-d','--no-deps','broker','portal'],env=env)
                ready()
                route_state=json.loads(run(['docker','inspect',route]))[0]
                assert route_state['Id']==route_before_upgrade, 'portal upgrade replaced verified proxy'
                verify="""import json,urllib.request
from pathlib import Path
assert Path('/portal/account.json').read_text()==ACCOUNT
assert Path('/portal/devices.json').read_text()==DEVICES
h={'Host':HOST,'X-Forwarded-Proto':'https','Content-Type':'application/json','Authorization':'Bearer '+TOKEN}
r=urllib.request.Request('http://127.0.0.1:8080/api/device/check',b'{}',h)
assert json.load(urllib.request.urlopen(r))['ok']
from buzz_agents.portal_recover import request_code
request_code()
""".replace('ACCOUNT',repr(preserved['account'])).replace('DEVICES',repr(preserved['devices'])).replace('HOST',repr(host)).replace('TOKEN',repr(preserved['token']))
                run(cmd+['exec','-T','portal','python','-c',verify],env=env)
                assert 'Buzz recovery code' in run(['docker','logs',project+'-portal-1']).decode()
            if args.legacy_upgrade:
                assert not route_state['Config']['Labels'].get('com.docker.compose.config-hash')
                config['services']['broker']['image']=target_broker
                actual.unlink()
                actual.write_text(json.dumps(config))
                run(cmd+['up','-d','--no-deps','broker'],env=env)
            for _ in range(40):
                found=subprocess.run(['docker','inspect',route],capture_output=True)
                if found.returncode:
                    time.sleep(2)
                    continue
                route_state=json.loads(found.stdout)[0]
                if route_state['Config']['Labels'].get('com.docker.compose.config-hash'): break
                time.sleep(2)
            assert route_state['Config']['Labels'].get('com.docker.compose.config-hash'), 'route absent from genuine Compose metadata'
            project_ids=run(cmd+['ps','-a','-q'],env=env).decode().split()
            assert route_state['Id'] in project_ids, 'route not in Compose ps'
            assert route_state['Config']['Labels']['com.docker.compose.project.config_files']==str(actual)
            assert route_state['Config']['Labels']['traefik.http.routers.'+project+'.rule']=='Host(`'+host+'`)'
            assert (json.loads(run(['docker','inspect',project+'-portal-1']))[0]['Id']==portal_before['Id']) != args.portal_upgrade
            resolved=json.loads(run(cmd+['config','--format','json'],env=env))
            # Compose config serializes literal dollars escaped; verify the real
            # container value and equivalence of config output across rewrite.
            assert 'BUZZ_FIXTURE_LITERAL=a$b' in portal_before['Config']['Env']
            assert (resolved['services']['setup-route']['image']==resolved['services']['portal']['image']) != args.portal_upgrade
            assert '@sha256:' in resolved['services']['setup-route']['image']
            assert resolved['services']['portal']['environment']['BUZZ_FIXTURE_LITERAL']==normalized_before['services']['portal']['environment']['BUZZ_FIXTURE_LITERAL']
            assert json.loads(actual.read_text())['services']['portal']['environment']['BUZZ_FIXTURE_LITERAL']=='a$$b'

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
            run(cmd+['down','--volumes'],env=env)
            assert not run(['docker','ps','-aq','--filter','name=^/'+route+'$']).strip(), 'Compose down left route behind'
            print(json.dumps({'genuine_compose_route':True,'legacy_upgrade':args.legacy_upgrade,'portal_upgrade_preserves_account_devices_route':args.portal_upgrade,'no_domain_environment':True,'auto_route_running':True,'route_restart_reused':True,'fixture_relay_unchanged':True,'fixture_dns_only':True,'live_hostinger_verified':False,'real_traefik_tls_fixture':True,'host_proxy':args.host_proxy}))
        finally:
            subprocess.run(['docker','rm','-f',route],capture_output=True)
            subprocess.run(cmd+['down','--volumes'],env=env,capture_output=True)
            subprocess.run(['docker','rm','-f',relay],capture_output=True)
            subprocess.run(['docker','rm','-f',proxy],capture_output=True)
            subprocess.run(['docker','network','rm',network],capture_output=True)


if __name__=='__main__':main()
