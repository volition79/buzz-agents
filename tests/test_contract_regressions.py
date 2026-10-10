"""CONTRACT-FIX-02: replay official launch seams, never a live deployment claim."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from helpers import agent, OWNER, RELAY, PUBKEY, settings
from buzz_agents.common import ToolError
from buzz_agents.config import normalize
from buzz_agents.host import Deployer
from buzz_agents.guard import Proxy
from buzz_agents.policy import Policy

class LaunchContractTests(unittest.TestCase):
    def normal(self, a, options=None):
        return normalize(a,options or {},OWNER,RELAY,derive=lambda _:PUBKEY)
    def test_publish_first_floor_is_transient_and_not_config_identity(self):
        a=agent();base=self.normal(a)
        a['launch']['policy_env']['BUZZ_ACP_REPLAY_FLOOR']='1791586800'
        c=self.normal(a)
        self.assertEqual(c['startup_env']['BUZZ_ACP_REPLAY_FLOOR'],'1791586800')
        self.assertNotIn('BUZZ_ACP_REPLAY_FLOOR',c['env'])
        self.assertEqual(c['fingerprint'],base['fingerprint'])
    def test_explicit_behavior_not_silently_replaced(self):
        a=agent();a['launch']['env'].update(BUZZ_ACP_MULTIPLE_EVENT_HANDLING='steer',BUZZ_ACP_DEDUP='queue',LANG='ko_KR.UTF-8')
        c=self.normal(a)
        self.assertEqual(c['env']['BUZZ_ACP_MULTIPLE_EVENT_HANDLING'],'steer')
        self.assertEqual(c['env']['LANG'],'ko_KR.UTF-8')
        self.assertNotIn('BUZZ_ACP_MULTIPLE_EVENT_HANDLING',self.normal(agent())['env'])
    def test_large_host_requested_resources_are_not_kvm2_capped(self):
        c=self.normal(agent(),{'cpus':4,'memory_mb':8192})
        self.assertEqual((c['cpus'],c['memory_mb']),(4,8192))
    def test_mesh_is_refused_before_identity_or_mutation(self):
        a=agent();a['provider']=' relay-mesh '
        with self.assertRaisesRegex(ToolError,'relay_mesh_not_supported'):
            self.normal(a)
    def test_invalid_transient_floor_refused(self):
        for value in ('-1','0.1','secret',str(2**64)):
            a=agent();a['launch']['policy_env']['BUZZ_ACP_REPLAY_FLOOR']=value
            with self.subTest(value=value),self.assertRaisesRegex(ToolError,'invalid_replay_floor'):
                self.normal(a)

class ErrorContractTests(unittest.TestCase):
    def test_real_validator_failure_survives_runner_boundary(self):
        a=agent();a['relay_url']='ws://wrong.example'
        payload={'agent':a,'owner':OWNER,'relay':RELAY}
        completed=subprocess.run([sys.executable,'-m','buzz_agents.cli','validate'],input=json.dumps(payload).encode(),capture_output=True)
        self.assertEqual(json.loads(completed.stdout)['error'],'invalid_relay')
        with patch('buzz_agents.host.subprocess.run',return_value=completed):
            with self.assertRaisesRegex(ToolError,'^invalid_relay$'):
                Deployer(settings('/unused')).normalize_in_image({'agent':a})
    def test_untrusted_validator_text_never_forwarded(self):
        completed=subprocess.CompletedProcess([],1,b'{"ok":false,"error":"secret_HUMAN_KEY"}',b'private')
        with patch('buzz_agents.host.subprocess.run',return_value=completed):
            with self.assertRaisesRegex(ToolError,'^host_command_failed$'):
                Deployer(settings('/unused')).normalize_in_image({'agent':agent()})

class WorkerIsolationTests(unittest.TestCase):
    def test_application_error_does_not_stop_other_worker(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'slots').mkdir()
            p=Policy(root,root/'slots',{'max_turn_seconds':60,'turn_limit':20,'window_seconds':60,'daily_limit':100},concurrency=2)
            def rpc(req):
                if req['op']=='acquire':return p.acquire()
                if req['op']=='release':return p.release(req['ticket'])
                return p.trip('adapter_or_guard_fault')
            one=Proxy(lambda m:None,lambda m:None,rpc);two=Proxy(lambda m:None,lambda m:None,rpc)
            try:
                for proxy in (one,two):
                    proxy.from_host({'id':1,'method':'session/prompt','params':{'sessionId':'s'}});proxy.tick()
                one.from_agent({'id':1,'error':{'code':-32000,'message':'synthetic'}})
                self.assertEqual(p.check(),'')
                self.assertEqual(len(p.active),1)
                self.assertFalse(one.stopped)
            finally:p.close()

class RuntimeContractTests(unittest.TestCase):
    def test_real_public_key_derivation_is_not_mocked(self):
        from buzz_agents.config import public_key
        self.assertEqual(public_key('0'*63+'1'), '79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798')
    def test_replay_only_first_start_and_fresh_nonce(self):
        from buzz_agents.native import runtime_env
        from helpers import config
        c=config();c['startup_env']={'BUZZ_ACP_REPLAY_FLOOR':'123'}
        first=runtime_env(c,'/tmp/sock',False);restart=runtime_env(c,'/tmp/sock',True)
        self.assertEqual(first['BUZZ_ACP_REPLAY_FLOOR'],'123')
        self.assertNotIn('BUZZ_ACP_REPLAY_FLOOR',restart)
        self.assertNotEqual(first['BUZZ_MANAGED_AGENT_START_NONCE'],restart['BUZZ_MANAGED_AGENT_START_NONCE'])
    def test_diagnostics_fragmentation_and_no_raw_secret(self):
        from buzz_agents.diagnostics import RuntimeDiagnostics
        d=RuntimeDiagnostics()
        self.assertEqual(d.feed(b'private-secret authentica'),[])
        self.assertEqual(d.feed(b'tion required SECRET'),['runtime_authentication_required'])
        self.assertEqual(d.feed(b'authentication required'),[])
        self.assertEqual(d.feed(b'x'*100000),[])
        self.assertLessEqual(len(d.buffer),512)
        self.assertEqual(d.feed(b'buzz-agents-diagnostic:runtime_adapter_exited'),['runtime_adapter_exited'])
    def test_shutdown_waits_longer_than_old_three_seconds(self):
        from buzz_agents.native import stop_group
        import time
        code='import signal,time,sys; signal.signal(signal.SIGTERM,lambda *a:(time.sleep(3.2),sys.exit(0))); print("ready",flush=True); time.sleep(30)'
        p=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,start_new_session=True)
        try:
            self.assertEqual(p.stdout.readline(),b'ready\n')
            start=time.monotonic();stop_group(p,grace=5)
            self.assertEqual(p.returncode,0)
            self.assertGreater(time.monotonic()-start,3)
        finally:
            p.kill();p.wait();p.stdout.close()
    def test_shutdown_kills_stubborn_process_within_budget(self):
        from buzz_agents.native import stop_group
        code='import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print("ready",flush=True); time.sleep(30)'
        p=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,start_new_session=True)
        try:
            p.stdout.readline();stop_group(p,grace=0.1)
            self.assertEqual(p.returncode,-9)
        finally:
            p.kill();p.wait();p.stdout.close()
