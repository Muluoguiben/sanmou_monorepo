"""Read-only evidence audit; creates a new manifest without rewriting artifacts."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tarfile

HERE = Path(__file__).resolve().parent
SOURCE = Path('/tmp/sanmou-h09a-selftest-2cc7b2f')
SHA = '2cc7b2f885b3d33b46c719b89fb3c85d2ade2e96'
TREE = '73309b5d5bf61b0c02765eb833e1c308bd04eec0'
PROTECTED = Path('/tmp/h09a-protected-b338-upcfx4ye/protected-blobs.jsonl')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def git(*args):
    return subprocess.run(['git', '-C', str(SOURCE), *args], check=True, capture_output=True).stdout

assert git('rev-parse', 'HEAD').decode().strip() == SHA
assert git('rev-parse', 'HEAD^{tree}').decode().strip() == TREE
assert not git('status', '--porcelain')
protected_bytes = PROTECTED.read_bytes()
assert sha(protected_bytes) == '651d4fd446e46c8dd2ae661ce27387016a0ff160ea94ec36f1de2c189531ae3e'
objects = {}
for row in git('ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
    if row:
        meta, path = row.split(b'\t', 1)
        mode, kind, oid = meta.decode().split()
        objects[path.decode()] = {'mode': mode, 'type': kind, 'oid': oid}
protected = [json.loads(line) for line in protected_bytes.splitlines()]
for entry in protected:
    assert objects[entry['path']] == {key: entry[key] for key in ('mode', 'type', 'oid')}, entry['path']

reports = []
for name in ('h09a-2cc7b2f-eval1', 'h09a-2cc7b2f-eval2', 'h09a-2cc7b2f-direct'):
    base = HERE / 'raw' / name
    report = json.loads((base / 'report.json').read_bytes())
    assert report['source']['commit'] == SHA and report['source']['tree'] == TREE
    assert report['source_verified'] and report['complete'] and report['gate_pass']
    assert report['source']['launcher']['bound']
    for relative, expected in report['artifacts'].items():
        assert sha((base / relative).read_bytes()) == expected, (name, relative)
    reports.append(report)
assert reports[0]['stable_projection'] == reports[1]['stable_projection'] == reports[2]['stable_projection']
assert reports[0]['inputs'] == reports[1]['inputs'] == reports[2]['inputs']

files = {}
logs = {}
for path in sorted((HERE / 'raw').rglob('*')):
    if not path.is_file():
        continue
    raw = path.read_bytes()
    relative = path.relative_to(HERE).as_posix()
    files[relative] = {'bytes': len(raw), 'sha256': sha(raw)}
    original = Path('/tmp') / path.relative_to(HERE / 'raw')
    if path.suffix != '.gz':
        assert original.read_bytes() == raw, relative
    if path.suffix == '.log':
        text = raw.decode()
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
        if match:
            skipped = re.search(r'OK \(skipped=(\d+)\)', text)
            failures = re.search(r'FAILED \(([^\n]+)\)', text)
            logs[path.name] = {'total': int(match[1]), 'seconds': float(match[2]),
                'skipped': int(skipped[1]) if skipped else 0,
                'failure_summary': failures[1] if failures else None,
                'status': 'failed' if failures else 'passed'}

members = {}
with tarfile.open(HERE / 'raw/frozen-probe-replay.tar.gz') as archive:
    for member in archive.getmembers():
        if member.isfile():
            raw = archive.extractfile(member).read()
            assert (Path('/tmp') / member.name).read_bytes() == raw
            members[member.name] = {'bytes': len(raw), 'sha256': sha(raw)}
        elif member.issym():
            members[member.name] = {'type': 'symlink', 'target': member.linkname}

for name in ('replay_frozen_cr.py', 'audit_evidence.py'):
    raw = (HERE / name).read_bytes()
    files[name] = {'bytes': len(raw), 'sha256': sha(raw)}
manifest = {
    'source_commit': SHA, 'source_tree': TREE, 'source_root': str(SOURCE),
    'source_status_clean': True, 'protected_paths_unchanged': len(protected),
    'protected_manifest_sha256': sha(protected_bytes),
    'frozen_cr_commit': '2bcd73e7b474c32f5aaf28f77e81c5bfc1cd2082',
    'formal_stable_projections_equal': True, 'formal_totals': reports[0]['totals'],
    'source_file_count': len(reports[0]['source']['raw_byte_manifest']),
    'loaded_module_count': len(reports[0]['source']['loaded_modules']),
    'input_file_count': len(reports[0]['inputs']),
    'environment': {'python': sys.version, 'executable': sys.executable,
        'platform': platform.platform(), 'PYTHONPATH': os.environ.get('PYTHONPATH'),
        'PYTHONDONTWRITEBYTECODE': os.environ.get('PYTHONDONTWRITEBYTECODE'),
        'versions': {name: importlib.metadata.version(name) for name in ('pydantic', 'PyYAML', 'mcp', 'anyio')}},
    'logs': logs, 'files': files, 'frozen_probe_replay_members': members,
    'independent_reapproval': False, 'h06_windows_acceptance': False,
}
target = HERE / 'evidence-manifest.json'
with target.open('x', encoding='utf-8') as handle:
    json.dump(manifest, handle, ensure_ascii=False, indent=2)
    handle.write('\n')
print(json.dumps({'manifest_sha256': sha(target.read_bytes()), 'files': len(files),
    'probe_members': len(members), 'protected_paths': len(protected), 'logs': logs}, ensure_ascii=False, indent=2))
