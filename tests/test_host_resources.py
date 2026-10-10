import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from buzz_agents.host import host_capacity, check_resources
from buzz_agents.portal_broker import Broker
from buzz_agents.common import ToolError
from helpers import config, settings, OWNER, RELAY


class ResourcesTests(unittest.TestCase):
    def test_daemon_capacity_reserves_os_and_relay(self):
        for gb, expected in ((4,2048),(8,6144),(64,49152)):
            calls=[]
            def runner(argv,**kwargs):
                calls.append(argv)
                return json.dumps({'NCPU':16,'MemTotal':gb*1024**3}).encode()
            value=host_capacity(runner)
            self.assertEqual(value['budget_mb'],expected)
            self.assertEqual(calls[0][:2],['docker','info'])
        for data in ({},{'NCPU':True,'MemTotal':2**40},{'NCPU':2,'MemTotal':'x'}):
            with self.assertRaisesRegex(ToolError,'host_capacity_unavailable'):
                host_capacity(lambda *a,**k:json.dumps(data).encode())

    def test_reserve_aggregate_and_explicit_limits(self):
        c=config(options={'memory_mb':4096,'cpus':2})
        capacity={'cpus':8,'budget_mb':6144}
        check_resources(c,{}, {},capacity)
        prior=config(pub='c'*64,options={'memory_mb':3072})
        with self.assertRaisesRegex(ToolError,'aggregate_memory_budget'):
            check_resources(c,{prior['pubkey']:prior},{},capacity)
        with self.assertRaisesRegex(ToolError,'aggregate_memory_budget'):
            check_resources(c,{}, {'memory_budget_mb':2048},capacity)
        with self.assertRaisesRegex(ToolError,'registered_bot_limit'):
            check_resources(c,{prior['pubkey']:prior},{'max_bots':1},capacity)
        # CPU limits are time-shared; only per-bot CPU must fit the daemon.
        check_resources(config(options={'memory_mb':512,'cpus':8}),
                        {prior['pubkey']:prior},{},capacity)

    def test_selected_image_refresh_needs_no_manual_reconfigure(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=settings(Path(tmp)/'data')
            Path(tmp,'settings.json').write_text(json.dumps(old))
            broker=Broker('runtime:new',root=Path(tmp)/'data',control=tmp)
            image=[{'Id':'sha256:'+'e'*64,'Config':{'Labels':{'org.opencontainers.image.title':'buzz-agents'}}}]
            with patch('buzz_agents.portal_broker.execute',return_value=json.dumps(image).encode()) as call:
                saved=broker.settings()
                self.assertEqual(saved['image'],'runtime:new')
                self.assertEqual(saved['image_id'],image[0]['Id'])
                self.assertEqual(call.call_args.args[0][:3],['docker','image','inspect'])
                self.assertEqual(call.call_count,1)

    def test_legacy_default_migrates_but_custom_and_fixed_preserved(self):
        variants=[({},False),({'memory_budget_mb':4096,'max_bots':4},True),
                  ({'resource_policy':'fixed'},True)]
        for extra,preserve in variants:
            with self.subTest(extra=extra),tempfile.TemporaryDirectory() as tmp:
                old=settings(Path(tmp)/'data');old.update(extra)
                Path(tmp,'settings.json').write_text(json.dumps(old))
                broker=Broker('runtime:verified',root=Path(tmp)/'data',control=tmp)
                image=[{'Id':'sha256:'+'e'*64,'Config':{'Labels':{'org.opencontainers.image.title':'buzz-agents'}}}]
                with patch('buzz_agents.portal_broker.execute',return_value=json.dumps(image).encode()):
                    broker.dispatch({'op':'configure','owner':OWNER,'relay':RELAY})
                saved=json.loads(Path(tmp,'settings.json').read_text())
                self.assertEqual(saved['image_id'],image[0]['Id'])
                if preserve:
                    self.assertEqual(saved['memory_budget_mb'],old['memory_budget_mb'])
                    self.assertEqual(saved['max_bots'],old['max_bots'])
                else:
                    self.assertNotIn('memory_budget_mb',saved)
                    self.assertNotIn('max_bots',saved)
                    self.assertEqual(saved['resource_policy'],'host-v1')
