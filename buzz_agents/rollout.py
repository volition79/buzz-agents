"""Durable per-bot release reconciliation. Uncertain work is never replayed."""
import json
import os
import re
import threading
import time
from pathlib import Path
from .common import ToolError
from .host import Deployer, execute, container_name
from .bot_update import ExistingBotUpdater
from .policy import atomic_json, read_json
from . import release_contract, memory_settings

class Rollout:
    def __init__(self, broker, contract=None, runner=execute):
        self.broker, self.contract, self.run = broker, contract, runner
        self.path = broker.control / 'release-update.json'
        self.lock = threading.RLock()

    def status(self):
        with self.lock:
            return read_json(self.path, {'state':'legacy', 'bots':{}})

    def save(self, job):
        with self.lock:
            atomic_json(self.path, job)

    def retry(self):
        # A separate durable request avoids racing a background snapshot write.
        with self.lock:
            atomic_json(self.path.with_name('release-retry.json'), {'requested': True})
        return {'ok':True}

    def verify_management(self):
        ids = self.run(['docker','container','ls','-a','--format','{{.ID}}']).decode().split()
        if not ids or len(ids)>100:
            raise ToolError('release_management_unavailable')
        containers = json.loads(self.run(['docker','inspect',*ids]))
        ident = os.environ.get('HOSTNAME','')
        own = [c for c in containers if ident and c.get('Id','').startswith(ident)
               and (c.get('Config',{}).get('Labels') or {}).get('com.docker.compose.service')=='broker']
        if len(own)!=1:
            raise ToolError('release_management_unavailable')
        release_contract.compatible_portal(self.contract,own[0],containers,self.run)

    def tick(self):
        if not self.contract:
            return
        job = self.status()
        retry_path=self.path.with_name('release-retry.json')
        with self.lock:
            if retry_path.exists():
                for item in job.get('bots',{}).values():
                    if item.get('state') in ('failed','interrupted','applying'):
                        item['state']='pending'; item.pop('error',None)
                retry_path.unlink()
        if job.get('target') != self.contract['release']:
            # Do not lose an incomplete old rollout's evidence by adopting a new target.
            if job.get('target') and any(v.get('state')=='applying' for v in job.get('bots',{}).values()):
                job['state']='interrupted'; job['error']='release_previous_update_uncertain'
                for item in job['bots'].values():
                    if item.get('state')=='applying': item['state']='interrupted'
                self.save(job); return
            job={'target':self.contract['release'],'runtime':self.contract['runtime'],'state':'checking','bots':{}}
        try:
            self.verify_management()
            release_contract.image(self.run,self.contract['runtime'],pull=True)
            with self.broker.lock:
                if self.broker.update_running or self.broker.reauth.running:
                    job['state']='waiting'; self.save(job); return
                settings=self.broker.settings()
                d=Deployer(settings)
                registry=read_json(d.root/'registry.json',{})
                for key in list(job['bots']):
                    if key not in registry: del job['bots'][key]
                for key in sorted(registry):
                    item=job['bots'].setdefault(key,{'state':'pending'})
                    if item['state'] in ('failed','interrupted'): continue
                    updater=ExistingBotUpdater(d)
                    try:
                        config,actual,revision=updater.inspect(key)
                        item['name']=config['name']
                        choice=memory_settings.load(d.root).get(key,{})
                        if choice and (choice['desired_mb'] != config['memory_mb'] or choice['committed_mb'] != config['memory_mb']):
                            item.update(state='waiting',error='memory_change_pending'); continue
                        if choice and not memory_settings.compatible_limits(actual,config['memory_mb']):
                            item.update(state='waiting',error='deployment_memory_limit_mismatch'); continue
                        if actual and actual.get('Image')==settings['image_id'] and memory_settings.limits_match(actual,config['memory_mb']) and item['state']!='applying':
                            item.update(state='current'); item.pop('error',None); continue
                        if item['state']=='applying':
                            item.update(state='interrupted',error='release_update_interrupted'); continue
                        state=read_json(d.root/'bots'/key/'state/runtime.json',{})
                        if not actual:
                            item.update(state='waiting',error='release_container_missing'); continue
                        if (d.root/'bots'/key/'state/reauth-hold.json').exists():
                            item.update(state='waiting',error='bot_reauthentication_pending'); continue
                        if actual.get('State',{}).get('Running') or state.get('status') not in ('stopped','held','needs_login'):
                            # Old and current upstream have no lossless drain capability.
                            item.update(state='waiting',error='update_requires_interruption_confirmation'); continue
                        if (d.root/'bots'/key/'state/portal-auth.json').exists():
                            item.update(state='waiting',error='authentication_already_in_progress'); continue
                        item.update(state='applying',container_id=actual['Id']); item.pop('error',None)
                        self.save(job)
                        updater.apply(key,revision,False,preserve_lifecycle=True)
                        item.update(state='current'); item.pop('error',None)
                    except ToolError as exc:
                        code=str(exc)
                        item.update(state='failed',error=code if re.fullmatch('[a-zA-Z0-9_]{1,160}',code) else 'release_update_failed')
                    self.save(job)
                job['state']='current' if all(v['state']=='current' for v in job['bots'].values()) else 'attention'
                job.pop('error',None)
        except Exception as exc:
            code=str(exc) if isinstance(exc,ToolError) else 'release_update_failed'
            job.update(state='waiting',error=code if re.fullmatch('[a-zA-Z0-9_]{1,160}',code) else 'release_update_failed')
        self.save(job)

    def serve(self):
        while True:
            try: self.tick()
            except Exception: print('Buzz release update: status unavailable',flush=True)
            time.sleep(15)
