from datetime import datetime
from pathlib import Path
import sqlite3
import tempfile
import unittest
from buzz_agents.scheduler import Scheduler, schedule_spec, due_at
from buzz_agents.common import ToolError


def cfg(kind='daily'):
    item={'id':'daily-review','kind':kind,'channel_id':'00000000-0000-0000-0000-000000000001',
          'bot_pubkey':'b'*64,'prompt':'필요한 봇과 협업하여 결과를 알려주세요.','time':'09:00','timezone':'Asia/Seoul',
          'at':'2026-10-09T09:00:00+09:00'}
    return {'enabled':True,'private_key_hex':'c'*64,'relay':'wss://relay.example.com','schedules':[item]}


class ScheduleTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'test.sqlite';self.sent=[]
    def tearDown(self):self.tmp.cleanup()
    def make(self,c=None,sender=None):return Scheduler(self.db,c or cfg(),sender or (lambda *args:self.sent.append(args)))
    def test_korean_daily_timezone(self):
        stamp=datetime.fromisoformat('2026-10-09T09:00:03+09:00').timestamp()
        self.assertEqual(due_at(cfg()['schedules'][0],stamp),stamp-3)
    def test_one_native_mention_not_three_stage_pipeline(self):
        s=self.make();t=datetime.fromisoformat('2026-10-09T09:00:01+09:00').timestamp()
        s.tick(t);s.tick(t+5);self.assertEqual(len(self.sent),1)
        self.assertEqual(s.db.execute('SELECT state FROM deliveries').fetchone()[0],'delivered_not_completion');s.db.close()
    def test_no_delivery_repeat_after_restart(self):
        s=self.make();t=datetime.fromisoformat('2026-10-09T09:00:01+09:00').timestamp();s.tick(t);s.db.close()
        s=self.make();s.tick(t+10);self.assertEqual(len(self.sent),1);s.db.close()
    def test_offline_missed_schedule_does_not_burst(self):
        s=self.make();t=datetime.fromisoformat('2026-10-09T12:00:00+09:00').timestamp();s.tick(t)
        self.assertEqual(self.sent,[]);self.assertEqual(s.db.execute('SELECT state FROM deliveries').fetchone()[0],'skipped_late');s.db.close()
    def test_unknown_delivery_is_not_retried(self):
        def fail(*args):self.sent.append(args);raise OSError('network cut')
        s=self.make(sender=fail);t=datetime.fromisoformat('2026-10-09T09:00:01+09:00').timestamp()
        s.tick(t);s.tick(t+5);self.assertEqual(len(self.sent),1)
        self.assertEqual(s.db.execute('SELECT state FROM deliveries').fetchone()[0],'unknown');s.db.close()
    def test_prepared_on_restart_becomes_unknown(self):
        s=self.make();s.db.execute("INSERT INTO deliveries VALUES('daily-review',1,'prepared')");s.db.commit();s.db.close()
        s=self.make();self.assertEqual(s.db.execute('SELECT state FROM deliveries').fetchone()[0],'unknown');s.db.close()
    def test_disabled_scheduler_sends_nothing(self):
        c=cfg();c['enabled']=False;s=self.make(c);s.tick(datetime.fromisoformat(c['schedules'][0]['at']).timestamp())
        self.assertEqual(self.sent,[]);s.db.close()
    def test_once_requires_explicit_offset(self):
        c=cfg('once');c['schedules'][0]['at']='2026-10-09T09:00:00'
        with self.assertRaises(ToolError):self.make(c)
    def test_unknown_bot_bad_channel_and_duplicate_schedule_rejected(self):
        for edit in ('bot','channel','duplicate'):
            c=cfg()
            if edit=='bot':c['schedules'][0]['bot_pubkey']='bad'
            elif edit=='channel':c['schedules'][0]['channel_id']='not-uuid'
            else:c['schedules'].append(c['schedules'][0].copy())
            with self.subTest(edit=edit),self.assertRaises((ToolError,ValueError)):self.make(c)
