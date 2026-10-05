"""Independent exact-path/hash checks on clean 2cc CLI evidence."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path('/tmp/h09a-cr-2cc7b2f8-20261006')
CODE = '2cc7b2f885b3d33b46c719b89fb3c85d2ade2e96'
TREE = '73309b5d5bf61b0c02765eb833e1c308bd04eec0'
REPORTS = [Path('/tmp/h09a-cr-2cc7b2f8-' + tail) for tail in ('eval1', 'eval2', 'direct')]
projection = None
for directory in REPORTS:
    report = json.loads((directory / 'report.json').read_bytes())
    assert report['source']['commit'] == CODE and report['source']['tree'] == TREE
    assert report['complete'] and report['source_verified'] and report['gate_pass']
    assert not report['infra_errors']
    if projection is None:
        projection = report['stable_projection']
    assert projection == report['stable_projection']
    modules = report['source']['loaded_modules']
    for name, value in modules.items():
        prefix = 'packages/pioneer-agent/src' if name.startswith('pioneer_agent') else 'packages/sanmou-common/src'
        stem = ROOT / prefix / name.replace('.', '/')
        expected = stem / '__init__.py' if value['package_paths'] else stem.with_suffix('.py')
        assert Path(value['file']) == expected, (name, value)
        assert Path(value['origin']) == expected, (name, value)
        if value['package_paths']:
            assert value['package_paths'] == [str(stem)], (name, value)
    for relative, digest in report['artifacts'].items():
        assert hashlib.sha256((directory / relative).read_bytes()).hexdigest() == digest
    print(json.dumps({'report': str(directory), 'module_count': len(modules), 'exact_module_paths': True,
                      'launcher': report['source']['launcher'], 'artifact_digests': True, 'stable_projection_equal': True}))
protected = Path('/tmp/h09a-protected-b338-upcfx4ye/protected-blobs.jsonl')
entries = {}
for row in subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-r', '-z', CODE]).split(b'\0'):
    if row:
        meta, name = row.split(b'\t')
        mode, kind, oid = meta.decode().split()
        entries[name.decode()] = {'mode': mode, 'type': kind, 'oid': oid}
rows = [json.loads(row) for row in protected.read_bytes().splitlines()]
assert all(entries[row['path']] == {key: row[key] for key in ('mode', 'type', 'oid')} for row in rows)
print(json.dumps({'protected_paths_unchanged': len(rows), 'source': CODE, 'tree': TREE}))
