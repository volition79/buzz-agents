"""Real local HTTP + privileged boundary fixtures. Never call the actual VPS."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

from buzz_agents.common import ToolError
from buzz_agents.portal import Portal, Server, origin_url, digest
from buzz_agents.portal_broker import Broker, LoginSessions, discover_relays
from buzz_agents import portal_auth
from helpers import OWNER, PUBKEY, RELAY


class PortalHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'Buzz-VPS-Connect.exe').write_bytes(b'MZ-test-executable')
        self.calls = []
        def rpc(value):
            self.calls.append(value)
            if value['op'] == 'deploy':
                return {'ok': True, 'agent_id': 'buzz-native-'+PUBKEY[:20]}
            return {'ok': True, 'configured': False, 'bots': []}
        self.now = [1000.0]
        self.app = Portal(self.root/'portal', 'http://127.0.0.1', rpc=rpc,
                          clock=lambda: self.now[0], local=True, artifacts=self.root)
        self.server = Server(('127.0.0.1', 0), self.app)
        self.app.url = self.url = 'http://127.0.0.1:'+str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = ''

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.tmp.cleanup()

    def call(self, path, data=None, *, cookie=None, origin=True, headers=None):
        h = {'Cookie': self.cookie if cookie is None else cookie}
        if origin: h['Origin'] = self.url if origin is True else origin
        if headers: h.update(headers)
        if data is not None:
            h['Content-Type'] = 'application/json'
            body = json.dumps(data).encode()
        else: body = None
        request = Request(self.url+path, data=body, headers=h)
        try: response = urlopen(request, timeout=3)
        except HTTPError as e: response = e
        raw = response.read()
        value = json.loads(raw) if response.headers.get('Content-Type', '').startswith('application/json') else raw
        return response.status, value, response.headers

    def login(self):
        status, data, headers = self.call('/api/login', {'setup_code': self.app.setup_code, 'password': 'test-password-long'})
        self.assertEqual(status, 200, data)
        self.cookie = headers['Set-Cookie'].split(';')[0]
        return self.cookie

    def pair(self):
        self.login()
        status, raw, _ = self.call('/api/pair/bundle', {})
        self.assertEqual(status, 200)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertIn('Buzz-VPS-Connect.exe', archive.namelist())
            return json.loads(archive.read('buzz-pairing.json'))

    def test_anonymous_admin_and_device_refused_before_broker(self):
        for path in ['/api/status', '/api/discover', '/api/auth/start', '/api/device/deploy']:
            self.assertEqual(self.call(path, {})[0], 401)
        self.assertEqual(self.calls, [])

    def test_setup_code_required_consumed_password_hashed_and_later_login(self):
        code = self.app.setup_code
        self.assertEqual(self.call('/api/login', {'setup_code': 'wrong', 'password': 'test-password-long'})[0], 400)
        self.login()
        self.assertEqual(self.app.setup_code, '')
        persisted = (self.root/'portal/account.json').read_text()
        self.assertNotIn('test-password-long', persisted)
        self.assertNotIn(code, persisted)
        self.assertEqual(self.call('/api/login', {'setup_code': code, 'password': 'different-password'})[0], 400)
        self.assertEqual(self.call('/api/login', {'password': 'test-password-long'})[0], 200)

    def test_csrf_origin_missing_or_foreign_refused(self):
        self.login()
        for origin in [False, 'https://evil.example']:
            self.assertEqual(self.call('/api/configure', {'owner': OWNER, 'relay': RELAY}, origin=origin)[0], 403)
        self.assertEqual(self.calls, [])

    def test_unauthenticated_bundle_and_arbitrary_operations_refused(self):
        self.assertEqual(self.call('/api/pair/bundle', {})[0], 401)
        self.login()
        self.assertEqual(self.call('/api/status', {'op': 'deploy'})[0], 404)
        self.assertEqual(self.call('/api/shell', {'command': 'id'})[0], 404)
        self.assertEqual(self.calls, [])

    def test_one_use_pairing_deploy_scope_revocation_and_persistence(self):
        pairing = self.pair()
        payload = {'pairing_code': pairing['pairing_code'], 'name': 'test-device'}
        status, answer, _ = self.call('/api/pair/exchange', payload, cookie='', origin=False)
        self.assertEqual(status, 200)
        token, device = answer['token'], answer['device_id']
        h = {'Authorization': 'Bearer '+token}
        self.assertEqual(self.call('/api/pair/exchange', payload, cookie='', origin=False)[0], 400)
        self.assertEqual(self.call('/api/auth/start', {'pubkey': PUBKEY}, cookie='', headers=h)[0], 401)
        self.assertEqual(self.call('/api/device/deploy', {'op': 'deploy', 'agent': {'test': True}}, cookie='', headers=h, origin=False)[0], 200)
        self.assertEqual(self.calls[-1]['op'], 'deploy')
        saved = (self.root/'portal/devices.json').read_text()
        self.assertNotIn(token, saved)
        restarted = Portal(self.root/'portal', self.url, local=True)
        self.assertTrue(restarted.device('Bearer '+token))
        self.assertFalse(restarted.admin(self.cookie))
        status, devices, _ = self.call('/api/devices', {})
        self.assertNotIn('hash', json.dumps(devices))
        self.assertEqual(self.call('/api/revoke', {'id': device})[0], 200)
        self.assertEqual(self.call('/api/device/deploy', {'op': 'deploy'}, cookie='', headers=h, origin=False)[0], 401)

    def test_pairing_expires_and_admin_session_expires(self):
        pairing = self.pair(); self.now[0] += 601
        self.assertEqual(self.call('/api/pair/exchange', {'pairing_code': pairing['pairing_code']}, origin=False)[0], 400)
        self.now[0] += 8*3600
        self.assertEqual(self.call('/api/status', {})[0], 401)

    def test_host_and_https_enforced(self):
        self.assertEqual(self.call('/api/hello', headers={'Host': 'evil.example'})[0], 421)
        self.app.local = False
        self.assertEqual(self.call('/api/hello')[0], 403)
        self.assertEqual(self.call('/api/hello', headers={'X-Forwarded-Proto': 'https'})[0], 200)

    def test_single_setup_script_preserves_dependency_order(self):
        status, raw, headers = self.call('/setup.js')
        self.assertEqual(status, 200)
        self.assertTrue(headers['Content-Type'].startswith('text/javascript'))
        from buzz_agents.portal import WEB
        self.assertEqual(raw, (WEB/'i18n.js').read_bytes()+b'\n;\n'+(WEB/'app.js').read_bytes())
        page = self.call('/')[1]
        self.assertIn(b'src="/setup.js"', page)
        self.assertNotIn(b'src="/i18n.js"', page)
        self.assertNotIn(b'src="/app.js"', page)

    def test_public_page_security_headers_and_no_secrets(self):
        status, raw, headers = self.call('/')
        self.assertEqual(status, 200)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertIn("form-action 'none'", headers['Content-Security-Policy'])
        self.assertNotIn(self.app.setup_code.encode(), raw)
        self.assertIn('root 비밀번호'.encode(), raw)

    def test_login_rate_limit(self):
        for _ in range(12): self.call('/api/login', {'setup_code': 'wrong', 'password': 'test-password-long'})
        self.assertEqual(self.call('/api/login', {'setup_code': self.app.setup_code, 'password': 'test-password-long'})[1]['error'], 'try_again_in_one_minute')
        self.now[0] += 61
        self.login()

    def test_broker_errors_and_exceptions_do_not_leak(self):
        self.login()
        def fail(_): raise RuntimeError('private-token-not-for-user')
        self.app.rpc = fail
        status, result, _ = self.call('/api/status', {})
        self.assertEqual(status, 500)
        self.assertNotIn('private-token', json.dumps(result))


    def test_access_reissue_socket_and_recovery_preserve_devices(self):
        from contextlib import redirect_stdout
        from buzz_agents.portal_recover import control_server, request_code
        output = io.StringIO()
        original = self.app.setup_code
        with control_server(self.app), redirect_stdout(output):
            socket_path = self.app.root/'access.sock'
            self.assertEqual(socket_path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(BlockingIOError):
                with control_server(self.app): pass
            request_code(socket_path)
        self.assertNotEqual(original, self.app.setup_code)
        self.assertFalse(socket_path.exists())
        self.assertIn('/#setup_code='+self.app.setup_code, output.getvalue())
        self.assertEqual(self.call('/api/login', {'setup_code': original, 'password': 'test-password-long'})[0], 400)
        pairing = self.pair()
        _, device, _ = self.call('/api/pair/exchange', {'pairing_code': pairing['pairing_code']}, origin=False)
        persisted = (self.app.root/'devices.json').read_bytes()
        old_cookie = self.cookie
        output = io.StringIO()
        with control_server(self.app), redirect_stdout(output):
            request_code(self.app.root/'access.sock')
        recovery = output.getvalue().split('/#recovery_code=')[1].splitlines()[0]
        self.assertEqual(self.call('/api/recover', {'recovery_code': recovery, 'password': 'new-long-password'}, origin=False)[0], 403)
        self.assertEqual(self.call('/api/recover', {'recovery_code': recovery, 'password': 'short'})[0], 400)
        self.assertEqual(self.call('/api/recover', {'recovery_code': recovery, 'password': 'new-long-password'})[0], 200)
        self.assertEqual(self.call('/api/status', {}, cookie=old_cookie)[0], 401)
        self.assertEqual((self.app.root/'devices.json').read_bytes(), persisted)
        self.assertTrue(self.app.device('Bearer '+device['token']))
        self.assertEqual(self.call('/api/recover', {'recovery_code': recovery, 'password': 'another-password'})[0], 400)
        self.assertEqual(self.call('/api/login', {'password': 'test-password-long'})[0], 400)
        self.assertEqual(self.call('/api/login', {'password': 'new-long-password'})[0], 200)
        self.assertNotIn(recovery, (self.app.root/'account.json').read_text())

    def test_recovery_expiry_reissue_restart_and_failed_save(self):
        from contextlib import redirect_stdout
        self.login()
        def issue():
            out = io.StringIO()
            with redirect_stdout(out): self.app.issue_access_code()
            return out.getvalue().split('/#recovery_code=')[1].splitlines()[0]
        old = issue(); fresh = issue()
        self.assertEqual(self.call('/api/recover', {'recovery_code': old, 'password': 'new-long-password'})[0], 400)
        self.now[0] += 3600
        self.assertEqual(self.call('/api/recover', {'recovery_code': fresh, 'password': 'new-long-password'})[0], 400)
        self.now[0] += 61
        fresh = issue()
        before = (self.app.root/'account.json').read_bytes()
        with patch('buzz_agents.portal.atomic_json', side_effect=OSError('fixture-write-failure')):
            self.assertEqual(self.call('/api/recover', {'recovery_code': fresh, 'password': 'new-long-password'})[0], 500)
        self.assertEqual((self.app.root/'account.json').read_bytes(), before)
        self.assertTrue(self.app.admin(self.cookie))
        restarted = Portal(self.app.root, self.url, local=True, clock=lambda: self.now[0])
        with self.assertRaisesRegex(ToolError, 'invalid_or_expired_recovery_code'):
            restarted.recover({'recovery_code': fresh, 'password': 'new-long-password'})
        self.assertEqual(restarted.account, self.app.account)
        self.assertFalse(restarted.grants)
        self.assertFalse(restarted.admin(self.cookie))

    def test_recovery_one_winner_and_unused_pairing_revoked(self):
        from concurrent.futures import ThreadPoolExecutor
        from contextlib import redirect_stdout
        pairing = self.pair()
        out = io.StringIO()
        with redirect_stdout(out): self.app.issue_access_code()
        code = out.getvalue().split('/#recovery_code=')[1].splitlines()[0]
        def attempt(_):
            return self.call('/api/recover', {'recovery_code': code, 'password': 'new-long-password'})[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sorted(results), [200, 400])
        self.assertEqual(self.call('/api/pair/exchange', {'pairing_code': pairing['pairing_code']}, origin=False)[0], 400)

    def test_setup_deadline_and_restart_regeneration(self):
        code = self.app.setup_code
        self.now[0] += 3600
        self.assertEqual(self.call('/api/login', {'setup_code': code, 'password': 'test-password-long'})[0], 400)
        restarted = Portal(self.app.root, self.url, local=True, clock=lambda: self.now[0])
        self.assertNotEqual(restarted.setup_code, code)
        with self.assertRaises(ToolError): restarted.login({'setup_code': code, 'password': 'test-password-long'})
        self.assertTrue(restarted.login({'setup_code': restarted.setup_code, 'password': 'test-password-long'}))

    def test_no_public_issuer_or_secret_readback(self):
        for path in ['/api/recover/issue', '/api/issue-access-code', '/access.sock']:
            self.assertNotEqual(self.call(path, {})[0], 200)
        self.assertEqual(self.call('/api/recover', {'password': 'new-long-password'})[0], 400)
        for path in ['/', '/api/hello', '/app.js', '/i18n.js']:
            _, body, _ = self.call(path)
            self.assertNotIn(self.app.setup_code, body.decode() if isinstance(body, bytes) else json.dumps(body))
        self.assertEqual(self.call('/?setup_code='+self.app.setup_code)[0], 400)

    def test_device_check_and_self_revoke_are_own_only(self):
        pairing = self.pair()
        _, device, _ = self.call('/api/pair/exchange', {'pairing_code': pairing['pairing_code']}, origin=False)
        h = {'Authorization': 'Bearer '+device['token']}
        self.calls.clear()
        status, value, _ = self.call('/api/device/check', {}, cookie='', origin=False, headers=h)
        self.assertEqual(status, 200)
        self.assertEqual(value['device_id'], device['device_id'])
        self.assertEqual(self.calls, [])
        other = 'f'*24
        self.app.devices[other] = {'hash': digest('x'*43), 'name': 'other'}
        self.assertEqual(self.call('/api/device/revoke-self', {'id':other}, cookie='', origin=False, headers=h)[0], 200)
        self.assertIn(other, self.app.devices)
        self.assertEqual(self.call('/api/device/check', {}, cookie='', origin=False, headers=h)[0], 401)


class BrokerTests(unittest.TestCase):
    def test_discovery_only_public_fields_and_multiple_relays(self):
        container = {'Config': {'Env': ['RELAY_OWNER_PUBKEY='+OWNER, 'BUZZ_REQUIRE_RELAY_MEMBERSHIP=true',
                                      'PRIVATE_KEY=never-return-this', 'OTHER_PASSWORD=secret'],
                                 'Labels': {'traefik.http.routers.buzz.rule': 'Host(`buzz.example.com`)'}}}
        result = discover_relays([container, container, {'Config': {'Env': ['RELAY_OWNER_PUBKEY=nsec-invalid']}}])
        self.assertEqual(result, [{'owner': OWNER, 'relay': 'wss://buzz.example.com', 'membership_required': True}])
        self.assertNotIn('secret', json.dumps(result))

    def test_rpc_rejects_unlisted_operations_extra_fields_and_invalid_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            broker = Broker('runtime:verified', root=tmp, control=tmp)
            for request in [{'op': 'shell', 'command': 'id'}, {'op': 'status', 'path': '/root'},
                            {'op': 'configure', 'owner': 'nsec-secret', 'relay': RELAY},
                            {'op': 'configure', 'owner': OWNER, 'relay': 'http://insecure'}]:
                with self.assertRaises(ToolError): broker.dispatch(request)
            with self.assertRaises(ToolError): broker.dispatch({'op': 'auth-start', 'pubkey': '../escape'})

    def test_configuration_is_immutable_and_runtime_image_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            broker = Broker('runtime:verified', root=Path(tmp)/'data', control=tmp)
            image = [{'Id': 'sha256:'+'d'*64, 'Config': {'Labels': {'org.opencontainers.image.title': 'buzz-agents'}}}]
            with patch('buzz_agents.portal_broker.execute', return_value=json.dumps(image).encode()):
                self.assertTrue(broker.dispatch({'op': 'configure', 'owner': OWNER, 'relay': RELAY})['ok'])
                with self.assertRaisesRegex(ToolError, 'existing_relay_configuration_preserved'):
                    broker.dispatch({'op': 'configure', 'owner': 'c'*64, 'relay': RELAY})
                image[0]['Id'] = 'sha256:'+'e'*64
            with patch('buzz_agents.portal_broker.execute', return_value=json.dumps(image).encode()):
                with self.assertRaisesRegex(ToolError, 'image_upgrade_requires_review'):
                    broker.dispatch({'op': 'configure', 'owner': OWNER, 'relay': RELAY})

    def test_legacy_registry_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'registry.json').write_text(json.dumps({PUBKEY: {}}))
            broker = Broker('runtime:verified', root=tmp, control=tmp)
            with self.assertRaisesRegex(ToolError, 'existing_installation_requires_migration'):
                broker.dispatch({'op': 'configure', 'owner': OWNER, 'relay': RELAY})

    def test_real_pty_login_input_completion_and_no_arbitrary_command(self):
        calls=[]
        def spawn(argv, **kwargs):
            calls.append(argv)
            return subprocess.Popen([sys.executable, '-c', "print('https://auth.openai.com/test',flush=True); input(); print('fixture login done',flush=True)"], **kwargs)
        sessions = LoginSessions(spawn=spawn)
        with patch('buzz_agents.portal_broker.read_json', return_value={PUBKEY:{'provider':'codex'}}), \
             patch('buzz_agents.portal_broker.inspect_container', return_value={'State':{'Running':True}}), \
             patch('buzz_agents.portal_broker.check_ownership'):
            result=sessions.start({'state_dir':'/unused'},PUBKEY)
            sid=result['session']
            try:
                self.assertEqual(calls[0][:-1], ['docker','exec','-it','--user','0:0','buzz-native-'+PUBKEY[:20],
                                             'python','-m','buzz_agents.portal_auth','run','codex'])
                self.assertRegex(calls[0][-1], r'^[a-f0-9]{32}$')
                with self.assertRaisesRegex(ToolError,'authentication_already_in_progress'):
                    sessions.start({'state_dir':'/unused'},PUBKEY)
                with self.assertRaises(ToolError):sessions.send(sid,'code\nrm -rf /')
                sessions.send(sid,'verification-code-fixture')
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    answer=sessions.poll(sid)
                    if answer['done'] and 'fixture login done' in answer['output']:break
                    time.sleep(.02)
                self.assertTrue(answer['done']);self.assertTrue(answer['success'])
                self.assertNotIn('verification-code-fixture', answer['output'])
            finally:
                sessions.cancel(sid);os.close(sessions.items[sid]['fd'])

    def test_auth_wrapper_timeout_kills_child_and_removes_marker(self):
        real_spawn=subprocess.Popen
        def spawn(argv, **kwargs):
            return real_spawn([sys.executable,'-c','import time; time.sleep(60)'],**kwargs)
        with tempfile.TemporaryDirectory() as tmp, patch.object(portal_auth,'BASE',Path(tmp)), \
             patch.object(portal_auth.subprocess,'Popen',side_effect=spawn):
            self.assertEqual(portal_auth.run('codex','a'*32,timeout=.05),124)
            self.assertFalse(Path(tmp,'portal-auth.json').exists())

    def test_cancel_before_start_does_not_launch_official_login(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(portal_auth,'BASE',Path(tmp)), \
             patch.object(portal_auth.subprocess,'Popen') as spawn:
            portal_auth.cancel('a'*32)
            self.assertEqual(portal_auth.run('codex','a'*32),130)
            spawn.assert_not_called()
            self.assertFalse(Path(tmp,'portal-auth-cancel.json').exists())

    def test_cancel_another_session_does_not_kill_current_login(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(portal_auth,'BASE',Path(tmp)), \
             patch.object(portal_auth.os,'killpg') as kill:
            Path(tmp,'portal-auth.json').write_text(json.dumps({'pid':12345,'session':'b'*32,'start':'123'}))
            portal_auth.cancel('a'*32)
            kill.assert_not_called()

    def test_production_origin_rejects_http_credentials_query_and_path(self):
        for value in ['http://example.com', 'https://user:pass@example.com', 'https://example.com/path', 'https://example.com?token=x']:
            with self.assertRaises(ToolError):origin_url(value)
        self.assertEqual(origin_url('https://setup.example.com/'),'https://setup.example.com')


if __name__ == '__main__': unittest.main()
