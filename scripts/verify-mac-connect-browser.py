"""Local Chrome + real portal HTTP; fake VPS only. No production state."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile

spec = importlib.util.spec_from_file_location('fixture', Path(__file__).with_name('verify-portal-browser.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def main():
    with tempfile.TemporaryDirectory(prefix='buzz-mac-browser-') as directory:
        root = Path(directory)
        (root/'Buzz-VPS-Connect.exe').write_bytes(b'MZ-fixture')
        broker = fixture.FixtureBroker()
        broker.configured = True
        app = fixture.Portal(root/'state', 'http://127.0.0.1', local=True, rpc=broker, artifacts=root)
        server = fixture.Server(('127.0.0.1', 0), app)
        app.url = 'http://127.0.0.1:'+str(server.server_port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        chrome = subprocess.Popen(['google-chrome','--headless=new','--no-sandbox','--disable-dev-shm-usage',
                                   '--remote-debugging-port=0','--user-data-dir='+str(root/'chrome'),'about:blank'],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cdp = None
        try:
            deadline = time.monotonic()+15
            while not (root/'chrome/DevToolsActivePort').exists():
                if time.monotonic()>deadline: raise RuntimeError('Chrome startup timeout')
                time.sleep(.1)
            port = (root/'chrome/DevToolsActivePort').read_text().splitlines()[0]
            pages = json.load(urllib.request.urlopen('http://127.0.0.1:'+port+'/json/list'))
            cdp = fixture.CDP(next(p for p in pages if p.get('type')=='page')['webSocketDebuggerUrl'])
            cdp.call('Runtime.enable'); cdp.call('Page.enable')
            downloads = root/'downloads'; downloads.mkdir()
            cdp.call('Browser.setDownloadBehavior', {'behavior':'allow','downloadPath':str(downloads)})
            cdp.call('Page.navigate', {'url':app.url})
            cdp.until("typeof boot === 'function' && !document.querySelector('#loginForm button').disabled")
            cdp.js("$('setupCode').value="+json.dumps(app.setup_code))
            cdp.js("$('password').value='fixture-password-long';document.querySelector('#loginForm button').click()")
            cdp.until("!$('workspace').hidden && !$('download').disabled")
            assert cdp.js("$('macConnect').hidden"), 'unpackaged Mac offered'
            mac = root/'macos'/'Buzz-VPS-Connect-macos-arm64'
            mac.parent.mkdir(); mac.write_bytes(b'\xcf\xfa\xed\xfe-fixture')
            cdp.js('refresh()')
            assert cdp.js("!$('macConnect').hidden && !$('downloadMac').disabled")
            for button, filename, executable in (
                ('download','Buzz-Windows-Connect.zip','Buzz-VPS-Connect.exe'),
                ('downloadMac','Buzz-Mac-AppleSilicon-Connect.zip','Buzz-VPS-Connect.command')):
                cdp.js("$('"+button+"').click()")
                deadline = time.monotonic()+10
                while not (downloads/filename).exists():
                    if time.monotonic()>deadline: raise AssertionError('download missing: '+filename)
                    time.sleep(.1)
                with zipfile.ZipFile(io.BytesIO((downloads/filename).read_bytes())) as archive:
                    assert executable in archive.namelist()
                    assert json.loads(archive.read('buzz-pairing.json'))['endpoint'] == app.url
                cdp.until("!$('"+button+"').disabled")
            mac.unlink(); cdp.js('refresh()')
            assert cdp.js("$('macConnect').hidden")
            assert not cdp.errors, 'browser exception'
            print('PASS: Mac capability visibility, Windows default, both actual downloads, missing-artifact hide; fake VPS only')
        finally:
            if cdp: cdp.ws.close()
            chrome.terminate(); chrome.wait(timeout=10)
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': main()
