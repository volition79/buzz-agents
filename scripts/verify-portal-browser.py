"""Real Chrome UI, real HTTP security/session/pairing, explicitly simulated VPS RPC.

No production network/credentials. Requires locally installed Chrome and websocket-client.
"""
from contextlib import redirect_stdout
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
import websocket

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from buzz_agents.portal import Portal, Server
from buzz_agents.common import ToolError


class FixtureBroker:
    def __init__(self):
        self.configured = False
        self.bots = []
        self.owner = 'a'*64
        self.auth_error = None

    def __call__(self, request):
        op = request['op']
        if self.auth_error and op == self.auth_error[0]:
            raise ToolError(self.auth_error[1])
        if op == 'discover':
            return {'ok': True, 'relays': [{'relay':'wss://relay.example.com','owner':self.owner,'membership_required':True}]}
        if op == 'configure':
            assert request['owner'] == self.owner and request['relay'] == 'wss://relay.example.com'
            self.configured = True
            return {'ok': True}
        if op == 'status':
            return {'ok':True, 'configured':self.configured, 'owner':self.owner,
                    'relay':'wss://relay.example.com', 'bots':self.bots}
        if op == 'deploy':
            self.bots = [{'pubkey':'b'*64,'name':'기획 담당 · 테스트 봇','provider':'codex','status':'needs_login','container_running':True},
                         {'pubkey':'c'*64,'name':'제작 담당 · 테스트 봇','provider':'claude','status':'needs_login','container_running':True}]
            return {'ok':True,'agent_id':'buzz-native-'+'b'*20}
        if op == 'auth-start':
            return {'ok':True,'session':'fixture-session','expires_in':600}
        if op == 'auth-poll':
            return {'ok':True,'output':'[브라우저 동작 시험 · 실제 계정 인증 아님]\n공식 로그인 안내가 이 영역에 표시됩니다.\nhttps://auth.openai.com/example\n확인 코드 입력을 기다리고 있습니다.', 'done':False, 'success':False}
        if op == 'auth-input':
            assert request['text'] == 'test-code'
            return {'ok':True}
        if op == 'auth-cancel': return {'ok':True}
        raise AssertionError(op)


class CDP:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=10, suppress_origin=True)
        self.sequence = 0
        self.errors = []
    def call(self, method, params=None):
        self.sequence += 1
        self.ws.send(json.dumps({'id':self.sequence,'method':method,'params':params or {}}))
        while True:
            response=json.loads(self.ws.recv())
            if response.get('method') == 'Runtime.exceptionThrown': self.errors.append(response['params'])
            if response.get('id') == self.sequence:
                if 'error' in response: raise RuntimeError(response['error'])
                return response.get('result',{})
    def js(self, expression):
        result=self.call('Runtime.evaluate', {'expression':expression,'returnByValue':True,'awaitPromise':True})
        if 'exceptionDetails' in result: raise RuntimeError(result['exceptionDetails'])
        return result.get('result',{}).get('value')
    def until(self, expression):
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            if self.js(expression): return
            time.sleep(.1)
        raise AssertionError('browser condition failed: '+expression)
    def shot(self, path):
        data=self.call('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})['data']
        path.write_bytes(base64.b64decode(data))



def verify_login_expiry(cdp, broker):
    # Actual page functions + HTTP responses; only Docker/official auth is simulated.
    for provider_key in ('b', 'c'):
        for path in ('poll', 'input', 'cancel'):
            broker.auth_error = None
            cdp.js("startLogin({pubkey:"+json.dumps(provider_key*64)+",name:'fixture'})")
            broker.auth_error = ('auth-'+path, 'host_command_failed')
            cdp.js("api('auth/"+path+"',{session:authSession,text:'test-code'}).catch(()=>{})")
            assert cdp.js('authSession !== null'), 'transient error lost live session'
            broker.auth_error = ('auth-'+path, 'login_session_expired')
            cdp.js("api('auth/"+path+"',{session:authSession,text:'test-code'}).catch(()=>{})")
            assert cdp.js('authSession === null')
            assert cdp.js("$('authForm').hidden && $('cancelAuth').hidden && $('authInput').value === ''")
            assert cdp.js("$('authStatus').textContent === errors.login_session_expired")
    broker.auth_error = None
    cdp.js("startLogin({pubkey:'"+'b'*64+"',name:'retry'})")
    assert cdp.js('authSession !== null'), 'retry still blocked'
    broker.auth_error = ('auth-poll', 'login_session_expired')
    cdp.js("api('auth/poll',{session:'older-session'}).catch(()=>{})")
    assert cdp.js('authSession !== null'), 'old response cleared newer session'
    broker.auth_error = ('auth-cancel', 'login_session_expired')
    cdp.js("$('cancelAuth').click()")
    cdp.until("authSession === null && $('authStatus').textContent === errors.login_session_expired")
    broker.auth_error = None


def main():
    output=ROOT/'.sonol-test/runtime/portal-v04'
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='buzz-portal-browser-') as directory:
        tmp=Path(directory)
        app=Portal(tmp/'state','http://127.0.0.1',local=True,rpc=FixtureBroker(),artifacts=ROOT/'connect/assets')
        server=Server(('127.0.0.1',0),app)
        app.url='http://127.0.0.1:'+str(server.server_port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        profile=tmp/'chrome'
        chrome=subprocess.Popen(['google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage',
                                 '--remote-debugging-port=0','--user-data-dir='+str(profile),
                                 '--no-first-run','--no-default-browser-check','about:blank'],
                                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        cdp=None
        try:
            deadline=time.monotonic()+15
            while not (profile/'DevToolsActivePort').exists():
                if time.monotonic()>deadline:raise RuntimeError('Chrome did not start')
                time.sleep(.1)
            port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
            with urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list') as r:pages=json.load(r)
            page=next(item for item in pages if item.get('type')=='page' and item.get('url')=='about:blank')
            cdp=CDP(page['webSocketDebuggerUrl']);cdp.call('Runtime.enable');cdp.call('Page.enable')
            cdp.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1120,'deviceScaleFactor':1,'mobile':False})
            cdp.call('Browser.setDownloadBehavior',{'behavior':'allow','downloadPath':str(tmp/'downloads')})
            cdp.call('Network.setUserAgentOverride', {'userAgent':cdp.js('navigator.userAgent'), 'acceptLanguage':'ko-KR,ko'})
            cdp.call('Page.navigate',{'url':app.url})
            cdp.until("document.querySelector('#loginForm') !== null")
            cdp.shot(output/'setup-login.png')
            cdp.until("document.querySelector('#setupCode').value === ''")
            assert '로그' in cdp.js("document.querySelector('#setupCodeField').innerText")
            cdp.call('Page.navigate',{'url':app.url+'/#setup_code=bad'})
            cdp.until("document.querySelector('#message')?.textContent.includes('읽지 못했습니다')")
            assert cdp.js('location.hash') == ''
            assert cdp.js("document.querySelector('#setupCode').value") == ''
            cdp.call('Page.navigate',{'url':app.url+'/#setup_code='+app.setup_code+'&setup_code='+app.setup_code})
            cdp.until("document.querySelector('#message')?.textContent.includes('읽지 못했습니다')")
            cdp.call('Page.navigate',{'url':app.url+'/#setup_code='+app.setup_code})
            cdp.until("document.querySelector('#message')?.textContent.includes('링크의 설정 코드')")
            assert cdp.js('location.hash') == ''
            assert cdp.js("document.querySelector('#setupCode').value") == app.setup_code
            assert not app.account, 'link visit must never claim the server'
            assert cdp.js("localStorage.length+sessionStorage.length") == 0
            app.setup_deadline=time.time()-1
            cdp.js("document.querySelector('#password').value='browser-test-password';document.querySelector('#loginForm button').click()")
            cdp.until("document.querySelector('#message').textContent.includes('만료')")
            with redirect_stdout(io.StringIO()): app.issue_access_code()
            cdp.call('Page.navigate',{'url':app.url+'/#setup_code='+app.setup_code})
            cdp.until("document.querySelector('#message')?.textContent.includes('링크의 설정 코드')")
            cdp.js("document.querySelector('#password').value='browser-test-password';document.querySelector('#loginForm button').click()")
            cdp.until("document.querySelector('#owner').value.length === 64")
            assert cdp.js("document.querySelector('#relay').value")=='wss://relay.example.com'
            cdp.js("document.querySelector('#saveRelay').click()")
            cdp.until("document.querySelector('#relayBadge').textContent === '연결됨'")
            cdp.js("document.querySelector('#download').click()")
            package=tmp/'downloads/Buzz-Windows-Connect.zip';deadline=time.monotonic()+15
            while not package.exists():
                if time.monotonic()>deadline:raise AssertionError('bundle download missing')
                time.sleep(.1)
            with zipfile.ZipFile(package) as archive:pairing=json.loads(archive.read('buzz-pairing.json'))
            # Actual one-use exchange, with a simulated Windows caller in this UI test.
            def post(path,data,token=None):
                headers={'Content-Type':'application/json'}
                if token:headers['Authorization']='Bearer '+token
                req=urllib.request.Request(app.url+path,json.dumps(data).encode(),headers)
                with urllib.request.urlopen(req) as response:return json.load(response)
            connection=post('/api/pair/exchange',{'pairing_code':pairing['pairing_code'],'name':'브라우저 시험 PC'})
            post('/api/device/deploy',{'op':'deploy','agent':{}},connection['token'])
            cdp.js("document.querySelector('#refresh').click()")
            cdp.until("document.querySelectorAll('.bot').length === 2")
            cdp.until("document.querySelector('#message').textContent.includes('서버에 등록')")
            assert '10분 후 만료' not in cdp.js("document.querySelector('#message').textContent")
            assert connection['device_id'] in cdp.js("document.querySelector('#devices').textContent")
            cdp.shot(output/'setup-desktop.png')
            cdp.js("document.querySelector('.bot button').click()")
            cdp.until("document.querySelector('#terminal').textContent.includes('브라우저 동작 시험')")
            cdp.js("document.querySelector('#authInput').value='test-code';document.querySelector('#authForm button').click()")
            cdp.until("document.querySelector('#authInput').value === ''")
            cdp.shot(output/'setup-login-session.png')
            cdp.js("document.querySelector('#cancelAuth').click()")
            cdp.until("document.querySelector('#authStatus').textContent.includes('중지했습니다')")
            verify_login_expiry(cdp, app.rpc)
            output_text=io.StringIO()
            with redirect_stdout(output_text): app.issue_access_code()
            code=output_text.getvalue().split('/#recovery_code=')[1].splitlines()[0]
            saved_devices=dict(app.devices)
            cdp.call('Page.navigate',{'url':app.url+'/#recovery_code='+code})
            cdp.until("document.querySelector('#recoveryCode')?.value.length === 32")
            assert cdp.js('location.hash') == ''
            cdp.shot(output/'setup-recovery.png')
            cdp.js("document.querySelector('#recoveryPassword').value='new-browser-password';document.querySelector('#recoveryForm button').click()")
            cdp.until("document.querySelector('#message').textContent.includes('비밀번호를 다시 설정')")
            assert app.devices == saved_devices
            cdp.js("document.querySelector('#password').value='new-browser-password';document.querySelector('#loginForm button').click()")
            cdp.until("document.querySelector('#workspace').hidden === false")
            cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            cdp.js('window.scrollTo(0,0)')
            assert cdp.js('document.documentElement.scrollWidth <= window.innerWidth'), 'mobile horizontal overflow'
            cdp.shot(output/'setup-mobile.png')
            assert not cdp.errors, cdp.errors
            report={'status':'passed','browser':'Google Chrome headless / CDP',
                    'viewports':[[1440,1120],[390,844]],'console_exceptions':0,
                    'checked':['fragment autofill and immediate URL scrubbing','no-value/manual fallback','malformed/duplicate fragment rejection','expired setup retry','recovery preserves devices and requires new login','first claim','auto Relay discovery confirmation','bundle download','one-use pairing',
                               'device deploy HTTP','bot list','PTY UI input/cancel','expired login retry and transient preservation for both providers','mobile overflow'],
                    'simulated':['Docker broker','official provider login','Windows installer'],
                    'not_proven':['Docker deployment','real AI login/reply','Windows-off scheduled task']}
            (output/'browser-report.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report))
        except Exception:
            if cdp:
                print('Browser failure:', cdp.js('JSON.stringify({url:location.origin+location.pathname,body:document.body?.innerText.slice(0,1500)})'))
                cdp.shot(output/'browser-failure.png')
            raise
        finally:
            if cdp:cdp.ws.close()
            chrome.terminate()
            try:chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:chrome.kill();chrome.wait()
            server.shutdown();server.server_close();thread.join()


if __name__=='__main__':main()
