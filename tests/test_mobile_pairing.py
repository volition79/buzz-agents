"""Regression: Hostinger relay advertises pairing but /pair returns HTTP 404.

Local replay covers discovery -> Compose -> status, not Android identity transfer.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from buzz_agents import mobile_pairing as mobile, portal_compose as compose
from buzz_agents.portal_broker import Broker
from buzz_agents.common import ToolError
from test_portal_bootstrap import fixture


def inputs():
    items = fixture()
    items[2]['Config']['Labels'].update(items[3]['Config']['Labels'])
    items.pop(3)
    return items, {'relay': 'wss://buzz.srv12345.hstgr.cloud', 'owner': 'e'*64}, {
        'project': 'fixture-setup', 'upstream': 'fixture-setup-portal-1'}


def deployed(data, path):
    spec = mobile.service(data)
    return {'Id': '8'*64, 'Name': '/'+data['name'], 'Image': data['image'],
            'State': {'Running': True}, 'Mounts': [],
            'Config': {'Entrypoint': spec['entrypoint'], 'Cmd': [], 'User': spec['user'],
                       'Env': ['BUZZ_PAIR_RELAY_BIND_ADDR=0.0.0.0:5000'],
                       'Labels': {**spec['labels'], 'com.docker.compose.project': data['project'],
                                  'com.docker.compose.service': mobile.SERVICE,
                                  'com.docker.compose.project.config_files': str(path)}},
            'HostConfig': {'ReadonlyRootfs': True, 'CapDrop': ['ALL'], 'SecurityOpt': spec['security_opt'],
                           'Memory': 128*1024*1024, 'PidsLimit': 64, 'NanoCpus': 250000000,
                           'RestartPolicy': {'Name': 'unless-stopped'}},
            'NetworkSettings': {'Networks': {data['network']: {}}}}


class MobileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'docker-compose.yml'
        self.original = {'services': {'broker': {'image': 'broker'},
                         'portal': {'image': 'portal', 'environment': {'KEEP': '${KEEP:-a$$b}'}}},
                         'volumes': {'control': None}}
        self.path.write_text(json.dumps(self.original))
        self.items, self.settings, self.bootstrap = inputs()
        self.data = mobile.plan(self.items, self.settings, self.bootstrap)
        self.calls = []
        self.current = None

    def command(self, argv, **kwargs):
        self.calls.append(argv)
        if 'config' in argv:
            return Path(argv[argv.index('-f')+1]).read_bytes()
        if argv[:3] == ['docker', 'image', 'inspect']:
            return json.dumps([{'Id': self.data['image'], 'Config': {'Labels': {
                'org.opencontainers.image.source': 'https://github.com/block/buzz'}}}]).encode()
        if 'up' in argv:
            self.current = deployed(self.data, self.path)
        return b''

    def run_reconcile(self, reachable=None):
        with patch.object(mobile, 'execute', self.command), \
                patch.object(compose, 'execute', self.command), \
                patch.object(mobile, 'inspect_container', side_effect=lambda _: self.current), \
                patch.object(mobile, 'reachable', side_effect=reachable or (lambda *_: self.current is not None)):
            return mobile._reconcile(self.items, self.path, self.data)

    def test_404_installs_service_and_preserves_ai_configuration(self):
        self.assertEqual(self.run_reconcile(), {'state': 'available'})
        result = json.loads(self.path.read_text())
        for key, value in self.original['services'].items():
            self.assertEqual(result['services'][key], value)
        self.assertEqual(result['volumes'], self.original['volumes'])
        service = result['services']['mobile-pairing']
        self.assertEqual(service['image'], self.items[2]['Image'])
        self.assertEqual(service['entrypoint'], ['/usr/local/bin/buzz-pair-relay'])
        self.assertNotIn('ports', service)
        self.assertNotIn('volumes', service)
        self.assertIn(['up','-d','--no-deps','--pull','never','mobile-pairing'], [a[-6:] for a in self.calls])
        self.assertFalse(any('rm' in a or '--remove-orphans' in a for a in self.calls))

    def test_per_customer_routing_no_fixed_server_network_or_tls(self):
        items, settings, bootstrap = inputs()
        settings['relay'] = 'wss://my-relay.srv98765.hstgr.cloud'
        items[2]['Config']['Labels']['traefik.http.routers.relay.rule'] = 'Host(`my-relay.srv98765.hstgr.cloud`)'
        for c in items:
            c['NetworkSettings']['Networks'] = {'customer-network': {}}
        data = mobile.plan(items, settings, bootstrap)
        self.assertEqual(data['network'], 'customer-network')
        spec = mobile.service(data)
        self.assertNotEqual(data['name'], self.data['name'])
        self.assertIn('secure-custom', spec['labels'].values())
        self.assertIn('acme-custom', spec['labels'].values())
        self.assertNotIn('srv2042329', json.dumps(spec))

    def test_ambiguous_relay_and_nonroot_url_refused(self):
        with self.assertRaisesRegex(ToolError, 'ambiguous'):
            mobile.plan(self.items+[copy.deepcopy(self.items[2])], self.settings, self.bootstrap)
        for url in ('ws://relay.example', 'wss://relay.example/other', 'wss://relay.example:444'):
            with self.assertRaises(ToolError):
                mobile.plan(self.items, dict(self.settings, relay=url), self.bootstrap)

    def test_existing_public_endpoint_reused_without_docker_mutation(self):
        original = self.path.read_bytes()
        self.assertEqual(self.run_reconcile(lambda *_: True), {'state': 'available'})
        self.assertEqual(self.calls, [])
        self.assertEqual(self.path.read_bytes(), original)

    def test_another_installation_healthy_reused_unhealthy_preserved(self):
        self.current = deployed(self.data, Path('/other/compose.yml'))
        self.assertEqual(self.run_reconcile(lambda *_: True), {'state': 'available'})
        with self.assertRaisesRegex(ToolError, 'container_preserved'):
            self.run_reconcile(lambda *_: False)
        self.assertEqual(self.calls, [])

    def test_stopped_external_route_is_not_shadowed(self):
        external = deployed(self.data, Path('/other/compose.yml'))
        external['State']['Running'] = False
        external['Name'] = '/manual-pairing'
        self.items.append(external)
        with self.assertRaisesRegex(ToolError, 'route_preserved'):
            self.run_reconcile(lambda *_: False)
        self.assertEqual(self.calls, [])

    def test_restart_reinstall_repairs_own_declaration_no_duplicate(self):
        self.run_reconcile()
        first = self.path.read_bytes()
        self.run_reconcile()
        self.assertEqual(first, self.path.read_bytes())
        # URL import may replace Compose while old sidecar remains running.
        self.path.write_text(json.dumps(self.original))
        self.run_reconcile()
        self.assertEqual(first, self.path.read_bytes())
        self.current['State']['Running'] = False
        self.run_reconcile(lambda *_: False if not self.current['State']['Running'] else True)
        self.assertTrue(self.current['State']['Running'])

    def test_compose_expanded_network_and_omitted_empty_command_restart(self):
        self.run_reconcile()
        model = json.loads(self.path.read_text())
        service = model['services']['mobile-pairing']
        service.pop('command')
        service['networks'] = {'buzz_mobile_pairing': None}
        self.path.write_text(json.dumps(model))
        self.assertEqual(self.run_reconcile()['state'], 'available')
        model['services']['mobile-pairing']['privileged'] = True
        self.path.write_text(json.dumps(model))
        with self.assertRaisesRegex(ToolError, 'service_preserved'):
            self.run_reconcile()

    def test_foreign_service_and_network_preserved(self):
        for section, key, value in [('services', 'mobile-pairing', {'image': 'other'}),
                                    ('networks', 'buzz_mobile_pairing', {'name': 'other'})]:
            model = copy.deepcopy(self.original)
            model.setdefault(section, {})[key] = value
            self.path.write_text(json.dumps(model))
            original = self.path.read_bytes()
            with self.assertRaises(ToolError): self.run_reconcile()
            self.assertEqual(self.path.read_bytes(), original)

    def test_missing_pairing_binary_does_not_write_compose(self):
        real = self.command
        def command(argv, **kwargs):
            if argv[:2] == ['docker', 'exec']: raise ToolError('host_command_failed')
            return real(argv, **kwargs)
        self.command = command
        original = self.path.read_bytes()
        with self.assertRaises(ToolError): self.run_reconcile()
        self.assertEqual(original, self.path.read_bytes())

    def test_failed_compose_up_keeps_recoverable_declaration(self):
        real = self.command
        def command(argv, **kwargs):
            if 'up' in argv: raise ToolError('host_command_failed')
            return real(argv, **kwargs)
        self.command = command
        with self.assertRaises(ToolError): self.run_reconcile()
        self.assertIn('mobile-pairing', json.loads(self.path.read_text())['services'])
        self.command = real
        self.assertEqual(self.run_reconcile(), {'state': 'available'})

    def test_no_claim_of_ready_when_public_probe_still_fails(self):
        with patch.object(mobile.time, 'sleep'):
            self.assertEqual(self.run_reconcile(lambda *_: False), {'state': 'pending'})

    def test_owned_label_does_not_authorize_unsafe_container(self):
        self.current = deployed(self.data, self.path)
        self.current['Mounts'] = [{'Source': '/var/run/docker.sock'}]
        with self.assertRaisesRegex(ToolError, 'container_preserved'):
            self.run_reconcile(lambda *_: False)

    def test_broker_failure_sanitized_and_nonfatal_status(self):
        root = Path(self.tmp.name)
        (root/'settings.json').write_text(json.dumps(self.settings))
        (root/'bootstrap.json').write_text(json.dumps(self.bootstrap))
        broker = Broker('fixture/runtime', root=root, control=root)
        with patch.object(mobile, 'reconcile', side_effect=RuntimeError('private-secret')):
            broker.reconcile_mobile_pairing(self.items)
        result = json.loads((root/'mobile-pairing.json').read_text())
        self.assertEqual(result['state'], 'pending')
        self.assertNotIn('private-secret', json.dumps(result))
        with patch.object(mobile, 'reconcile', return_value={'state':'available'}):
            broker.reconcile_mobile_pairing(self.items)
        with patch('buzz_agents.portal_broker.bot_records', return_value=[]):
            self.assertEqual(broker.dispatch({'op':'status'})['mobile_pairing']['state'], 'available')

    def test_first_configure_triggers_optional_mobile_setup(self):
        root = Path(self.tmp.name)
        (root/'bootstrap.json').write_text(json.dumps(self.bootstrap))
        broker = Broker('fixture/runtime', root=root, control=root)
        image = [{'Id':'sha256:'+'a'*64, 'Config':{'Labels':{'org.opencontainers.image.title':'buzz-agents'}}}]
        def execute(argv):
            if argv[1:3] == ['image','inspect']: return json.dumps(image).encode()
            if argv[1] == 'container': return b'a b'
            return json.dumps(self.items).encode()
        with patch('buzz_agents.portal_broker.execute', execute), \
                patch.object(mobile, 'reconcile', side_effect=ToolError('mobile_pairing_binary_missing')) as check:
            self.assertTrue(broker.dispatch({'op':'configure', **self.settings})['ok'])
            self.assertEqual(check.call_count, 1)
        self.assertEqual(json.loads((root/'settings.json').read_text())['relay'], self.settings['relay'])

    def test_custom_pairing_url_preserved(self):
        self.items[2]['Config']['Env'].append('BUZZ_PAIRING_RELAY_URL=wss://pair.example')
        with self.assertRaisesRegex(ToolError, 'custom_pairing_preserved'):
            mobile.plan(self.items, self.settings, self.bootstrap)

    def test_setup_route_reconciliation_preserves_mobile_service(self):
        from test_portal_compose import ComposeRouteTests
        case = ComposeRouteTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        model = copy.deepcopy(case.original)
        model['services']['mobile-pairing'] = mobile.service(self.data)
        case.path.write_text(json.dumps(model))
        with patch.object(compose, 'execute', case.run_command), \
                patch.object(compose, 'inspect_container', side_effect=[None,None,{'Id':'new','State':{'Running':True}}]), \
                patch.object(compose, 'check_current'):
            compose._reconcile(case.path, case.data)
        self.assertEqual(json.loads(case.path.read_text())['services']['mobile-pairing'], model['services']['mobile-pairing'])


if __name__ == '__main__':
    unittest.main()
