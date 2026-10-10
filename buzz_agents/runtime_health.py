"""Bounded cgroup-v2 observations. Counters report evidence, never stop a worker."""
from pathlib import Path
import time

INTEGER_FIELDS = frozenset('pids_current pids_peak pids_events_max pids_events_baseline pids_events_delta memory_current memory_peak memory_events_oom memory_events_oom_kill sampled_at'.split())
LIMIT_FIELDS = frozenset(('pids_max', 'memory_max'))
WARNINGS = frozenset(('', 'runtime_process_limit_near_capacity'))


def number(value):
    return type(value) is int and 0 <= value <= 2**63 - 1


def public_resources(value):
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if
            (k in INTEGER_FIELDS and number(v)) or
            (k in LIMIT_FIELDS and (v is None or number(v))) or
            (k == 'health_warning' and isinstance(v, str) and v in WARNINGS)}


class ResourceSampler:
    def __init__(self, root='/sys/fs/cgroup'):
        self.root = Path(root)
        self.baseline = None
        self.last_counter = None
        self.delta = 0
        self.diagnostic = ''

    def read(self, name):
        try:
            with (self.root / name).open('rb') as f:
                raw = f.read(4097)
            return raw.decode('ascii') if len(raw) <= 4096 else ''
        except (OSError, UnicodeError):
            return ''

    def sample(self):
        result = {'sampled_at': int(time.time()), 'health_warning': ''}
        for name in ('pids.current', 'pids.max', 'pids.peak', 'memory.current', 'memory.max', 'memory.peak'):
            text = self.read(name).strip()
            if text == 'max' and name.endswith('.max'):
                result[name.replace('.', '_')] = None
            elif text.isascii() and text.isdigit() and len(text) <= 19:
                value = int(text)
                if number(value):
                    result[name.replace('.', '_')] = value
        for file, fields in (('pids.events', ('max',)), ('memory.events', ('oom', 'oom_kill'))):
            for line in self.read(file).splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0] in fields and parts[1].isascii() and parts[1].isdigit() and len(parts[1]) <= 19:
                    value = int(parts[1])
                    if number(value):
                        result[file.replace('.', '_') + '_' + parts[0]] = value
        counter = result.get('pids_events_max')
        if counter is not None:
            if self.baseline is None:
                self.baseline = counter
            if self.last_counter is not None and counter >= self.last_counter:
                self.delta = min(2**63-1, self.delta + counter - self.last_counter)
            self.last_counter = counter
            result.update(pids_events_baseline=self.baseline, pids_events_delta=self.delta)
            if self.delta:
                self.diagnostic = 'runtime_process_limit'
        current, limit = result.get('pids_current'), result.get('pids_max')
        if current is not None and limit and current * 10 >= limit * 9:
            result['health_warning'] = 'runtime_process_limit_near_capacity'
        return public_resources(result)
