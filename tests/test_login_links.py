"""Sanitized official auth URLs; no live account or secret-bearing transcript."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

class LoginLinkTests(unittest.TestCase):
    def test_official_output_shapes_and_untrusted_urls(self):
        # Extract pure helpers from the same app shipped in /setup.js.
        source=(ROOT/'buzz_agents/web/app.js').read_text()
        start=source.index('function stripLoginControls(') if 'function stripLoginControls(' in source else source.index('function officialLinks(')
        end=source.index('async function poll()',start)
        code=source[start:end]+r'''
const expected='https://claude.com/cai/oauth/authorize?client_id=fixture&state=test-state&code_challenge=abc_DEF-123&redirect_uri=https%3A%2F%2Fplatform.claude.com%2Foauth%2Fcode%2Fcallback&scope=user%3Aprofile+user%3Ainference';
const assert=require('node:assert/strict');
assert.equal(typeof extractLoginLinks,'function','the shipped parser must support the current official Claude endpoint');
assert.deepEqual(extractLoginLinks('If the browser did not open, visit: '+expected+'\r\nPaste code:'),[expected]);
assert.deepEqual(extractLoginLinks('\x1b[32m'+expected+'\x1b[0m\r\n'),[expected]);
for(const ending of ['\x07','\x1b\\']) {
 const osc='\x1b]8;;'+expected+ending+'Open Claude\x1b]8;;'+ending;
 assert.deepEqual(extractLoginLinks(osc),[expected]);
 assert.equal(stripLoginControls(osc),'Open Claude');
}
assert.deepEqual(extractLoginLinks(expected+'\n'+expected),[expected]);
for(const url of ['https://auth.openai.com/deviceauth','https://chatgpt.com/deviceauth','https://claude.ai/oauth/authorize?state=x','https://console.anthropic.com/oauth/authorize?state=x','https://platform.claude.com/oauth/authorize?state=x']) assert.deepEqual(extractLoginLinks(url+'\n'),[url]);
for(const url of ['http://claude.com/cai/oauth/authorize','https://claude.com.evil.test/cai/oauth/authorize','https://evil.test/?next=https%3A%2F%2Fclaude.com','https://user:pass@claude.com/cai/oauth/authorize','https://claude.com:444/cai/oauth/authorize','javascript:alert(1)','https://claude.com/pricing']) assert.deepEqual(extractLoginLinks(url+'\n'),[]);
assert.deepEqual(extractLoginLinks('\x1b]8;;'+expected),[], 'incomplete OSC must not produce partial links');
assert.equal(stripLoginControls('\x1b]0;title\x1b\\keep\n'+expected),'keep\n'+expected);
console.log('login link fixtures passed');
'''
        result=subprocess.run(['node','-e',code],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
