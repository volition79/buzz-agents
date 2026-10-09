"""HTTPS-terminated first-run portal. No Docker socket, root password or human nsec.

Browser administrator and Windows deploy credentials are distinct. Only the
administrator can see interactive official-login output or configure schedules.
"""
from collections import deque
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import re
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit
import zipfile
from .common import ToolError
from .policy import atomic_json, read_json

LIMIT = 512 * 1024
TOKEN = re.compile(r'[a-zA-Z0-9_-]{32,100}\Z')
WEB = Path(__file__).with_name('web')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def origin_url(value, local=False):
    url = urlsplit(value)
    if (url.scheme != 'https' and not (local and url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost'))
            or not url.hostname or url.username or url.password or url.path not in ('', '/')
            or url.query or url.fragment):
        raise ToolError('https_public_url_required')
    return value.rstrip('/')


def broker_call(request, path='/rpc/broker.sock'):
    data = json.dumps(request, ensure_ascii=False).encode() + b'\n'
    if len(data) > LIMIT:
        raise ToolError('request_too_large')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(245)
        sock.connect(path)
        sock.sendall(data)
        with sock.makefile('rb') as stream:
            raw = stream.readline(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ToolError('broker_response_too_large')
    answer = json.loads(raw)
    if not isinstance(answer, dict) or answer.get('ok') is not True:
        code = answer.get('error', '') if isinstance(answer, dict) else ''
        raise ToolError(code if re.fullmatch(r'[a-zA-Z0-9_]{1,160}', code) else 'broker_failed')
    return answer


class Portal:
    def __init__(self, directory, public_url, rpc=broker_call, clock=time.time, local=False, artifacts=None):
        self.root = Path(directory)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.url = origin_url(public_url, local)
        self.local, self.rpc, self.clock = local, rpc, clock
        self.artifacts = Path(artifacts or '/artifacts')
        self.lock = threading.RLock()
        self.sessions, self.grants = {}, {}
        self.attempts = deque()
        self.setup_code = secrets.token_urlsafe(24)
        self.setup_deadline = clock() + 3600
        self.account = read_json(self.root / 'account.json', {})
        self.devices = read_json(self.root / 'devices.json', {})

    def throttle(self):
        # Global bounded rate limit avoids trusting spoofable forwarded client IPs.
        now = self.clock()
        while self.attempts and self.attempts[0] < now - 60:
            self.attempts.popleft()
        if len(self.attempts) >= 12:
            raise ToolError('try_again_in_one_minute')
        self.attempts.append(now)

    @staticmethod
    def password_hash(password, salt):
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise ToolError('settings_password_minimum_12_characters')
        return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

    def login(self, data):
        with self.lock:
            self.throttle()
            password = data.get('password')
            if not self.account:
                code = data.get('setup_code', '')
                if (not isinstance(code, str) or self.clock() > self.setup_deadline
                        or not hmac.compare_digest(code, self.setup_code)):
                    raise ToolError('invalid_or_expired_setup_code')
                salt = secrets.token_hex(16)
                record = {'salt': salt, 'hash': self.password_hash(password, salt)}
                atomic_json(self.root / 'account.json', record)
                self.account = record
                self.setup_code = ''
            else:
                supplied = self.password_hash(password, self.account['salt'])
                if not hmac.compare_digest(supplied, self.account['hash']):
                    raise ToolError('invalid_settings_password')
            token = secrets.token_urlsafe(32)
            self.sessions = {k: v for k, v in self.sessions.items() if v > self.clock()}
            if len(self.sessions) >= 16:
                self.sessions.clear()
            self.sessions[digest(token)] = self.clock() + 8 * 3600
            return token

    def admin(self, cookie):
        try:
            jar = SimpleCookie(cookie)
            token = jar['buzz_session'].value
        except (KeyError, TypeError):
            return False
        return bool(TOKEN.fullmatch(token) and self.sessions.get(digest(token), 0) > self.clock())

    def device(self, authorization):
        token = authorization.removeprefix('Bearer ')
        if not authorization.startswith('Bearer ') or not TOKEN.fullmatch(token):
            return False
        fingerprint = digest(token)
        return any(hmac.compare_digest(fingerprint, d['hash']) for d in self.devices.values())

    def bundle(self):
        with self.lock:
            self.grants = {k: v for k, v in self.grants.items() if v > self.clock()}
            if len(self.grants) >= 8 or len(self.devices) >= 16:
                raise ToolError('pairing_limit_revoke_old_connections')
            executable = self.artifacts / 'Buzz-VPS-Connect.exe'
            if not executable.is_file():
                raise ToolError('connection_program_not_packaged')
            token = secrets.token_urlsafe(32)
            self.grants[digest(token)] = self.clock() + 600
            data = {'schema': 1, 'endpoint': self.url, 'pairing_code': token}
            out = io.BytesIO()
            with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.write(executable, executable.name)
                archive.writestr('buzz-pairing.json', json.dumps(data))
                archive.writestr('시작하기.txt', '압축을 풀고 Buzz-VPS-Connect.exe를 실행하세요. 연결 파일은 10분간 한 번만 사용할 수 있습니다.\n')
            return out.getvalue()

    def exchange(self, data):
        with self.lock:
            self.throttle()
            code = data.get('pairing_code', '')
            name = data.get('name', 'Windows Buzz')
            if not isinstance(name, str) or not 1 <= len(name) <= 80 or any(ord(c) < 32 for c in name):
                raise ToolError('invalid_device_name')
            if not isinstance(code, str) or not TOKEN.fullmatch(code) or self.grants.get(digest(code), 0) <= self.clock():
                raise ToolError('pairing_expired_or_used')
            if len(self.devices) >= 16:
                raise ToolError('pairing_limit_revoke_old_connections')
            token, identifier = secrets.token_urlsafe(32), secrets.token_hex(12)
            updated = {**self.devices, identifier: {'hash': digest(token), 'name': name, 'created': int(self.clock())}}
            atomic_json(self.root / 'devices.json', updated)
            self.devices = updated
            del self.grants[digest(code)]
            return {'ok': True, 'token': token, 'device_id': identifier}

    def revoke(self, identifier):
        with self.lock:
            if not isinstance(identifier, str) or identifier not in self.devices:
                raise ToolError('unknown_device')
            updated = {k: v for k, v in self.devices.items() if k != identifier}
            atomic_json(self.root / 'devices.json', updated)
            self.devices = updated
            return {'ok': True}


class Handler(BaseHTTPRequestHandler):
    server_version = 'BuzzSetup'
    sys_version = ''

    def log_message(self, *_):
        # No query strings, OAuth text, bodies, cookies, or tokens in access logs.
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def respond(self, status, value, content_type='application/json; charset=utf-8', cookie=None, attachment=None):
        data = json.dumps(value, ensure_ascii=False).encode() if isinstance(value, dict) else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if not self.server.app.local:
            self.send_header('Strict-Transport-Security', 'max-age=31536000')
        if cookie is not None:
            self.send_header('Set-Cookie', cookie)
        if attachment:
            self.send_header('Content-Disposition', 'attachment; filename="'+attachment+'"')
        self.end_headers()
        self.wfile.write(data)

    def request_body(self):
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            raise ToolError('content_length_required')
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            raise ToolError('json_content_type_required')
        try:
            size = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            raise ToolError('invalid_content_length') from None
        if not 0 <= size <= LIMIT:
            raise ToolError('request_too_large')
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ToolError('incomplete_request')
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ToolError('json_object_required')
        return value

    def dispatch(self):
        app = self.server.app
        if self.headers.get('Host') != urlsplit(app.url).netloc:
            return self.respond(421, {'ok': False, 'error': 'unexpected_host'})
        if not app.local and self.headers.get('X-Forwarded-Proto') != 'https':
            return self.respond(403, {'ok': False, 'error': 'https_required'})
        if '?' in self.path or '#' in self.path:
            raise ToolError('query_parameters_not_supported')
        static = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8')}
        if self.command == 'GET' and self.path in static:
            file, content_type = static[self.path]
            return self.respond(200, (WEB / file).read_bytes(), content_type)
        if self.command == 'GET' and self.path == '/api/hello':
            return self.respond(200, {'ok': True, 'claimed': bool(app.account),
                                      'authenticated': app.admin(self.headers.get('Cookie', ''))})
        if self.command != 'POST':
            return self.respond(404, {'ok': False, 'error': 'not_found'})
        origin = self.headers.get('Origin')
        device_route = self.path in ('/api/pair/exchange', '/api/device/deploy', '/api/device/status')
        if (origin and origin != app.url) or (not device_route and origin != app.url):
            return self.respond(403, {'ok': False, 'error': 'origin_rejected'})
        data = self.request_body()
        if self.path == '/api/login':
            token = app.login(data)
            cookie = 'buzz_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'
            if not app.local: cookie += '; Secure'
            return self.respond(200, {'ok': True}, cookie=cookie)
        if self.path == '/api/pair/exchange':
            return self.respond(200, app.exchange(data))
        if self.path.startswith('/api/device/'):
            if not app.device(self.headers.get('Authorization', '')):
                return self.respond(401, {'ok': False, 'error': 'connection_revoked_or_invalid'})
            if self.path == '/api/device/deploy':
                return self.respond(200, app.rpc({'op': 'deploy', 'request': data}))
            if self.path == '/api/device/status':
                return self.respond(200, app.rpc({'op': 'status'}))
            return self.respond(404, {'ok': False, 'error': 'not_found'})
        if not app.admin(self.headers.get('Cookie', '')):
            return self.respond(401, {'ok': False, 'error': 'settings_login_required'})
        if self.path == '/api/logout':
            jar = SimpleCookie(self.headers.get('Cookie', ''))
            app.sessions.pop(digest(jar['buzz_session'].value), None)
            return self.respond(200, {'ok': True}, cookie='buzz_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0; Secure')
        if self.path == '/api/pair/bundle':
            return self.respond(200, app.bundle(), 'application/zip', attachment='Buzz-Windows-Connect.zip')
        if self.path == '/api/devices':
            return self.respond(200, {'ok': True, 'devices': [{'id': k, 'name': v['name']} for k, v in app.devices.items()]})
        if self.path == '/api/revoke':
            return self.respond(200, app.revoke(data.get('id')))
        operations = {'/api/status': 'status', '/api/discover': 'discover', '/api/configure': 'configure',
                      '/api/auth/start': 'auth-start', '/api/auth/poll': 'auth-poll',
                      '/api/auth/input': 'auth-input', '/api/auth/cancel': 'auth-cancel',
                      '/api/schedule/init': 'schedule-init', '/api/schedule/save': 'schedule-save',
                      '/api/schedule/disable': 'schedule-disable'}
        if self.path not in operations or 'op' in data:
            return self.respond(404, {'ok': False, 'error': 'not_found'})
        return self.respond(200, app.rpc({'op': operations[self.path], **data}))

    def do_GET(self):
        try:
            self.dispatch()
        except ToolError as error:
            code = str(error)
            self.respond(400, {'ok': False, 'error': code if re.fullmatch(r'[a-zA-Z0-9_]{1,160}', code) else 'request_failed'})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        except Exception:
            self.respond(500, {'ok': False, 'error': 'service_unavailable_check_docker_manager'})

    do_POST = do_GET


class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, app):
        self.app = app
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, Handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


def main():
    os.umask(0o077)
    app = Portal('/portal', os.environ['BUZZ_PUBLIC_URL'])
    if not app.account:
        print('Buzz first setup code (valid 60 minutes): '+app.setup_code, flush=True)
    with Server(('0.0.0.0', 8080), app) as server:
        server.serve_forever()


if __name__ == '__main__': main()
