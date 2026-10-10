"""Real browser/HTTP login links, simulated provider authentication; no live VPS or credentials."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
import urllib.request

spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('verify-portal-browser.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

class Broker(f.FixtureBroker):
    def __init__(self):
        super().__init__();self.configured=True;self.output='';self.inputs=[]
        self.bots=[{'name':'Claude VPS','pubkey':'b'*64,'provider':'claude','status':'needs_login','container_running':True}]
    def __call__(self,r):
        if r['op']=='auth-poll':return {'ok':True,'output':self.output,'done':False,'success':False}
        if r['op']=='auth-input':self.inputs.append(r['text']);return {'ok':True}
        return super().__call__(r)

def main():
    output=Path('.sonol-test/runtime/login-links');output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);broker=Broker();app=f.Portal(root/'state','http://127.0.0.1',local=True,rpc=broker)
        server=f.Server(('127.0.0.1',0),app);app.url='http://127.0.0.1:'+str(server.server_port)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        chrome=subprocess.Popen(['google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-port=0','--user-data-dir='+str(root/'chrome'),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        cdp=None
        try:
            deadline=time.monotonic()+15
            while not (root/'chrome/DevToolsActivePort').exists():
                if time.monotonic()>deadline:raise RuntimeError('chrome timeout')
                time.sleep(.1)
            port=(root/'chrome/DevToolsActivePort').read_text().splitlines()[0]
            page=next(p for p in json.load(urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list')) if p.get('type')=='page')
            cdp=f.CDP(page['webSocketDebuggerUrl']);cdp.call('Runtime.enable');cdp.call('Page.enable');cdp.call('Network.enable')
            ua=cdp.js('navigator.userAgent')
            for lang,width in [('ko-KR',1440),('en-US',390)]:
                cdp.call('Network.setUserAgentOverride',{'userAgent':ua,'acceptLanguage':lang})
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<500})
                cdp.call('Page.navigate',{'url':app.url})
                cdp.until("document.readyState === 'complete' && typeof startLogin === 'function' && !document.querySelector('#loginForm button').disabled")
                cdp.call('Emulation.setFocusEmulationEnabled', {'enabled':True})
                if not app.account:
                    cdp.js("$('setupCode').value="+json.dumps(app.setup_code)+";$('password').value='test-password-long';document.querySelector('#loginForm button').click()")
                try: cdp.until("!$('workspace').hidden && !initializing")
                except Exception:
                    print(cdp.js("document.body.innerText"));raise
                cdp.js("startLogin({pubkey:'"+'b'*64+"',name:'Claude VPS'})")
                url='https://claude.com/cai/oauth/authorize?state=fixture-only&redirect_uri=https%3A%2F%2Fexample.com&scope=user%3Aprofile+user%3Ainference&code_challenge=fixture'
                for transcript in [url,'\x1b[32m'+url+'\x1b[0m','\x1b]8;;'+url+'\x1b\\Open official login\x1b]8;;\x1b\\']:
                    broker.output=transcript;cdp.js('poll()')
                    cdp.until("document.querySelector('#authLinks a')?.href === "+json.dumps(url))
                    assert cdp.js("document.querySelector('.auth-url').value") == url
                    assert cdp.js("document.querySelector('#authLinks a').target === '_blank' && document.querySelector('#authLinks a').rel === 'noopener noreferrer'")
                cdp.call('Browser.grantPermissions',{'origin':app.url,'permissions':['clipboardReadWrite','clipboardSanitizedWrite']})
                cdp.call('Runtime.evaluate',{'expression':"document.querySelector('.auth-link button').click()",'userGesture':True})
                cdp.until("document.querySelector('.auth-link [role=status]').textContent.length > 0")
                assert cdp.js('navigator.clipboard.readText()')==url
                cdp.js("navigator.clipboard.writeText=async()=>{throw new Error('fixture clipboard denied')};document.querySelector('.auth-link button').click()")
                cdp.until("document.activeElement.className === 'auth-url'")
                assert cdp.js('document.activeElement.selectionEnd - document.activeElement.selectionStart')==len(url)
                cdp.js('poll()')
                assert cdp.js("document.activeElement.className === 'auth-url'")
                if lang=='en-US':assert not re.search('[가-힣]',cdp.js("$('authLinks').textContent"))
                assert cdp.js('document.documentElement.scrollWidth <= innerWidth'), 'horizontal overflow'
                cdp.js("$('authPanel').scrollIntoView({block:'center'})")
                cdp.shot(output/(lang+'.png'))
                cdp.js("$('authInput').value='fixture-code';$('authForm').requestSubmit()")
                cdp.until("$('authInput').value === ''")
                cdp.js("$('cancelAuth').click()")
                cdp.until("authSession === null && !$('authLinks').children.length")
                assert 'fixture-code' in broker.inputs
                cdp.js("startLogin({pubkey:'"+'b'*64+"',name:'Codex VPS'})")
                broker.output='https://auth.openai.com/codex/device https://claude.com.evil.example/cai/oauth/authorize https://example.com'
                cdp.js('poll()')
                cdp.until("document.querySelector('#authLinks a')?.href === 'https://auth.openai.com/codex/device'")
                assert cdp.js("$('authLinks').children.length")==1
                cdp.js("$('cancelAuth').click()")
                cdp.until('authSession === null')
            assert not cdp.errors, cdp.errors
            print(json.dumps({'ok':True,'locales':['ko-KR','en-US'],'flows':['Claude-domain','ANSI','OSC8','clipboard','manual-copy','poll-focus','code-input','cancel','Codex','untrusted-hosts']}))
        finally:
            if cdp:cdp.ws.close()
            chrome.terminate();chrome.wait(timeout=10);server.shutdown();server.server_close()
if __name__=='__main__':main()
