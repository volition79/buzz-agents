import os
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from buzz_agents.portal_broker import LoginSessions
from buzz_agents.common import ToolError

class LoginCapacityTests(unittest.TestCase):
    def test_completed_attempts_do_not_block_either_provider(self):
        for provider in ('codex','claude'):
            with self.subTest(provider=provider):
                def spawn(argv,**kwargs):
                    return subprocess.Popen([sys.executable,'-c',"print('completed',flush=True)"],**kwargs)
                sessions=LoginSessions(spawn=spawn)
                try:
                    with patch('buzz_agents.portal_broker.read_json',return_value={'b'*64:{'provider':provider}}), \
                         patch('buzz_agents.portal_broker.inspect_container',return_value={'State':{'Running':True}}), \
                         patch('buzz_agents.portal_broker.check_ownership'):
                        for _ in range(12):
                            sid=sessions.start({'state_dir':'/unused'},'b'*64)['session']
                            sessions.items[sid]['process'].wait(timeout=3)
                            deadline=time.monotonic()+2
                            while time.monotonic()<deadline:
                                result=sessions.poll(sid)
                                if 'completed' in result['output']:break
                                time.sleep(.01)
                            self.assertTrue(result['success'])
                            self.assertIn('completed',result['output'])
                        self.assertLessEqual(len(sessions.items),8)
                finally:
                    for item in sessions.items.values():os.close(item['fd'])

    def test_eight_running_logins_still_refuse_ninth(self):
        from unittest.mock import Mock
        sessions=LoginSessions(clock=lambda:100)
        process=Mock();process.poll.return_value=None
        sessions.items={str(i):{'pubkey':str(i)*64,'created':99,'process':process} for i in range(8)}
        with patch('buzz_agents.portal_broker.read_json',return_value={'b'*64:{'provider':'codex'}}), \
             patch('buzz_agents.portal_broker.inspect_container',return_value={'State':{'Running':True}}), \
             patch('buzz_agents.portal_broker.check_ownership'):
            with self.assertRaisesRegex(ToolError,'too_many_login_sessions'):
                sessions.start({'state_dir':'/unused'},'b'*64)

    def test_failed_expiry_isolated_and_retried_without_overlapping_bot(self):
        import threading
        from unittest.mock import Mock
        for provider in ('codex', 'claude'):
            with self.subTest(provider=provider):
                now=[1000]
                command=Mock(side_effect=ToolError('host_command_failed'))
                old=Mock();old.poll.return_value=None
                sessions=LoginSessions(clock=lambda:now[0],command=command,
                    spawn=lambda argv,**kw:subprocess.Popen([sys.executable,'-c',"print('done')"],**kw))
                sessions.items['expired']={'pubkey':'a'*64,'created':1,'process':old,
                    'job':'a'*32,'fd':os.open(os.devnull,os.O_RDONLY),'reader_stop':threading.Event()}
                try:
                    with patch('buzz_agents.portal_broker.read_json',return_value={k*64:{'provider':provider} for k in ('a','b')}), \
                         patch('buzz_agents.portal_broker.inspect_container',return_value={'State':{'Running':True}}), \
                         patch('buzz_agents.portal_broker.check_ownership'):
                        sid=sessions.start({'state_dir':'/unused'},'b'*64)['session']
                        sessions.items[sid]['process'].wait(timeout=3)
                        self.assertTrue(sessions.poll(sid)['success'])
                        self.assertEqual(command.call_count,1)
                        old.kill.assert_not_called()
                        with self.assertRaisesRegex(ToolError,'authentication_already_in_progress'):
                            sessions.start({'state_dir':'/unused'},'a'*64)
                        with self.assertRaisesRegex(ToolError,'login_session_expired'):
                            sessions.get('expired')
                        command.side_effect=None
                        now[0]+=31
                        sessions.expire()
                        self.assertEqual(command.call_count,2)
                        old.wait.assert_called_once_with(timeout=5)
                        self.assertNotIn('expired',sessions.items)
                finally:
                    for item in sessions.items.values():
                        item['reader_stop'].set();os.close(item['fd'])
