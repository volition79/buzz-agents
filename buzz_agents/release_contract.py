"""A management image selects a reviewed, immutable release, never a task URL."""
import json
from pathlib import Path
import re
from .common import ToolError

PATH = Path('/app/buzz-release.json')
PREFIX = 'ghcr.io/volition79/buzz-agents-'

def validate(value):
    if not isinstance(value, dict) or set(value) != {'schema', 'release', 'runtime', 'portal', 'api'}:
        raise ToolError('invalid_release_contract')
    if value['schema'] != 1 or value['api'] != 1 or not re.fullmatch('[0-9a-f]{40}', str(value['release'])):
        raise ToolError('invalid_release_contract')
    for role in ('runtime', 'portal'):
        if not re.fullmatch(re.escape(PREFIX + role) + r'@sha256:[0-9a-f]{64}', str(value[role])):
            raise ToolError('invalid_release_contract')
    return value

def load(path=PATH):
    if not path.exists():
        return None  # Legacy immutable candidates keep their original explicit flow.
    return validate(json.loads(path.read_text()))

def image(runner, ref, pull=False):
    try:
        record = json.loads(runner(['docker', 'image', 'inspect', ref]))[0]
    except ToolError:
        if not pull:
            raise
        runner(['docker', 'pull', '--quiet', ref], timeout=600)
        record = json.loads(runner(['docker', 'image', 'inspect', ref]))[0]
    if ref not in record.get('RepoDigests', []) or not re.fullmatch('sha256:[0-9a-f]{64}', record.get('Id', '')):
        raise ToolError('release_image_digest_mismatch')
    return record

def compatible_portal(contract, own, containers, runner):
    project = (own.get('Config', {}).get('Labels') or {}).get('com.docker.compose.project')
    portals = [c for c in containers if (c.get('Config', {}).get('Labels') or {}).get('com.docker.compose.project') == project
               and (c.get('Config', {}).get('Labels') or {}).get('com.docker.compose.service') == 'portal']
    if not project or len(portals) != 1 or not portals[0].get('State', {}).get('Running'):
        raise ToolError('release_portal_not_ready')
    expected = image(runner, contract['portal'])
    if portals[0].get('Image') != expected['Id']:
        raise ToolError('release_management_mismatch')
    return True
