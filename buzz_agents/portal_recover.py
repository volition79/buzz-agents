"""Owner-only recovery via the portal container terminal; never an HTTP issuer."""
from contextlib import contextmanager
import fcntl
import os
import socket
import socketserver
import stat
import threading

SOCKET = '/portal/access.sock'


@contextmanager
def control_server(app):
    lock_fd = os.open(app.root / 'access.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except Exception:
        os.close(lock_fd)
        raise
    try:
        with _serve(app):
            yield
    finally:
        os.close(lock_fd)


@contextmanager
def _serve(app):
    path = app.root / 'access.sock'
    if path.is_symlink():
        raise RuntimeError('access_socket_path_conflict')
    if path.exists():
        if not stat.S_ISSOCK(path.lstat().st_mode):
            raise RuntimeError('access_socket_path_conflict')
        path.unlink()

    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(3)
            if self.rfile.readline(64) != b'issue-access-code\n':
                self.wfile.write(b'unsupported\n')
                return
            app.issue_access_code()
            self.wfile.write(b'issued\n')

    with socketserver.UnixStreamServer(str(path), Handler) as server:
        path.chmod(0o600)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield
        finally:
            server.shutdown()
            thread.join()
            path.unlink(missing_ok=True)


def request_code(path=SOCKET):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(5)
        sock.connect(str(path))
        sock.sendall(b'issue-access-code\n')
        if sock.makefile('rb').readline(64) != b'issued\n':
            raise RuntimeError('access_code_not_issued')


def main():
    try:
        request_code()
    except (OSError, RuntimeError):
        print('발급하지 못했습니다. 실행 중인 portal 컨테이너의 터미널에서 다시 실행하세요.')
        raise SystemExit(1) from None
    print('발급 완료. Docker Manager → buzz-agents → 관리 → 로그에서 portal의 최신 코드를 확인하세요.\n'
          '초기 설정 전이면 setup code, 설정 후이면 복구 코드가 발급됩니다. 60분간 한 번만 유효합니다.\n'
          '새 코드를 발급하거나 portal을 재시작하면 이전 코드는 무효가 됩니다.')


if __name__ == '__main__':
    main()
