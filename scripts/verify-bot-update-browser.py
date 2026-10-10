"""Real browser/HTTP controls, simulated Docker job; no live VPS or credentials."""
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
        super().__init__();self.configured=True;self.update={};self.starts=[]
        self.bots=[{'name':'Claude VPS','pubkey':'b'*64,'provider':'claude','status':'stopped','container_running':True}]
    def __call__(self,r):
        if r['op']=='bot-update-preview':return {'ok':True,'name':'Claude VPS','pubkey':'b'*64,'revision':'a'*64,'policy':{'turn_limit':20,'daily_limit':100,'max_turn_seconds':600,'window_seconds':3600}}
        if r['op']=='bot-update':
            self.starts.append(r);self.update={'id':r['request_id'],'pubkey':r['pubkey'],'state':'running'}
            return {'ok':True,'update':self.update}
        answer=super().__call__(r)
        if r['op']=='status':answer['update']=self.update
        return answer

def main():
    output=Path('.sonol-test/runtime/bot-update');output.mkdir(parents=True,exist_ok=True)
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
                broker.update={}
                cdp.call('Network.setUserAgentOverride',{'userAgent':ua,'acceptLanguage':lang})
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<500})
                cdp.call('Page.navigate',{'url':app.url})
                cdp.until("typeof openUpdate === 'function'")
                if not app.account:
                    cdp.js("$('setupCode').value="+json.dumps(app.setup_code)+";$('password').value='test-password-long';$('loginForm button').click()".replace("$('loginForm button')","document.querySelector('#loginForm button')"))
                cdp.until("document.querySelector('.update-bot') !== null")
                before=len(broker.starts)
                cdp.js("document.querySelector('.update-bot').click()")
                cdp.until("$('updateDialog').open")
                assert cdp.js("$('updateDefaults').checked") is False
                if lang=='en-US':assert not re.search('[가-힣]',cdp.js("$('updateDialog').textContent"))
                cdp.shot(output/(lang+'.png'))
                cdp.js("$('cancelUpdate').click()")
                assert len(broker.starts)==before
                cdp.js("document.querySelector('.update-bot').click()")
                cdp.until("$('updateDialog').open")
                cdp.js("$('updateDefaults').checked=true;$('confirmUpdate').click();$('confirmUpdate').click()")
                cdp.until("!$('updateDialog').open && !updateBusy")
                assert len(broker.starts)==before+1 and broker.starts[-1]['use_defaults'] is True
                assert cdp.js("document.querySelector('.update-bot').disabled")
                cdp.call('Page.navigate',{'url':app.url})
                cdp.until("typeof refresh === 'function' && document.querySelector('.update-bot') && !$('updateStatus').hidden && document.querySelector('.update-bot').disabled")
                assert len(broker.starts)==before+1, 'page refresh must not retry a mutation'
                broker.update['state']='succeeded';cdp.js('refresh()')
                cdp.until("!document.querySelector('.update-bot').disabled")
                assert ('업데이트를 확인' in cdp.js("$('updateStatus').textContent")) if lang.startswith('ko') else ('update verified' in cdp.js("$('updateStatus').textContent"))
                for state in ('failed','interrupted'):
                    broker.update['state']=state;broker.update['error']='bot_update_failed_check_status'
                    cdp.js('refresh()')
                    expected=('완료하지 못했습니다' if state=='failed' else '완료 여부를 확인할 수 없습니다') if lang.startswith('ko') else ('did not complete' if state=='failed' else 'completion is unknown')
                    cdp.until("!document.querySelector('.update-bot').disabled && $('updateStatus').textContent.includes("+json.dumps(expected)+")")
                    assert len(broker.starts)==before+1
            print(json.dumps({'ok':True,'locales':['ko-KR','en-US'],'flows':['cancel','explicit-defaults','double-click','refresh-running','completion','failure','interrupted']}))
        finally:
            if cdp:cdp.ws.close()
            chrome.terminate();chrome.wait(timeout=10);server.shutdown();server.server_close()
if __name__=='__main__':main()
