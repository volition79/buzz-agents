import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from buzz_agents.policy import Policy, Broker

ROOT=Path(__file__).resolve().parents[1]


class RealProxyTests(unittest.TestCase):
    COMMAND = "codex-acp"
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        (self.path/'slots').mkdir()
        self.policy=Policy(self.path,self.path/'slots',{'turn_limit':2,'window_seconds':60,'daily_limit':5,'max_turn_seconds':30})
        self.socket=self.path/'broker.sock';self.server=Broker(self.socket,self.policy)
        self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
        script=self.path/self.COMMAND
        script.write_text('#!/bin/sh\nexec '+sys.executable+' '+str(ROOT/'tests/fixtures/fake_adapter.py')+'\n');script.chmod(0o700)
        env={**os.environ,'PATH':str(self.path)+':'+os.environ['PATH'],'PYTHONPATH':str(ROOT),
             'BUZZ_NATIVE_COMMAND':self.COMMAND,'BUZZ_GUARD_SOCKET':str(self.socket)}
        self.process=subprocess.Popen([sys.executable,'-m','buzz_agents.guard'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,env=env,process_group=0)
    def tearDown(self):
        import signal
        try:os.killpg(self.process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        self.process.wait(timeout=5)
        for s in (self.process.stdin,self.process.stdout,self.process.stderr):s.close()
        self.policy.close();self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def send(self,message):self.process.stdin.write(json.dumps(message).encode()+b'\n');self.process.stdin.flush()
    def read(self):
        ready,_,_=select.select([self.process.stdout],[],[],4)
        self.assertTrue(ready,'proxy response timeout')
        return json.loads(self.process.stdout.readline())
    def test_real_json_lines_roundtrip_and_persisted_budget(self):
        self.send({'jsonrpc':'2.0','id':1,'method':'initialize','params':{}})
        self.assertEqual(self.read()['result']['protocolVersion'],1)
        self.send({'jsonrpc':'2.0','id':2,'method':'session/prompt','params':{'sessionId':'s','prompt':[]}})
        self.assertEqual(self.read()['result']['stopReason'],'end_turn')
        self.assertEqual(len(self.policy.data['starts']),1)
        self.assertEqual(self.policy.active,{})
    def test_real_rate_limit_rejects_third_turn(self):
        for i in (1,2):
            self.send({'id':i,'method':'session/prompt','params':{'sessionId':'s','prompt':[]}})
            self.assertIn('result',self.read())
        self.send({'id':3,'method':'session/prompt','params':{'sessionId':'s','prompt':[]}})
        self.assertIn('error',self.read())
        self.assertIsNone(self.process.poll())
        self.assertEqual(self.policy.tripped,'')
        self.policy.clock=lambda: __import__('time').time()+61
        self.send({'id':4,'method':'session/prompt','params':{'sessionId':'s','prompt':[]}})
        self.assertIn('result',self.read())
    def test_real_large_frame_and_following_request(self):
        self.send({'id':1,'method':'test/large-frame'})
        self.assertEqual(len(self.read()['result']['data']),5*1024*1024)
        self.send({'id':2,'method':'session/prompt','params':{}})
        self.assertEqual(self.read()['result']['stopReason'],'end_turn')

    def test_real_invalid_json_has_safe_specific_diagnosis(self):
        self.process.stdin.write(b'SECRET-INVALID-JSON\n');self.process.stdin.flush()
        self.assertEqual(self.process.wait(timeout=4),3)
        raw=self.process.stderr.read()
        self.assertIn(b'runtime_frame_invalid_json',raw)
        self.assertNotIn(b'SECRET',raw)
        self.assertEqual(self.policy.tripped,'')

    def test_real_sustained_work_with_budgets_disabled(self):
        self.policy.limits.update(turn_limit=0,daily_limit=0)
        for n in range(105):
            self.send({'id':n,'method':'session/prompt','params':{}})
            self.assertEqual(self.read()['result']['stopReason'],'end_turn')
        self.assertIsNone(self.process.poll())
        self.assertEqual(self.policy.check(),'')
        self.assertEqual(self.policy.data['starts'],[])
    def test_adapter_crash_is_observed(self):
        self.send({'id':1,'method':'session/prompt','params':{'crash':True}})
        self.assertEqual(self.process.wait(timeout=4),3)
        self.assertEqual(self.policy.tripped,'')
        self.assertEqual(self.policy.active,{})
        self.assertEqual(len(self.policy.data['starts']),1)

    def test_idle_eof_never_trips_bot(self):
        self.send({'method':'test/idle-eof'})
        self.assertEqual(self.process.wait(timeout=4),3)
        self.assertEqual(self.policy.tripped,'')
        self.assertEqual(self.policy.active,{})
        self.assertEqual(self.policy.data['starts'],[])
    def test_adapter_stderr_is_classified_without_secret(self):
        self.send({'method':'test/stderr'})
        ready,_,_=select.select([self.process.stderr],[],[],4)
        self.assertTrue(ready)
        line=self.process.stderr.readline()
        self.assertIn(b'runtime_authentication_required',line)
        self.assertNotIn(b'SECRET',line)

    def test_crashed_adapter_descendants_die_before_slot_reuse(self):
        import time
        self.send({'id':99,'method':'test/descendant'})
        pid=self.read()['result']['pid']
        sibling=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],start_new_session=True)
        try:
            self.send({'id':1,'method':'session/prompt','params':{'crash':True}})
            self.assertEqual(self.process.wait(timeout=4),3)
            self.assertEqual(self.policy.active,{})
            self.assertIsNone(sibling.poll(),'another worker group was killed')
            status=Path('/proc')/str(pid)/'stat'
            for _ in range(20):
                if not status.exists() or status.read_text().split()[2]=='Z':
                    break
                time.sleep(.05)
            else:self.fail('adapter descendant still running after ticket release')
        finally:
            sibling.kill();sibling.wait(timeout=3)
            try:os.kill(pid,9)
            except ProcessLookupError:pass

    def test_fast_adapter_failure_keeps_safe_diagnosis(self):
        self.send({'method':'test/stderr-exit'})
        self.assertEqual(self.process.wait(timeout=4),3)
        raw=self.process.stderr.read()
        self.assertIn(b'runtime_authentication_required',raw)
        self.assertNotIn(b'SECRET',raw)

    def test_upstream_group_kill_stops_adapter_descendants(self):
        import signal,time
        self.send({'id':99,'method':'test/descendant'})
        pid=self.read()['result']['pid']
        old_group=os.getpgid(pid)
        try:
            os.killpg(self.process.pid,signal.SIGKILL)
            self.process.wait(timeout=4)
            status=Path('/proc')/str(pid)/'stat'
            for _ in range(40):
                if not status.exists() or status.read_text().split()[2]=='Z':break
                time.sleep(.025)
            else:self.fail('AI descendant survived upstream guard-group SIGKILL')
        finally:
            # Clean both the old buggy separate group and the corrected group.
            for pgid in {old_group,self.process.pid}:
                try:os.killpg(pgid,signal.SIGKILL)
                except ProcessLookupError:pass

    def test_killed_active_worker_slot_reclaimed_without_quota_reset(self):
        import signal,time
        self.send({'id':1,'method':'session/prompt','params':{'hold':True}})
        self.assertEqual(self.read()['method'],'session/update')
        self.assertEqual(len(self.policy.active),1)
        self.assertEqual(self.policy.acquire()['error'],'busy')
        os.killpg(self.process.pid,signal.SIGKILL);self.process.wait(timeout=4)
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            self.policy.check()
            if not self.policy.active:break
            time.sleep(.01)
        self.assertEqual(self.policy.active,{})
        self.assertEqual(self.policy.tripped,'')
        self.assertEqual(len(self.policy.data['starts']),1)
        next_turn=self.policy.acquire()
        self.assertTrue(next_turn['ok'])
        self.assertEqual(len(self.policy.data['starts']),2)
        self.policy.release(next_turn['ticket'])
        self.policy.monotonic=lambda:time.monotonic()+1000
        self.assertEqual(self.policy.check(),'')

class ClaudeRealProxyTests(RealProxyTests):
    COMMAND = "claude-agent-acp"


class EnvironmentChecks(unittest.TestCase):
    def test_actual_uid_drop_and_root_file_boundary(self):
        if os.geteuid()!=0:self.skipTest('current process is not root')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o755);(root/'private').write_text('disposable');(root/'private').chmod(0o600)
            code='''import os,sys
assert os.geteuid()==10001
try: open(sys.argv[1]).read()
except PermissionError: raise SystemExit(0)
raise SystemExit(2)
'''
            try:
                p=subprocess.run([sys.executable,'-c',code,str(root/'private')],user=10001,group=10001,
                                 extra_groups=[],capture_output=True,timeout=5)
            except (OSError,subprocess.SubprocessError) as error:
                self.skipTest('this environment does not allow UID switching: '+type(error).__name__)
            self.assertEqual(p.returncode,0,p.stderr.decode())
    def test_real_nostr_dependency_when_installed(self):
        if not (ROOT/'node_modules/@noble/secp256k1').exists():
            self.skipTest('npm package is not installed in offline test environment; image preflight must check it')
        from buzz_agents.common import crypto
        pair=crypto('keygen');self.assertEqual(crypto('public',pair['private_key']),pair['public_key'])
