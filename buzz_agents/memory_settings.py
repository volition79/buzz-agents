"""Privileged staged RAM choices. Callers own deploy.lock for every write."""
import hashlib
import json
from pathlib import Path
import stat
from .common import ToolError
from .swap_pool import LABEL
from .config import HEX
from .policy import atomic_json, read_json


def valid_mb(value):
    return type(value) is int and 512 <= value <= 16777216


def load(root):
    path = Path(root) / 'memory-settings.json'
    try:
        st = path.lstat()
    except FileNotFoundError:
        return {}
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077 or st.st_size > 512 * 1024:
        raise ToolError('unsafe_memory_settings')
    data = read_json(path)
    if not isinstance(data, dict):
        raise ToolError('invalid_memory_settings')
    for key, value in data.items():
        if (not isinstance(key, str) or not HEX.fullmatch(key) or not isinstance(value, dict)
                or set(value) != {'desired_mb', 'committed_mb'}
                or not all(valid_mb(v) for v in value.values())):
            raise ToolError('invalid_memory_settings')
    return data


def save(root, pubkey, desired, committed):
    if not isinstance(pubkey, str) or not HEX.fullmatch(pubkey) or not valid_mb(desired) or not valid_mb(committed):
        raise ToolError('invalid_memory')
    data = load(root)
    data[pubkey] = {'desired_mb': desired, 'committed_mb': committed}
    atomic_json(Path(root) / 'memory-settings.json', data)


def with_memory(config, mb):
    """Only a trusted server setting overrides the already validated config."""
    result = {**config, 'memory_mb': mb}
    payload = {k: v for k, v in result.items() if k not in ('fingerprint', 'startup_env')}
    result['fingerprint'] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return result


def actual_mb(actual):
    value = (actual or {}).get('HostConfig', {}).get('Memory')
    return value // (1024 * 1024) if type(value) is int and value > 0 else None


def limits_match(actual, mb):
    expected = mb * 1024 * 1024
    limits = (actual or {}).get('HostConfig', {})
    return limits.get('Memory') == expected and limits.get('MemorySwap') == expected*4


def compatible_limits(actual, mb):
    """Allow only the known unmarked no-swap predecessor during migration."""
    if limits_match(actual, mb):
        return True
    limits = (actual or {}).get('HostConfig', {})
    labels = ((actual or {}).get('Config', {}).get('Labels') or {})
    expected = mb * 1024 * 1024
    return LABEL not in labels and limits.get('Memory') == expected and limits.get('MemorySwap') == expected


def public(config, actual, choice):
    applied = actual_mb(actual)
    desired = choice.get('desired_mb', config['memory_mb'])
    committed = choice.get('committed_mb', config['memory_mb'])
    return {'desired_mb': desired, 'configured_mb': config['memory_mb'], 'applied_mb': applied,
            'swap_limit_mb': desired*3,
            'swap_pending': not limits_match(actual, config['memory_mb']),
            'pending': not compatible_limits(actual, desired) or committed != applied,
            'recovery_required': committed != config['memory_mb'] or
                (bool(choice) and not compatible_limits(actual, config['memory_mb']))}
