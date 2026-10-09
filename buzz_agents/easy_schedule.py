"""One daily server-side schedule, configured via the restricted SSH helper."""
import json
import os
from pathlib import Path
from .common import ToolError
from .host import execute, inspect_container
from .policy import read_json, atomic_json
from .scheduler import schedule_spec

BASE = Path('/var/lib/buzz-agents-easy-scheduler')
NAME = 'buzz-agents-easy-scheduler'
LABEL = 'buzz-agents-easy-scheduler-v1'


def initialize(settings):
    image = json.loads(execute(['docker', 'image', 'inspect', settings['image']]))[0]
    if image['Id'] != settings['image_id']:
        raise ToolError('image_changed_revalidate_before_schedule')
    BASE.mkdir(mode=0o700, exist_ok=True)
    path = BASE / 'config/config.json'
    if not path.exists():
        # Official image helper generates a new scheduler identity, not a human key.
        execute(['docker', 'run', '--rm', '--network', 'none', '-u', '0:0',
                 '-v', str(BASE)+':/bootstrap', '--entrypoint', 'python', settings['image'],
                 '-m', 'buzz_agents.cli', 'automation-init', '/bootstrap', '--relay', settings['relay']])
    config = read_json(path)
    if config.get('relay') != settings['relay']:
        raise ToolError('scheduler_relay_mismatch')
    # Derive the public key inside the reviewed image; private bytes use stdin only.
    result = execute(['docker', 'run', '--rm', '--network', 'none', '-i', '--entrypoint', 'node',
                      settings['image'], '/app/buzz_agents/nostr.mjs', 'public'], config['private_key_hex'])
    public_key = json.loads(result)
    return {'ok': True, 'pubkey': public_key, 'enabled': config.get('enabled', False),
            'note': 'Register this public identity in the Relay and channel; allow it on the target bot before enabling.'}


def compose(settings):
    return {'name': NAME, 'services': {'scheduler': {
        'image': settings['image'], 'pull_policy': 'never', 'container_name': NAME,
        'labels': {'io.buzz-agents.managed': LABEL}, 'user': '10001:10001',
        'command': ['python','-m','buzz_agents.scheduler'], 'restart': 'unless-stopped',
        'init': True, 'read_only': True, 'cap_drop': ['ALL'],
        'security_opt': ['no-new-privileges:true'], 'cpus': .15, 'mem_limit': '192m',
        'memswap_limit': '192m', 'pids_limit': 64,
        'tmpfs': ['/tmp:size=32m,mode=1777,nosuid,nodev'],
        'volumes': [{'type':'bind','source':str(BASE/'config'),'target':'/automation-config',
                     'read_only':True,'bind':{'create_host_path':False}},
                    {'type':'bind','source':str(BASE/'state'),'target':'/automation-state',
                     'bind':{'create_host_path':False}}],
        'logging': {'driver':'json-file','options':{'max-size':'5m','max-file':'2'}}}}}


def validate_schedule(item, registry):
    required = {'channel_id', 'bot_pubkey', 'prompt', 'time', 'membership_confirmed'}
    if not isinstance(item, dict) or set(item) != required or item['membership_confirmed'] is not True:
        raise ToolError('scheduler_membership_confirmation_required')
    if item['bot_pubkey'] not in registry:
        raise ToolError('scheduler_target_not_registered')
    spec = {k:item[k] for k in required if k != 'membership_confirmed'}
    spec.update(id='easy-daily',kind='daily',timezone='Asia/Seoul',enabled=True)
    try:
        return schedule_spec(spec)
    except (KeyError, ValueError):
        raise ToolError('invalid_daily_schedule') from None


def configure(settings, item):
    registry = read_json(Path(settings['state_dir'])/'registry.json', {})
    spec = validate_schedule(item, registry)
    image = json.loads(execute(['docker', 'image', 'inspect', settings['image']]))[0]
    if image['Id'] != settings['image_id']:
        raise ToolError('image_changed_revalidate_before_schedule')
    cfgpath = BASE/'config/config.json'
    if not cfgpath.is_file():
        raise ToolError('initialize_scheduler_first')
    actual = inspect_container(NAME)
    if actual and (actual.get('Config',{}).get('Labels') or {}).get('io.buzz-agents.managed') != LABEL:
        raise ToolError('scheduler_container_collision')
    # Stop before replacing a schedule so a live process never runs stale settings.
    if actual:
        execute(['docker','stop','--time','30',NAME])
    config = read_json(cfgpath)
    config.update(enabled=True, schedules=[spec])
    atomic_json(cfgpath,config,0o600)
    os.chown(cfgpath,10001,10001)
    manifest = BASE/'compose.json'
    atomic_json(manifest,compose(settings))
    execute(['docker','compose','-f',str(manifest),'up','-d','--force-recreate'],timeout=180)
    return {'ok':True,'note':'Daily schedule saved (Asia/Seoul); delivery and AI completion must be verified separately.'}


def disable():
    config = read_json(BASE/'config/config.json')
    if not config:
        raise ToolError('scheduler_not_initialized')
    actual = inspect_container(NAME)
    if actual:
        if (actual.get('Config',{}).get('Labels') or {}).get('io.buzz-agents.managed') != LABEL:
            raise ToolError('scheduler_container_collision')
        execute(['docker','stop','--time','30',NAME])
    config['enabled'] = False
    atomic_json(BASE/'config/config.json',config,0o600)
    os.chown(BASE/'config/config.json',10001,10001)
    return {'ok':True,'note':'Scheduler disabled; pending/running AI tasks are not cancelled.'}
