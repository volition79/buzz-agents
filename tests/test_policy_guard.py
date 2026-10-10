import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from buzz_agents.guard import Proxy, broker
from buzz_agents.policy import Policy, Broker, atomic_json


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'slots').mkdir();self.now=[100000.0];self.mono=[20.0]
        self.limits={'turn_limit':2,'window_seconds':60,'daily_limit':3,'max_turn_seconds':10}
        self.policy=Policy(self.root,self.root/'slots',self.limits,clock=lambda:self.now[0],monotonic=lambda:self.mono[0])
    def tearDown(self): self.policy.close();self.tmp.cleanup()
    def test_ticket_required_to_release(self):
        a=self.policy.acquire();self.assertTrue(a['ok'])
        self.assertFalse(self.policy.release('wrong')['ok']);self.assertEqual(self.policy.acquire()['error'],'busy')
        self.assertTrue(self.policy.release(a['ticket'])['ok'])
    def test_persistent_window_limit(self):
        for _ in range(2):
            a=self.policy.acquire();self.policy.release(a['ticket'])
        other=Policy(self.root,self.root/'slots',self.limits,clock=lambda:self.now[0])
        self.assertEqual(other.acquire()['error'],'turn_window_limit')
    def test_rolling_daily_limit(self):
        for i in range(3):
            self.now[0]+=61; a=self.policy.acquire();self.policy.release(a['ticket'])
        self.now[0]+=61
        self.assertEqual(self.policy.acquire()['error'],'daily_start_limit')
    def test_monotonic_deadline(self):
        self.policy.acquire();self.now[0]-=900;self.mono[0]+=11
        self.assertEqual(self.policy.check(),'turn_deadline')
    def test_wall_clock_rollback_refused(self):
        a=self.policy.acquire();self.policy.release(a['ticket']);self.now[0]-=5
        self.assertEqual(self.policy.acquire()['error'],'clock_moved_backwards')
    def test_expired_window_not_entire_bot_lifetime(self):
        for _ in range(2):
            a=self.policy.acquire();self.policy.release(a['ticket'])
        self.now[0]+=61
        self.assertTrue(self.policy.acquire()['ok'])
    def test_other_bots_do_not_block_a_delegation(self):
        self.policy.acquire()
        otherdir=self.root/'other';otherdir.mkdir();(otherdir/'slots').mkdir()
        other=Policy(otherdir,otherdir/'slots',self.limits,clock=lambda:self.now[0])
        self.assertTrue(other.acquire()['ok']);other.close()
    def test_unix_broker_real_io(self):
        p=self.root/'guard.sock';server=Broker(p,self.policy)
        thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            a=broker({'op':'acquire'},str(p));self.assertTrue(a['ok'])
            self.assertTrue(broker({'op':'release','ticket':a['ticket']},str(p))['ok'])
        finally:server.shutdown();server.server_close();thread.join()
    def test_quota_storage_failure_refuses_execution(self):
        from unittest.mock import patch
        with patch('buzz_agents.policy.atomic_json',side_effect=OSError('disk full')):
            self.assertEqual(self.policy.acquire()['error'],'quota_storage_failed')
        self.assertEqual(self.policy.active,{})

    def test_user_selected_concurrency_through_real_socket(self):
        for count in (1, 2, 10, 32):
            with self.subTest(count=count):
                self.policy.close()
                (self.root/'quota.json').unlink(missing_ok=True)
                limits=dict(self.limits,turn_limit=100,daily_limit=200)
                self.policy=Policy(self.root,self.root/'slots',limits,concurrency=count)
                path=self.root/'parallel.sock';server=Broker(path,self.policy)
                thread=threading.Thread(target=server.serve_forever);thread.start()
                try:
                    tickets=[broker({'op':'acquire'},str(path)) for _ in range(count)]
                    self.assertTrue(all(t['ok'] for t in tickets))
                    self.assertEqual(len(self.policy.active),count)
                    self.assertEqual(broker({'op':'acquire'},str(path))['error'],'busy')
                    token=tickets[0]['ticket']
                    self.assertTrue(broker({'op':'release','ticket':token},str(path))['ok'])
                    self.assertFalse(broker({'op':'release','ticket':token},str(path))['ok'])
                    self.assertTrue(broker({'op':'acquire'},str(path))['ok'])
                    self.assertEqual(len(json.loads((self.root/'quota.json').read_text())['starts']),count+1)
                finally:
                    server.shutdown();server.server_close();thread.join();path.unlink()

    def test_each_concurrent_ticket_has_its_own_deadline(self):
        self.policy.close()
        self.policy=Policy(self.root,self.root/'slots',self.limits,concurrency=2,
                           clock=lambda:self.now[0],monotonic=lambda:self.mono[0])
        first=self.policy.acquire()
        self.mono[0]+=5
        self.policy.acquire()
        self.policy.release(first['ticket'])
        self.mono[0]+=6
        self.assertEqual(self.policy.check(),'')
        self.mono[0]+=5
        self.assertEqual(self.policy.check(),'turn_deadline')

    def test_dead_owner_with_live_descendant_keeps_slot_until_group_dies(self):
        import subprocess,sys,signal,time
        path=self.root/'lifetime.sock';server=Broker(path,self.policy)
        thread=threading.Thread(target=server.serve_forever);thread.start()
        code="""import subprocess,sys,time,json
from buzz_agents.guard import broker
answer=broker({'op':'acquire'},sys.argv[1])
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
print(json.dumps({'ticket':answer['ticket'],'child':child.pid}),flush=True)
time.sleep(60)
"""
        process=subprocess.Popen([sys.executable,'-c',code,str(path)],stdout=subprocess.PIPE,process_group=0)
        try:
            data=json.loads(process.stdout.readline())
            process.kill();process.wait(timeout=3)
            self.assertEqual(self.policy.check(),'')
            self.assertIn(data['ticket'],self.policy.active)
            self.assertEqual(self.policy.acquire()['error'],'busy')
            os.killpg(process.pid,signal.SIGKILL)
            for _ in range(100):
                self.policy.check()
                if not self.policy.active:break
                time.sleep(.01)
            self.assertEqual(self.policy.active,{})
            self.assertEqual(self.policy.owners,{})
            self.assertEqual(len(self.policy.data['starts']),1)
        finally:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=3);process.stdout.close()
            server.shutdown();server.server_close();thread.join()


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.to_agent=[];self.to_host=[];self.calls=[];self.busy=False
        def call(req):
            self.calls.append(req)
            if req['op']=='acquire':return {'ok':False,'error':'busy'} if self.busy else {'ok':True,'ticket':'token'}
            return {'ok':True}
        self.proxy=Proxy(self.to_agent.append,self.to_host.append,call)
        self.prompt={'jsonrpc':'2.0','id':1,'method':'session/prompt','params':{'sessionId':'s','prompt':[{'type':'text','text':'자유 협업'}]}}
    def test_initialize_and_notifications_pass_unchanged(self):
        message={'id':7,'method':'initialize','params':{'protocolVersion':1}}
        self.proxy.from_host(message);self.assertEqual(self.to_agent,[message]);self.assertEqual(self.calls,[])
        update={'method':'session/update','params':{'sessionId':'s','update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':'hello'}}}}
        self.proxy.from_agent(update);self.assertEqual(self.to_host,[update])
    def test_prompt_is_gated_then_forwarded_without_rewriting(self):
        self.proxy.from_host(self.prompt);self.assertEqual(self.to_agent,[])
        self.proxy.tick();self.assertEqual(self.to_agent,[self.prompt])
    def test_reply_releases_and_preserves_native_output(self):
        self.proxy.from_host(self.prompt);self.proxy.tick()
        response={'jsonrpc':'2.0','id':1,'result':{'stopReason':'end_turn'}}
        self.proxy.from_agent(response);self.assertEqual(self.to_host[-1],response)
        self.assertEqual(self.calls[-1]['op'],'release')
    def test_failure_releases_worker_without_tripping_bot(self):
        self.proxy.from_host(self.prompt);self.proxy.tick()
        self.proxy.from_agent({'id':1,'error':{'code':-32000,'message':'auth expired'}})
        self.assertFalse(self.proxy.stopped);self.assertEqual(self.calls[-1]['op'],'release')
    def test_permission_request_with_matching_id_is_not_completion(self):
        self.proxy.from_host(self.prompt);self.proxy.tick()
        self.proxy.from_agent({'id':1,'method':'session/request_permission','params':{}})
        self.assertTrue(self.proxy.active);self.assertFalse(any(c['op']=='release' for c in self.calls))
    def test_busy_does_not_repeatedly_consume_tickets(self):
        self.busy=True;self.proxy.from_host(self.prompt);self.proxy.tick()
        self.assertEqual(self.to_agent,[]);self.assertEqual(len(self.proxy.waiting),1)
        self.busy=False;self.proxy.tick();self.assertEqual(self.to_agent,[self.prompt])
    def test_cancel_pending_prompt_without_running_it(self):
        self.busy=True;self.proxy.from_host(self.prompt);self.proxy.tick()
        cancel={'method':'session/cancel','params':{'sessionId':'s'}}
        self.proxy.from_host(cancel);self.assertEqual(self.proxy.waiting,[])
        self.assertEqual(self.to_host[-1]['result']['stopReason'],'cancelled')
        self.assertEqual(self.to_agent,[cancel])
    def test_guard_rejection_never_forwards_prompt(self):
        self.proxy.call=lambda r:{'ok':False,'error':'daily_start_limit'}
        self.proxy.from_host(self.prompt);self.proxy.tick()
        self.assertTrue(self.proxy.stopped);self.assertEqual(self.to_agent,[])
        self.assertIn('error',self.to_host[-1])

    def test_active_cancel_keeps_slot_until_final_response(self):
        self.proxy.from_host(self.prompt);self.proxy.tick()
        cancel={'method':'session/cancel','params':{'sessionId':'s'}}
        self.proxy.from_host(cancel)
        self.assertEqual(self.to_agent[-1],cancel)
        self.assertTrue(self.proxy.active)
        self.assertFalse(any(c['op']=='release' for c in self.calls))
        self.proxy.from_agent({'id':1,'result':{'stopReason':'cancelled'}})
        self.assertEqual(self.calls[-1]['op'],'release')
