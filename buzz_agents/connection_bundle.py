"""Desktop bundles only: no broker RPC, bot mutation or credential migration."""
import io
import json
from pathlib import Path
import zipfile

from .common import ToolError

# Never derive a filesystem path from client input. Old callers select Windows.
TARGETS = {
    'windows-amd64': ('Buzz-VPS-Connect.exe', 'Buzz-Windows-Connect.zip'),
    'macos-arm64': ('macos/Buzz-VPS-Connect-macos-arm64', 'Buzz-Mac-AppleSilicon-Connect.zip'),
}
MAC_LAUNCHER = '''#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
exec ./Buzz-VPS-Connect
'''


def target(value):
    if not isinstance(value, str) or value not in TARGETS:
        raise ToolError('unsupported_connection_platform')
    return TARGETS[value]


def available(artifacts):
    return [name for name, (path, _) in TARGETS.items()
            if (Path(artifacts) / path).is_file()]


def build(artifacts, platform, data):
    filename, _ = target(platform)
    executable = Path(artifacts) / filename
    if not executable.is_file():
        raise ToolError('connection_program_not_packaged')
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        if platform == 'windows-amd64':
            archive.write(executable, executable.name)
            instructions = '압축을 모두 풀고 Buzz-VPS-Connect.exe를 실행하세요.'
        else:
            # Unix mode survives standard Mac ZIP extraction. No chmod of user
            # files, quarantine stripping, sudo or shell interpolation of secrets.
            for name, raw in [('Buzz-VPS-Connect', executable.read_bytes()),
                              ('Buzz-VPS-Connect.command', MAC_LAUNCHER.encode())]:
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = 0o100755 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, raw)
            instructions = ('Apple Silicon Mac용입니다. 압축을 모두 풀고 Buzz를 종료한 뒤 '
                            'Buzz-VPS-Connect.command를 실행하세요. 모든 파일을 같은 폴더에 두세요. '
                            'macOS가 실행을 차단하면 중단하고 배포자에게 문의하세요. '
                            '보안 기능을 끄지 마세요.')
        archive.writestr('buzz-pairing.json', json.dumps(data))
        archive.writestr('시작하기.txt', instructions + '\n연결 파일은 10분간 한 번만 사용할 수 있습니다.\n'
                         '만료·실패 시 설정 화면에서 새 연결 파일을 받으세요. 정상 연결 후에는 파일의 만료와 무관하게 연결이 유지됩니다.\n'
                         '다시 실행하면 기존 연결을 확인합니다. 재연결은 직접 선택할 때만 진행하며 Buzz를 먼저 종료하세요.\n'
                         '저장 실패 시 표시된 장치 ID를 설정 화면에서 찾아 해제하고 새 파일로 재시도하세요.\n')
    return output.getvalue()
