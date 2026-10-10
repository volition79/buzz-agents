"""Replay supervisor state writes, not only a helper returning a category."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from buzz_agents import native

class DiagnosticRestartTests(unittest.TestCase):
    def test_legacy_budget_hold_expires_in_running_supervisor_without_auth_bypass(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);state=root/'runtime.json';now=[100000.0]
            state.write_text(json.dumps({'status':'held','reason':'turn_window_limit',
                'diagnostic':'runtime_protocol_failed','startup_consumed':True}))
            (root/'quota.json').write_text(json.dumps({'starts':[100000],'last':100000}))
            cfg={'pubkey':'b'*64,'provider':'claude',
                 'policy':{'turn_limit':1,'window_seconds':3600,'daily_limit':0,'max_turn_seconds':7200}}
            def expire(_):
                now[0]+=3601
                return False
            with patch.dict(os.environ,{'NATIVE_STATE':d}), \
                 patch.object(native,'load_config',return_value=cfg), \
                 patch.object(native.signal,'signal'), \
                 patch.object(native.time,'time',side_effect=lambda:now[0]), \
                 patch.object(native.threading.Event,'wait',side_effect=expire), \
                 patch.object(native.subprocess,'Popen') as spawn:
                self.assertEqual(native.main(),0)
                spawn.assert_not_called()
            saved=json.loads(state.read_text())
            self.assertEqual(saved['status'],'ready')
            self.assertEqual(saved['reason'],'expired_budget_hold')
            self.assertTrue(saved['startup_consumed'])
            self.assertEqual(saved['diagnostic'],'runtime_protocol_failed')
            # A fresh supervisor still requires the existing subscription-login record.
            with patch.dict(os.environ,{'NATIVE_STATE':d}), \
                 patch.object(native,'load_config',return_value=cfg), \
                 patch.object(native.signal,'signal'), \
                 patch.object(native.threading.Event,'wait',return_value=True), \
                 patch.object(native.subprocess,'Popen') as spawn:
                self.assertEqual(native.main(),0)
                spawn.assert_not_called()
            self.assertEqual(json.loads(state.read_text())['status'],'needs_login')

    def test_nonlaunch_restart_preserves_last_diagnosis(self):
        for status in ('held','stopped','needs_login','ready'):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as d:
                path=Path(d)/'runtime.json'
                path.write_text(json.dumps({'status':status,'reason':'native_process_failed',
                    'diagnostic':'runtime_authentication_required','startup_consumed':True}))
                with patch.dict(os.environ,{'NATIVE_STATE':d}), \
                     patch.object(native,'load_config',return_value={'pubkey':'b'*64,'provider':'claude'}), \
                     patch.object(native.signal,'signal'), \
                     patch.object(native.threading.Event,'wait',return_value=True):
                    self.assertEqual(native.main(),0)
                saved=json.loads(path.read_text())
                self.assertEqual(saved['diagnostic'],'runtime_authentication_required')
                self.assertEqual(saved['status'],'needs_login' if status=='ready' else status)
                self.assertTrue(saved['startup_consumed'])

    def test_actual_new_launch_clears_old_diagnosis(self):
        self._new_launch(False)

    def test_new_cgroup_event_is_persisted_even_on_fast_exit(self):
        self._new_launch(True)

    def _new_launch(self, exhausted):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'slots').mkdir(mode=0o700)
            (root/'auth-claude.json').write_text('{}')
            state=root/'runtime.json'
            state.write_text(json.dumps({'status':'ready','startup_consumed':True,
                'diagnostic':'runtime_authentication_required'}))
            config={'pubkey':'b'*64,'provider':'claude','command':'claude-agent-acp',
                'env':{'BUZZ_ACP_AGENTS':'1'},'policy':{'max_turn_seconds':60}}
            process=MagicMock();process.poll.return_value=0;process.returncode=0
            pipes=[]
            for field in ('stdout','stderr'):
                r,w=os.pipe();os.close(w);f=os.fdopen(r,'rb');pipes.append(f)
                setattr(process,field,f)
            launch_records=[]
            class Sampler:
                diagnostic=""
                calls=0
                def sample(self):
                    self.calls+=1
                    if exhausted and self.calls>1:
                        self.diagnostic="runtime_process_limit"
                    return {"pids_current":251,"pids_max":256,"pids_events_delta":int(bool(self.diagnostic))}
            def launch(*args,**kwargs):
                launch_records.append(json.loads(state.read_text()))
                return process
            def paths(value):
                return root/'socket' if str(value)=='/tmp/buzz-guard.sock' else Path(value)
            try:
                with patch.dict(os.environ,{'NATIVE_STATE':d}), \
                     patch.object(native,'Path',side_effect=paths), \
                     patch.object(native,'load_config',return_value=config), \
                     patch.object(native.signal,'signal'), \
                     patch.object(native.os,'chown'), \
                     patch.object(native.os,'chmod'), \
                     patch.object(native,'Broker'), \
                     patch.object(native,'ResourceSampler',return_value=Sampler()), \
                     patch.object(native,'stop_group'), \
                     patch.object(native.subprocess,'Popen',side_effect=launch):
                    self.assertEqual(native.main(),0)
                self.assertEqual(launch_records[0]['status'],'running')
                self.assertEqual(launch_records[0]['diagnostic'],'')
                final=json.loads(state.read_text())
                self.assertEqual(final['diagnostic'],'runtime_process_limit' if exhausted else '')
                self.assertEqual(final['status'],'stopped')
                self.assertEqual(final['resources']['pids_events_delta'],int(exhausted))
            finally:
                for f in pipes:f.close()
