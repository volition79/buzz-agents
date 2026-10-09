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
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)
        (self.path/'slots').mkdir()
        self.policy=Policy(self.path,self.path/'slots',{'turn_limit':2,'window_seconds':60,'daily_limit':5,'max_turn_seconds':30})
        self.socket=self.path/'broker.sock';self.server=Broker(self.socket,self.policy)
        self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
        script=self.path/'codex-acp'
        script.write_text('#!/bin/sh\nexec '+sys.executable+' '+str(ROOT/'tests/fixtures/fake_adapter.py')+'\n');script.chmod(0o700)
        env={**os.environ,'PATH':str(self.path)+':'+os.environ['PATH'],'PYTHONPATH':str(ROOT),
             'BUZZ_NATIVE_COMMAND':'codex-acp','BUZZ_GUARD_SOCKET':str(self.socket)}
        self.process=subprocess.Popen([sys.executable,'-m','buzz_agents.guard'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,env=env)
    def tearDown(self):
        self.process.kill();self.process.wait(timeout=5)
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
        self.assertIsNone(self.policy.active)
    def test_real_rate_limit_rejects_third_turn(self):
        for i in (1,2):
            self.send({'id':i,'method':'session/prompt','params':{'sessionId':'s','prompt':[]}})
            self.assertIn('result',self.read())
        self.send({'id':3,'method':'session/prompt','params':{'sessionId':'s','prompt':[]}})
        self.assertIn('error',self.read())
        self.assertEqual(self.process.wait(timeout=4),3)
        self.assertEqual(self.policy.tripped,'turn_window_limit')
    def test_adapter_crash_is_observed(self):
        self.send({'id':1,'method':'session/prompt','params':{'crash':True}})
        self.assertEqual(self.process.wait(timeout=4),3)
        self.assertEqual(self.policy.tripped,'adapter_or_guard_fault')


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
