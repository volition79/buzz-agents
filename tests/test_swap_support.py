"""SWAP-SUPPORT-01: deterministic host-policy/lifecycle tests, no real swapon.

Provider preservation is exercised through existing updater fixtures. Kernel
activation/security profiles and reboot ordering require disposable Docker VM.
"""
from copy import deepcopy
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from buzz_agents import memory_settings, swap_manager as manager
from buzz_agents import swap_pool
from buzz_agents.swap_pool import Pool, MIB, LABEL, POLICY, allocation
from buzz_agents.common import ToolError
from buzz_agents.host import compose_document, service_name, public_record
from buzz_agents.policy import atomic_json, read_json
import test_bot_update as fixtures
from helpers import PUBKEY, config


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)/'swap'
        self.root.mkdir(mode=0o700)
        self.active, self.commands, self.signatures = {}, [], {}
        self.free, self.total = 40*1024*MIB, 100*1024*MIB
        self.fail = None
        def run(argv):
            self.commands.append(argv)
            if argv[0] == 'stat':
                return 'ext2/ext3'
            if argv[0] == self.fail:
                raise ToolError('swap_activation_or_filesystem_denied')
            if argv[0] == 'blkid':return self.signatures.get(argv[-1], '')
            if argv[0] == 'mkswap':self.signatures[argv[-1]] = 'TYPE=swap\nUUID='+argv[argv.index('--uuid')+1]
            if argv[0] == 'swapon':
                self.active[argv[-1]] = {'bytes':Path(argv[-1]).stat().st_size-4096,'used':0}
            return ''
        self.pool = Pool(self.root,run,lambda:deepcopy(self.active),lambda _:(self.free,self.total))
        # Allocate sparse *fixture* files only. The product uses real reservation.
        self.alloc = patch('buzz_agents.swap_pool.os.posix_fallocate',side_effect=lambda fd,off,size:os.ftruncate(fd,size))
        self.alloc.start()
    def tearDown(self):
        self.alloc.stop()
        self.tmp.cleanup()
    def test_fixed_budget_reserve_and_existing_swap(self):
        self.active['/existing']={'bytes':8*1024*MIB,'used':MIB}
        result=self.pool.tick(6*1024)
        self.assertEqual(result['state'],'ready')
        self.assertEqual(result['managed_mb'],0)
        self.assertEqual(result['budget_mb'],12*1024)
        self.free=80*1024*MIB
        self.pool.tick(16*1024)
        self.assertEqual(read_json(self.root/'pool.json')['budget'],12*1024*MIB)
        self.assertFalse(any(a[0] in ('mkswap','swapon') and a[-1]=='/existing' for a in self.commands))
        self.free=5*1024*MIB
        result=self.pool.tick(64*1024)
        self.assertEqual(result['state'],'limited')
        self.assertEqual(result['managed_mb'],1024)
    def test_idempotent_activation_reboot_and_no_shrink(self):
        result=self.pool.tick(512)
        self.assertEqual(result['state'],'ready')
        self.assertEqual(sum(a[0]=='mkswap' for a in self.commands),1)
        self.pool.tick(512)
        self.assertEqual(sum(a[0]=='swapon' for a in self.commands),1)
        self.active.clear()  # simulated reboot; files/journal retained
        result=Pool(self.root,self.pool.run,self.pool.inventory,self.pool.space).tick(0)
        self.assertEqual(result['state'],'ready')
        self.assertEqual(sum(a[0]=='mkswap' for a in self.commands),1)
        self.assertEqual(sum(a[0]=='swapon' for a in self.commands),2)
        self.assertEqual((self.root/'chunk-0000').stat().st_size,512*MIB)
    def test_activation_failure_retries_without_reformat_or_growth(self):
        self.fail='swapon'
        with self.assertRaises(ToolError):self.pool.tick(512)
        with self.assertRaises(ToolError):self.pool.tick(512)
        self.assertEqual(len(list(self.root.glob('chunk-*'))),1)
        self.assertEqual(sum(a[0]=='mkswap' for a in self.commands),1)
        self.fail=None
        self.assertEqual(self.pool.tick(512)['state'],'ready')
    def test_uncertain_format_failure_never_reformats(self):
        self.fail='mkswap'
        with self.assertRaises(ToolError):self.pool.tick(512)
        before=(self.root/'chunk-0000').stat()
        self.fail=None
        with self.assertRaisesRegex(ToolError,'signature_changed'):self.pool.tick(512)
        self.assertEqual((self.root/'chunk-0000').stat().st_ino,before.st_ino)
        self.assertEqual(sum(a[0]=='mkswap' for a in self.commands),1)

    def test_disk_full_retry_finishes_same_inode(self):
        with patch('buzz_agents.swap_pool.os.posix_fallocate',side_effect=OSError(28,'disk full')):
            with self.assertRaises(OSError):self.pool.tick(512)
        before=(self.root/'chunk-0000').stat()
        self.free=5*1024*MIB
        with self.assertRaisesRegex(ToolError,'disk_reserve'):self.pool.tick(512)
        self.free=40*1024*MIB
        self.assertEqual(self.pool.tick(512)['state'],'ready')
        self.assertEqual((self.root/'chunk-0000').stat().st_ino,before.st_ino)
        self.assertEqual(sum(a[0]=='mkswap' for a in self.commands),1)
        self.assertEqual(len(list(self.root.glob('chunk-*'))),1)

    def test_format_success_lost_journal_save_never_reformats(self):
        save=self.pool.save
        def fail_ready(state):
            if state['shards'] and state['shards'][-1]['phase']=='ready':raise OSError('save failed')
            save(state)
        with patch.object(self.pool,'save',side_effect=fail_ready):
            with self.assertRaises(OSError):self.pool.tick(512)
        self.assertEqual(self.pool.tick(512)['state'],'ready')
        self.assertEqual(sum(a[0]=='mkswap' for a in self.commands),1)

    def test_probe_failure_after_lost_save_never_reformats(self):
        # Incident: formatted file + lost ready save + blkid exit 2/read error
        # formerly executed mkswap again and reported ready (dirty 23d49290).
        from subprocess import CompletedProcess, TimeoutExpired
        save=self.pool.save
        def fail_ready(state):
            if state['shards'] and state['shards'][-1]['phase']=='ready':raise OSError('save failed')
            save(state)
        with patch.object(self.pool,'save',side_effect=fail_ready):
            with self.assertRaises(OSError):self.pool.tick(512)
        original=self.pool.run
        def run(argv):
            return swap_pool.command(argv) if argv[0]=='blkid' else original(argv)
        self.pool.run=run
        cases=[(2,b'',b'Input/output error'),(2,b'',b''),(4,b'',b''),
               (8,b'',b''),(0,b'',b''),(0,b'garbage',b''),
               (0,b'TYPE=swap\nUUID=foreign',b'')]
        for code,out,err in cases:
            with self.subTest(code=code,out=out,err=err):
                with patch.object(swap_pool.subprocess,'run',return_value=CompletedProcess([],code,out,err)):
                    with self.assertRaises(ToolError):self.pool.tick(512)
                self.assertEqual(sum(a[0]=='mkswap' for a in self.commands),1)
                self.assertFalse(self.active)
                self.assertEqual(read_json(self.root/'pool.json')['shards'][0]['phase'],'formatting')
        for exc in (OSError('read failure'),TimeoutExpired('blkid',45)):
            with patch.object(swap_pool.subprocess,'run',side_effect=exc):
                with self.assertRaises(ToolError):self.pool.tick(512)
        self.pool.run=original
        self.assertEqual(self.pool.tick(512)['state'],'ready')
        self.assertEqual(sum(a[0]=='mkswap' for a in self.commands),1)

    def test_resume_rejects_foreign_signature_and_active_unformatted_file(self):
        self.fail='mkswap'
        with self.assertRaises(ToolError):self.pool.tick(512)
        self.fail=None
        path=str(self.root/'chunk-0000')
        self.signatures[path]='TYPE=swap\nUUID=foreign'
        with self.assertRaisesRegex(ToolError,'signature_changed'):self.pool.tick(512)
        self.signatures[path]=''
        self.active[path]={'bytes':512*MIB,'used':0}
        with self.assertRaisesRegex(ToolError,'signature_changed'):self.pool.tick(512)
        self.assertEqual(sum(a[0]=='mkswap' for a in self.commands),1)

    def test_legacy_uncertain_allocation_still_preserved(self):
        self.fail='mkswap'
        with self.assertRaises(ToolError):self.pool.tick(512)
        state=read_json(self.root/'pool.json')
        state['shards'][0].pop('uuid');state['shards'][0]['phase']='allocating'
        atomic_json(self.root/'pool.json',state)
        self.fail=None
        with self.assertRaisesRegex(ToolError,'allocation_interrupted'):self.pool.tick(512)
        self.assertEqual(sum(a[0]=='mkswap' for a in self.commands),1)

    def test_symlink_unknown_file_and_mutation_refused(self):
        victim=Path(self.tmp.name)/'victim';victim.write_text('preserve')
        (self.root/'chunk-0000').symlink_to(victim)
        with self.assertRaisesRegex(ToolError,'untracked'):self.pool.tick(512)
        self.assertEqual(victim.read_text(),'preserve')
        (self.root/'chunk-0000').unlink()
        self.pool.tick(512)
        (self.root/'chunk-0000').chmod(0o644)
        with self.assertRaisesRegex(ToolError,'file_changed'):self.pool.tick(512)
    def test_no_budget_until_first_bot_and_growth_area_limit(self):
        self.assertEqual(self.pool.tick(0)['managed_mb'],0)
        self.assertFalse((self.root/'pool.json').exists())
        for i in range(1,9):self.pool.tick(i*512)
        result=self.pool.tick(64*1024)
        self.assertEqual(result['state'],'limited')
        self.assertEqual(len(list(self.root.glob('chunk-*'))),8)
        self.assertLess(result['managed_mb'],result['budget_mb'])
    def test_external_area_limit_and_unsupported_fs(self):
        self.active={f'/external-{i}':{'bytes':MIB,'used':0} for i in range(24)}
        self.assertEqual(self.pool.tick(512)['state'],'limited')
        self.assertFalse(list(self.root.glob('chunk-*')))
        self.pool.run=lambda _: 'btrfs'
        with self.assertRaisesRegex(ToolError,'filesystem_unsupported'):self.pool.tick(512)
    def test_allocation_never_exceeds_any_budget(self):
        for budget in (0,10*MIB,100*MIB):
            for used in (0,10*MIB,110*MIB):
                for free in (0,6*1024*MIB,50*1024*MIB):
                    value=allocation(budget,used,free,100*1024*MIB,200*MIB,0)
                    self.assertLessEqual(value,max(0,budget-used))
                    self.assertLessEqual(value,max(0,free-10*1024*MIB))
    def test_startup_lock_contention_does_not_publish_error(self):
        class EndLoop(Exception):pass
        atomic_json(self.root/'request.json',{'target_mb':512})
        writes=[]
        def sleep(seconds):
            if seconds != 1:raise EndLoop()
        with patch.object(swap_pool,'ROOT',self.root), patch.object(swap_pool.Pool,'tick',
                side_effect=[BlockingIOError(),{'state':'ready'}]), \
                patch.object(swap_pool,'atomic_json',side_effect=lambda path,value:writes.append(value)), \
                patch.object(swap_pool.time,'sleep',side_effect=sleep):
            with self.assertRaises(EndLoop):swap_pool.main()
        self.assertEqual(writes,[{'state':'ready'}])


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'swap'
        self.path=patch.object(manager,'ROOT',self.root);self.path.start()
        self.image='sha256:'+'a'*64
        self.current=None;self.commands=[];self.fail=False
        self.broker={'Image':self.image,'Config':{'Labels':{'com.docker.compose.service':'broker'}},
                     'Mounts':[{'Type':'bind','Source':str(self.root.parent),'Destination':str(self.root.parent)}]}
        def run(argv,**kw):
            self.commands.append(argv)
            if argv[:2]==['docker','info']:return json.dumps({'OSType':'linux','SwapLimit':True,'SecurityOptions':[]}).encode()
            if argv[:2]==['docker','inspect']:return json.dumps([self.broker]).encode()
            if argv[:2]==['docker','create']:
                self.current={'Id':'b'*64,'Image':argv[-3],'Config':{'Labels':{manager.OWNER:'1',manager.INTENT:argv[argv.index(manager.OWNER+'=1')+2].split('=',1)[1]}},
                              'Mounts':[{'Type':'bind','Source':str(self.root),'Destination':str(self.root)}],
                              'State':{'Running':False}}
                return ('b'*64).encode()
            if argv[:2]==['docker','start']:self.current['State']['Running']=True
            if argv[:2]==['docker','stop']:self.current['State']['Running']=False
            if argv[:2]==['docker','rm']:self.current=None
            return b''
        self.run=run
    def tearDown(self):self.path.stop();self.tmp.cleanup()
    def reconcile(self):manager.reconcile(self.run,lambda _:deepcopy(self.current),'short-broker-id')
    def test_self_inspect_and_minimal_helper_authority(self):
        self.reconcile();self.reconcile()
        calls=[c for c in self.commands if c[:2]==['docker','create']]
        self.assertEqual(len(calls),1)
        argv=calls[0]
        self.assertNotIn('--privileged',argv);self.assertNotIn('--pid',argv)
        self.assertNotIn('seccomp=unconfined',argv)
        self.assertIn('--cap-add',argv);self.assertEqual(argv[argv.index('--cap-add')+1],'SYS_ADMIN')
        self.assertEqual(sum(a=='--mount' for a in argv),1)
        self.assertIn('seccomp=/app/buzz_agents/swap-seccomp.json',argv)
        self.assertNotIn('/var/run/docker.sock',' '.join(argv))
        self.assertTrue(any(c[:2]==['docker','inspect'] for c in self.commands))
    def test_create_id_save_failure_recovers_without_duplicate(self):
        save=manager.atomic_json
        def fail_id(path,value):
            if 'id' in value:raise OSError('save failed')
            save(path,value)
        with patch.object(manager,'atomic_json',side_effect=fail_id):
            with self.assertRaises(OSError):self.reconcile()
        ident=self.current['Id']
        self.reconcile();self.reconcile()
        self.assertTrue(self.current['State']['Running'])
        self.assertEqual(self.current['Id'],ident)
        self.assertEqual(sum(c[:2]==['docker','create'] for c in self.commands),1)

    def test_lost_create_response_recovers_using_intent(self):
        run=self.run
        def lost(argv,**kw):
            result=run(argv,**kw)
            if argv[:2]==['docker','create']:raise ToolError('timeout')
            return result
        self.run=lost
        with self.assertRaises(ToolError):self.reconcile()
        self.run=run
        self.reconcile()
        self.assertTrue(self.current['State']['Running'])
        self.assertEqual(sum(c[:2]==['docker','create'] for c in self.commands),1)

    def test_delayed_create_keeps_intent_across_upgrade(self):
        run=self.run
        calls=[]
        def delayed(argv,**kw):
            if argv[:2]==['docker','create']:
                calls.append(argv)
                raise ToolError('timeout')
            return run(argv,**kw)
        self.run=delayed
        with self.assertRaises(ToolError):self.reconcile()
        first=read_json(self.root/'helper.json')['creating']
        self.broker['Image']='sha256:'+'e'*64
        with self.assertRaises(ToolError):self.reconcile()
        self.assertEqual(read_json(self.root/'helper.json')['creating'],first)
        self.assertEqual(calls[0],calls[1])
        # Original daemon request becomes visible only after the retry.
        run(calls[0])
        self.run=run
        self.reconcile()
        self.assertTrue(self.current['State']['Running'])
        self.assertEqual(self.current['Image'],self.broker['Image'])

    def test_unpersisted_intent_never_creates_and_foreign_token_never_adopted(self):
        with patch.object(manager,'atomic_json',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.reconcile()
        self.assertIsNone(self.current)
        run=self.run
        def lost(argv,**kw):
            result=run(argv,**kw)
            if argv[:2]==['docker','create']:raise ToolError('timeout')
            return result
        self.run=lost
        with self.assertRaises(ToolError):self.reconcile()
        self.run=run
        self.current['Config']['Labels'][manager.INTENT]='c'*64
        with self.assertRaisesRegex(ToolError,'name_collision'):self.reconcile()
        self.assertFalse(self.current['State']['Running'])
        self.assertFalse(any(c[:2]==['docker','rm'] for c in self.commands))

    def test_foreign_collision_never_stopped(self):
        self.reconcile();self.current['Id']='c'*64
        with self.assertRaisesRegex(ToolError,'name_collision'):self.reconcile()
        self.assertFalse(any(c[:2]==['docker','stop'] for c in self.commands))
    def test_image_upgrade_waits_for_allocation_lock(self):
        self.reconcile();self.broker['Image']='sha256:'+'e'*64
        with open(self.root/'pool.lock','w') as fd:
            fcntl.flock(fd,fcntl.LOCK_EX)
            with self.assertRaises(BlockingIOError):self.reconcile()
        self.assertFalse(any(c[:2]==['docker','stop'] for c in self.commands))
        self.reconcile()
        self.assertTrue(any(c[:2]==['docker','stop'] for c in self.commands))
    def test_status_staleness_and_private_filter(self):
        self.reconcile()
        atomic_json(self.root/'status.json',dict(state='ready',total_mb=200,checked_at=int(time.time()),secret='not-public'))
        s=manager.public(self.root.parent);self.assertEqual(s['state'],'ready');self.assertNotIn('secret',s)
        atomic_json(self.root/'status.json',dict(state='ready',total_mb=200,checked_at=1))
        self.assertEqual(manager.public(self.root.parent)['state'],'pending')
    def test_controller_does_not_write_through_rejected_directory(self):
        class EndLoop(Exception):pass
        control=Path(self.tmp.name)/'control';control.mkdir()
        atomic_json(control/'settings.json',{'configured':True})
        victim=Path(self.tmp.name)/'victim';victim.mkdir(mode=0o700)
        self.root.symlink_to(victim,target_is_directory=True)
        broker=SimpleNamespace(control=control,root=self.root.parent,contract=None)
        with patch.object(manager.time,'sleep',side_effect=EndLoop):
            with self.assertRaises(EndLoop):manager.loop(broker,self.run,lambda _:None)
        self.assertFalse(list(victim.iterdir()))
        self.assertFalse(self.commands)
    def test_controller_waits_for_coherent_management_contract(self):
        class EndLoop(Exception):pass
        control=Path(self.tmp.name)/'control';control.mkdir()
        atomic_json(control/'settings.json',{'configured':True})
        def reject():raise ToolError('management_contract_mismatch')
        broker=SimpleNamespace(control=control,root=self.root.parent,contract={'release':'new'},
                               rollout=SimpleNamespace(verify_management=reject))
        with patch.object(manager.time,'sleep',side_effect=EndLoop):
            with self.assertRaises(EndLoop):manager.loop(broker,self.run,lambda _:None)
        self.assertFalse(self.commands)
        self.assertEqual(manager.public(self.root.parent)['state'],'attention')


class MigrationTests(unittest.TestCase):
    normalizer=fixtures.UpdateTests.normalizer
    setUp=fixtures.UpdateTests.setUp
    tearDown=fixtures.UpdateTests.tearDown
    apply=fixtures.UpdateTests.apply
    def test_unmarked_legacy_migrates_but_bad_marked_limits_do_not(self):
        self.current['Config']['Labels'].pop(LABEL)
        self.current['HostConfig']['MemorySwap']=self.old['memory_mb']*MIB
        self.assertTrue(memory_settings.compatible_limits(self.current,self.old['memory_mb']))
        status=self.u.preview(PUBKEY)['memory']
        self.assertFalse(status['recovery_required']);self.assertTrue(status['swap_pending'])
        self.u.save_memory(PUBKEY,self.u.preview(PUBKEY)['revision'],2048)
        self.apply()
        self.assertEqual(self.current['HostConfig']['MemorySwap'],8192*MIB)
        self.assertEqual(self.current['Config']['Labels'][LABEL],POLICY)
        self.current['HostConfig']['MemorySwap']=2048*MIB
        with self.assertRaisesRegex(ToolError,'memory_apply_recovery_required'):
            self.u.save_memory(PUBKEY,self.u.preview(PUBKEY)['revision'],3072)
        for p in self.kept:self.assertEqual(p.read_text(),'private-sentinel')
    def test_other_bot_generated_limits_are_preserved(self):
        other='f'*64;c=config(pub=other)
        reg={PUBKEY:public_record(self.old),other:public_record(c)}
        old={'services':{service_name(other):{'image':'old-runtime','memswap_limit':'1536m','labels':{}}}}
        doc=compose_document(reg,self.settings,old,updating_pubkey=PUBKEY)
        self.assertEqual(doc['services'][service_name(other)]['memswap_limit'],'1536m')
        self.assertNotIn(LABEL,doc['services'][service_name(other)]['labels'])
        self.assertEqual(doc['services'][service_name(PUBKEY)]['memswap_limit'],'6144m')
    def test_no_sidecar_bad_post_deploy_swap_is_failure(self):
        run=self.d.run
        def bad(argv,*a,**kw):
            result=run(argv,*a,**kw)
            if 'up' in argv:self.current['HostConfig']['MemorySwap']=self.old['memory_mb']*MIB
            return result
        self.d.run=bad
        with self.assertRaisesRegex(ToolError,'deployment_memory_limit_mismatch'):self.apply()
    def test_seccomp_only_adds_swapon_without_sysadmin_expansion(self):
        profile=json.loads((Path(__file__).parents[1]/'buzz_agents/swap-seccomp.json').read_text())
        self.assertEqual(profile['defaultAction'],'SCMP_ACT_ERRNO')
        allowed={name for r in profile['syscalls'] if r['action']=='SCMP_ACT_ALLOW' for name in r['names']}
        self.assertIn('swapon',allowed);self.assertNotIn('swapoff',allowed)
        self.assertNotIn('mount',allowed);self.assertNotIn('setns',allowed)
        for rule in profile['syscalls']:
            if set(rule['names']) & {'clone','clone3'}:
                self.assertNotIn('CAP_SYS_ADMIN',rule.get('excludes',{}).get('caps',[]))
