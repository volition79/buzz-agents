import json
import os
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from buzz_agents.common import ToolError
from buzz_agents.host import Deployer, compose_document, labels, container_name, service_name
from buzz_agents.native import state_on_start, runtime_env
from buzz_agents.policy import atomic_json, read_json
from helpers import config,settings, PUBKEY


class HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'state'
        self.settings=settings(self.root);self.config=config();self.commands=[];self.actual=None
        def runner(argv,data=None,timeout=None):
            self.commands.append(argv)
            if argv[:3]==['docker','image','inspect']:return json.dumps([{'Id':self.settings['image_id']}]).encode()
            if 'up' in argv:
                self.actual={'State':{'Running':True},'Image':self.settings['image_id'],'Config':{'Labels':labels(self.config)}}
            return b''
        self.deploy=Deployer(self.settings,runner,lambda n:self.actual,lambda request:self.config)
    def tearDown(self):self.tmp.cleanup()
    def test_new_bot_creates_only_v2_project(self):
        result=self.deploy.deploy({})
        self.assertTrue(result['ok'])
        manifest=read_json(self.root/'compose.yaml')
        self.assertEqual(manifest['name'],'buzz-agents-v2')
        self.assertEqual(list(manifest['services']),[service_name(PUBKEY)])
        self.assertNotIn('buzz-rpka',json.dumps(self.commands))
    def test_second_same_provider_bot_is_not_a_fixed_two_worker_pool(self):
        self.deploy.deploy({});self.actual=None
        self.config=config(pub='e'*64)
        self.deploy.deploy({})
        registry=read_json(self.root/'registry.json')
        self.assertEqual(len(registry),2)
        self.assertTrue(all(c['provider']=='codex' for c in registry.values()))
    def test_no_secrets_in_compose_or_public_registry(self):
        self.deploy.deploy({})
        raw=(self.root/'compose.yaml').read_text()+(self.root/'registry.json').read_text()
        self.assertNotIn('BUZZ_PRIVATE_KEY',raw);self.assertNotIn('0'*63+'1',raw)
        info=(self.root/'bots'/PUBKEY/'config/config.json').stat()
        self.assertEqual(info.st_mode&0o777,0o400)
    def test_running_idempotent_deploy_is_noop(self):
        self.deploy.deploy({});self.commands.clear()
        atomic_json(self.root/'bots'/PUBKEY/'state/runtime.json',{'status':'running'})
        answer=self.deploy.deploy({})
        self.assertEqual(answer['action'],'already_deployed')
        self.assertFalse(any('up' in c or 'stop' in c for c in self.commands))
    def test_live_changed_config_is_refused(self):
        self.deploy.deploy({});self.commands.clear()
        atomic_json(self.root/'bots'/PUBKEY/'state/runtime.json',{'status':'running'})
        self.config=config(options={'workspace':'different'})
        with self.assertRaisesRegex(ToolError,'stop_native_bot'):self.deploy.deploy({})
        self.assertFalse(any('stop' in c for c in self.commands))
    def test_owned_stopped_bot_can_be_redeployed(self):
        self.deploy.deploy({});self.commands.clear()
        atomic_json(self.root/'bots'/PUBKEY/'state/runtime.json',{'status':'stopped'})
        self.config=config('claude-agent-acp')
        self.deploy.deploy({})
        self.assertTrue(any(c[:2]==['docker','stop'] for c in self.commands))
    def test_foreign_container_never_stopped(self):
        self.actual={'State':{'Running':True},'Config':{'Labels':{}}}
        with self.assertRaisesRegex(ToolError,'collision'):self.deploy.deploy({})
        self.assertFalse(any('stop' in c for c in self.commands))
    def test_full_pubkey_collision_check(self):
        c=deepcopy(self.config);c['pubkey']='e'*64
        self.actual={'State':{'Running':True},'Config':{'Labels':labels(c)}}
        with self.assertRaisesRegex(ToolError,'collision'):self.deploy.deploy({})
    def test_total_memory_is_bounded(self):
        self.deploy.deploy({});self.actual=None;self.config=config(pub='e'*64,options={'memory_mb':4096})
        with self.assertRaisesRegex(ToolError,'memory_budget'):self.deploy.deploy({})
    def test_changed_local_image_is_refused(self):
        self.deploy.run=lambda *a,**k:json.dumps([{'Id':'sha256:'+'e'*64}]).encode()
        with self.assertRaisesRegex(ToolError,'image_changed'):self.deploy.deploy({})
    def test_compose_has_no_public_ports_or_management_socket(self):
        document=compose_document({PUBKEY:self.config},self.settings)
        body=document['services'][service_name(PUBKEY)]
        for key in ('ports','privileged','pid','network_mode'):self.assertNotIn(key,body)
        self.assertNotIn('docker.sock',json.dumps(body));self.assertNotIn('/slots', [v['target'] for v in body['volumes']])
        self.assertEqual(body['cap_drop'],['ALL'])
    def test_retire_requires_prior_native_stop(self):
        self.deploy.deploy({})
        atomic_json(self.root/'bots'/PUBKEY/'state/runtime.json',{'status':'running'})
        with self.assertRaisesRegex(ToolError,'stop_native_bot'):self.deploy.retire(PUBKEY)
    def test_retire_preserves_files_and_releases_memory_registration(self):
        self.deploy.deploy({})
        atomic_json(self.root/'bots'/PUBKEY/'state/runtime.json',{'status':'stopped'})
        answer=self.deploy.retire(PUBKEY)
        self.assertTrue(answer['data_preserved'])
        self.assertNotIn(PUBKEY,read_json(self.root/'registry.json'))
        self.assertTrue((self.root/'bots'/PUBKEY/'config/config.json').is_file())
        self.assertTrue(any(c[:2]==['docker','rm'] for c in self.commands))
    def test_provider_change_does_not_mount_old_provider_home(self):
        a=compose_document({PUBKEY:config()},self.settings)['services'][service_name(PUBKEY)]
        b=compose_document({PUBKEY:config('claude-agent-acp')},self.settings)['services'][service_name(PUBKEY)]
        home=lambda c:next(v['source'] for v in c['volumes'] if v['target']=='/home/agent')
        self.assertNotEqual(home(a),home(b))
    def test_quota_is_preserved_after_explicit_restart(self):
        self.deploy.deploy({})
        q=self.root/'bots'/PUBKEY/'state/quota.json';atomic_json(q,{'starts':[123],'last':123})
        atomic_json(q.parent/'runtime.json',{'status':'held'})
        self.deploy.deploy({});self.assertEqual(read_json(q)['starts'],[123])


class NativeTests(unittest.TestCase):
    def test_first_and_graceful_restart_can_start(self):
        self.assertEqual(state_on_start(None)[0],'ready')
        self.assertEqual(state_on_start({'status':'ready'})[0],'ready')
    def test_intentional_stop_stays_stopped(self):
        self.assertEqual(state_on_start({'status':'stopped'})[0],'stopped')
    def test_abrupt_restart_is_held_not_replayed(self):
        self.assertEqual(state_on_start({'status':'running'}),('held','unexpected_container_restart'))
    def test_broker_fault_stays_held(self):
        self.assertEqual(state_on_start({'status':'held','reason':'daily_start_limit'}),('held','daily_start_limit'))
    def test_native_environment_not_task_mode(self):
        env=runtime_env(config(),'/tmp/sock')
        self.assertEqual(env['BUZZ_ACP_AGENT_COMMAND'],'/app/guard-bin/codex-acp')
        self.assertEqual(env['BUZZ_NATIVE_COMMAND'],'codex-acp')
        self.assertNotIn('stage',json.dumps(env));self.assertNotIn('run --task',json.dumps(env))
        self.assertEqual(env['HOME'],'/home/agent')

    def test_wrapper_retains_native_provider_basename(self):
        for command in ('codex-acp','claude-agent-acp'):
            env=runtime_env(config(command),'/tmp/sock')
            self.assertEqual(Path(env['BUZZ_ACP_AGENT_COMMAND']).name,command)
            self.assertNotIn('/app/guard-bin',env.get('PATH',''))
