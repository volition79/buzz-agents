import json
import unittest
from copy import deepcopy
from buzz_agents.common import ToolError
from buzz_agents.config import normalize, decode_nsec, relay_url
from helpers import agent, config, OWNER, RELAY, PUBKEY


class ConfigTests(unittest.TestCase):
    def test_codex_and_claude_are_independent_not_a_workflow(self):
        a, b = config(), config('claude-agent-acp', 'f'*64)
        self.assertEqual(a['provider'],'codex'); self.assertEqual(b['provider'],'claude')
        self.assertNotEqual(a['pubkey'],b['pubkey'])
        self.assertEqual(a['workspace'],'team');self.assertEqual(b['workspace'],'team')
        self.assertNotIn('stage',a); self.assertNotIn('order',a)

    def test_arbitrary_bot_name_role_and_model_survive(self):
        a=agent(); a['name']='시장성 조사 봇'; a['launch']['env']['BUZZ_ACP_MODEL']='another-model'
        c=normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)
        self.assertEqual(c['name'],a['name'])
        self.assertEqual(c['env']['BUZZ_ACP_MODEL'],'another-model')
        self.assertIn('자유롭게',c['env']['BUZZ_ACP_SYSTEM_PROMPT'])

    def test_claude_model_authority_is_not_reinterpreted(self):
        a=agent('claude-agent-acp'); a['launch']['policy_env'].pop('BUZZ_ACP_MODEL')
        a['launch']['policy_env']['ANTHROPIC_MODEL']='claude-model'
        c=normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)
        self.assertEqual(c['env']['ANTHROPIC_MODEL'],'claude-model')
        self.assertNotIn('BUZZ_ACP_MODEL',c['env'])

    def test_old_desktop_payload_refused_not_silently_guessed(self):
        a=agent(); del a['launch']
        with self.assertRaisesRegex(ToolError,'launch_contract'):
            normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)

    def test_different_relay_refused(self):
        a=agent(); a['relay_url']='wss://other.example'
        with self.assertRaisesRegex(ToolError,'relay_mismatch'):
            normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)

    def test_wrong_owner_refused(self):
        a=agent(); a['launch']['owner_pubkey']='e'*64
        with self.assertRaises(ToolError): normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)

    def test_human_secret_refused(self):
        with self.assertRaisesRegex(ToolError,'human_key'):
            normalize(agent(),{},OWNER,RELAY,derive=lambda _:OWNER)

    def test_unknown_environment_and_api_routes_refused(self):
        for key in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','NODE_OPTIONS','PATH','BUZZ_PRIVATE_KEY','ANTHROPIC_BASE_URL','PYTHONPATH'):
            with self.subTest(key=key):
                a=agent(); a['launch']['env'][key]='sensitive-value'
                with self.assertRaises(ToolError) as error:
                    normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)
                self.assertNotIn('sensitive-value',str(error.exception))

    def test_unsupported_binaries_and_args_refused(self):
        for command in ('/bin/sh','C:\\bin\\codex.exe','codex','goose'):
            with self.subTest(command=command), self.assertRaises(ToolError):
                normalize(agent(command),{},OWNER,RELAY,derive=lambda _:PUBKEY)
        a=agent(); a['launch']['args']=['--danger']
        with self.assertRaises(ToolError): normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)

    def test_rate_limits_not_fixed_collaboration_steps(self):
        c=config(options={'turn_limit':40,'max_turn_seconds':900,'daily_limit':150})
        self.assertEqual(c['policy']['turn_limit'],40)
        self.assertEqual(c['policy']['max_turn_seconds'],900)
        self.assertEqual(c['env']['BUZZ_ACP_HEARTBEAT_INTERVAL'],'0')

    def test_native_lower_timeout_is_respected(self):
        a=agent(); a['launch']['policy_env']['BUZZ_ACP_MAX_TURN_DURATION']='120'
        c=normalize(a,{'max_turn_seconds':900},OWNER,RELAY,derive=lambda _:PUBKEY)
        self.assertEqual(c['policy']['max_turn_seconds'],120)
        self.assertLess(int(c['env']['BUZZ_ACP_IDLE_TIMEOUT']),120)

    def test_explicit_native_duration_can_exceed_default_within_official_cap(self):
        a=agent();a['launch']['policy_env']['BUZZ_ACP_MAX_TURN_DURATION']='10800'
        c=normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)
        self.assertEqual(c['policy']['max_turn_seconds'],10800)
        self.assertEqual(normalize(a,{'max_turn_seconds':900},OWNER,RELAY,derive=lambda _:PUBKEY)['policy']['max_turn_seconds'],900)
        a['launch']['policy_env']['BUZZ_ACP_MAX_TURN_DURATION']='604801'
        with self.assertRaises(ToolError):normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)

    def test_unsafe_options_refused(self):
        for options in ({'memory_mb':16777217},{'cpus':float('nan')},{'workspace':'../../root'},
                        {'turn_limit':-1},{'max_turn_seconds':True},{'daily_limit':-1}):
            with self.subTest(options=options), self.assertRaises(ToolError): config(options=options)

    def test_shared_workspace_requires_explicit_group(self):
        self.assertEqual(config(options={'workspace':'webtoon'})['workspace'],'webtoon')

    def test_auth_tag_json_is_supported(self):
        a=agent(); a['auth_tag']=json.dumps(a['auth_tag'])
        self.assertEqual(normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)['pubkey'],PUBKEY)

    def test_attestation_shape_and_owner_required(self):
        for tag in (None,[],['auth','d'*64,'','e'*128],['auth',OWNER,'','bad']):
            a=agent(); a['auth_tag']=tag
            with self.subTest(tag=tag), self.assertRaises(ToolError): normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)

    def test_anyone_is_not_silently_enabled(self):
        a=agent(); a['respond_to']='anyone'
        with self.assertRaises(ToolError): normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)

    def test_allowlist_survives(self):
        a=agent(); a['respond_to']='allowlist';a['respond_to_allowlist']=['e'*64]
        c=normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)
        self.assertEqual(c['env']['BUZZ_ACP_RESPOND_TO_ALLOWLIST'],'e'*64)

    def test_desktop_default_workers_are_preserved(self):
        # Synthetic official launch shape; observed local record uses default10.
        # Source/provenance and limits are recorded in fixtures/provider-error.json.
        for command, model_key in [('codex-acp', 'BUZZ_ACP_MODEL'), ('claude-agent-acp', 'ANTHROPIC_MODEL')]:
            a=agent(command); a['parallelism']=10
            a['launch']['policy_env']={
                'BUZZ_ACP_AGENTS':'10', 'BUZZ_ACP_RELAY_OBSERVER':'true',
                'BUZZ_ACP_LAZY_POOL':'true', 'BUZZ_ACP_SESSION_POLICY':'channel',
                model_key:'selected-model'}
            c=normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)
            self.assertEqual(c['env']['BUZZ_ACP_AGENTS'],'10')
            self.assertEqual(c['env'][model_key],'selected-model')
            self.assertEqual(a['parallelism'],10)  # Input remains unchanged.
            self.assertEqual(c['memory_mb'],1536)
            self.assertEqual(c['command'],command)

    def test_user_counts_and_missing_count_default(self):
        for count in (1,2,10,32):
            a=agent();a['parallelism']=count
            a['launch']['policy_env']['BUZZ_ACP_AGENTS']=str(count)
            c=normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)
            self.assertEqual(c['env']['BUZZ_ACP_AGENTS'],str(count))
            a['launch']['policy_env'].pop('BUZZ_ACP_AGENTS')
            c=normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)
            self.assertEqual(c['env']['BUZZ_ACP_AGENTS'],str(count))
        a.pop('parallelism')
        c=normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)
        self.assertEqual(c['env']['BUZZ_ACP_AGENTS'],'10')

    def test_invalid_parallelism_is_not_silently_capped(self):
        for count in (0, -1, 33, True, '10', 1.5):
            a=agent();a['parallelism']=count
            with self.subTest(count=count), self.assertRaisesRegex(ToolError,'invalid_parallelism'):
                normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)
        for count in ('0','33','1.5','-1','secret'):
            a=agent();a['launch']['policy_env']['BUZZ_ACP_AGENTS']=count
            with self.subTest(count=count), self.assertRaisesRegex(ToolError,'invalid_parallelism'):
                normalize(a,{},OWNER,RELAY,derive=lambda _:PUBKEY)

    def test_nsec_checksum_not_just_prefix(self):
        self.assertEqual(decode_nsec('0'*63+'1'),'0'*63+'1')
        for value in ('nsec1'+'q'*58, 'npub1'+'q'*58, 'secret', '0'*63):
            with self.subTest(value=value), self.assertRaises(ToolError): decode_nsec(value)

    def test_relay_no_credentials_or_downgrade(self):
        for value in ('ws://relay.example','wss://user:password@relay.example','wss://relay.example/path','wss://relay.example?token=x'):
            with self.subTest(value=value), self.assertRaises(ToolError): relay_url(value)

    def test_provider_config_secrets_or_unknown_fields_refused(self):
        with self.assertRaisesRegex(ToolError,'provider_configuration'):
            config(options={'ssh_token':'do-not-store'})
