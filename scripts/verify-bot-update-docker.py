"""Ephemeral real Docker update, both providers; no AI login or production VPS."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buzz_agents.bot_update import ExistingBotUpdater
from buzz_agents.config import public_key
from buzz_agents.host import Deployer, execute, container_name, inspect_container, service_name
from buzz_agents.policy import atomic_json, read_json


def main():
    image=os.environ['BUZZ_RUNTIME_IMAGE']
    prior='buzz-update-fixture:'+secrets.token_hex(6)
    subprocess.run(['docker','build','-t',prior,'-'],input=('FROM '+image+'\nLABEL io.buzz-agents.update-fixture=prior\n').encode(),check=True,stdout=subprocess.DEVNULL)
    image_id=json.loads(execute(['docker','image','inspect',image]))[0]['Id']
    old_id=json.loads(execute(['docker','image','inspect',prior]))[0]['Id']
    assert image_id!=old_id
    names=[]
    with tempfile.TemporaryDirectory(prefix='buzz-bot-update-') as tmp:
        root=Path(tmp)/'state'
        settings={'state_dir':str(root),'owner':'a'*64,'relay':'wss://unused.invalid','image':prior,'image_id':old_id}
        try:
            bots=[]
            for command in ('codex-acp','claude-agent-acp'):
                key=secrets.token_hex(32);pubkey=public_key(key);names.append(container_name(pubkey))
                request={'op':'deploy','provider_config':{'turn_limit':20,'daily_limit':100,'max_turn_seconds':600,'memory_mb':512,'cpus':.1},'agent':{
                    'name':'update-fixture-'+command,'relay_url':settings['relay'],'private_key_nsec':key,
                    'auth_tag':['auth',settings['owner'],'','b'*128],'respond_to':'owner-only','parallelism':1,
                    'launch':{'command':command,'args':[],'owner_pubkey':settings['owner'],'env':{},'policy_env':{'BUZZ_ACP_SYSTEM_PROMPT':'preserve role','BUZZ_ACP_MODEL':'fixture-model'}}}}
                d=Deployer(settings);d.deploy(request)
                c=read_json(root/'bots'/pubkey/'config/config.json')
                home=root/'bots'/pubkey/'home'/c['provider']
                (home/'credential-sentinel').write_text('private-fixture')
                (root/'bots'/pubkey/'state/quota.json').write_text('{"sentinel":true}')
                (root/'workspaces/team/page.txt').write_text('webtoon')
                # No auth marker: native stays needs_login, never connects externally.
                deadline=time.monotonic()+20
                while read_json(root/'bots'/pubkey/'state/runtime.json',{}).get('status')!='needs_login':
                    if time.monotonic()>deadline:raise RuntimeError('native auth gate timeout')
                    time.sleep(.2)
                bots.append((pubkey,c))
            settings={**settings,'image':image,'image_id':image_id}
            u=ExistingBotUpdater(Deployer(settings))
            for index,(pubkey,before) in enumerate(bots):
                u.apply(pubkey,u.preview(pubkey)['revision'],index==0)
                current=inspect_container(container_name(pubkey))
                assert current['Image']==image_id and current['State']['Running']
                after=read_json(root/'bots'/pubkey/'config/config.json')
                for field in ('pubkey','owner','provider','workspace','name','command'):assert after[field]==before[field]
                for field in ('BUZZ_PRIVATE_KEY','BUZZ_ACP_MODEL','BUZZ_ACP_SYSTEM_PROMPT'):assert after['env'][field]==before['env'][field]
                assert (root/'bots'/pubkey/'home'/before['provider']/'credential-sentinel').read_text()=='private-fixture'
                assert read_json(root/'bots'/pubkey/'state/quota.json')=={'sentinel':True}
                assert (root/'workspaces/team/page.txt').read_text()=='webtoon'
                assert after['policy']['turn_limit']==(0 if index==0 else 20)
                if index==0:
                    other=bots[1][0]
                    assert inspect_container(container_name(other))['Image']==old_id
                    assert read_json(root/'compose.yaml')['services'][service_name(other)]['image']==prior
            print(json.dumps({'ok':True,'providers':['codex','claude'],'actual_image_readback':True,'preserved':['identity','role','model','credential-files','quota','workspace','other-runtime']}))
        finally:
            for name in names:subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(['docker','image','rm',prior],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if __name__=='__main__':main()
