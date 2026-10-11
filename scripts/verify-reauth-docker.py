"""Real Docker lifecycle and process cleanup; CLI/AI fixtures, no subscriptions."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buzz_agents.config import public_key
from buzz_agents.host import Deployer, execute, container_name, inspect_container
from buzz_agents.policy import read_json
from buzz_agents.portal_broker import LoginSessions
from buzz_agents.reauth import Reauthentication, HOLD


def wait_for(predicate):
    deadline=time.monotonic()+35
    while not predicate():
        if time.monotonic()>deadline:raise RuntimeError('reauth fixture timeout')
        time.sleep(.2)


def main():
    image=os.environ['BUZZ_RUNTIME_IMAGE'];fixture='buzz-reauth-fixture:'+secrets.token_hex(6);names=[]
    with tempfile.TemporaryDirectory(prefix='buzz-reauth-') as tmp:
        base=Path(tmp)
        (base/'cli').write_text('''#!/usr/bin/env python3
from pathlib import Path
import time
mode=Path('/home/agent/login-mode').read_text().strip()
print('https://auth.openai.com/fixture-only',flush=True)
if mode=='wait':time.sleep(300)
raise SystemExit(0 if mode=='success' else 1)
''')
        (base/'worker').write_text('''#!/usr/bin/env python3
from pathlib import Path
import time
p=Path('/workspace/fixture-starts')
with p.open('a') as f:f.write('started\\n')
time.sleep(300)
''')
        (base/'Dockerfile').write_text('FROM '+image+'\nCOPY --chmod=0755 cli /usr/local/bin/codex-acp\nCOPY --chmod=0755 cli /usr/local/bin/claude-agent-acp\nCOPY --chmod=0755 worker /usr/local/bin/buzz-acp\n')
        subprocess.run(['docker','build','-t',fixture,str(base)],check=True,stdout=subprocess.DEVNULL)
        image_id=json.loads(execute(['docker','image','inspect',fixture]))[0]['Id']
        root=base/'state';settings={'state_dir':str(root),'owner':'a'*64,'relay':'wss://unused.invalid','image':fixture,'image_id':image_id}
        try:
            for provider,command in [('codex','codex-acp'),('claude','claude-agent-acp')]:
                key=secrets.token_hex(32);pubkey=public_key(key);name=container_name(pubkey);names.append(name)
                d=Deployer(settings)
                d.deploy({'op':'deploy','provider_config':{'memory_mb':512,'cpus':.1,'workspace':provider},'agent':{
                    'name':'reauth-fixture-'+provider,'relay_url':settings['relay'],'private_key_nsec':key,
                    'auth_tag':['auth',settings['owner'],'','b'*128],'respond_to':'owner-only','parallelism':1,
                    'launch':{'command':command,'args':[],'owner_pubkey':settings['owner'],'env':{},'policy_env':{}}}})
                folder=root/'bots'/pubkey;state=folder/'state';home=folder/'home'/provider;work=root/'workspaces'/provider
                wait_for(lambda:read_json(state/'runtime.json',{}).get('status')=='needs_login')
                baseline={p:p.read_bytes() for p in (folder/'config/config.json',root/'registry.json')}
                (work/'sentinel').write_text('preserve work');(home/'credential-sentinel').write_text('preserve auth home')
                before=inspect_container(name)['Id']
                sessions=LoginSessions();r=Reauthentication(base,sessions,root)
                def start(mode):
                    (home/'login-mode').write_text(mode)
                    return r.start(d,pubkey,secrets.token_hex(16))
                start('success');wait_for(lambda:not r.running)
                assert r.status()['reauth']['state']=='succeeded',r.status()
                wait_for(lambda:read_json(state/'runtime.json',{}).get('status')=='running')
                wait_for(lambda:(work/'fixture-starts').exists())
                assert inspect_container(name)['Id']==before
                starts=(work/'fixture-starts').read_text()
                start('fail');wait_for(lambda:not r.running)
                assert r.status()['reauth']['state']=='failed'
                assert (state/HOLD).exists()
                assert read_json(state/'runtime.json')['status']=='needs_login'
                execute(['docker','restart',name],timeout=30)
                time.sleep(3)
                assert read_json(state/'runtime.json')['status']=='needs_login'
                assert (work/'fixture-starts').read_text()==starts
                start('wait');wait_for(lambda:r.session is not None)
                # Cancel during the actual in-container login process.
                wait_for(lambda:(state/'portal-auth.json').exists())
                sessions.cancel(r.session);wait_for(lambda:not r.running)
                assert r.status()['reauth']['state']=='failed'
                assert (state/HOLD).exists() and not (state/'portal-auth.json').exists()
                start('success');wait_for(lambda:not r.running)
                assert r.status()['reauth']['state']=='succeeded',r.status()
                wait_for(lambda:(work/'fixture-starts').read_text()!=starts)
                for p,data in baseline.items():assert p.read_bytes()==data
                assert (work/'sentinel').read_text()=='preserve work'
                assert (home/'credential-sentinel').read_text()=='preserve auth home'
                assert inspect_container(name)['Id']==before
                execute(['docker','stop','--time','10',name],timeout=20)
                print(provider,'same container, success auto-run, failed hold, restart hold, cancellation, retry, identity/files passed')
        finally:
            for name in names:subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(['docker','image','rm',fixture],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if __name__=='__main__':main()
