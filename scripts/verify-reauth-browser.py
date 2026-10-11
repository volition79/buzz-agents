"""Actual ko/en browser + admin HTTP; provider login is an explicit fixture."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.request
spec=importlib.util.spec_from_file_location('fixture',Path(__file__).with_name('verify-portal-browser.py'))
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

class Broker(f.FixtureBroker):
    def __init__(self):
        super().__init__();self.configured=True;self.job={};self.starts=[]
        self.bots=[{'name':'Claude VPS','pubkey':'b'*64,'provider':'claude','status':'running','container_running':True}]
    def __call__(self,r):
        if r['op']=='reauth-start':
            self.starts.append(r);self.job={'id':r['request_id'],'pubkey':r['pubkey'],'name':'Claude VPS','state':'preparing'}
            return {'ok':True,'reauth':self.job}
        if r['op']=='reauth-status':
            result={'ok':True,'reauth':self.job}
            if self.job.get('state')=='authenticating':result['session']='reauth-test-session'
            return result
        if r['op']=='auth-cancel':
            self.job={**self.job,'state':'failed','error':'reauth_login_incomplete'}
            return {'ok':True}
        return super().__call__(r)

def main():
    out=Path('.sonol-test/runtime/reauth');out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);broker=Broker();app=f.Portal(root/'state','http://127.0.0.1',local=True,rpc=broker)
        server=f.Server(('127.0.0.1',0),app);app.url='http://127.0.0.1:'+str(server.server_port)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        chrome=subprocess.Popen(['google-chrome','--headless=new','--no-first-run','--no-default-browser-check','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-port=0','--user-data-dir='+str(root/'chrome'),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        cdp=None
        try:
            deadline=time.monotonic()+15
            while not (root/'chrome/DevToolsActivePort').exists():
                assert time.monotonic()<deadline;time.sleep(.1)
            port=(root/'chrome/DevToolsActivePort').read_text().splitlines()[0]
            pages=json.load(urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list'))
            cdp=f.CDP(next(p for p in pages if p.get('type')=='page')['webSocketDebuggerUrl'])
            cdp.call('Runtime.enable');cdp.call('Page.enable');cdp.call('Network.enable')
            ua=cdp.js('navigator.userAgent')
            for lang,width in [('ko-KR',1440),('en-US',390)]:
                broker.job={};broker.starts=[]
                cdp.call('Network.setUserAgentOverride',{'userAgent':ua,'acceptLanguage':lang})
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<500})
                def navigate():
                    cdp.js('window.__priorDocument=true');cdp.call('Page.navigate',{'url':app.url})
                    cdp.until("!window.__priorDocument && typeof refreshReauth==='function' && !document.querySelector('#loginForm button').disabled")
                navigate()
                if not app.account:
                    cdp.js("$('setupCode').value="+json.dumps(app.setup_code)+";$('password').value='test-password-long';document.querySelector('#loginForm button').click()")
                cdp.until("!$('workspace').hidden && document.querySelector('.reauth-bot') && !reauthBusy")
                assert not cdp.js("document.querySelector('.reauth-bot').disabled")
                assert cdp.js("document.querySelector('.bot-actions button').disabled")
                cdp.js("window.confirm=()=>false;document.querySelector('.reauth-bot').click()")
                assert not broker.starts
                cdp.js("window.confirm=()=>true;document.querySelector('.reauth-bot').click()")
                cdp.until('reauthBusy');cdp.until("document.querySelector('.reauth-bot').disabled")
                assert len(broker.starts)==1
                broker.job['state']='authenticating';cdp.js('refresh()');cdp.until("authSession==='reauth-test-session'")
                navigate();cdp.until("authSession==='reauth-test-session' && !$('authForm').hidden")
                assert len(broker.starts)==1  # Refresh resumes UI; never starts login twice.
                cdp.js("$('cancelAuth').click()")
                cdp.until("authSession===null && !reauthBusy && !document.querySelector('.reauth-bot').disabled")
                assert ('대기' if lang.startswith('ko') else 'waiting') in cdp.js("$('authStatus').textContent")
                cdp.js("window.confirm=()=>true;document.querySelector('.reauth-bot').click()")
                cdp.until("reauthBusy && document.querySelector('.reauth-bot').disabled");assert len(broker.starts)==2
                broker.job['state']='succeeded';cdp.js('refresh()');cdp.until('!reauthBusy')
                assert ('다시 실행' if lang.startswith('ko') else 'starting again') in cdp.js("$('authStatus').textContent")
                cdp.js("$('authPanel').scrollIntoView({block:'center'})");cdp.shot(out/(lang+'.png'))
                # A later ordinary sign-in must not be overwritten by the last reauth job.
                cdp.js("startLogin({pubkey:'"+'c'*64+"',name:'Other bot'})")
                cdp.until("authSession==='fixture-session'")
                cdp.js("authSession=null;$('authStatus').textContent='ordinary-sign-in-result';refresh()")
                cdp.until("document.querySelector('.reauth-bot')!==null")
                assert cdp.js("$('authStatus').textContent")=='ordinary-sign-in-result'
                assert not cdp.errors,cdp.errors
                print(lang,'running-bot confirmation, refresh, cancellation, retry and completion passed')
        finally:
            if cdp:cdp.ws.close()
            chrome.terminate();chrome.wait(timeout=10);server.shutdown();server.server_close()
if __name__=='__main__':main()
