"""Release contract and safe reconciliation fixtures: no live Docker or account."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from buzz_agents import release_contract as rc
from buzz_agents.portal_broker import Broker
from buzz_agents.rollout import Rollout
from buzz_agents.common import ToolError
from buzz_agents.policy import atomic_json,read_json
import test_bot_update as fixtures
from helpers import PUBKEY

CONTRACT={'schema':1,'api':1,'release':'a'*40,'runtime':rc.PREFIX+'runtime@sha256:'+'b'*64,'portal':rc.PREFIX+'portal@sha256:'+'c'*64}

class ContractTests(unittest.TestCase):
    def test_closed_pinned_contract(self):
        self.assertEqual(rc.validate(CONTRACT),CONTRACT)
        for change in ({'runtime':rc.PREFIX+'runtime:stable'},{'portal':'evil@sha256:'+'a'*64},{'schema':2},{'extra':1}):
            with self.assertRaises(ToolError):rc.validate({**CONTRACT,**change})
    def test_contract_overrides_legacy_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Broker('runtime:old',Path(tmp),Path(tmp),CONTRACT)
            self.assertEqual(b.image,CONTRACT['runtime'])
    def test_verified_digest_and_pull_failure(self):
        def run(args,**kw):return json.dumps([{'Id':'sha256:'+'e'*64,'RepoDigests':[CONTRACT['runtime']]}])
        self.assertEqual(rc.image(run,CONTRACT['runtime'])['Id'],'sha256:'+'e'*64)
        with self.assertRaises(ToolError):rc.image(lambda *a,**kw:json.dumps([{'Id':'sha256:'+'e'*64,'RepoDigests':[]}]),CONTRACT['runtime'])
    def test_management_mismatch(self):
        own={'Config':{'Labels':{'com.docker.compose.project':'custom'}}}
        portal={'Image':'sha256:'+'f'*64,'State':{'Running':True},'Config':{'Labels':{'com.docker.compose.project':'custom','com.docker.compose.service':'portal'}}}
        with patch.object(rc,'image',return_value={'Id':'sha256:'+'e'*64}):
            with self.assertRaisesRegex(ToolError,'mismatch'):rc.compatible_portal(CONTRACT,own,[portal],None)

class LifecycleTests(unittest.TestCase):
    def setUp(self):self.f=fixtures.UpdateTests();self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def test_active_bot_refused_before_stop(self):
        atomic_json(self.f.root/'bots'/PUBKEY/'state/runtime.json',{'status':'running'})
        with self.assertRaisesRegex(ToolError,'interruption'):
            self.f.u.apply(PUBKEY,self.f.u.preview(PUBKEY)['revision'],False,preserve_lifecycle=True)
        self.assertFalse(any('stop' in a for a in self.f.commands))
    def test_held_bot_keeps_reason_diagnosis_and_files(self):
        state={'status':'held','reason':'supervisor_fault','diagnostic':'runtime_process_limit','startup_consumed':True}
        atomic_json(self.f.root/'bots'/PUBKEY/'state/runtime.json',state)
        self.f.current['State']['Running']=False
        original=self.f.d.run
        def runner(args,*a,**kw):
            result=original(args,*a,**kw)
            if '--no-start' in args:self.f.current['State']['Running']=False
            return result
        self.f.d.run=runner
        self.f.u.apply(PUBKEY,self.f.u.preview(PUBKEY)['revision'],False,preserve_lifecycle=True)
        self.assertEqual(read_json(self.f.root/'bots'/PUBKEY/'state/runtime.json'),state)
        for p in self.f.kept:self.assertEqual(p.read_text(),'private-sentinel')
    def test_stopped_container_not_started(self):
        self.f.current['State']['Running']=False
        atomic_json(self.f.root/'bots'/PUBKEY/'state/runtime.json',{'status':'stopped'})
        original=self.f.d.run
        def runner(args,*a,**kw):
            result=original(args,*a,**kw)
            if '--no-start' in args:self.f.current['State']['Running']=False
            return result
        self.f.d.run=runner
        self.f.u.apply(PUBKEY,self.f.u.preview(PUBKEY)['revision'],False,preserve_lifecycle=True)
        self.assertFalse(self.f.current['State']['Running'])
        self.assertTrue(any('--no-start' in a for a in self.f.commands))

    def test_second_stop_rejects_replacement_or_unconfirmed_exit_before_writes(self):
        from copy import deepcopy
        from buzz_agents import host
        original_run=self.f.d.run
        original_container=deepcopy(self.f.current)
        state={'status':'stopped','reason':'native_clean_exit','startup_consumed':True}
        atomic_json(self.f.root/'bots'/PUBKEY/'state/runtime.json',state)
        paths=[self.f.root/'bots'/PUBKEY/'config/config.json',
               self.f.root/'bots'/PUBKEY/'state/runtime.json',
               self.f.root/'registry.json',self.f.root/'compose.yaml',*self.f.kept]
        before={p:p.read_bytes() for p in paths}
        for failure in ('replaced','running','restarting','live_pid','missing'):
            with self.subTest(failure=failure):
                self.f.current=deepcopy(original_container)
                self.f.current['State']={'Running':False,'Restarting':False,'Pid':0}
                self.f.commands.clear()
                expected_id=self.f.current['Id']
                stop_count=0
                def runner(args,*a,**kw):
                    nonlocal stop_count
                    result=original_run(args,*a,**kw)
                    if args[:2]==['docker','stop']:
                        stop_count+=1
                        self.assertEqual(args[-1],expected_id)
                        if stop_count==2:
                            if failure=='replaced':self.f.current['Id']='external-replacement'
                            elif failure=='running':self.f.current['State']['Running']=True
                            elif failure=='restarting':self.f.current['State']['Restarting']=True
                            elif failure=='live_pid':self.f.current['State']['Pid']=321
                            else:self.f.current=None
                    return result
                self.f.d.run=runner
                with patch.object(host,'atomic_json',wraps=host.atomic_json) as write:
                    with self.assertRaisesRegex(ToolError,'container_changed|stop_not_confirmed'):
                        self.f.u.apply(PUBKEY,self.f.u.preview(PUBKEY)['revision'],False,preserve_lifecycle=True)
                    write.assert_not_called()
                self.assertEqual(stop_count,2)
                self.assertFalse(any('up' in a for a in self.f.commands))
                self.assertEqual({p:p.read_bytes() for p in paths},before)

    def test_matching_generation_second_stop_keeps_stopped_lifecycle(self):
        state={'status':'stopped','reason':'native_clean_exit','startup_consumed':True}
        atomic_json(self.f.root/'bots'/PUBKEY/'state/runtime.json',state)
        self.f.current['State']={'Running':False,'Restarting':False,'Pid':0}
        expected_id=self.f.current['Id']
        original=self.f.d.run
        def runner(args,*a,**kw):
            result=original(args,*a,**kw)
            if '--no-start' in args:self.f.current['State']['Running']=False
            return result
        self.f.d.run=runner
        self.f.u.apply(PUBKEY,self.f.u.preview(PUBKEY)['revision'],False,preserve_lifecycle=True)
        stops=[a for a in self.f.commands if a[:2]==['docker','stop']]
        self.assertEqual(len(stops),2)
        self.assertTrue(all(a[-1]==expected_id for a in stops))
        self.assertFalse(self.f.current['State']['Running'])
        self.assertEqual(read_json(self.f.root/'bots'/PUBKEY/'state/runtime.json'),state)
        self.assertEqual(self.f.current['Image'],self.f.settings['image_id'])
        for p in self.f.kept:self.assertEqual(p.read_text(),'private-sentinel')

class RolloutTests(unittest.TestCase):
    def test_uncertain_apply_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Broker('runtime:old',Path(tmp),Path(tmp),CONTRACT)
            atomic_json(b.rollout.path,{'target':'old','state':'applying','bots':{'b'*64:{'state':'applying'}}})
            b.rollout.tick()
            self.assertEqual(b.rollout.status()['state'],'interrupted')
    def test_retry_only_failed_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Broker('runtime:old',Path(tmp),Path(tmp),CONTRACT)
            atomic_json(b.rollout.path,{'bots':{'a':{'state':'failed'},'b':{'state':'current'}}})
            b.rollout.retry()
            self.assertTrue(b.rollout.path.with_name('release-retry.json').exists())
            self.assertEqual(b.rollout.status()['bots']['b']['state'],'current')
    def test_release_status_is_not_device_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Broker('runtime:old',Path(tmp),Path(tmp))
            self.assertIn('release_update',b.dispatch({'op':'release-status'}))
            with self.assertRaisesRegex(ToolError,'unsupported'):
                b.dispatch({'op':'release-retry','image':'evil'})

class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.UpdateTests();self.f.setUp()
        self.b=Broker('runtime:old',self.f.root,self.f.root)
        self.r=Rollout(self.b,CONTRACT)
        self.patches=[patch.object(self.r,'verify_management'),patch.object(rc,'image'),
                      patch.object(self.b,'settings',return_value=self.f.settings),
                      patch('buzz_agents.rollout.Deployer',return_value=self.f.d)]
        for p in self.patches:p.start()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.f.tearDown()
    def test_running_runtime_waits_without_stop(self):
        atomic_json(self.f.root/'bots'/PUBKEY/'state/runtime.json',{'status':'running'})
        self.r.tick()
        self.assertEqual(self.r.status()['bots'][PUBKEY]['state'],'waiting')
        self.assertFalse(any('stop' in a for a in self.f.commands))
    def test_held_but_running_supervisor_also_waits(self):
        atomic_json(self.f.root/'bots'/PUBKEY/'state/runtime.json',{'status':'held','reason':'daily_start_limit'})
        self.r.tick()
        self.assertEqual(self.r.status()['bots'][PUBKEY]['state'],'waiting')
        self.assertFalse(any('stop' in a for a in self.f.commands))
    def test_staged_memory_and_mismatched_swap_never_marked_current_or_applied(self):
        from buzz_agents import memory_settings
        self.f.current['Image']=self.f.settings['image_id']
        self.f.current['State']['Running']=False
        self.f.current['HostConfig'].update(Memory=1536*1024**2,MemorySwap=1536*1024**2)
        atomic_json(self.f.root/'bots'/PUBKEY/'state/runtime.json',{'status':'stopped'})
        memory_settings.save(self.f.root,PUBKEY,3072,1536)
        self.r.tick()
        self.assertEqual(self.r.status()['bots'][PUBKEY]['error'],'memory_change_pending')
        memory_settings.save(self.f.root,PUBKEY,1536,1536)
        self.f.current['HostConfig']['MemorySwap']=3072*1024**2
        self.r.tick()
        self.assertEqual(self.r.status()['bots'][PUBKEY]['error'],'deployment_memory_limit_mismatch')
        self.assertFalse(any('stop' in a or 'up' in a for a in self.f.commands))

    def test_matching_runtime_is_not_recreated(self):
        self.f.current['Image']=self.f.settings['image_id']
        self.r.tick();self.r.tick()
        self.assertEqual(self.r.status()['state'],'current')
        self.assertFalse(any('stop' in a for a in self.f.commands))
    def test_partial_failure_requires_retry_and_keeps_data(self):
        self.f.current['State']['Running']=False
        atomic_json(self.f.root/'bots'/PUBKEY/'state/runtime.json',{'status':'stopped'})
        self.f.fail='up'
        self.r.tick();count=len(self.f.commands);self.r.tick()
        self.assertEqual(self.r.status()['bots'][PUBKEY]['state'],'failed')
        self.assertEqual(len(self.f.commands),count)
        for p in self.f.kept:self.assertEqual(p.read_text(),'private-sentinel')
    def test_saved_apply_is_uncertain_not_automatically_replayed(self):
        atomic_json(self.r.path,{'target':CONTRACT['release'],'state':'checking','bots':{PUBKEY:{'state':'applying'}}})
        self.r.tick()
        self.assertEqual(self.r.status()['bots'][PUBKEY]['state'],'interrupted')
        self.assertFalse(any('stop' in a for a in self.f.commands))

class StableRouteTests(unittest.TestCase):
    def test_stable_resolves_exact_image_but_keeps_compose_reference(self):
        from buzz_agents import portal_compose as pc
        with tempfile.TemporaryDirectory() as tmp:
            portal={'Name':'/portal','Image':'sha256:'+'a'*64,'Config':{'Image':rc.PREFIX+'portal:stable'}}
            data={'project':'custom','upstream':'portal','image':portal['Image']}
            record={'Id':portal['Image'],'RepoDigests':[CONTRACT['portal']]}
            with patch.object(pc,'project_file',return_value=Path(tmp)/'compose.json'),patch.object(pc,'execute',return_value=json.dumps([record])),patch.object(pc,'_reconcile') as reconcile:
                pc.reconcile([portal],'self',data)
                self.assertEqual(reconcile.call_args.args[2:],(CONTRACT['portal'],rc.PREFIX+'portal:stable'))
    def test_unknown_tag_is_not_accepted(self):
        from buzz_agents import portal_compose as pc
        with patch.object(pc,'project_file',return_value=Path('/unused')):
            with self.assertRaisesRegex(ToolError,'digest_required'):
                pc.reconcile([{'Name':'/portal','Config':{'Image':rc.PREFIX+'portal:latest'}}],'self',{'project':'custom','upstream':'portal'})
