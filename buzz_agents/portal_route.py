"""Bounded same-server HTTP bridge; TLS and certificate handling stay in Traefik."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import re
import threading

REQUEST_LIMIT = 512 * 1024
RESPONSE_LIMIT = 32 * 1024 * 1024
FORWARD = ('Content-Type', 'Origin', 'Cookie', 'Authorization')
RESPONSE_HEADERS = {'content-type', 'content-disposition', 'set-cookie', 'cache-control',
                    'content-security-policy', 'strict-transport-security', 'x-content-type-options',
                    'referrer-policy', 'x-frame-options'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def fail(self, status):
        self.send_response(status)
        self.send_header('Content-Length', '0')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True

    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        if (self.headers.get_all('Host', []) != [self.server.hostname]
                or self.headers.get_all('X-Forwarded-Proto', []) != ['https']):
            return self.fail(421)
        if not self.path.startswith('/') or self.path.startswith('//') or '?' in self.path or '#' in self.path:
            return self.fail(400)
        lengths = self.headers.get_all('Content-Length', [])
        if self.headers.get('Transfer-Encoding') or len(lengths) > 1:
            return self.fail(400)
        if self.command == 'POST' and len(lengths) != 1:
            return self.fail(411)
        try:
            size = int(lengths[0]) if lengths else 0
        except ValueError:
            return self.fail(400)
        if not 0 <= size <= REQUEST_LIMIT:
            return self.fail(413)
        if self.command == 'GET' and size:
            return self.fail(400)
        if any(len(self.headers.get_all(key, [])) > 1 for key in FORWARD):
            return self.fail(400)
        conn = None
        try:
            body = self.rfile.read(size)
            if len(body) != size:
                return self.fail(400)
            headers = {k: self.headers[k] for k in FORWARD if k in self.headers}
            headers.update({'Host': self.server.hostname, 'X-Forwarded-Proto': 'https', 'Connection': 'close'})
            if self.command == 'POST': headers['Content-Length'] = str(size)
            conn = http.client.HTTPConnection(self.server.upstream, self.server.upstream_port, timeout=30)
            conn.request(self.command, self.path, body=body if self.command == 'POST' else None, headers=headers)
            response = conn.getresponse()
            payload = response.read(RESPONSE_LIMIT + 1)
            if len(payload) > RESPONSE_LIMIT:
                return self.fail(502)
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() in RESPONSE_HEADERS:
                    self.send_header(key, value)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(payload)
            self.close_connection = True
        except (OSError, http.client.HTTPException):
            self.close_connection = True
            try: self.fail(502)
            except OSError: pass
        finally:
            if conn: conn.close()


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, hostname, upstream, upstream_port=8080):
        self.hostname, self.upstream, self.upstream_port = hostname, upstream, upstream_port
        self.slots = threading.BoundedSemaphore(2)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try: super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try: super().process_request_thread(request, address)
        finally: self.slots.release()


def main():
    host, upstream = os.environ['BUZZ_ROUTE_HOST'], os.environ['BUZZ_ROUTE_UPSTREAM']
    if (not re.fullmatch(r'buzz-setup-[a-f0-9]{12}\.srv[0-9]+\.hstgr\.cloud', host)
            or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}', upstream)):
        raise SystemExit('invalid_route_configuration')
    with Server(('0.0.0.0', 8080), host, upstream) as server:
        server.serve_forever()


if __name__ == '__main__': main()
