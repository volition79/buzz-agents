import json
import os
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from buzz_agents.common import ToolError
from buzz_agents.host import Deployer, compose_document, labels, container_name, service_name, process_limit, public_record
from buzz_agents.native import state_on_start, runtime_env, runtime_parallelism
from buzz_agents.policy import atomic_json, read_json
from helpers import config,settings, PUBKEY


class HostTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'state'
        self.settings=settings(self.root);self.config=config();self.commands=[];self.actual=None
        def runner(argv,data=None,timeout=None):
            self.commands.append(argv)
            if argv[:3]==['docker','image','inspect']:return json.dumps([{'Id':self.settings['image_id']}]).encode()
            if argv[:2]==['docker','info']:return json.dumps({'NCPU':16,'MemTotal':64*1024**3}).encode()
            if 'up' in argv:
                self.actual={'HostConfig':{'PidsLimit':process_limit(self.config)},'State':{'Running':True},'Image':self.settings['image_id'],'Config':{'Labels':labels(self.config)}}
            return b''
        self.deploy=Deployer(self.settings,runner,lambda n:self.actual,lambda request:self.config)
    def tearDown(self):self.tmp.cleanup()
    def test_worker_budget_and_registry_roundtrip(self):
        for workers in (1, 10, 32):
            self.config['env']['BUZZ_ACP_AGENTS']=str(workers)
            self.assertEqual(process_limit(self.config), max(256, 128+64*workers))
            self.assertEqual(process_limit(public_record(self.config)), process_limit(self.config))
        legacy=public_record(self.config);legacy.pop('parallelism')
        self.assertEqual(process_limit(legacy),256)
    def test_live_old_limit_requires_explicit_stop(self):
        self.config['env']['BUZZ_ACP_AGENTS']='10'
        self.deploy.deploy({})
        self.actual['HostConfig']['PidsLimit']=256
        atomic_json(self.root/'bots'/PUBKEY/'state/runtime.json',{'status':'running'})
        self.commands.clear()
        with self.assertRaisesRegex(ToolError,'stop_native_bot_before_resource_upgrade'):
            self.deploy.deploy({})
        self.assertFalse(any('up' in c or 'stop' in c for c in self.commands))
        atomic_json(self.root/'bots'/PUBKEY/'state/runtime.json',{'status':'stopped'})
        self.deploy.deploy({})
        self.assertEqual(self.actual['HostConfig']['PidsLimit'],768)
    def test_deploy_readback_rejects_missing_limits(self):
        original=self.deploy.run
        def runner(*args,**kwargs):
            result=original(*args,**kwargs)
            if self.actual:self.actual.pop('HostConfig',None)
            return result
        self.deploy.run=runner
        with self.assertRaisesRegex(ToolError,'deployment_resource_limit_mismatch'):
            self.deploy.deploy({})
    def test_invalid_worker_budget_fails_closed(self):
        for value in (True, 0, 33, 'NaN', '-1', '1.5'):
            self.config['env']['BUZZ_ACP_AGENTS']=value
            with self.assertRaises(ToolError):process_limit(self.config)
    def test_resource_upgrade_preserves_data_and_other_registration(self):
        self.deploy.deploy({})
        root=self.root/'bots'/PUBKEY
        kept=[root/'home/codex/auth.json',root/'state/quota.json',self.root/'workspaces'/self.config['workspace']/'work.txt']
        for p in kept:p.write_text('preserve')
        registry=read_json(self.root/'registry.json')
        other=public_record(config(pub='e'*64));other.pop('parallelism')
        registry['e'*64]=other;atomic_json(self.root/'registry.json',registry)
        self.config['env']['BUZZ_ACP_AGENTS']='10'
        atomic_json(root/'state/runtime.json',{'status':'stopped'})
        self.deploy.deploy({})
        for p in kept:self.assertEqual(p.read_text(),'preserve')
        self.assertEqual(read_json(self.root/'registry.json')['e'*64],other)
        self.assertEqual(read_json(self.root/'compose.yaml')['services'][service_name('e'*64)]['pids_limit'],256)
    def test_wrong_numeric_readback_is_rejected(self):
        original=self.deploy.run
        def runner(*args,**kwargs):
            result=original(*args,**kwargs)
            if self.actual:self.actual['HostConfig']['PidsLimit']=1
            return result
        self.deploy.run=runner
        with self.assertRaisesRegex(ToolError,'deployment_resource_limit_mismatch'):self.deploy.deploy({})
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
    def test_high_spec_host_accepts_large_bot_with_auto_budget(self):
        self.settings.pop('memory_budget_mb');self.settings.pop('max_bots')
        self.config=config(options={'memory_mb':16384,'cpus':8})
        self.assertTrue(self.deploy.deploy({})['ok'])
    def test_requested_cpu_exceeding_host_fails_before_mutation(self):
        self.config=config(options={'cpus':17})
        with self.assertRaisesRegex(ToolError,'requested_cpu_exceeds_host'):self.deploy.deploy({})
        self.assertFalse(any('up' in c or 'stop' in c for c in self.commands))
    def test_running_old_image_requires_stop_after_selection_upgrade(self):
        self.deploy.deploy({})
        atomic_json(self.root/'bots'/PUBKEY/'state/runtime.json',{'status':'running'})
        self.settings['image_id']='sha256:'+'e'*64
        self.commands.clear()
        with self.assertRaisesRegex(ToolError,'stop_native_bot_before_image_upgrade'):self.deploy.deploy({})
        self.assertFalse(any('up' in c or 'stop' in c for c in self.commands))
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


class ConcurrencyEnvironmentTests(unittest.TestCase):
    def test_pool_and_policy_use_same_selected_count(self):
        for count in (1,2,10,32):
            c=config();c['env']['BUZZ_ACP_AGENTS']=str(count)
            self.assertEqual(runtime_parallelism(c),count)
            self.assertEqual(runtime_env(c,'/tmp/sock')['BUZZ_ACP_AGENTS'],str(count))
        c=config();c['env'].pop('BUZZ_ACP_AGENTS',None)
        self.assertEqual(runtime_parallelism(c),1)
        self.assertEqual(runtime_env(c,'/tmp/sock')['BUZZ_ACP_AGENTS'],'1')
