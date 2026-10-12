"""Trusted, networkless host-swap helper. No client-supplied paths or commands.

Only rootful Linux Docker on ext4/XFS is supported. Active shards are never
resized, reformatted, deleted or swapped off, including during image upgrades.
"""
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import uuid

from .common import ToolError
from .policy import atomic_json

ROOT = Path('/var/lib/buzz-agents-v2/swap')
MIB = 1024 ** 2
POLICY = 'ram3-v1'
LABEL = 'io.buzz-agents.swap-policy'


def private_json(path, default=None):
    try:
        st = path.lstat()
    except FileNotFoundError:
        return default
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077
            or st.st_nlink != 1 or st.st_size > MIB):
        raise ToolError('swap_unsafe_state')
    try:
        return json.loads(path.read_text())
    except (ValueError, UnicodeError):
        raise ToolError('swap_invalid_state') from None


def checked_directory(root):
    parent = root.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or parent.st_mode & 0o022:
        raise ToolError('swap_unsafe_directory')
    root.mkdir(mode=0o700, parents=False, exist_ok=True)
    st = root.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077:
        raise ToolError('swap_unsafe_directory')


def command(argv):
    try:
        p = subprocess.run(argv, capture_output=True, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ToolError('swap_command_failed') from None
    if argv[0] == 'blkid' and (p.returncode or p.stderr.strip()):
        # Exit 2 also means unreadable content, not proof of an empty file.
        raise ToolError('swap_probe_failed')
    if p.returncode:
        raise ToolError('swap_activation_or_filesystem_denied')
    return p.stdout.decode().strip()


def active_swaps():
    result = {}
    for line in Path('/proc/swaps').read_text().splitlines()[1:]:
        fields = line.split()
        if len(fields) != 5:
            raise ToolError('swap_inventory_unavailable')
        name = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), fields[0])
        result[name] = {'bytes': int(fields[2]) * 1024, 'used': int(fields[3]) * 1024}
    return result


def disk(root):
    s = os.statvfs(root)
    return s.f_bavail * s.f_frsize, s.f_blocks * s.f_frsize


def allocation(budget, managed, free, total, target, active):
    """Byte arithmetic; a fixed budget prevents repeated 30%-of-remainder growth."""
    reserve = max(5 * 1024**3, total // 10)
    return max(0, min(budget - managed, free - reserve, target - active)) // MIB * MIB


class Pool:
    def __init__(self, root=ROOT, run=command, inventory=active_swaps, space=disk):
        self.root, self.run, self.inventory, self.space = Path(root), run, inventory, space

    def load(self):
        state = private_json(self.root / 'pool.json')
        if state is None:
            # Unjournalled files must never be adopted or formatted.
            if list(self.root.glob('chunk-*')):
                raise ToolError('swap_untracked_file')
            free, _ = self.space(self.root)
            state = {'schema': 1, 'budget': free * 30 // 100 // MIB * MIB, 'shards': []}
            self.save(state)
        if (not isinstance(state, dict) or set(state) != {'schema', 'budget', 'shards'}
                or state['schema'] != 1 or type(state['budget']) is not int or state['budget'] < 0
                or not isinstance(state['shards'], list) or len(state['shards']) > 8):
            raise ToolError('swap_invalid_state')
        names = set()
        for s in state['shards']:
            if (not isinstance(s, dict) or set(s) not in ({'name', 'size', 'phase', 'inode', 'device'},
                                                   {'name', 'size', 'phase', 'inode', 'device', 'uuid'})
                    or not re.fullmatch(r'chunk-[0-9]{4}', s.get('name', ''))
                    or s['name'] in names or type(s['size']) is not int or s['size'] < 64*MIB
                    or s['phase'] not in ('allocating', 'reserving', 'formatting', 'ready')
                    or type(s['inode']) is not int or type(s['device']) is not int):
                raise ToolError('swap_invalid_state')
            if ('uuid' in s and not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', str(s['uuid']))) or (
                    s['phase'] in ('reserving', 'formatting') and 'uuid' not in s):
                raise ToolError('swap_invalid_state')
            names.add(s['name'])
        if sum(s['size'] for s in state['shards']) > state['budget']:
            raise ToolError('swap_invalid_state')
        if {p.name for p in self.root.glob('chunk-*')} - names:
            raise ToolError('swap_untracked_file')
        return state

    def save(self, state):
        atomic_json(self.root / 'pool.json', state)

    def verify(self, shard, partial=False):
        path = self.root / shard['name']
        st = path.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != 0 or st.st_mode & 0o077
                or st.st_nlink != 1 or st.st_ino != shard['inode'] or st.st_dev != shard['device']
                or (not 0 <= st.st_size <= shard['size'] if partial else st.st_size != shard['size'])):
            raise ToolError('swap_file_changed')
        return path

    def activate(self, state):
        active = self.inventory()
        for s in state['shards']:
            path = self.root / s['name']
            if s['phase'] in ('reserving', 'formatting'):
                self.resume(state, s)
            if s['phase'] != 'ready':
                # A crash during allocation/mkswap is uncertain. Never guess that
                # a partial file is safe to reformat. Keep it and report recovery.
                raise ToolError('swap_allocation_interrupted')
            self.verify(s)
            if str(path) not in active:
                self.run(['swapon', '--', str(path)])
                active = self.inventory()
            if str(path) not in active:
                raise ToolError('swap_activation_unconfirmed')
        return active

    def add(self, state, size):
        if len(state['shards']) >= 8:
            raise ToolError('swap_shard_limit')
        name = 'chunk-%04d' % len(state['shards'])
        path = self.root / name
        # Separate unformatted allocation from uncertain legacy journals.
        shard = dict(name=name, size=size, phase='reserving', inode=0, device=0,
                     uuid=str(uuid.uuid4()))
        state['shards'].append(shard)
        self.save(state)
        self.resume(state, shard)
        self.activate(state)

    def resume(self, state, shard):
        path = self.root / shard['name']
        if shard['phase'] == 'reserving':
            if str(path) in self.inventory():
                raise ToolError('swap_file_unexpectedly_active')
            if shard['inode'] == 0:
                # Missing file is safe to create. An existing unrecorded inode
                # is never adopted, even when it has our intended filename.
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                try:
                    st = os.fstat(fd)
                    shard.update(inode=st.st_ino, device=st.st_dev)
                    self.save(state)
                finally:
                    os.close(fd)
            self.verify(shard, partial=True)
            fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
            try:
                st = os.fstat(fd)
                if (st.st_ino, st.st_dev) != (shard['inode'], shard['device']):
                    raise ToolError('swap_file_changed')
                free, total = self.space(self.root)
                needed = max(0, shard['size'] - st.st_blocks * 512)
                if free - max(5 * 1024**3, total // 10) < needed:
                    raise ToolError('swap_disk_reserve')
                # Repeating allocation is safe only BEFORE any mkswap call.
                os.posix_fallocate(fd, 0, shard['size'])
                os.fsync(fd)
            finally:
                os.close(fd)
            self.verify(shard)
            # Only this transition proves we have never attempted formatting.
            # Persist before invoking mkswap; after any interruption recovery is
            # read-only and must positively identify our completed signature.
            shard['phase'] = 'formatting'
            self.save(state)
            self.run(['mkswap', '--uuid', shard['uuid'], '--', str(path)])
            shard['phase'] = 'ready'
            self.save(state)
            return
        self.verify(shard)
        signature = self.run(['blkid', '-p', '-o', 'export', '--', str(path)])
        fields = dict(line.split('=', 1) for line in signature.splitlines() if '=' in line)
        if fields.get('TYPE') == 'swap' and fields.get('UUID') == shard['uuid']:
            # mkswap completed before a crash/save failure: do NOT format again.
            pass
        else:
            raise ToolError('swap_signature_changed')
        shard['phase'] = 'ready'
        self.save(state)

    def tick(self, target_mb):
        if type(target_mb) is not int or not 0 <= target_mb <= 2**31:
            raise ToolError('swap_invalid_target')
        checked_directory(self.root)
        fd = os.open(self.root / 'pool.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if self.run(['stat', '-f', '-c', '%T', str(self.root)]) not in ('ext2/ext3', 'ext4', 'xfs'):
                raise ToolError('swap_filesystem_unsupported')
            # Do not freeze the budget before the first bot actually exists.
            state = self.load() if target_mb or (self.root/'pool.json').exists() else {'budget': 0, 'shards': []}
            active = self.activate(state)
            managed = sum(s['size'] for s in state['shards'])
            total_active = sum(s['bytes'] for s in active.values())
            free, total = self.space(self.root)
            amount = allocation(state['budget'], managed, free, total, target_mb*MIB, total_active)
            # Use at most eight managed swap areas. Larger shards avoid exhausting
            # the kernel's finite area table; external areas also consume slots.
            slots = max(0, 8-len(state['shards']))
            area_limited = not slots or len(active) >= 24
            if amount >= 64*MIB and not area_limited:
                chunk = max(1024*MIB, ((amount+slots-1)//slots+MIB-1)//MIB*MIB)
                self.add(state, min(amount, chunk))
                active = self.inventory()
                managed = sum(s['size'] for s in state['shards'])
                total_active = sum(s['bytes'] for s in active.values())
                free, total = self.space(self.root)
            remaining = allocation(state['budget'], managed, free, total, target_mb*MIB, total_active)
            # One swap-header page per file is not a capacity shortage.
            sufficient = total_active + len(active)*os.sysconf('SC_PAGE_SIZE') >= target_mb*MIB
            return {'state': 'ready' if sufficient else ('preparing' if remaining >= 64*MIB and len(state['shards']) < 8 and len(active) < 24 else 'limited'),
                    'target_mb': target_mb, 'total_mb': total_active//MIB,
                    'used_mb': sum(s['used'] for s in active.values())//MIB,
                    'managed_mb': managed//MIB, 'budget_mb': state['budget']//MIB,
                    'free_mb': free//MIB, 'checked_at': int(time.time())}
        finally:
            os.close(fd)


def main():
    checked_directory(ROOT)
    pool = Pool()
    while True:
        try:
            request = private_json(ROOT/'request.json', {})
            if set(request) != {'target_mb'}:
                raise ToolError('swap_invalid_target')
            status = pool.tick(request['target_mb'])
        except BlockingIOError:
            # Controller may still hold pool.lock while starting this helper.
            # Contention is not an activation error and must not overwrite status.
            time.sleep(1)
            continue
        except Exception as exc:
            reason = str(exc) if isinstance(exc, ToolError) else 'swap_operation_failed'
            status = {'state': 'attention', 'reason': reason, 'checked_at': int(time.time())}
        atomic_json(ROOT/'status.json', status)
        time.sleep(10 if status['state'] == 'preparing' else 30)


if __name__ == '__main__':
    main()
