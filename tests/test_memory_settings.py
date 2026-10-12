"""RAM-SETTINGS-01: staged admin choice, explicit apply, later Windows deploy.
Sanitized OOM incident: Claude had 1536 MiB limit and oom_kill=4 on 2026-10-12.
Synthetic Docker fixture only; no real subscription or production mutation.
"""
import json
import os
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path
import unittest
import test_bot_update as fixtures
from helpers import PUBKEY, agent, config
from buzz_agents import memory_settings
from buzz_agents.common import ToolError
from buzz_agents.policy import read_json, atomic_json
from buzz_agents.host import public_record, service_name


class MemoryTests(unittest.TestCase):
    normalizer = fixtures.UpdateTests.normalizer
    tearDown = fixtures.UpdateTests.tearDown
    apply = fixtures.UpdateTests.apply
    def setUp(self):
        fixtures.UpdateTests.setUp(self)
        self.current['HostConfig'].update(Memory=1536*1024**2, MemorySwap=1536*4*1024**2)
        run = self.d.run
        def runner(argv, *args, **kwargs):
            result = run(argv, *args, **kwargs)
            if 'up' in argv:
                mb = read_json(self.root/'bots'/PUBKEY/'config/config.json')['memory_mb']
                self.current['HostConfig'].update(Memory=mb*1024**2, MemorySwap=mb*4*1024**2)
            return result
        self.d.run = runner
    def choose(self, value):
        return self.u.save_memory(PUBKEY, self.u.preview(PUBKEY)['revision'], value)
    def test_stage_only_and_stale_preview(self):
        prior=self.u.preview(PUBKEY); before=deepcopy(read_json(self.root/'registry.json'))
        self.choose(3072)
        self.assertEqual(read_json(self.root/'registry.json'), before)
        self.assertEqual(read_json(self.root/'bots'/PUBKEY/'config/config.json'), self.old)
        self.assertEqual(memory_settings.actual_mb(self.current),1536)
        self.assertFalse(any('stop' in a or 'up' in a for a in self.commands))
        with self.assertRaisesRegex(ToolError,'preview_changed'):
            self.u.apply(PUBKEY,prior['revision'],False)
    def test_apply_preserves_fields_and_windows_keeps_committed_not_pending(self):
        self.choose(3072);self.apply()
        after=read_json(self.root/'bots'/PUBKEY/'config/config.json')
        self.assertEqual(after,memory_settings.with_memory(self.old,3072))
        self.assertEqual(self.current['HostConfig']['MemorySwap'],3072*4*1024**2)
        self.choose(4096)
        # Old desktop value must not revert 3072 or consume the unapproved 4096.
        self.current['State']['Running']=False
        self.d.deploy({'agent':agent(),'provider_config':self.old['policy']})
        self.assertEqual(memory_settings.actual_mb(self.current),3072)
        self.assertEqual(self.u.preview(PUBKEY)['memory']['desired_mb'],4096)
        for p in self.kept:self.assertEqual(p.read_text(),'private-sentinel')
    def test_unapplied_selection_not_consumed_by_windows_or_automatic_update(self):
        self.choose(3072)
        self.current['State']['Running']=False
        atomic_json(self.root/'bots'/PUBKEY/'state/runtime.json',{'status':'stopped'})
        with self.assertRaisesRegex(ToolError,'memory_change_pending'):
            self.u.apply(PUBKEY,self.u.preview(PUBKEY)['revision'],False,preserve_lifecycle=True)
        self.d.deploy({'agent':agent(),'provider_config':self.old['policy']})
        self.assertEqual(memory_settings.actual_mb(self.current),1536)
    def test_failed_apply_remains_retryable_no_new_selection(self):
        self.choose(3072);self.fail='up'
        with self.assertRaises(ToolError):self.apply()
        with self.assertRaisesRegex(ToolError,'memory_apply_recovery_required'):self.choose(1536)
        self.assertEqual(memory_settings.load(self.root)[PUBKEY]['committed_mb'],3072)
        self.fail=None;self.apply()
        self.assertFalse(self.u.preview(PUBKEY)['memory']['pending'])
        for p in self.kept:self.assertEqual(p.read_text(),'private-sentinel')
    def test_memory_and_swap_readback_required(self):
        self.choose(3072)
        run=self.d.run
        def bad(argv,*args,**kwargs):
            result=run(argv,*args,**kwargs)
            if 'up' in argv:self.current['HostConfig']['MemorySwap']=1536*1024**2
            return result
        self.d.run=bad
        with self.assertRaisesRegex(ToolError,'memory_limit_mismatch'):self.apply()
        status=self.u.preview(PUBKEY)['memory']
        self.assertTrue(status['pending']);self.assertTrue(status['recovery_required'])
        with self.assertRaisesRegex(ToolError,'memory_apply_recovery_required'):self.choose(4096)
        with self.assertRaisesRegex(ToolError,'memory_limit_mismatch'):
            self.d.deploy({'agent':agent(),'provider_config':self.old['policy']})
    def test_capacity_reserves_staged_increases_and_does_not_free_staged_decrease(self):
        other='f'*64
        registry=read_json(self.root/'registry.json');registry[other]=public_record(config(pub=other))
        atomic_json(self.root/'registry.json',registry)
        memory_settings.save(self.root,other,4096,1536)
        with self.assertRaisesRegex(ToolError,'aggregate_memory'):self.choose(2048)
        memory_settings.save(self.root,other,512,4096)
        with self.assertRaisesRegex(ToolError,'aggregate_memory'):self.choose(2048)
        self.assertFalse(any('stop' in a for a in self.commands))
    def test_invalid_inputs_and_unsafe_sidecar(self):
        for value in (True,False,'3072',3.5,0,511,16777217,None):
            with self.assertRaisesRegex(ToolError,'invalid_memory'):self.choose(value)
        p=self.root/'memory-settings.json';p.symlink_to(self.kept[0])
        with self.assertRaisesRegex(ToolError,'unsafe_memory'):self.u.preview(PUBKEY)
    def test_both_providers_ram_only(self):
        for command in ('codex-acp','claude-agent-acp'):
            self.current['State']['Running']=False
            a=agent(command);self.d.deploy({'agent':a,'provider_config':self.old['policy']})
            before=read_json(self.root/'bots'/PUBKEY/'config/config.json')
            self.choose(2048);self.apply()
            after=read_json(self.root/'bots'/PUBKEY/'config/config.json')
            self.assertEqual(after,memory_settings.with_memory(before,2048))
            self.assertEqual(self.current['HostConfig']['Memory'],2048*1024**2)
