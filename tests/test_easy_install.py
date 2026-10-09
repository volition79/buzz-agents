import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import zipfile

from buzz_agents.bridge import parse_command, main as bridge_main, authenticate
from buzz_agents.common import ToolError
from buzz_agents.easy_schedule import validate_schedule, compose

spec = importlib.util.spec_from_file_location('easy_bootstrap', Path(__file__).resolve().parents[1]/'scripts/easy-bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def archive(extra=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for n in ['Dockerfile','scripts/install-host.sh','buzz_agents/bridge.py']:
            z.writestr(n,'fixture')
        if extra:
            z.writestr(extra,'malicious')
    return out.getvalue()


def request():
    data = archive()
    return {'archive':base64.b64encode(data).decode(),'sha256':hashlib.sha256(data).hexdigest(),
            'public_key':'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFixture buzz-agents-easy',
            'owner':'a'*64,'relay':'wss://relay.example.com'}


class BootstrapTests(unittest.TestCase):
    def test_valid_bundle_and_safe_unpack(self):
        data = bootstrap.validate(request())
        with tempfile.TemporaryDirectory() as d:
            bootstrap.unpack(data,Path(d))
            self.assertEqual((Path(d)/'buzz_agents/bridge.py').read_text(),'fixture')

    def test_changed_bytes_rejected_before_unpack(self):
        r=request();r['archive']=base64.b64encode(archive('scripts/extra.py')).decode()
        with self.assertRaisesRegex(ValueError,'checksum'): bootstrap.validate(r)

    def test_private_key_and_ssh_options_rejected(self):
        for key,val in [('owner','nsec1SECRET'),('public_key','command="sh" ssh-ed25519 AAAA'),
                        ('relay','wss://user:pass@server'),('relay','wss://host/path'),('relay','ws://host')]:
            r=request();r[key]=val
            with self.subTest(key=key,val=val), self.assertRaises(ValueError): bootstrap.validate(r)

    def test_traversal_and_unexpected_archive_members_write_nothing(self):
        for name in ['../../escape','/root/file',r'scripts\escape','scripts/a/b','unauthorized.sh']:
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(ValueError): bootstrap.unpack(archive(name),Path(d))
                self.assertEqual(list(Path(d).iterdir()),[])

    def test_existing_installation_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'existing';root.mkdir();sentinel=root/'keep';sentinel.write_text('untouched')
            source=Mock();source.buffer=io.BytesIO(json.dumps(request()).encode())
            with patch.object(bootstrap,'ROOT',root),patch.object(bootstrap,'MARKER',root/'missing'),patch.object(bootstrap.sys,'stdin',source),patch.object(bootstrap.os,'geteuid',return_value=0),patch.object(bootstrap,'run') as run:
                with self.assertRaisesRegex(ValueError,'existing_installation_preserved'):bootstrap.main()
                run.assert_not_called()
            self.assertEqual(sentinel.read_text(),'untouched')


class BridgeTests(unittest.TestCase):
    def test_explicit_operations_only(self):
        self.assertEqual(parse_command('buzz-agents-status'),('status',))
        self.assertEqual(parse_command('buzz-agents-auth claude '+'b'*64),('auth','claude','b'*64))
        for command in ['', 'sh', 'buzz-agents-status;id', 'buzz-agents-auth codex ../root',
                        'buzz-agents-auth codex '+'b'*64+' --help','buzz-agents-receive\nwhoami']:
            with self.subTest(command=command),self.assertRaises(ToolError):parse_command(command)

    def test_bad_command_cannot_reach_docker_or_settings(self):
        with patch('buzz_agents.bridge.load_settings') as load:
            with self.assertRaises(ToolError):bridge_main('docker exec anything sh')
            load.assert_not_called()

    def test_auth_wrong_identity_never_executes(self):
        with patch('buzz_agents.bridge.read_json',return_value={'b'*64:{'provider':'codex'}}),patch('buzz_agents.bridge.subprocess.run') as run:
            with self.assertRaises(ToolError):authenticate({'state_dir':'/tmp'},'claude','b'*64)
            run.assert_not_called()

    def test_auth_fixed_container_command_and_terminal(self):
        item={'provider':'codex','pubkey':'b'*64}
        with patch('buzz_agents.bridge.read_json',return_value={'b'*64:item}),patch('buzz_agents.bridge.inspect_container',return_value={'State':{'Running':True}}),patch('buzz_agents.bridge.check_ownership') as ownership,patch('buzz_agents.bridge.sys.stdin.isatty',return_value=True),patch('buzz_agents.bridge.subprocess.run',return_value=Mock(returncode=0)) as run:
            result=authenticate({'state_dir':'/tmp'},'codex','b'*64)
            ownership.assert_called_once()
            self.assertTrue(result['ok'])
            argv=run.call_args.args[0]
            self.assertEqual(argv,['docker','exec','-it','--user','0:0','buzz-native-'+'b'*20,'python','-m','buzz_agents.cli','auth','codex'])

    def test_failed_official_login_does_not_record_ready_or_auth(self):
        from buzz_agents.cli import authenticate_locked
        with patch('buzz_agents.cli.read_json',return_value={'status':'needs_login'}),patch('buzz_agents.cli.load_config',return_value={'provider':'codex','pubkey':'b'*64}),patch('buzz_agents.cli.os.geteuid',return_value=0),patch('buzz_agents.cli.subprocess.run',return_value=Mock(returncode=1)),patch('buzz_agents.cli.atomic_json') as write:
            with self.assertRaisesRegex(ToolError,'official_login_failed'):authenticate_locked('codex')
            write.assert_not_called()

    def test_successful_auth_runs_as_agent_and_only_then_rearms(self):
        from buzz_agents.cli import authenticate_locked
        with patch('buzz_agents.cli.read_json',return_value={'status':'needs_login'}),patch('buzz_agents.cli.load_config',return_value={'provider':'claude','pubkey':'b'*64}),patch('buzz_agents.cli.os.geteuid',return_value=0),patch('buzz_agents.cli.subprocess.run',return_value=Mock(returncode=0)) as run,patch('buzz_agents.cli.atomic_json') as write:
            self.assertTrue(authenticate_locked('claude')['ok'])
            self.assertEqual(run.call_args.kwargs['user'],10001)
            self.assertEqual(run.call_args.kwargs['env']['HOME'],'/home/agent')
            self.assertEqual(write.call_args_list[-1].args[1]['status'],'ready')


class EasyScheduleTests(unittest.TestCase):
    def item(self):
        return {'channel_id':'12345678-1234-1234-1234-123456789abc','bot_pubkey':'b'*64,
                'prompt':'협업해 파일을 작성하세요','time':'09:00','membership_confirmed':True}

    def test_schedule_uses_known_bot_explicit_membership_and_korean_time(self):
        result=validate_schedule(self.item(),{'b'*64:{}})
        self.assertEqual(result['timezone'],'Asia/Seoul')
        self.assertEqual(result['kind'],'daily')
        for mutation in [{'membership_confirmed':False},{'bot_pubkey':'c'*64},{'time':'25:00'},{'channel_id':'bad'}]:
            with self.assertRaises((ToolError,ValueError)):validate_schedule({**self.item(),**mutation},{'b'*64:{}})

    def test_scheduler_has_only_own_volumes_no_socket_or_ports(self):
        doc=compose({'image':'verified-image'})['services']['scheduler']
        self.assertNotIn('ports',doc)
        self.assertNotIn('privileged',doc)
        self.assertEqual(doc['user'],'10001:10001')
        self.assertTrue(all(v['source'].startswith('/var/lib/buzz-agents-easy-scheduler/') for v in doc['volumes']))


if __name__=='__main__':unittest.main()
