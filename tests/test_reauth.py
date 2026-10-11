"""Reauth incident checks: no duplicate worker, durable hold, preserved bot data."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import test_bot_update as fixtures
from helpers import PUBKEY, config
from buzz_agents import native, portal_auth
from buzz_agents.common import ToolError
from buzz_agents.host import labels, public_record
from buzz_agents.policy import atomic_json, read_json
from buzz_agents.reauth import Reauthentication, HOLD, CAPABILITY

class ReauthTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.UpdateTests();self.fixture.setUp()
        self.d=self.fixture.d;self.root=self.d.root
        self.folder=self.root/'bots'/PUBKEY/'state'
        self.login=Mock();self.login.lock=threading.RLock();self.login.items={}
        self.login.start.return_value={'session':'test-session'}
        self.r=Reauthentication(self.root,self.login,self.root)
        self.job={'id':'a'*32,'pubkey':PUBKEY,'name':'bot','state':'preparing'}
        self.fixture.current['Config']['Labels'][CAPABILITY]='1'
        original=self.d.run
        def run(argv,*args,**kw):
            if argv[:2]==['docker','start']:
                self.fixture.current['State']['Running']=True
            return original(argv,*args,**kw)
        self.d.run=run
    def tearDown(self):self.fixture.tearDown()

    def test_same_container_and_all_data_preserved_both_providers(self):
        for command in ('codex-acp','claude-agent-acp'):
            c=config(command,options=self.fixture.old['policy'])
            atomic_json(self.root/'bots'/PUBKEY/'config/config.json',c)
            atomic_json(self.root/'registry.json',{PUBKEY:public_record(c)})
            self.fixture.current['Config']['Labels']={**labels(c),CAPABILITY:'1'}
            prior_id=self.fixture.current['Id']
            prior_image=self.fixture.current['Image']
            atomic_json(self.folder/'runtime.json',{'status':'running','startup_consumed':True})
            result=self.r.prepare(self.d,self.job)
            self.assertEqual(result['session'],'test-session')
            self.assertEqual(self.fixture.current['Id'],prior_id)
            self.assertEqual(self.fixture.current['Image'],prior_image)
            self.assertEqual(read_json(self.root/'bots'/PUBKEY/'config/config.json'),c)
            self.assertEqual(read_json(self.folder/'runtime.json')['status'],'needs_login')
            self.assertTrue(read_json(self.folder/'runtime.json')['startup_consumed'])
            for p in self.fixture.kept:self.assertEqual(p.read_text(),'private-sentinel')
            self.assertFalse(any('rm' in a or 'up' in a or 'down' in a for a in self.fixture.commands))
            self.assertTrue((self.folder/HOLD).exists())

    def test_old_runtime_and_foreign_identity_refused_before_stop(self):
        self.fixture.current['Config']['Labels'].pop(CAPABILITY)
        with self.assertRaisesRegex(ToolError,'runtime_update'):self.r.prepare(self.d,self.job)
        self.fixture.current['Config']['Labels']={CAPABILITY:'1'}
        with self.assertRaisesRegex(ToolError,'collision'):self.r.prepare(self.d,self.job)
        self.assertEqual(self.fixture.commands,[])

    def test_stop_and_start_failure_retain_hold_no_login(self):
        for failure in ('stop','unconfirmed'):
            self.fixture.fail=failure
            with self.assertRaises(ToolError):self.r.prepare(self.d,self.job)
            self.assertTrue((self.folder/HOLD).exists())
            self.login.start.assert_not_called()
        self.fixture.fail=None
        old=self.d.run
        def failstart(a,**kw):
            if a[:2]==['docker','start']:raise ToolError('host_command_failed')
            return old(a,**kw)
        self.d.run=failstart
        with self.assertRaises(ToolError):self.r.prepare(self.d,self.job)
        self.login.start.assert_not_called()

    def test_live_lock_after_stop_refuses_and_retry_recovers(self):
        for name in ('runtime.lock','auth.lock','portal-auth.lock'):
            with open(self.folder/name,'w') as fd:
                fcntl.flock(fd,fcntl.LOCK_EX)
                with self.assertRaisesRegex(ToolError,'cleanup_unconfirmed|authentication_already'):self.r.prepare(self.d,self.job)
            self.login.start.assert_not_called()
        atomic_json(self.folder/'portal-auth.json',{'pid':123})
        self.assertEqual(self.r.prepare(self.d,self.job)['session'],'test-session')
        self.assertFalse((self.folder/'portal-auth.json').exists())

    def test_pending_blocks_deploy_update_retire(self):
        atomic_json(self.folder/HOLD,{'request_id':self.job['id']})
        for action in (lambda:self.d._deploy_locked(self.fixture.old),
                       lambda:self.fixture.apply(),lambda:self.d.retire(PUBKEY)):
            with self.assertRaisesRegex(ToolError,'reauthentication_pending'):action()
        self.assertEqual(self.fixture.commands,[])

    def test_stale_normal_auth_record_recovers_only_after_confirmed_stop(self):
        atomic_json(self.folder/'portal-auth.json',{'pid':123,'start':'old','session':'c'*32})
        atomic_json(self.folder/'portal-auth-cancel.json',{'session':'c'*32})
        self.assertEqual(self.r.prepare(self.d,self.job)['session'],'test-session')
        self.assertFalse((self.folder/'portal-auth.json').exists())
        self.assertFalse((self.folder/'portal-auth-cancel.json').exists())
        self.assertTrue((self.folder/HOLD).exists())
        for path in self.fixture.kept:self.assertEqual(path.read_text(),'private-sentinel')

    def test_live_normal_auth_lock_refuses_before_any_container_mutation(self):
        for name in ('portal-auth.lock','auth.lock'):
            with self.subTest(lock=name),open(self.folder/name,'w') as fd:
                atomic_json(self.folder/'portal-auth.json',{'pid':123})
                fcntl.flock(fd,fcntl.LOCK_EX)
                with self.assertRaisesRegex(ToolError,'authentication_already'):
                    self.r.prepare(self.d,self.job)
                self.assertEqual(self.fixture.commands,[])
                self.assertFalse((self.folder/HOLD).exists())
                self.assertTrue((self.folder/'portal-auth.json').exists())
                self.login.start.assert_not_called()

    def test_stale_auth_metadata_survives_unconfirmed_stop(self):
        atomic_json(self.folder/'portal-auth.json',{'pid':123})
        self.fixture.fail='unconfirmed'
        with self.assertRaisesRegex(ToolError,'stop_unconfirmed'):
            self.r.prepare(self.d,self.job)
        self.assertTrue((self.folder/'portal-auth.json').exists())
        self.assertTrue((self.folder/HOLD).exists())
        self.login.start.assert_not_called()

    def test_stale_auth_metadata_survives_external_container_replacement(self):
        atomic_json(self.folder/'portal-auth.json',{'pid':123})
        original=self.d.run
        def replace_after_stop(argv,*args,**kwargs):
            result=original(argv,*args,**kwargs)
            if argv[:2]==['docker','stop']:
                self.fixture.current={**self.fixture.current,'Id':'different-generation'}
            return result
        self.d.run=replace_after_stop
        with self.assertRaisesRegex(ToolError,'stop_unconfirmed'):
            self.r.prepare(self.d,self.job)
        self.assertTrue((self.folder/'portal-auth.json').exists())
        self.login.start.assert_not_called()

    def test_supervisor_hold_blocks_stale_ready_and_login_marker(self):
        atomic_json(self.folder/HOLD,{'request_id':self.job['id']})
        atomic_json(self.folder/'quota.json',{})
        atomic_json(self.folder/'runtime.json',{'status':'ready','startup_consumed':True})
        atomic_json(self.folder/'auth-codex.json',{'official_login_returned_zero':True})
        with patch.dict(os.environ,{'NATIVE_STATE':str(self.folder)}), \
             patch.object(native,'load_config',return_value=self.fixture.old), \
             patch.object(native.signal,'signal'), \
             patch.object(native.threading.Event,'wait',side_effect=[False,True]), \
             patch.object(native.subprocess,'Popen') as spawn:
            self.assertEqual(native.main(),0);spawn.assert_not_called()
        self.assertEqual(read_json(self.folder/'runtime.json')['status'],'needs_login')

    def test_idempotent_and_restart_status_without_session_leak(self):
        with patch('buzz_agents.reauth.threading.Thread') as thread:
            a=self.r.start(self.d,PUBKEY,self.job['id'])
            b=self.r.start(self.d,PUBKEY,self.job['id'])
            self.assertEqual(a,b);self.assertEqual(thread.call_count,1)
            with self.assertRaisesRegex(ToolError,'authentication_already'):
                self.r.start(self.d,PUBKEY,'b'*32)
        recovered=Reauthentication(self.root,self.login,self.root)
        self.assertEqual(recovered.status()['reauth']['state'],'interrupted')
        self.assertNotIn('session',recovered.status())
        atomic_json(self.folder/'reauth-result.json',{'request_id':self.job['id'],'success':True})
        self.assertEqual(recovered.status()['reauth']['state'],'succeeded')

    def test_worker_success_requires_cleanup_proof_not_just_cli_exit(self):
        self.login.poll.return_value={'done':True,'success':True}
        self.r._work(self.d,self.job)
        self.assertEqual(self.r.status()['reauth']['state'],'failed')
        self.assertTrue((self.folder/HOLD).exists())

class AuthWrapperTests(unittest.TestCase):
    def test_failure_timeout_and_success_hold_behavior_both_providers(self):
        real_spawn=subprocess.Popen
        for provider in ('codex','claude'):
            for code in (0,1,124):
                with self.subTest(provider=provider,code=code),tempfile.TemporaryDirectory() as tmp:
                    base=Path(tmp);atomic_json(base/HOLD,{'request_id':'b'*32})
                    command="import time;time.sleep(10)" if code==124 else f"raise SystemExit({code})"
                    def spawn(*args,**kw):return real_spawn([sys.executable,'-c',command],**kw)
                    with patch.object(portal_auth,'BASE',base),patch.object(portal_auth.subprocess,'Popen',side_effect=spawn):
                        self.assertEqual(portal_auth.run(provider,'a'*32,timeout=.2),code)
                    self.assertEqual((base/HOLD).exists(),code!=0)
                    self.assertFalse((base/'portal-auth.json').exists())
                    if code==0:self.assertTrue(read_json(base/'reauth-result.json')['success'])
