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
        super().__init__();self.configured=True;self.update={};self.starts=[];self.retries=0;self.memory={'desired_mb':1536,'applied_mb':1536,'configured_mb':1536,'pending':False};self.saves=[]
        self.bots=[{'name':'Claude VPS','pubkey':'b'*64,'provider':'claude','status':'stopped','container_running':True,'memory':self.memory}]
    def __call__(self,r):
        if r['op']=='release-status':return {'ok':True,'release_update':{'state':'attention','target':'a'*40,'bots':{'b'*64:{'name':'Claude VPS','state':'waiting','error':'update_requires_interruption_confirmation'}}}}
        if r['op']=='release-retry':
            self.retries+=1;return {'ok':True}
        if r['op']=='bot-update-preview':return {'ok':True,'name':'Claude VPS','pubkey':'b'*64,'revision':'a'*64,'memory':self.memory,'policy':{'turn_limit':20,'daily_limit':100,'max_turn_seconds':600,'window_seconds':3600}}
        if r['op']=='bot-memory':
            self.saves.append(r)
            if r['memory_mb']>4096:return {'ok':False,'error':'aggregate_memory_budget_exceeded'}
            self.memory.update(desired_mb=r['memory_mb'],pending=r['memory_mb']!=self.memory['applied_mb'])
            return {'ok':True,'memory':self.memory}
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
        chrome=subprocess.Popen(['google-chrome','--headless=new','--no-first-run','--no-default-browser-check','--no-sandbox','--disable-dev-shm-usage','--remote-debugging-port=0','--user-data-dir='+str(root/'chrome'),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
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
                broker.memory.update(desired_mb=1536,applied_mb=1536,pending=False)
                cdp.call('Network.setUserAgentOverride',{'userAgent':ua,'acceptLanguage':lang})
                cdp.call('Emulation.setDeviceMetricsOverride',{'width':width,'height':1000,'deviceScaleFactor':1,'mobile':width<500})
                cdp.js('window.__previousDocument=true')
                cdp.call('Page.navigate',{'url':app.url})
                cdp.until("!window.__previousDocument && typeof openUpdate === 'function' && !document.querySelector('#loginForm button').disabled")
                if not app.account:
                    cdp.js("$('setupCode').value="+json.dumps(app.setup_code)+";$('password').value='test-password-long';$('loginForm button').click()".replace("$('loginForm button')","document.querySelector('#loginForm button')"))
                cdp.until("document.querySelector('.update-bot') !== null")
                cdp.until("!$('releaseRetry').hidden && $('releaseUpdate').textContent.includes('Claude VPS')")
                if lang=='en-US':assert not re.search('[가-힣]',cdp.js("$('releaseUpdate').textContent"))
                cdp.js("$('updateGuide').open=true")
                guide=cdp.js("$('updateGuide').innerText")
                if lang=='en-US':
                    assert not re.search('[가-힣]',guide)
                    assert 'not guaranteed to resume' in guide and 'not a new-release notification' in guide
                    assert 'Stopped bots may be updated' in guide
                    assert cdp.js("$('releaseRetry').textContent") == 'Retry update application'
                else:
                    assert '자동 재개는 보장하지 않습니다' in guide and '새 버전 출시 알림은 아닙니다' in guide
                assert cdp.js("$('updateGuide').querySelectorAll('li').length") == 5
                steps=cdp.js("Array.from($('updateGuide').querySelectorAll('li'), e=>e.innerText)")
                assert 'Shutdown' in steps[1] and 'Docker Manager' in steps[2]
                assert ('Closing Windows Buzz does not stop VPS bots' in steps[1]) if lang=='en-US' else ('Windows Buzz 창만 닫는 것은 VPS 봇 중지가 아닙니다' in steps[1])
                assert cdp.js("document.documentElement.scrollWidth <= window.innerWidth"), 'guide must fit mobile viewport'
                cdp.js("$('updateGuide').open=false")
                retry_before=broker.retries
                cdp.js("$('releaseRetry').click()")
                cdp.until("!$('releaseRetry').disabled")
                assert broker.retries==retry_before+1
                before=len(broker.starts)
                cdp.until("document.querySelector('.memory-select') !== null")
                cdp.js("var s=document.querySelector('.memory-select');s.value='3072';s.dispatchEvent(new Event('change'))")
                cdp.until("!memoryBusy && document.querySelector('.memory-status').textContent.includes("+json.dumps('Pending change' if lang=='en-US' else '변경 대기')+")")
                assert len(broker.starts)==before and broker.memory['applied_mb']==1536
                assert broker.saves[-1]['memory_mb']==3072
                cdp.js("var s=document.querySelector('.memory-select');s.value='8192';s.dispatchEvent(new Event('change'))")
                cdp.until("!memoryBusy && document.querySelector('.memory-select').value==='3072'")
                assert broker.memory['desired_mb']==3072 and len(broker.starts)==before
                if lang=='en-US':assert not re.search('[가-힣]',cdp.js("document.querySelector('.memory-control').textContent"))
                cdp.js("document.querySelector('.update-bot').click()")
                cdp.until("$('updateDialog').open")
                assert cdp.js("$('updateDefaults').checked") is False
                assert '1.5 GiB' in cdp.js("$('updateMemory').textContent") and '3 GiB' in cdp.js("$('updateMemory').textContent")
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
                cdp.js('window.__previousDocument=true')
                cdp.call('Page.navigate',{'url':app.url})
                cdp.until("!window.__previousDocument && typeof refresh === 'function' && document.querySelector('.update-bot') && !$('updateStatus').hidden && document.querySelector('.update-bot').disabled")
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
            print(json.dumps({'ok':True,'locales':['ko-KR','en-US'],'flows':['ram-stage-no-restart','ram-capacity-refusal','ram-preview','cancel','explicit-defaults','double-click','refresh-running','completion','failure','interrupted']}))
        except Exception:
            if cdp:print(cdp.js('document.body.innerText'))
            raise
        finally:
            if cdp:cdp.ws.close()
            chrome.terminate();chrome.wait(timeout=10);server.shutdown();server.server_close()
if __name__=='__main__':main()
