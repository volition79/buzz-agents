"""Incident replay: healthy work must not latch the entire bot.

Source baseline d1a887eb422ed0dcc24e37b700863670d0917866 (dirty mobile UI).
2026-10-10 sanitized incident: held/turn_window_limit, window=0, daily=47.
These local ACP fixtures use neither provider accounts nor the live VPS.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from buzz_agents.guard import Proxy, decode_frames, ProtocolFault, MAX_LINE
from buzz_agents.policy import Policy, budget_wait, atomic_json
from buzz_agents.native import state_on_start
from buzz_agents.diagnostics import RuntimeDiagnostics, DIAGNOSTIC_CODES
from helpers import config


class RecoveryTests(unittest.TestCase):
    def test_default_claude_and_codex_allow_sustained_healthy_work(self):
        for command in ('codex-acp', 'claude-agent-acp'):
            with self.subTest(command=command), tempfile.TemporaryDirectory() as d:
                root=Path(d);(root/'slots').mkdir()
                cfg=config(command)
                self.assertEqual(cfg['policy']['turn_limit'],0)
                self.assertEqual(cfg['policy']['daily_limit'],0)
                self.assertEqual(cfg['env']['BUZZ_ACP_MAX_TURN_DURATION'],'7200')
                self.assertEqual(cfg['env']['BUZZ_ACP_IDLE_TIMEOUT'],'1500')
                policy=Policy(root,root/'slots',cfg['policy'])
                host=[];worker=[]
                def call(req):
                    return policy.acquire() if req['op']=='acquire' else policy.release(req['ticket'])
                proxy=Proxy(worker.append,host.append,call)
                try:
                    for n in range(125):
                        proxy.from_host({'id':n,'method':'session/prompt','params':{'sessionId':'s'}})
                        proxy.tick()
                        self.assertEqual(worker[-1]['id'],n)
                        proxy.from_agent({'id':n,'result':{'stopReason':'end_turn'}})
                    self.assertEqual(len(host),125)
                    self.assertFalse(proxy.stopped)
                    self.assertEqual(policy.check(),'')
                    self.assertEqual(policy.active,{})
                    self.assertEqual(policy.data['starts'],[])
                finally:policy.close()

    def test_enabled_budget_expiry_and_restart_preserve_history(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'slots').mkdir()
            cfg=config(options={'turn_limit':1,'daily_limit':2})['policy']
            now=[100000]
            p=Policy(root,root/'slots',cfg,clock=lambda:now[0])
            ticket=p.acquire()['ticket'];p.release(ticket)
            self.assertEqual(p.acquire()['retry_after_seconds'],3600)
            self.assertEqual(p.check(),'');p.close()
            p=Policy(root,root/'slots',cfg,clock=lambda:now[0])
            try:
                self.assertEqual(p.acquire()['error'],'turn_window_limit')
                now[0]+=3600
                ticket=p.acquire()['ticket'];p.release(ticket)
                self.assertEqual(p.acquire()['retry_after_seconds'],82800)
                now[0]+=82800
                self.assertTrue(p.acquire()['ok'])
            finally:p.close()

    def test_expired_legacy_hold_recovers_but_faults_and_stops_do_not(self):
        cfg=config(options={'turn_limit':20,'daily_limit':100})['policy']
        quota={'starts':[95000]*47,'last':95000}
        held={'status':'held','reason':'turn_window_limit'}
        self.assertEqual(state_on_start(held,cfg,quota,100000),('ready','expired_budget_hold'))
        self.assertEqual(state_on_start(held,cfg,quota,95001),('held','turn_window_limit'))
        self.assertEqual(state_on_start(held,cfg,quota,90000),('held','turn_window_limit'))
        for reason in ('native_process_failed','adapter_or_guard_fault','turn_deadline','operator_action_required'):
            state={'status':'held','reason':reason}
            self.assertEqual(state_on_start(state,cfg,quota,100000),('held',reason))
        self.assertEqual(state_on_start({'status':'stopped','reason':'native_clean_exit'},cfg,quota,100000),('stopped','native_clean_exit'))

    def test_worker_deadline_does_not_latch_other_workers(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'slots').mkdir();now=[0.0]
            policy=Policy(root,root/'slots',config()['policy'],concurrency=2)
            def call(req):
                return policy.acquire() if req['op']=='acquire' else policy.release(req['ticket'])
            out=[];a=Proxy(lambda _:None,out.append,call,monotonic=lambda:now[0])
            b=Proxy(lambda _:None,out.append,call,monotonic=lambda:now[0])
            try:
                a.from_host({'id':1,'method':'session/prompt'});a.tick()
                now[0]=7000
                b.from_host({'id':2,'method':'session/prompt'});b.tick()
                now[0]=7201;a.tick();self.assertFalse(a.stopped)
                now[0]=7321;a.tick();b.tick()
                self.assertTrue(a.stopped);self.assertFalse(b.stopped)
                a.tick();self.assertEqual(len(out),1) # one terminal response only
                self.assertEqual(policy.check(),'')
                self.assertEqual(len(policy.active),2) # cleanup must precede release
                b.from_agent({'id':2,'result':{'stopReason':'end_turn'}})
                self.assertEqual(len(policy.active),1)
            finally:policy.close()

    def test_budget_rejection_has_reason_and_keeps_proxy_available(self):
        out=[];answers=[{'ok':False,'error':'daily_start_limit','retry_after_seconds':7},
                         {'ok':True,'ticket':'t'}]
        proxy=Proxy(lambda _:None,out.append,lambda _:answers.pop(0))
        proxy.from_host({'id':1,'method':'session/prompt'});proxy.tick()
        self.assertIn('7 seconds',out[0]['error']['message'])
        self.assertFalse(proxy.stopped)
        proxy.from_host({'id':2,'method':'session/prompt'});proxy.tick()
        self.assertTrue(proxy.active)

    def test_activity_does_not_claim_semantic_progress_or_erase_failures(self):
        # We forward errors to the official retry owner, without our own retry loop.
        out=[];calls=[]
        def call(req):
            calls.append(req);return {'ok':True,'ticket':'t'}
        proxy=Proxy(lambda _:None,out.append,call)
        for n in range(12):
            proxy.from_host({'id':n,'method':'session/prompt'});proxy.tick()
            failure={'id':n,'error':{'code':-32000,'message':'transient fixture'}}
            proxy.from_agent(failure)
            self.assertEqual(out[-1],failure)
        self.assertFalse(proxy.stopped)
        self.assertEqual(len(calls),24)


class FramingTests(unittest.TestCase):
    def test_official_sized_image_frame_passes(self):
        raw=json.dumps({'id':1,'result':{'data':'a'*(5*1024*1024)}}).encode()+b'\n'
        buffer=bytearray();got=[]
        for i in range(0,len(raw),65536):got.extend(decode_frames(buffer,raw[i:i+65536]))
        self.assertEqual(len(got[0]['result']['data']),5*1024*1024)
        self.assertEqual(buffer,b'')
        self.assertEqual(MAX_LINE,10_000_000)

    def test_limit_is_per_frame_not_combined_read(self):
        with patch('buzz_agents.guard.MAX_LINE',16):
            self.assertEqual(len(list(decode_frames(bytearray(),b'{"id":1}\n{"id":2}\n{"id":3}\n'))),3)
            buffer=bytearray(b'{"id":1')
            self.assertEqual(len(list(decode_frames(buffer,b'}\n{"id":2}\n'))),2)
            with self.assertRaisesRegex(ProtocolFault,'runtime_frame_too_large'):
                list(decode_frames(bytearray(),b' '*17))

    def test_safe_diagnostic_survives_supervisor_decoder(self):
        for raw,code in ((b'SECRET\n','runtime_frame_invalid_json'),(b'[]\n','runtime_frame_invalid_shape')):
            with self.assertRaises(ProtocolFault) as ctx:list(decode_frames(bytearray(),raw))
            self.assertEqual(str(ctx.exception),code)
            self.assertIn(code,DIAGNOSTIC_CODES)
            self.assertEqual(RuntimeDiagnostics().feed(('buzz-agents-diagnostic:'+code+'\n').encode()),[code])
