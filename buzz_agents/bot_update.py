"""Administrator-requested updates of existing identities, never a new bot."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat

from .common import ToolError
from .config import ENV_ALLOWED, HEX
from .host import (Deployer, check_ownership, container_name, public_record,
                   private_directory, check_resources, host_capacity)
from .policy import read_json
from . import memory_settings


def saved_config(root, pubkey):
    if not isinstance(pubkey, str) or not HEX.fullmatch(pubkey):
        raise ToolError('invalid_bot_public_key')
    path = root / 'bots' / pubkey / 'config' / 'config.json'
    # This is privileged configuration, never an agent-writable input file.
    for parent in (root, root / 'bots', path.parent.parent, path.parent, path.parent.parent / 'state'):
        st = parent.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o022:
            raise ToolError('unsafe_saved_bot_configuration')
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077 or st.st_size > 512 * 1024:
        raise ToolError('unsafe_saved_bot_configuration')
    value = read_json(path)
    if not isinstance(value, dict) or value.get('pubkey') != pubkey or value.get('schema') != 2:
        raise ToolError('invalid_saved_bot_configuration')
    payload = {k: v for k, v in value.items() if k not in ('fingerprint', 'startup_env')}
    if hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest() != value.get('fingerprint'):
        raise ToolError('saved_bot_configuration_changed')
    return value


def request_from_saved(config, settings, use_defaults):
    """Re-enter the existing runtime validator, including its key derivation."""
    env = config['env']
    if config['owner'] != settings['owner'] or env.get('BUZZ_RELAY_URL') != settings['relay']:
        raise ToolError('saved_bot_scope_mismatch')
    options = {**config['policy'], **{k: config[k] for k in ('workspace', 'memory_mb', 'cpus')}}
    launch_env = {k: v for k, v in env.items() if k in ENV_ALLOWED and k != 'BUZZ_ACP_REPLAY_FLOOR'}
    if use_defaults:
        options.update(turn_limit=0, daily_limit=0, max_turn_seconds=7200)
        launch_env['BUZZ_ACP_MAX_TURN_DURATION'] = '7200'
    return {'op': 'deploy', 'provider_config': options, 'agent': {
        'name': config['name'], 'relay_url': settings['relay'],
        'private_key_nsec': env['BUZZ_PRIVATE_KEY'], 'auth_tag': env['BUZZ_AUTH_TAG'],
        'respond_to': env['BUZZ_ACP_RESPOND_TO'],
        'respond_to_allowlist': [k for k in env['BUZZ_ACP_RESPOND_TO_ALLOWLIST'].split(',') if k],
        'launch': {'command': config['command'], 'args': [], 'owner_pubkey': settings['owner'],
                   'policy_env': {}, 'env': launch_env}}}


class ExistingBotUpdater:
    def __init__(self, deployer):
        self.deployer = deployer
        self.root = deployer.root

    def inspect(self, pubkey):
        config = saved_config(self.root, pubkey)
        registry = read_json(self.root / 'registry.json', {})
        item = registry.get(pubkey, {})
        expected = public_record(config)
        if 'parallelism' not in item:
            expected.pop('parallelism', None)
        if {k: v for k, v in item.items() if k != 'runtime_image'} != expected:
            raise ToolError('saved_bot_registry_mismatch')
        actual = self.deployer.inspect(container_name(pubkey))
        if actual:
            check_ownership(actual, config)
            if actual.get('Config', {}).get('Labels', {}).get('io.buzz-agents.fingerprint') != config['fingerprint']:
                # A failed recreation may have persisted the desired config but
                # left the old stopped container. Retry that case only.
                if actual.get('State', {}).get('Running'):
                    raise ToolError('saved_bot_configuration_changed')
        revision = hashlib.sha256(json.dumps({
            'fingerprint': config['fingerprint'], 'image': self.deployer.settings['image'],
            'image_id': self.deployer.settings['image_id'],
            'container': actual.get('Id') if actual else None,
            'current_image': actual.get('Image') if actual else None,
            'memory': memory_settings.load(self.root).get(pubkey, {}),
            'actual_memory': (actual or {}).get('HostConfig', {}).get('Memory'),
            'actual_swap': (actual or {}).get('HostConfig', {}).get('MemorySwap'),
        }, sort_keys=True).encode()).hexdigest()
        return config, actual, revision

    def preview(self, pubkey):
        config, actual, revision = self.inspect(pubkey)
        return {'ok': True, 'pubkey': pubkey, 'name': config['name'], 'revision': revision,
                'provider': config['provider'], 'policy': config['policy'],
                'memory': memory_settings.public(config, actual, memory_settings.load(self.root).get(pubkey, {})),
                'target_image': self.deployer.settings['image'],
                'image_update': not actual or actual.get('Image') != self.deployer.settings['image_id']}

    def save_memory(self, pubkey, revision, memory_mb):
        if not memory_settings.valid_mb(memory_mb):
            raise ToolError('invalid_memory')
        fd = os.open(self.root / 'deploy.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ToolError('bot_update_busy') from None
            from .reauth import require_unheld
            require_unheld(self.root, pubkey)
            config, actual, current = self.inspect(pubkey)
            if current != revision:
                raise ToolError('bot_update_preview_changed')
            if not memory_settings.limits_match(actual, config['memory_mb']):
                raise ToolError('memory_apply_recovery_required')
            choice = memory_settings.load(self.root).get(pubkey, {})
            committed = choice.get('committed_mb', config['memory_mb'])
            if committed != config['memory_mb']:
                raise ToolError('memory_apply_recovery_required')
            # Reserve both the currently applied and staged limit until application.
            candidate = {**config, 'memory_mb': max(memory_mb, committed, config['memory_mb'])}
            check_resources(candidate, read_json(self.root / 'registry.json', {}),
                            self.deployer.settings, host_capacity(self.deployer.run))
            memory_settings.save(self.root, pubkey, memory_mb, committed)
            return {'ok': True, 'memory': memory_settings.public(config, actual,
                    {'desired_mb': memory_mb, 'committed_mb': committed})}
        finally:
            os.close(fd)

    def apply(self, pubkey, revision, use_defaults, preserve_lifecycle=False):
        if not isinstance(revision, str) or not HEX.fullmatch(revision) or type(use_defaults) is not bool:
            raise ToolError('invalid_bot_update_request')
        private_directory(self.root)
        fd = os.open(self.root / 'deploy.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise ToolError('bot_update_busy') from None
        auth_locks = []
        try:
            from .reauth import require_unheld
            require_unheld(self.root, pubkey)
            old, actual, current = self.inspect(pubkey)
            saved_state = read_json(self.root / "bots" / pubkey / "state" / "runtime.json", {})
            was_running = bool(actual and actual.get("State", {}).get("Running"))
            if preserve_lifecycle and (not actual or was_running or saved_state.get("status") not in ("stopped", "held", "needs_login")):
                raise ToolError("update_requires_interruption_confirmation")
            if current != revision:
                raise ToolError('bot_update_preview_changed')
            for name in ('portal-auth.lock', 'auth.lock'):
                auth_fd = os.open(self.root / 'bots' / pubkey / 'state' / name,
                                  os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                auth_locks.append(auth_fd)
                try:
                    fcntl.flock(auth_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ToolError('authentication_already_in_progress') from None
            d = self.deployer
            image = json.loads(d.run(['docker', 'image', 'inspect', d.settings['image']]))[0]
            if image['Id'] != d.settings['image_id']:
                raise ToolError('image_changed_revalidate_before_deploy')
            choice = memory_settings.load(self.root).get(pubkey, {})
            target_memory = choice.get('desired_mb', old['memory_mb'])
            if preserve_lifecycle and target_memory != old['memory_mb']:
                raise ToolError('memory_change_pending')
            request = request_from_saved(old, d.settings, use_defaults)
            request['provider_config']['memory_mb'] = target_memory
            config = d.normalizer(request)
            if config['memory_mb'] != target_memory:
                raise ToolError('bot_update_identity_or_settings_changed')
            # Updating must never switch identities, auth homes, files or models.
            for key in ('pubkey', 'owner', 'provider', 'command', 'workspace', 'cpus', 'name'):
                if config.get(key) != old[key]:
                    raise ToolError('bot_update_identity_or_settings_changed')
            changed = {'BUZZ_ACP_MAX_TURN_DURATION'} if use_defaults else set()
            if {k: v for k, v in config['env'].items() if k not in changed} != {k: v for k, v in old['env'].items() if k not in changed}:
                raise ToolError('bot_update_identity_or_settings_changed')
            expected_policy = {**old['policy']}
            if use_defaults:
                expected_policy.update(turn_limit=0, daily_limit=0, max_turn_seconds=7200)
            if config['policy'] != expected_policy or config.get('startup_env'):
                raise ToolError('bot_update_identity_or_settings_changed')
            registry = read_json(self.root / 'registry.json', {})
            check_resources(config, registry, d.settings, host_capacity(d.run))
            # Also fence a login left running across a broker restart. Do not
            # guess whether its PID belongs to this host or the container.
            if (self.root / 'bots' / pubkey / 'state' / 'portal-auth.json').exists():
                raise ToolError('authentication_already_in_progress')
            # The operator explicitly consented to interrupt this one bot. The
            # device deploy-only API still requires a prior native stop.
            if actual:
                before = d.inspect(container_name(pubkey))
                if not before or before.get('Id') != actual.get('Id'):
                    raise ToolError('bot_update_container_changed')
                if preserve_lifecycle and before.get('State', {}).get('Running'):
                    raise ToolError('update_requires_interruption_confirmation')
                d.run(['docker', 'stop', '--time', '70', actual['Id']], timeout=80)
                stopped = d.inspect(container_name(pubkey))
                if stopped:
                    check_ownership(stopped, config)
                    if (stopped.get('Id') != actual.get('Id') or stopped.get('State', {}).get('Running')
                            or stopped.get('State', {}).get('Restarting') or stopped.get('State', {}).get('Pid', 0) != 0):
                        raise ToolError('bot_update_stop_unconfirmed')
                else:
                    raise ToolError('bot_update_container_changed')
            return d._deploy_locked(config, runtime_state=saved_state if preserve_lifecycle else None,
                                    start=was_running if preserve_lifecycle else True,
                                    expected_container_id=actual['Id'] if actual else None,
                                    commit_memory=bool(choice) and not preserve_lifecycle)
        finally:
            for auth_fd in auth_locks:
                os.close(auth_fd)
            os.close(fd)
