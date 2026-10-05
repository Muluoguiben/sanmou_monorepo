"""Bind raw local evidence and protected Git blobs without changing either."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path('/tmp/h09a-cr-64adbfbb-20261006')
PROTECTED = Path('/tmp/h09a-protected-b338-upcfx4ye/protected-blobs.jsonl')
COMMITS = ['64adbfbb951754a36cfd9189f4294d70b323eb28', '134d73b0960d51b6361fb4085a58a3d598a74595']
def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])
protected = [json.loads(line) for line in PROTECTED.read_bytes().splitlines()]
results = {}
for commit in COMMITS:
    entries = {}
    for line in git('ls-tree', '-r', '-z', commit).split(b'\0'):
        if line:
            meta, path = line.split(b'\t')
            mode, kind, oid = meta.decode().split()
            entries[path.decode()] = {'mode': mode, 'type': kind, 'oid': oid}
    mismatches = [row['path'] for row in protected if entries.get(row['path']) != {k: row[k] for k in ('mode', 'type', 'oid')}]
    results[commit] = {'tree': git('rev-parse', commit + '^{tree}').decode().strip(), 'protected_paths': len(protected), 'mismatches': mismatches}
paths = [Path(p) for p in (
    '/tmp/h09a-cr-64adbfbb-eval1', '/tmp/h09a-cr-64adbfbb-eval2',
    '/tmp/h09a-independent-probes-4c1rskcf', '/tmp/h09a-supplemental-exe7yxqj',
    '/tmp/h09a-independent-probes-vaz958sk', '/tmp/h09a-supplemental-eucap0gm',
    '/tmp/h09a-cr-64adbfbb-eval1.log', '/tmp/h09a-cr-64adbfbb-eval2.log',
    '/tmp/h09a-cr-64adbfbb-focused.log', '/tmp/h09a-cr-64adbfbb-task-regression.log',
    '/tmp/h09a-cr-64adbfbb-probes-first.log', '/tmp/h09a-cr-64adbfbb-supplement-first.log',
    '/tmp/h09a-cr-134d73b0-probes-first.log')]
manifest = {}
for root in paths:
    for path in ([root] if root.is_file() else sorted(root.rglob('*'))):
        if path.is_file():
            raw = path.read_bytes()
            manifest[str(path)] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
report = {'python': sys.version, 'platform': platform.platform(), 'protected_manifest_sha256': hashlib.sha256(PROTECTED.read_bytes()).hexdigest(), 'source': results, 'artifacts': manifest}
with (HERE / 'evidence-manifest.json').open('x') as f:
    json.dump(report, f, indent=2)
print(json.dumps({'source': results, 'artifact_count': len(manifest), 'protected_manifest_sha256': report['protected_manifest_sha256']}))
assert all(not item['mismatches'] for item in results.values())
