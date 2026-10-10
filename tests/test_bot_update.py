"""Stopped provider remains Deployed in Buzz: update without deleting identity."""
import fcntl
import json
from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from buzz_agents.bot_update import ExistingBotUpdater, request_from_saved
from buzz_agents.common import ToolError
from buzz_agents.config import normalize
from buzz_agents.host import Deployer, labels, process_limit, public_record, service_name
from buzz_agents.policy import atomic_json, read_json
from buzz_agents.portal_broker import Broker
from helpers import agent, config, settings, PUBKEY, OWNER, RELAY


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'state'
        self.settings = settings(self.root)
        self.old = config(options={'turn_limit':20, 'daily_limit':100, 'max_turn_seconds':600})
        self.current = None
        self.commands = []
        self.fail = None
        self.readback_image = None
        def runner(argv, data=None, **kwargs):
            self.commands.append(argv)
            if argv[:3] == ['docker','image','inspect']:
                return json.dumps([{'Id': self.settings['image_id']}]).encode()
            if argv[:2] == ['docker','info']:
                return json.dumps({'NCPU':8,'MemTotal':32*1024**3}).encode()
            if argv[:2] == ['docker','stop']:
                if self.fail == 'stop': raise ToolError('host_command_failed')
                if self.current: self.current['State']['Running'] = self.fail == 'unconfirmed'
            if 'up' in argv:
                if self.fail == 'up': raise ToolError('host_command_failed')
                c=read_json(self.root/'bots'/PUBKEY/'config/config.json')
                self.current={'Id':'container-new','Image':self.readback_image or self.settings['image_id'],
                              'State':{'Running':True},'Config':{'Labels':labels(c)},
                              'HostConfig':{'PidsLimit':process_limit(c)}}
            return b''
        self.d = Deployer(self.settings, runner, lambda _:self.current, self.normalizer)
        self.d.deploy({'agent':agent(),'provider_config':self.old['policy']})
        self.settings['image'] = 'runtime:new'
        self.settings['image_id'] = 'sha256:'+'e'*64
        self.u = ExistingBotUpdater(self.d)
        self.commands.clear()
        self.kept = [self.root/'bots'/PUBKEY/'home/codex/auth.json',
                     self.root/'bots'/PUBKEY/'state/quota.json', self.root/'workspaces/team/webtoon.txt']
        for p in self.kept: p.write_text('private-sentinel')
    def normalizer(self, request):
        return normalize(request['agent'], request['provider_config'], OWNER, RELAY, derive=lambda _:PUBKEY)
    def tearDown(self): self.tmp.cleanup()
    def apply(self, defaults=False):
        return self.u.apply(PUBKEY, self.u.preview(PUBKEY)['revision'], defaults)
    def test_retire_preserves_legacy_other_image(self):
        other = public_record(config(pub='f'*64))
        registry=read_json(self.root/'registry.json');registry['f'*64]=other
        atomic_json(self.root/'registry.json',registry)
        manifest=read_json(self.root/'compose.yaml');manifest['services'][service_name('f'*64)]={'image':'runtime:old-other'}
        atomic_json(self.root/'compose.yaml',manifest)
        self.current['State']['Running']=False
        self.d.retire(PUBKEY)
        self.assertEqual(read_json(self.root/'compose.yaml')['services'][service_name('f'*64)]['image'],'runtime:old-other')

    def test_preserves_files_policy_identity_and_other_runtime(self):
        other = public_record(config(pub='f'*64))
        registry=read_json(self.root/'registry.json');registry['f'*64]=other
        atomic_json(self.root/'registry.json',registry)
        manifest=read_json(self.root/'compose.yaml');manifest['services'][service_name('f'*64)]={'image':'runtime:old-other'}
        atomic_json(self.root/'compose.yaml',manifest)
        atomic_json(self.root/'bots'/PUBKEY/'state/runtime.json',{'status':'running'})
        self.assertTrue(self.apply()['ok'])
        new=read_json(self.root/'bots'/PUBKEY/'config/config.json')
        self.assertEqual(new,self.old)
        for p in self.kept:self.assertEqual(p.read_text(),'private-sentinel')
        self.assertEqual(read_json(self.root/'registry.json')['f'*64],other)
        self.assertEqual(read_json(self.root/'compose.yaml')['services'][service_name('f'*64)]['image'],'runtime:old-other')
        self.assertTrue(any('stop' in a for a in self.commands))
        self.assertFalse(any('rm' in a or 'down' in a or '--remove-orphans' in a for a in self.commands))
    def test_defaults_are_explicit_and_both_providers_keep_role_model(self):
        for command in ('codex-acp','claude-agent-acp'):
            c=config(command,options={'turn_limit':20,'daily_limit':100,'max_turn_seconds':600})
            request=request_from_saved(c,self.settings,True)
            n=self.normalizer(request)
            self.assertEqual(n['policy'],{'turn_limit':0,'daily_limit':0,'max_turn_seconds':7200,'window_seconds':3600})
            for key in ('BUZZ_PRIVATE_KEY','BUZZ_AUTH_TAG','BUZZ_ACP_MODEL','BUZZ_ACP_SYSTEM_PROMPT','BUZZ_ACP_AGENTS'):
                self.assertEqual(n['env'][key],c['env'][key])
        self.apply(True)
        for p in self.kept:self.assertEqual(p.read_text(),'private-sentinel')
    def test_stale_preview_refuses_before_stop(self):
        p=self.u.preview(PUBKEY);self.current['Id']='replacement'
        with self.assertRaisesRegex(ToolError,'preview_changed'):self.u.apply(PUBKEY,p['revision'],False)
        self.assertFalse(any('stop' in a for a in self.commands))
    def test_busy_deploy_lock_refuses(self):
        with open(self.root/'deploy.lock','w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            with self.assertRaisesRegex(ToolError,'busy'):self.apply()
    def test_auth_surviving_broker_restart_refuses(self):
        atomic_json(self.root/'bots'/PUBKEY/'state/portal-auth.json',{'pid':123})
        with self.assertRaisesRegex(ToolError,'authentication_already'):self.apply()
        self.assertFalse(any('stop' in a for a in self.commands))
    def test_both_auth_locks_fence_concurrent_login(self):
        for name in ('auth.lock','portal-auth.lock'):
            with open(self.root/'bots'/PUBKEY/'state'/name,'w') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                with self.assertRaisesRegex(ToolError,'authentication_already'):self.apply()
        self.assertFalse(any('stop' in a for a in self.commands))
    def test_foreign_container_refused(self):
        self.current['Config']['Labels']={}
        with self.assertRaisesRegex(ToolError,'collision'):self.apply()
        self.assertFalse(any('stop' in a for a in self.commands))
    def test_stop_failure_and_false_success_preserve_config(self):
        for failure in ('stop','unconfirmed'):
            self.fail=failure
            with self.assertRaises(ToolError):self.apply(True)
            self.assertEqual(read_json(self.root/'bots'/PUBKEY/'config/config.json'),self.old)
            for p in self.kept:self.assertEqual(p.read_text(),'private-sentinel')
    def test_failed_recreation_preserves_data_and_can_retry(self):
        self.fail='up'
        with self.assertRaises(ToolError):self.apply(True)
        for p in self.kept:self.assertEqual(p.read_text(),'private-sentinel')
        self.fail=None
        self.assertTrue(self.apply()['ok'])
    def test_wrong_image_is_not_success(self):
        self.readback_image='sha256:'+'a'*64
        with self.assertRaisesRegex(ToolError,'image_mismatch'):self.apply()
    def test_corrupt_and_symlink_saved_config_refused(self):
        p=self.root/'bots'/PUBKEY/'config/config.json'
        altered=deepcopy(self.old);altered['workspace']='other'
        atomic_json(p,altered,0o400)
        with self.assertRaisesRegex(ToolError,'configuration_changed'):self.apply()
        p.unlink();p.symlink_to(self.kept[0])
        with self.assertRaisesRegex(ToolError,'unsafe_saved'):self.apply()
    def test_replay_floor_is_not_reused(self):
        c=deepcopy(self.old);c['startup_env']={'BUZZ_ACP_REPLAY_FLOOR':'123'}
        atomic_json(self.root/'bots'/PUBKEY/'config/config.json',c,0o400)
        self.apply()
        self.assertEqual(read_json(self.root/'bots'/PUBKEY/'config/config.json')['startup_env'],{})
    def test_preview_never_exposes_secrets(self):
        raw=json.dumps(self.u.preview(PUBKEY))
        for secret in ('private-sentinel',self.old['env']['BUZZ_PRIVATE_KEY'],self.old['env']['BUZZ_AUTH_TAG']):
            self.assertNotIn(secret,raw)


class UpdateJobTests(unittest.TestCase):
    def test_async_dedup_busy_and_restart_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);b=Broker('runtime:new',root,root)
            atomic_json(root/'settings.json',{**settings(root),'image':'runtime:new','resource_policy':'fixed'})
            started,finish=threading.Event(),threading.Event()
            def work(*a):started.set();finish.wait(3)
            req={'op':'bot-update','pubkey':PUBKEY,'revision':'a'*64,'use_defaults':False,'request_id':'b'*32}
            with patch('buzz_agents.portal_broker.ExistingBotUpdater') as factory:
                factory.return_value.preview.return_value={'revision':'a'*64}
                factory.return_value.apply.side_effect=work
                r=b.dispatch(req);self.assertEqual(r['update']['state'],'running')
                self.assertTrue(started.wait(1))
                self.assertEqual(b.dispatch(req)['update']['id'],'b'*32)
                with self.assertRaisesRegex(ToolError,'busy'):b.dispatch({**req,'request_id':'c'*32})
                with self.assertRaisesRegex(ToolError,'busy'):b.dispatch({'op':'auth-start','pubkey':PUBKEY})
                with self.assertRaisesRegex(ToolError,'busy'):b.dispatch({'op':'deploy','request':{}})
                self.assertEqual(Broker('runtime:new',root,root).update_job()['state'],'interrupted')
                finish.set()
                deadline=time.monotonic()+2
                while b.update_running and time.monotonic()<deadline:time.sleep(.01)
                self.assertEqual(b.update_job()['state'],'succeeded')
                self.assertEqual(factory.return_value.apply.call_count,1)
                self.assertEqual(b.dispatch(req)['update']['state'],'succeeded')
    def test_closed_operations(self):
        b=Broker('runtime:new')
        for r in ({'op':'bot-update','image':'evil'}, {'op':'bot-update-preview','pubkey':PUBKEY,'command':'evil'}):
            with self.assertRaisesRegex(ToolError,'unsupported'):b.dispatch(r)
