"""Cold Chrome through the actual retained two-slot bridge; no live credentials.

Incident 2026-10-09, source daccc5f: parallel CSS/i18n/app requests drop
scripts, and native login form GET /? produces HTTP400. RPC is a fixture;
HTTP bridge, browser events, first claim, password and session are real.
Post-login regression adds slow guide images and sanitized gateway failures;
manual Relay discovery was observed working on 2026-10-09.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.request

spec = importlib.util.spec_from_file_location('fixture', Path(__file__).with_name('verify-portal-browser.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from buzz_agents import portal
from buzz_agents.portal_route import Server as Route


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--web-root', type=Path, help='Original source for the negative control')
    args = parser.parse_args()
    if args.web_root:
        portal.WEB = args.web_root.resolve()
    with tempfile.TemporaryDirectory(prefix='buzz-route-browser-') as directory:
        tmp = Path(directory)
        app = fixture.Portal(tmp/'state', 'http://127.0.0.1', local=True, rpc=fixture.FixtureBroker())
        upstream = fixture.Server(('127.0.0.1', 0), app)
        calls, gateway = {}, {}
        class IncidentHandler(portal.Handler):
            def dispatch(self):
                calls[self.path] = calls.get(self.path, 0)+1
                if self.path.startswith('/guide/'): time.sleep(1)
                remaining = gateway.get(self.path, 0)
                if remaining:
                    gateway[self.path] = remaining-1
                    if self.command == 'POST': self.request_body()
                    return self.respond(502, b'Bad Gateway', 'text/plain')
                return super().dispatch()
        upstream.RequestHandlerClass = IncidentHandler
        route = Route(('127.0.0.1', 0), '', '127.0.0.1', upstream.server_port)
        route.hostname = '127.0.0.1:'+str(route.server_port)
        app.url = 'http://'+route.hostname
        for server in (upstream, route):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        chrome = subprocess.Popen(['google-chrome', '--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
            '--remote-debugging-port=0', '--user-data-dir='+str(tmp/'chrome'), 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cdp = None
        try:
            deadline = time.monotonic()+15
            while not (tmp/'chrome/DevToolsActivePort').exists():
                if time.monotonic() > deadline: raise RuntimeError('Chrome startup timeout')
                time.sleep(.1)
            port = (tmp/'chrome/DevToolsActivePort').read_text().splitlines()[0]
            pages = json.load(urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list'))
            cdp = fixture.CDP(next(p for p in pages if p.get('type')=='page')['webSocketDebuggerUrl'])
            cdp.call('Runtime.enable'); cdp.call('Page.enable'); cdp.call('Network.enable')
            cdp.call('Emulation.setDeviceMetricsOverride', {'width':1920,'height':1080,'deviceScaleFactor':1,'mobile':False})
            cdp.call('Network.setCacheDisabled', {'cacheDisabled':True})
            cdp.call('Network.setExtraHTTPHeaders', {'headers':{'X-Forwarded-Proto':'https'}})
            # Cold page loads must initialize through the unchanged two-slot bridge.
            for _ in range(5):
                cdp.call('Page.navigate', {'url':app.url})
                cdp.until("typeof window.BuzzI18n === 'object' && typeof boot === 'function' && !document.querySelector('#loginForm button').disabled")
                assert cdp.js('location.search') == ''
            cdp.js("document.querySelector('#setupCode').value='invalid';document.querySelector('#password').value='fixture-password-123';document.querySelector('#loginForm button').click()")
            cdp.until("!document.querySelector('#message').hidden && document.querySelector('#message').className === 'error'")
            assert cdp.js('location.search') == '' and not app.account
            gateway['/api/status'] = 1
            cdp.js('document.querySelector("#setupCode").value='+json.dumps(app.setup_code))
            cdp.js("document.querySelector('#loginForm button').click()")
            cdp.until("document.querySelector('#owner').value.length === 64")
            assert app.account and cdp.js('location.search') == ''
            assert calls['/api/status'] == 2, 'transient read should retry once'
            assert calls['/api/login'] == 2, 'invalid attempt and one valid claim only'
            cdp.until("[...document.querySelectorAll('#buzzGuide img')].every(i=>i.complete && i.naturalWidth>0)")
            # Persistent gateway failure is bounded and has a user-operated retry.
            gateway['/api/status'] = 3
            before = calls['/api/status']
            cdp.call('Page.navigate', {'url':app.url})
            cdp.until("document.querySelector('#retryStartup') && !document.querySelector('#retryStartup').hidden && !document.querySelector('#message').hidden")
            assert calls['/api/status']-before == 3
            assert 'JSON' not in cdp.js("document.querySelector('#message').textContent")
            assert 'Bad Gateway' not in cdp.js("document.querySelector('#message').textContent")
            cdp.js("document.querySelector('#retryStartup').click()")
            cdp.until("document.querySelector('#owner').value.length === 64 && document.querySelector('#retryStartup').hidden")
            cdp.js("document.querySelector('#logout').click()")
            cdp.until("document.querySelector('#setupCodeField')?.hidden && !document.querySelector('#loginPanel').hidden && !document.querySelector('#loginForm button').disabled")
            gateway['/api/login'] = 1
            before = calls['/api/login']
            cdp.js("document.querySelector('#password').value='fixture-password-123';document.querySelector('#loginForm button').click()")
            cdp.until("!document.querySelector('#message').hidden && !document.querySelector('#loginForm button').disabled")
            assert calls['/api/login']-before == 1, 'non-idempotent login must never auto-retry'
            assert not cdp.js("document.querySelector('#loginPanel').hidden")
            cdp.js("document.querySelector('#loginForm button').click()")
            cdp.until("document.querySelector('#owner').value.length === 64 && !document.querySelector('#workspace').hidden")
            # Script unavailable: fail closed, give reload guidance, never GET /?.
            cdp.call('Network.setBlockedURLs', {'urls':['*/setup.js']})
            cdp.call('Page.navigate', {'url':app.url})
            cdp.until("document.querySelector('#startupNote') !== null")
            assert cdp.js("document.querySelector('#loginForm button').disabled")
            assert not cdp.js("document.querySelector('#startupNote').hidden")
            assert 'refresh' in cdp.js("document.querySelector('#startupNote').textContent")
            cdp.js("document.querySelector('#password').value='fixture-password-123';document.querySelector('#loginForm').requestSubmit()")
            time.sleep(.3)
            assert cdp.js('location.href') == app.url+'/', 'native form navigation must be blocked'
            assert not cdp.errors, cdp.errors
            print(json.dumps({'status':'passed','bridge_slots':2,'cold_loads':5,
                'first_claim_and_existing_password_login':True,'invalid_code_stays_on_page':True,
                'slow_images_and_transient_gateway':True,'bounded_read_retry_and_manual_retry':True,'login_not_retried':True,
                'missing_script_fail_closed':True,'live_VPS_mutation':False}))
        finally:
            if cdp: cdp.ws.close()
            chrome.terminate()
            try: chrome.wait(timeout=5)
            except subprocess.TimeoutExpired: chrome.kill();chrome.wait()
            for server in (route,upstream): server.shutdown();server.server_close()


if __name__ == '__main__': main()
