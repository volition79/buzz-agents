import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

class RuntimeHealthTests(unittest.TestCase):
    def test_cgroup_history_is_not_a_new_failure_and_delta_is_sticky(self):
        from buzz_agents.runtime_health import ResourceSampler
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for name,value in {'pids.current':'251','pids.max':'256','pids.events':'max 211\n','memory.current':'700','memory.max':'1600','memory.events':'oom 0\noom_kill 0\n'}.items():
                (p/name).write_text(value)
            sampler=ResourceSampler(p)
            first=sampler.sample()
            self.assertEqual(first['pids_events_delta'],0)
            self.assertEqual(first['health_warning'],'runtime_process_limit_near_capacity')
            self.assertEqual(sampler.diagnostic,'')
            (p/'pids.events').write_text('max 212\n')
            self.assertEqual(sampler.sample()['pids_events_delta'],1)
            self.assertEqual(sampler.diagnostic,'runtime_process_limit')
            (p/'pids.current').write_text('20')
            self.assertEqual(sampler.sample()['health_warning'],'')
            self.assertEqual(sampler.diagnostic,'runtime_process_limit')

    def test_missing_invalid_and_unlimited_are_not_fabricated(self):
        from buzz_agents.runtime_health import ResourceSampler, public_resources
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'pids.max').write_text('max');(p/'pids.current').write_text('-1')
            r=ResourceSampler(p).sample()
            self.assertIsNone(r['pids_max']);self.assertNotIn('pids_current',r)
            self.assertEqual(public_resources({'pids_current':True,'pids_max':None,'secret':'nsec','memory_current':float('inf')}),{'pids_max':None})

    def test_guardian_structured_error_only_and_no_raw_output(self):
        from buzz_agents.diagnostics import structured_diagnostic, RuntimeDiagnostics
        error='Automatic approval review failed: internal error; agent loop died unexpectedly SECRET'
        frame={'method':'session/update','params':{'update':{'sessionUpdate':'tool_call_update','content':[{'type':'content','content':{'type':'text','text':error}}]}}}
        self.assertEqual(structured_diagnostic(frame),'runtime_approval_review_failed')
        frame['params']['update']['sessionUpdate']='agent_message_chunk'
        self.assertIsNone(structured_diagnostic(frame))
        self.assertEqual(RuntimeDiagnostics().feed(b'cannot fork: Resource temporarily unavailable SECRET'),['runtime_process_creation_failed'])

    def test_public_bot_records_include_only_safe_health(self):
        from buzz_agents.bridge import bot_records
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);key='b'*64;state=p/'bots'/key/'state';state.mkdir(parents=True)
            (p/'registry.json').write_text(json.dumps({key:{'name':'Codex','provider':'codex'}}))
            (state/'runtime.json').write_text(json.dumps({'status':'running','reason':'secret token','diagnostic':'runtime_process_limit','resources':{'pids_current':251,'secret':'token'}}))
            with patch('buzz_agents.bridge.inspect_container',return_value=None):
                record=bot_records({'state_dir':d})[0]
            self.assertEqual(record['diagnostic'],'runtime_process_limit');self.assertEqual(record['reason'],'')
            self.assertEqual(record['resources'],{'pids_current':251})

    def test_guard_proxy_reports_without_changing_forwarded_frame(self):
        import io
        from buzz_agents.guard import Proxy
        error={'method':'session/update','params':{'update':{'sessionUpdate':'tool_call_update','content':[{'content':{'type':'text','text':'Automatic approval review failed: PRIVATE'}}]}}}
        forwarded=[];output=io.StringIO()
        with patch('sys.stderr',output):
            Proxy(lambda _:None,forwarded.append).from_agent(error)
        self.assertEqual(forwarded,[error])
        self.assertEqual(output.getvalue(),'buzz-agents-diagnostic:runtime_approval_review_failed\n')

    def test_counter_reset_is_not_an_increase_and_invalid_size_is_bounded(self):
        from buzz_agents.runtime_health import ResourceSampler
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);counter=root/'pids.events';counter.write_text('max 10\n')
            sampler=ResourceSampler(root);sampler.sample()
            counter.write_text('max 1\n');self.assertEqual(sampler.sample()['pids_events_delta'],0)
            counter.write_text('max 2\n');self.assertEqual(sampler.sample()['pids_events_delta'],1)
            (root/'pids.current').write_text('9'*5000)
            self.assertNotIn('pids_current',sampler.sample())
