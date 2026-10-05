"""CR05 immutable source, old evidence, generated metadata and raw-byte audit."""
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
SOURCE = Path('/tmp/sanmou-h09a-cr05-103d0d1')
METADATA_SOURCE = Path('/tmp/sanmou-h09a-cr05-metadata-103d0d1')
SHA = '103d0d1594a11af905515182913731d2d8bb4ac9'
TREE = 'e9b80b3a76b494b73e0266cb383793cacb3e246d'
OLD_REPORT = '08c97024b4c0566c26f5c2b0461c1efb3e5d3c23'
OLD_PREFIX = 'docs/test-reports/2026-10-06/h09a-selftest'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def git(*args, root=SOURCE):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True).stdout

def tree(ref, *paths):
    result = {}
    for row in git('ls-tree', '-r', '-z', ref, '--', *paths).split(b'\0'):
        if row:
            meta, name = row.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            result[name.decode()] = {'mode': mode, 'type': kind, 'oid': oid}
    return result

for root in (SOURCE, METADATA_SOURCE):
    assert git('rev-parse', 'HEAD', root=root).decode().strip() == SHA
    assert git('rev-parse', 'HEAD^{tree}', root=root).decode().strip() == TREE
    assert not git('status', '--porcelain', root=root)
objects = tree('HEAD')
protected_raw = Path('/tmp/h09a-protected-b338-upcfx4ye/protected-blobs.jsonl').read_bytes()
assert sha(protected_raw) == '651d4fd446e46c8dd2ae661ce27387016a0ff160ea94ec36f1de2c189531ae3e'
protected = [json.loads(line) for line in protected_raw.splitlines()]
for entry in protected:
    assert objects[entry['path']] == {k: entry[k] for k in ('mode', 'type', 'oid')}
old = tree(OLD_REPORT, OLD_PREFIX)
assert old == tree('HEAD', OLD_PREFIX)

reports = []
for name in ('eval1', 'eval2', 'direct'):
    base = HERE / 'raw' / ('h09a-cr05-103d0d1-' + name)
    report = json.loads((base / 'report.json').read_bytes())
    assert report['complete'] and report['gate_pass'] and report['source_verified']
    assert report['source']['commit'] == SHA and report['source']['tree'] == TREE
    assert report['source']['non_source_metadata']['files'] == {}
    reports.append(report)
metadata_root = HERE / 'raw/h09a-cr05-103d0d1-metadata'
matrix = json.loads((metadata_root / 'matrix.json').read_bytes())
assert len(matrix['cases']) == 18 and sum(not r['expected_pass'] for r in matrix['cases']) == 16
for relative, count in (('report', 5), ('both-packages-positive', 10), ('restored-both-packages-positive', 10)):
    report = json.loads((metadata_root / relative / 'report.json').read_bytes())
    assert report['source_verified'] and report['complete'] and report['gate_pass']
    assert report['source']['commit'] == SHA and report['source']['tree'] == TREE
    recorded = report['source']['non_source_metadata']
    assert recorded['git_bound'] is False and recorded['interpreted_by_evaluator'] is False
    assert len(recorded['files']) == count
    for path, entry in recorded['files'].items():
        raw = (METADATA_SOURCE / path).read_bytes()
        assert entry == {'bytes': len(raw), 'sha256': sha(raw)}
    reports.append(report)
assert all(r['stable_projection'] == reports[0]['stable_projection'] for r in reports)
assert all(r['inputs'] == reports[0]['inputs'] for r in reports)

files, logs = {}, {}
for path in sorted((HERE / 'raw').rglob('*')):
    if not path.is_file():
        continue
    raw = path.read_bytes()
    relative = path.relative_to(HERE).as_posix()
    files[relative] = {'bytes': len(raw), 'sha256': sha(raw)}
    if path.suffix != '.gz':
        assert raw == (Path('/tmp') / path.relative_to(HERE / 'raw')).read_bytes()
    if path.name == 'report.json':
        report = json.loads(raw)
        for relative_artifact, expected in report.get('artifacts', {}).items():
            assert sha((path.parent / relative_artifact).read_bytes()) == expected
    if path.suffix == '.log':
        text = raw.decode()
        match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
        if match:
            skip = re.search(r'OK \(skipped=(\d+)\)', text)
            logs[path.name] = {'total': int(match[1]), 'seconds': float(match[2]),
                'skipped': int(skip[1]) if skip else 0, 'failed': 'FAILED (' in text}

inventories = {}
for filename, original_root in (('probes.tar.gz', Path('/tmp')), ('generated-metadata.tar.gz', METADATA_SOURCE)):
    members = {}
    with tarfile.open(HERE / 'raw' / filename) as archive:
        for member in archive.getmembers():
            if member.isfile():
                raw = archive.extractfile(member).read()
                assert raw == (original_root / member.name).read_bytes()
                members[member.name] = {'type': 'regular', 'bytes': len(raw), 'sha256': sha(raw)}
            elif member.issym():
                members[member.name] = {'type': 'symlink', 'target': member.linkname}
            elif member.isdir():
                members[member.name] = {'type': 'directory'}
            else:
                raise AssertionError('unexpected archive type')
    inventories[filename] = members
for name in ('audit.py', 'replay_cr.py', 'metadata_cli_regression.py'):
    raw = (HERE / name).read_bytes()
    files[name] = {'bytes': len(raw), 'sha256': sha(raw)}
manifest = {'source_commit': SHA, 'source_tree': TREE, 'source_root': str(SOURCE),
    'metadata_source_root': str(METADATA_SOURCE), 'both_git_status_clean': True,
    'protected_paths_unchanged': len(protected), 'old_report_commit': OLD_REPORT,
    'old_report_paths_unchanged': len(old), 'formal_stable_projections_equal': True,
    'formal_totals': reports[0]['totals'], 'metadata_cli_matrix': matrix,
    'source_file_count': len(reports[0]['source']['raw_byte_manifest']),
    'input_file_count': len(reports[0]['inputs']),
    'environment': {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
        'PYTHONPATH': os.environ.get('PYTHONPATH'), 'PYTHONDONTWRITEBYTECODE': os.environ.get('PYTHONDONTWRITEBYTECODE'),
        'versions': {name: importlib.metadata.version(name) for name in ('pydantic', 'PyYAML', 'mcp', 'anyio', 'setuptools')}},
    'files': files, 'logs': logs, 'typed_archives': inventories,
    'independent_reapproval': False, 'h06_windows_acceptance': False}
target = HERE / 'evidence-manifest.json'
with target.open('x', encoding='utf-8') as handle:
    json.dump(manifest, handle, ensure_ascii=False, indent=2)
    handle.write('\n')
print(json.dumps({'manifest_sha256': sha(target.read_bytes()), 'files': len(files),
    'protected_paths': len(protected), 'old_report_paths': len(old), 'logs': logs}, indent=2))
