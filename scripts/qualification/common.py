"""D04 evidence: fixed thresholds, measured host and sanitized machine-readable results."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import time
from datetime import datetime, timezone


def optional_text(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ''


def hardware():
    memory = next((line.split()[1] for line in optional_text('/proc/meminfo').splitlines()
                   if line.startswith('MemTotal:')), None)
    limits = {}
    for key in ('memory.max', 'cpu.max', 'pids.max'):
        path = Path('/sys/fs/cgroup') / key
        if path.is_file():
            limits[key] = path.read_text().strip()
    cpu = next((line.split(':', 1)[1].strip() for line in optional_text('/proc/cpuinfo').splitlines()
                if line.startswith('model name')), platform.machine())
    return {'os': platform.platform(), 'architecture': platform.machine(), 'cpu': cpu,
            'logical_cpus': os.cpu_count(), 'memory_kib': int(memory) if memory else None,
            'cgroup_limits': limits, 'gpu_measured': False}


class Evidence:
    def __init__(self, group, output):
        self.output = Path(output)
        self.data = {'schema': 1, 'lot': 'D04', 'group': group,
                     'scope': os.environ.get('NEVOLIUM_QUALIFICATION_SCOPE', 'development-host'),
                     'commit': os.environ.get('NEVOLIUM_QUALIFICATION_COMMIT', 'unrecorded'),
                     'started_at': datetime.now(timezone.utc).isoformat(), 'hardware': hardware(),
                     'provider_calls_paid': False, 'cases': [], 'd04_gate': 'incomplete'}
        self.save()

    def save(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        temp = self.output.with_suffix('.tmp')
        temp.write_text(json.dumps(self.data, indent=2) + '\n')
        temp.replace(self.output)

    def finish(self):
        self.data['finished_at'] = datetime.now(timezone.utc).isoformat()
        self.save()
        print(json.dumps(self.data), flush=True)

    def case(self, name, deadline, call):
        started = time.monotonic()
        row = {'id': name, 'threshold_seconds': deadline, 'status': 'running'}
        self.data['cases'].append(row)
        self.save()
        try:
            details = call() or {}
            elapsed = time.monotonic() - started
            if elapsed > deadline:
                raise TimeoutError('Qualification threshold exceeded')
            row.update(status='passed', details=details)
        except Exception as exc:
            # Never put exception text, DSNs, tokens or document contents in evidence.
            row.update(status='failed', error_class=type(exc).__name__)
            raise
        finally:
            row.update(elapsed_seconds=round(time.monotonic() - started, 3),
                       process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                       child_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
            self.save()
            print(json.dumps(row), flush=True)


def versions(names):
    return {name: importlib.metadata.version(name) for name in names}


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def command(args, *, timeout=300, **kwargs):
    return subprocess.run(args, check=True, timeout=timeout, **kwargs)
