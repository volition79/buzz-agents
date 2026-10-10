"""Real Chrome + HTTP locale checks. Local fixture only; no VPS or provider login."""
import base64
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
import urllib.request

spec = importlib.util.spec_from_file_location('browser_fixture', Path(__file__).with_name('verify-portal-browser.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
ROOT = fixture.ROOT


def main():
    output = ROOT / '.sonol-test/runtime/portal-i18n'
    output.mkdir(parents=True, exist_ok=True)
    checked = []
    with tempfile.TemporaryDirectory(prefix='buzz-i18n-') as directory:
        tmp = Path(directory)
        broker = fixture.FixtureBroker()
        app = fixture.Portal(tmp/'state', 'http://127.0.0.1', local=True, rpc=broker)
        server = fixture.Server(('127.0.0.1', 0), app)
        app.url = 'http://127.0.0.1:' + str(server.server_port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        profile = tmp/'chrome'
        chrome = subprocess.Popen(['google-chrome', '--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
            '--remote-debugging-port=0', '--user-data-dir='+str(profile), '--no-first-run', 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cdp = None
        try:
            deadline = time.monotonic()+15
            while not (profile/'DevToolsActivePort').exists():
                if time.monotonic() > deadline: raise RuntimeError('Chrome did not start')
                time.sleep(.1)
            port = (profile/'DevToolsActivePort').read_text().splitlines()[0]
            with urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list') as r: pages = json.load(r)
            cdp = fixture.CDP(next(p for p in pages if p.get('type')=='page')['webSocketDebuggerUrl'])
            cdp.call('Runtime.enable'); cdp.call('Page.enable')
            cdp.call('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1120,'deviceScaleFactor':1,'mobile':False})
            ua = cdp.js('navigator.userAgent')
            for locale, expected in [('ko-KR,ko,en-US','ko'), ('en-US,en,ko','en'), ('en-GB,en','en'), ('fr-FR,fr,ko','en')]:
                cdp.call('Network.setUserAgentOverride', {'userAgent':ua, 'acceptLanguage':locale})
                cdp.call('Page.navigate', {'url':app.url})
                cdp.until("typeof window.BuzzI18n !== 'undefined' && typeof boot === 'function'")
                assert cdp.js('document.documentElement.lang') == expected
                assert cdp.js('navigator.languages[0]') == locale.split(',')[0]
                if expected == 'en':
                    assert cdp.js("document.title") == 'Buzz · VPS Setup'
                    assert not re.search('[가-힣]', cdp.js('document.body.textContent'))
                    assert cdp.js("document.querySelector('#channel').placeholder") == 'Channel UUID'
                    assert cdp.js("document.querySelector('#terminal').getAttribute('aria-label')") == 'Official sign-in instructions'
                    assert 'Restart' in cdp.js("document.querySelector('#accessHelp').textContent")
                    assert 'portal_recover' not in cdp.js("document.querySelector('#accessHelp').textContent")
                else:
                    assert '최초 설정 코드' in cdp.js("document.querySelector('#setupCodeField').textContent")
                health = cdp.js("botHealth({diagnostic:'runtime_process_limit',resources:{pids_current:251,pids_max:256}})")
                assert '251 / 256' in health
                assert ('한도' in health) if expected == 'ko' else ('limit' in health and not re.search('[가-힣]', health))
                assert 'SECRET' not in cdp.js("botHealth({diagnostic:'SECRET'})")
                assert cdp.js("botHealth({resources:{health_warning:'runtime_process_limit_near_capacity'}})")
                # Real invalid/expired setup-code response must be localized too.
                cdp.js("document.querySelector('#setupCode').value='invalid';document.querySelector('#password').value='test-password-123';document.querySelector('#loginForm button').click()")
                word = '만료' if expected == 'ko' else 'expired'
                cdp.until("document.querySelector('#message').textContent.includes("+json.dumps(word)+")")
                cdp.shot(output/('setup-'+locale.split(',')[0]+'.png'))
                checked.append(locale)
            # Actual first setup and dynamic bot statuses in English; user names stay unchanged.
            cdp.js('document.querySelector("#setupCode").value='+json.dumps(app.setup_code))
            cdp.js("document.querySelector('#loginForm button').click()")
            cdp.until("document.querySelector('#owner').value.length === 64")
            assert 'Relay was found' in cdp.js("document.querySelector('#message').textContent")
            cdp.js("document.querySelector('#saveRelay').click()")
            cdp.until("document.querySelector('#relayBadge').textContent === 'Connected'")
            # Saved Relay, not the setup hostname or a developer-specific address.
            assert cdp.js("document.querySelector('#communityRelay').value") == 'wss://relay.example.com'
            assert not cdp.js("document.querySelector('#copyCommunityRelay').disabled")
            for locale, text in [('ko-KR,ko','주소를 복사했습니다'), ('en-US,en','Address copied')]:
                cdp.call('Network.setUserAgentOverride', {'userAgent':ua, 'acceptLanguage':locale})
                cdp.call('Page.navigate', {'url':app.url})
                cdp.until("document.querySelector('#communityRelay')?.value === 'wss://relay.example.com'")
                cdp.js("document.querySelectorAll('#buzzGuide img').forEach(i=>i.loading='eager')")
                try:
                    cdp.until("[...document.querySelectorAll('#buzzGuide img')].length === 8 && [...document.querySelectorAll('#buzzGuide img')].every(i=>i.complete && i.naturalWidth>0)")
                except AssertionError:
                    print(cdp.js("[...document.querySelectorAll('#buzzGuide img')].map(i=>({src:i.getAttribute('src'),pending:i.dataset.src,complete:i.complete,width:i.naturalWidth}))"))
                    print(cdp.errors)
                    raise
                assert 'Skip for now' in cdp.js("document.querySelector('#buzzGuide').textContent")
                assert 'Join a community' in cdp.js("document.querySelector('#buzzGuide').textContent")
                if locale.startswith('en'):
                    assert not re.search('[가-힣]', cdp.js("document.querySelector('#buzzGuide').textContent"))
                    assert not re.search('[가-힣]', cdp.js("[...document.querySelectorAll('#buzzGuide img')].map(i=>i.alt).join(' ')") )
                # Numbered steps are mutually exclusive, accessible and independent of setup state.
                assert cdp.js("document.querySelectorAll('#buzzGuide [role=tab]').length") == 6
                assert cdp.js("document.querySelector('#guidePrev').disabled")
                for step in range(6):
                    cdp.js(f"document.querySelector('#guideTab{step}').click()")
                    assert cdp.js("document.querySelectorAll('#buzzGuide [role=tabpanel]:not([hidden])').length") == 1
                    assert cdp.js(f"document.querySelector('#guideTab{step}').getAttribute('aria-selected')") == 'true'
                    assert cdp.js("document.querySelector('#guideProgress').textContent") == f'{step+1} / 6'
                assert cdp.js("document.querySelector('#guideNext').disabled")
                cdp.js("document.querySelector('#guideTab5').focus()")
                cdp.call('Input.dispatchKeyEvent', {'type':'keyDown','key':'Home','code':'Home'})
                assert cdp.js("document.activeElement.id") == 'guideTab0'
                cdp.call('Input.dispatchKeyEvent', {'type':'keyDown','key':'ArrowRight','code':'ArrowRight'})
                assert cdp.js("document.activeElement.id") == 'guideTab1'
                assert not cdp.js("document.querySelector('#guidePanel1').hidden")
                cdp.js("document.querySelector('#guideNext').click()")
                assert not cdp.js("document.querySelector('#guidePanel2').hidden")
                cdp.js("document.querySelector('#guidePrev').click()")
                assert not cdp.js("document.querySelector('#guidePanel1').hidden")
                # Clipboard mock only; never touch the user's real clipboard.
                cdp.js("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>{window.copiedRelay=value}}})")
                cdp.js("document.querySelector('#copyCommunityRelay').click()")
                cdp.until("document.querySelector('#relayCopyStatus').textContent.includes("+json.dumps(text)+")")
                assert cdp.js('window.copiedRelay') == 'wss://relay.example.com'
                cdp.js("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw new Error('denied')}}})")
                cdp.js("document.querySelector('#copyCommunityRelay').click()")
                cdp.until("document.querySelector('#relayCopyStatus').textContent.includes('Ctrl+C')")
                assert cdp.js("document.querySelector('#communityRelay').selectionEnd") == len('wss://relay.example.com')
                for width,height in [(1440,1120),(390,844)]:
                    cdp.call('Emulation.setDeviceMetricsOverride', {'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<500})
                    for step in range(6):
                        cdp.js(f"document.querySelector('#guideTab{step}').click();document.querySelector('.guide-tabs').scrollIntoView()")
                        assert cdp.js('document.documentElement.scrollWidth <= window.innerWidth'), 'guide overflow'
                        assert cdp.js(f"document.querySelector('#guidePanel{step}').getBoundingClientRect().height > 0")
                        cdp.shot(output/f'guide-{locale.split(",")[0]}-{width}-step{step+1}.png')
            cdp.call('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1120,'deviceScaleFactor':1,'mobile':False})
            broker({'op':'deploy'})
            broker.bots[0]['name'] = '연결됨'  # Same as a translation key: never translate user data.
            cdp.js("document.querySelector('#refresh').click()")
            cdp.until("document.querySelectorAll('.bot').length === 2")
            assert cdp.js("document.querySelector('.bot strong').textContent") == '연결됨'
            assert cdp.js("document.querySelector('.bot .state').textContent") == 'Sign-in required'
            assert cdp.js("document.querySelector('.bot button').textContent") == 'Sign in'
            cdp.js("document.querySelector('.bot button').click()")
            cdp.until("document.querySelector('#terminal').textContent.includes('브라우저 동작 시험')")
            assert cdp.js("document.querySelector('#authLinks a').textContent").startswith('Open official sign-in')
            cdp.js("document.querySelector('#cancelAuth').click()")
            cdp.until("document.querySelector('#authStatus').textContent === 'Sign-in session canceled.'")
            # Recovery + already-claimed login labels also use the selected language.
            with redirect_stdout(io.StringIO()) as logs: app.issue_access_code()
            code = logs.getvalue().split('/#recovery_code=')[1].splitlines()[0]
            cdp.call('Page.navigate', {'url':app.url+'/#recovery_code='+code})
            cdp.until("document.querySelector('#recoveryCode')?.value.length === 32")
            assert cdp.js('location.hash') == ''
            assert cdp.js("document.querySelector('#passwordLabel').textContent") == 'Setup password'
            assert 'Recovery code filled in' in cdp.js("document.querySelector('#message').textContent")
            cdp.shot(output/'recovery-en.png')
            for width, height in [(1440,1120), (390,844)]:
                cdp.call('Emulation.setDeviceMetricsOverride', {'width':width,'height':height,'deviceScaleFactor':1,'mobile':width<500})
                assert cdp.js('document.documentElement.scrollWidth <= window.innerWidth'), 'horizontal overflow'
                cdp.shot(output/f'recovery-en-{width}.png')
            fixture.verify_login_expiry(cdp, broker)
            assert not cdp.errors, cdp.errors
            report = {'status':'passed', 'locales':checked, 'dynamic_messages':True, 'user_and_provider_text_preserved':True,
                      'recovery':True, 'guide_images_and_copy_both_languages':True, 'viewports':[[1440,1120],[390,844]], 'console_exceptions':0,
                      'not_proven':['live VPS deployment','real AI login or task execution']}
            (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report))
        finally:
            if cdp: cdp.ws.close()
            chrome.terminate()
            try: chrome.wait(timeout=5)
            except subprocess.TimeoutExpired: chrome.kill(); chrome.wait()
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': main()
