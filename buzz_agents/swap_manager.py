"""Broker-owned helper lifecycle. Never give helper Docker or bot-data access."""
import fcntl
import json
import os
import re
import secrets
import time
from pathlib import Path

from .common import ToolError
from .policy import atomic_json, read_json
from .swap_pool import ROOT, checked_directory, private_json

NAME = 'buzz-agents-swap-v1'
OWNER = 'io.buzz-agents.swap-helper'
INTENT = 'io.buzz-agents.swap-creation'


def desired(root, candidate=None):
    registry = read_json(Path(root)/'registry.json', {})
    if candidate:
        registry = {**registry, candidate['pubkey']: candidate}
    values = [c['memory_mb'] for c in registry.values()]
    if any(type(v) is not int or not 512 <= v <= 16777216 for v in values):
        raise ToolError('swap_invalid_target')
    return sum(values)*3


def request_capacity(root, candidate=None):
    """Only configured portal installations opt into host swap management."""
    folder = Path(root)/'swap'
    if not folder.exists():
        return
    checked_directory(folder)
    atomic_json(folder/'request.json', {'target_mb': desired(root, candidate)})


def public(root):
    try:
        value = private_json(Path(root)/'swap/status.json', {})
        if not value:
            return {'state': 'pending'}
        if not isinstance(value, dict):
            raise ToolError('swap_invalid_state')
        result = {k: value[k] for k in ('target_mb','total_mb','used_mb','managed_mb','budget_mb','free_mb')
                  if type(value.get(k)) is int and value[k] >= 0}
        result['state'] = value.get('state') if value.get('state') in ('ready','limited','preparing','attention') else 'attention'
        reason = value.get('reason', '')
        if isinstance(reason, str) and re.fullmatch(r'swap_[a-z_]{1,80}', reason):
            result['reason'] = reason
        if type(value.get('checked_at')) is not int or time.time()-value['checked_at'] > 120:
            result['state'] = 'pending'
        return result
    except (OSError, ToolError, ValueError):
        return {'state': 'attention', 'reason': 'swap_status_unavailable'}


def create_args(image, token):
    return ['docker','create','--name',NAME,'--label',OWNER+'=1','--label',INTENT+'='+token,
            '--network','none','--read-only','--user','0:0','--init',
            '--cap-drop','ALL','--cap-add','SYS_ADMIN',
            '--security-opt','no-new-privileges:true',
            '--security-opt','seccomp=/app/buzz_agents/swap-seccomp.json',
            '--restart','unless-stopped','--memory','128m','--memory-swap','128m',
            '--cpus','0.10','--pids-limit','24',
            '--log-driver','json-file','--log-opt','max-size=1m','--log-opt','max-file=2',
            '--mount',f'type=bind,src={ROOT},dst={ROOT}',
            '--entrypoint','python',image,'-m','buzz_agents.swap_pool']


def owned(container, saved_id):
    """A label alone is not sufficient to delete a container with this name."""
    return (saved_id and container.get('Id') == saved_id
            and (container.get('Config',{}).get('Labels') or {}).get(OWNER) == '1'
            and len(container.get('Mounts',[])) == 1
            and container['Mounts'][0].get('Type') == 'bind'
            and container['Mounts'][0].get('Source') == str(ROOT)
            and container['Mounts'][0].get('Destination') == str(ROOT))


def reconcile(run, inspect, self_name):
    checked_directory(ROOT)
    fd = os.open(ROOT/'controller.lock', os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW, 0o600)
    pool_fd = None
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        info = json.loads(run(['docker','info','--format','{{json .}}'], timeout=20))
        if (info.get('OSType') != 'linux' or info.get('SwapLimit') is not True
                or any('rootless' in str(x) or 'userns' in str(x) for x in info.get('SecurityOptions',[]))):
            raise ToolError('swap_host_unsupported')
        if not isinstance(self_name,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}', self_name):
            raise ToolError('swap_broker_identity_unavailable')
        candidates = json.loads(run(['docker','inspect','--type','container',self_name], timeout=20))
        broker = candidates[0] if len(candidates) == 1 else None
        if (not broker or (broker.get('Config',{}).get('Labels') or {}).get('com.docker.compose.service') != 'broker'
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', broker.get('Image',''))
                or not any(m.get('Source') == str(ROOT.parent) and m.get('Destination') == str(ROOT.parent)
                           and m.get('Type') == 'bind' for m in broker.get('Mounts',[]))):
            raise ToolError('swap_broker_identity_unavailable')
        image = broker['Image']
        saved = private_json(ROOT/'helper.json', {})
        if not isinstance(saved, dict):
            raise ToolError('swap_invalid_state')
        current = inspect(NAME)
        # Intent is durable BEFORE Docker create. Recover a lost create response
        # or ID-save failure only when the exact private creation token matches.
        intent = saved.get('creating', {})
        if 'creating' in saved and (not isinstance(intent, dict)
                or not re.fullmatch(r'[0-9a-f]{64}', str(intent.get('token', '')))
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', str(intent.get('image', '')))):
            raise ToolError('swap_invalid_state')
        if current and not owned(current, saved.get('id')):
            if (not isinstance(intent, dict)
                    or not re.fullmatch(r'[0-9a-f]{64}', str(intent.get('token', '')))
                    or current.get('Image') != intent.get('image')
                    or (current.get('Config', {}).get('Labels') or {}).get(INTENT) != intent['token']
                    or not owned(current, current.get('Id'))):
                raise ToolError('swap_helper_name_collision')
            saved = {'id': current['Id']}
            atomic_json(ROOT/'helper.json', saved)
        if current is None or current.get('Image') != image:
            pool_fd = os.open(ROOT/'pool.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
            fcntl.flock(pool_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if current:
            if not owned(current, saved.get('id')):
                raise ToolError('swap_helper_name_collision')
            if current.get('Image') != image:
                # Stopping helper does NOT deactivate swap. Never swapoff/unlink.
                run(['docker','stop','--time','45',current['Id']], timeout=55)
                run(['docker','rm',current['Id']], timeout=20)
                current = None
        if current is None:
            # Docker may still be completing a timed-out create. Keep its token
            # AND image until that intent completes, including across upgrades.
            if not intent or saved.get('id'):
                intent = {'token': secrets.token_hex(32), 'image': image}
                atomic_json(ROOT/'helper.json', {'creating': intent})
            ident = run(create_args(intent['image'], intent['token']), timeout=30).decode().strip()
            if not re.fullmatch(r'[0-9a-f]{64}', ident):
                raise ToolError('swap_helper_create_unconfirmed')
            atomic_json(ROOT/'helper.json', {'id':ident})
            current = inspect(NAME)
            if (not current or not owned(current, ident)
                    or current.get('Image') != intent['image']
                    or (current.get('Config',{}).get('Labels') or {}).get(INTENT) != intent['token']):
                raise ToolError('swap_helper_create_unconfirmed')
        if current.get('Image') != image:
            return  # Next tick replaces this recovered predecessor under pool.lock.
        if not current.get('State',{}).get('Running'):
            run(['docker','start',current['Id']], timeout=20)
    finally:
        if pool_fd is not None:
            os.close(pool_fd)
        os.close(fd)


def loop(broker, run, inspect):
    while True:
        try:
            if read_json(broker.control/'settings.json', {}):
                if broker.contract:
                    broker.rollout.verify_management()
                checked_directory(ROOT)
                # Synchronize the registry snapshot with all deployment writers.
                fd = os.open(broker.root/'deploy.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
                try:
                    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    request_capacity(broker.root)
                finally:
                    os.close(fd)
                reconcile(run, inspect, os.environ.get('HOSTNAME',''))
        except BlockingIOError:
            pass
        except Exception as exc:
            reason = str(exc) if isinstance(exc,ToolError) else 'swap_controller_failed'
            try:
                checked_directory(ROOT)
                atomic_json(ROOT/'status.json', {'state':'attention','reason':reason,'checked_at':int(time.time())})
            except (OSError, ToolError):
                pass
            print('Swap support awaiting verification: '+reason, flush=True)
        time.sleep(30)
