"""Actual setuptools positive and malicious-metadata negatives on isolated ext4."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from pioneer_agent.agent_harness import task_eval as ev
from pioneer_agent.agent_harness._task_eval_inputs import InputError

ROOT = Path('/tmp/h09a-cr-103d-editable-metadata')
OUT = Path('/tmp/h09a-cr-103d-metadata-boundaries')
OUT.mkdir(exist_ok=False)
records = []
def record(name, callback):
    try:
        callback()
    except InputError as error:
        records.append({'name': name, 'rejected': True, 'reason': str(error)})
    else:
        records.append({'name': name, 'rejected': False})
        raise AssertionError('metadata negative accepted: ' + name)
try:
    build = subprocess.run([sys.executable, '-B', '-c', "from setuptools import setup; setup(script_args=['egg_info'])"],
        cwd=ROOT / 'packages/sanmou-common', capture_output=True, text=True)
    (OUT / 'common-setuptools.json').write_text(json.dumps({'code': build.returncode, 'stdout': build.stdout, 'stderr': build.stderr}))
    assert build.returncode == 0
    cli = subprocess.run([sys.executable, '-B', '-m', 'pioneer_agent.app.task_eval', '--output', str(OUT / 'both-metadata-report')],
        cwd=ROOT, capture_output=True, text=True)
    report = json.loads((OUT / 'both-metadata-report/report.json').read_bytes())
    assert cli.returncode == 0 and report['gate_pass'] and report['source_verified']
    meta = report['source']['non_source_metadata']
    assert not meta['git_bound'] and not meta['interpreted_by_evaluator']
    assert len(meta['files']) == 10
    assert set(meta['files']).isdisjoint(report['source']['raw_byte_manifest'])
    for relative, expected in meta['files'].items():
        raw = (ROOT / relative).read_bytes()
        assert expected == {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    records.append({'name': 'actual_setuptools_both_roots', 'positive': True, 'metadata_files': 10})
    for parent in (ROOT / 'packages/pioneer-agent/src/pioneer_agent.egg-info', ROOT / 'packages/sanmou-common/src/sanmou_common.egg-info'):
        for filename in ('hidden.py', 'native.so', 'inject.pth', 'unknown.txt', '__pycache__/hidden.py'):
            path = parent / filename
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'negative test artifact\n')
            try:
                record(str(path.relative_to(ROOT)), lambda: ev.SourceBinding(ROOT))
            finally:
                path.unlink()
                if path.parent != parent:
                    path.parent.rmdir()
        path = parent / 'PKG-INFO'
        original = path.read_bytes()
        for label, raw in [('nul', b'\0'), ('binary', b'\xff'), ('oversize', b'x' * 1000001)]:
            path.write_bytes(raw)
            try:
                record(str(parent.relative_to(ROOT)) + '/' + label, lambda: ev.SourceBinding(ROOT))
            finally:
                path.write_bytes(original)
        path.chmod(0o755)
        try:
            record(str(parent.relative_to(ROOT)) + '/executable', lambda: ev.SourceBinding(ROOT))
        finally:
            path.chmod(0o644)
        outside = OUT / ('outside-' + parent.name)
        outside.write_bytes(original)
        for kind in ('symlink', 'hardlink'):
            path.unlink()
            if kind == 'symlink':
                path.symlink_to(outside)
            else:
                path.hardlink_to(outside)
            try:
                record(str(parent.relative_to(ROOT)) + '/' + kind, lambda: ev.SourceBinding(ROOT))
            finally:
                path.unlink()
                path.write_bytes(original)
        binding = ev.SourceBinding(ROOT)
        path.write_bytes(original + b'changed\n')
        try:
            record(str(parent.relative_to(ROOT)) + '/runtime-drift', binding.verify_bytes)
        finally:
            path.write_bytes(original)
    other = ROOT / 'packages/pioneer-agent/src/unrelated.egg-info'
    other.mkdir()
    (other / 'PKG-INFO').write_bytes(b'unknown distribution\n')
    try:
        record('unknown-egg-info', lambda: ev.SourceBinding(ROOT))
    finally:
        (other / 'PKG-INFO').unlink()
        other.rmdir()
    assert not subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'])
finally:
    (OUT / 'results.json').write_text(json.dumps(records, indent=2))
print(json.dumps({'checks': len(records), 'positive': sum(r.get('positive', False) for r in records),
                  'rejected': sum(r.get('rejected', False) for r in records)}, indent=2))
