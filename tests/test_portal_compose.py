"""Migration rollback and preservation boundaries; actual Compose runs in CI."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from buzz_agents import portal_compose as pc
from buzz_agents import portal_bootstrap as boot
from buzz_agents.common import ToolError
from test_portal_bootstrap import fixture


class ComposeRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'docker-compose.yml'
        self.original = {'name': 'fixture-setup', 'services': {
            'broker': {'image': 'test'}, 'portal': {'environment': {'KEEP': '${KEEP:-a$$b}'}}}}
        self.path.write_text(json.dumps(self.original))
        self.bytes = self.path.read_bytes()
        self.data = boot.plan(fixture(), 'a'*12)
        self.calls = []

    def run_command(self, argv):
        self.calls.append(argv)
        if 'config' in argv:
            return Path(argv[argv.index('-f')+1]).read_bytes()
        return b''

    def test_route_keeps_pullable_pinned_portal_reference(self):
        ref='ghcr.io/example/portal@sha256:'+'f'*64
        self.assertEqual(pc.service(self.data,ref)['image'],ref)
        self.assertNotEqual(pc.service(self.data,ref)['image'],self.data['image'])

    def test_upgraded_portal_uses_retained_proxy_digest_only_after_identity_check(self):
        items = fixture()
        portal_ref = 'ghcr.io/example/portal@sha256:'+'a'*64
        route_ref = 'ghcr.io/example/portal@sha256:'+'b'*64
        items[1]['Image'] = 'sha256:'+'c'*64
        items[1]['Config']['Image'] = portal_ref
        route = {'Config': {'Image': route_ref}}
        with patch.object(pc, 'project_file', return_value=self.path), \
             patch.object(pc, 'inspect_container', return_value=route), \
             patch.object(pc, 'check_current') as check, \
             patch.object(pc, '_reconcile') as reconcile:
            pc.reconcile(items, 'a'*12, self.data)
            check.assert_called_once_with(route, self.data, self.path)
            reconcile.assert_called_once_with(self.path, self.data, route_ref, portal_ref)
        with patch.object(pc, 'project_file', return_value=self.path), \
             patch.object(pc, 'inspect_container', return_value=route):
            with self.assertRaises(ToolError): pc.reconcile(items, 'a'*12, self.data)

    def test_preservation_rejects_changed_old_service_and_volume(self):
        for changed in ({'services': {'portal': {'image': 'other'}}},
                        {'services': {}, 'volumes': {'portal': {'name': 'other'}}}):
            with self.assertRaisesRegex(ToolError, 'would_change'):
                pc.preserved(self.original, changed)
        expected = copy.deepcopy(self.original)
        expected['services']['setup-route'] = pc.service(self.data)
        pc.preserved(self.original, expected)

    def test_variable_expressions_preserved_and_real_compose_used(self):
        created = {'Id': 'new', 'State': {'Running': True}}
        with patch.object(pc, 'execute', self.run_command), \
                patch.object(pc, 'inspect_container', side_effect=[None, None, created]), \
                patch.object(pc, 'check_current'):
            pc._reconcile(self.path, self.data)
        result = json.loads(self.path.read_bytes())
        self.assertEqual(result['services']['portal'], self.original['services']['portal'])
        labels = result['services']['setup-route']['labels']
        self.assertFalse(any(k.startswith('com.docker.compose.') for k in labels))
        self.assertEqual(labels['traefik.http.routers.fixture-setup.rule'], 'Host(`'+self.data['hostname']+'`)')
        self.assertTrue(any('--no-interpolate' in call and '--no-env-resolution' in call for call in self.calls))
        self.assertIn(['up','-d','--no-deps','--pull','never','setup-route'], [call[-6:] for call in self.calls])

    def test_failed_migration_restores_legacy_and_compose(self):
        legacy = {'Id': 'old', 'State': {'Running': True}, 'Config': {'Labels': {'io.buzz-agents.managed': boot.MANAGED}}}
        def run(argv):
            if 'up' in argv:
                raise ToolError('fixture_create_failed')
            return self.run_command(argv)
        with patch.object(pc, 'execute', run), \
                patch.object(pc, 'inspect_container', side_effect=[legacy, None, None]), \
                patch.object(boot, 'check_route'):
            with self.assertRaisesRegex(ToolError, 'fixture_create_failed'):
                pc._reconcile(self.path, self.data)
        self.assertEqual(self.path.read_bytes(), self.bytes)
        self.assertIn(['docker','rename','old',self.data['route_name']], self.calls)
        self.assertIn(['docker','start','old'], self.calls)
        self.assertFalse(any(call[1]=='rm' for call in self.calls))

    def test_failed_new_readiness_removes_only_owned_replacement_and_restores_legacy(self):
        legacy={'Id':'old','State':{'Running':True},'Config':{'Labels':{'io.buzz-agents.managed':boot.MANAGED}}}
        created={'Id':'new','Image':self.data['image'],'State':{'Running':False},'Config':{'Labels':{
            **pc.service(self.data)['labels'], 'com.docker.compose.project':self.data['project'],
            'com.docker.compose.service':'setup-route','com.docker.compose.config-hash':'fixture',
            'com.docker.compose.project.config_files':str(self.path)}}}
        with patch.object(pc,'execute',self.run_command),patch.object(pc,'inspect_container',side_effect=[legacy,None,created,created]),patch.object(boot,'check_route'):
            with self.assertRaisesRegex(ToolError,'not_running'):pc._reconcile(self.path,self.data)
        self.assertIn(['docker','rm','-f','new'],self.calls)
        self.assertIn(['docker','start','old'],self.calls)
        self.assertEqual(self.path.read_bytes(),self.bytes)

    def test_cleanup_failure_keeps_committed_new_route(self):
        legacy = {'Id':'old','State':{'Running':True},'Config':{'Labels':{'io.buzz-agents.managed':boot.MANAGED}}}
        created = {'Id':'new','State':{'Running':True}}
        def run(argv):
            self.calls.append(argv)
            if argv == ['docker','rm','old']: raise ToolError('fixture_lost_cleanup_response')
            if 'config' in argv: return Path(argv[argv.index('-f')+1]).read_bytes()
            return b''
        with patch.object(pc,'execute',run), patch.object(pc,'inspect_container',side_effect=[legacy,None,created]), patch.object(boot,'check_route'), patch.object(pc,'check_current'):
            self.assertEqual(pc._reconcile(self.path,self.data),created)
        self.assertNotIn(['docker','rm','-f','new'], self.calls)
        self.assertNotIn(['docker','rename','old',self.data['route_name']],self.calls)
        self.assertIn('setup-route',json.loads(self.path.read_bytes())['services'])

    def test_crash_recovery_restores_running_state_before_retry(self):
        backup={'Id':'old','State':{'Running':False},'Config':{'Labels':{'io.buzz-agents.managed':boot.MANAGED}}}
        recovered=copy.deepcopy(backup); recovered['State']['Running']=True
        (self.path.parent/'.buzz-route-transaction.json').write_text(json.dumps({'legacy_id':'old','was_running':True,'fingerprint':self.data['fingerprint']}))
        def run(argv):
            if 'up' in argv: raise ToolError('fixture_failed')
            return self.run_command(argv)
        with patch.object(pc,'execute',run),patch.object(pc,'inspect_container',side_effect=[None,backup,recovered,None]),patch.object(boot,'check_route'):
            with self.assertRaisesRegex(ToolError,'fixture_failed'): pc._reconcile(self.path,self.data)
        self.assertEqual(self.calls.count(['docker','start','old']),2)

    def test_crash_between_stop_and_rename_preserves_original_running_state(self):
        legacy={'Id':'old','State':{'Running':False},'Config':{'Labels':{'io.buzz-agents.managed':boot.MANAGED}}}
        (self.path.parent/'.buzz-route-transaction.json').write_text(json.dumps({'legacy_id':'old','was_running':True,'fingerprint':self.data['fingerprint']}))
        def run(argv):
            if 'up' in argv: raise ToolError('fixture_failed')
            return self.run_command(argv)
        with patch.object(pc,'execute',run),patch.object(pc,'inspect_container',side_effect=[legacy,None,None]),patch.object(boot,'check_route'):
            with self.assertRaisesRegex(ToolError,'fixture_failed'): pc._reconcile(self.path,self.data)
        self.assertIn(['docker','start','old'],self.calls)
        self.assertFalse((self.path.parent/'.buzz-route-transaction.json').exists())

    def test_concurrent_edit_is_never_rolled_back(self):
        def run(argv):
            if 'up' in argv:
                self.path.write_text('user-edited')
                raise ToolError('fixture_failed')
            return self.run_command(argv)
        with patch.object(pc, 'execute', run), patch.object(pc, 'inspect_container', return_value=None):
            with self.assertRaises(ToolError): pc._reconcile(self.path, self.data)
        self.assertEqual(self.path.read_text(), 'user-edited')

    def test_stopped_legacy_remains_stopped_on_failed_migration(self):
        legacy = {'Id': 'old', 'State': {'Running': False}, 'Config': {'Labels': {'io.buzz-agents.managed': boot.MANAGED}}}
        def run(argv):
            if 'up' in argv: raise ToolError('fixture_failed')
            return self.run_command(argv)
        with patch.object(pc, 'execute', run), patch.object(pc, 'inspect_container', side_effect=[legacy,None,None]), patch.object(boot,'check_route'):
            with self.assertRaises(ToolError): pc._reconcile(self.path, self.data)
        self.assertFalse(any(call[1] in ('start','stop') for call in self.calls))

    def test_foreign_route_fails_before_write_or_stop(self):
        with patch.object(pc, 'execute', self.run_command), patch.object(pc, 'inspect_container', side_effect=[{'Id':'foreign'},None]):
            with self.assertRaises(ToolError): pc._reconcile(self.path, self.data)
        self.assertEqual(self.path.read_bytes(), self.bytes)
        self.assertFalse(any(call[1] in ('stop','rename','rm') for call in self.calls))

    def test_compare_before_write_and_symlink_refused(self):
        with self.assertRaisesRegex(ToolError,'concurrently'):
            pc.replace_if_unchanged(self.path,b'wrong',b'replacement')
        link = self.path.parent/'link'; link.symlink_to(self.path)
        with self.assertRaisesRegex(ToolError,'concurrently'):
            pc.replace_if_unchanged(link,self.bytes,b'replacement')
        self.assertEqual(self.path.read_bytes(), self.bytes)

    def test_foreign_multiple_and_temporary_working_paths_refused(self):
        for path in ('/docker/foreign/docker-compose.yml','/tmp/hstgr-x/docker-compose.yml','/docker/fixture-setup/docker-compose.yml,/tmp/other.yml'):
            containers=fixture()
            containers[0]['Config']['Labels']['com.docker.compose.project.config_files']=path
            with self.assertRaisesRegex(ToolError,'requires_review'):
                pc.project_file(containers,'a'*12,'fixture-setup')


if __name__ == '__main__': unittest.main()
