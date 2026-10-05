"""Real local egg_info and formal CLI negatives; no pip/install/network."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
SHA = '103d0d1594a11af905515182913731d2d8bb4ac9'
FROZEN = Path('/tmp/h09a-frozen-probes-0c40a7b/docs/test-reports/2026-10-06/h09a-independent-cr/editable_metadata_fece.py')
COMMIT = '0c40a7b426f16930dc1928abd903e2d249f14b2a'
assert not OUT.exists()
assert subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip() == SHA
original = subprocess.check_output(['git', '-C', str(ROOT), 'show',
    f'{COMMIT}:docs/test-reports/2026-10-06/h09a-independent-cr/editable_metadata_fece.py'])
assert original == FROZEN.read_bytes()
# The frozen reproducer is top-level code with fixed identity/path literals.
# Map only these three identifiers; leave every command and assertion unchanged.
mapping = {
    '/tmp/h09a-cr-fece-editable-metadata-evidence': str(OUT),
    '/tmp/h09a-cr-fece-editable-metadata': str(ROOT),
    'fece4163d04af5057493549da2db74a8fa65ed06': SHA,
}
mapped = original.decode()
for before, after in mapping.items():
    assert before in mapped
    mapped = mapped.replace(before, after)
exec(compile(mapped, str(FROZEN), 'exec'), {'__name__': '__main__', '__file__': str(FROZEN)})
(OUT / 'frozen-probe-mapping.json').write_text(json.dumps({
    'commit': COMMIT, 'original_sha256': hashlib.sha256(original).hexdigest(),
    'mapped_sha256': hashlib.sha256(mapped.encode()).hexdigest(), 'mapping': mapping,
    'assertions_changed': False}, indent=2))
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=':'.join(str(ROOT / p) for p in (
    'packages/pioneer-agent/src', 'packages/qa-agent/src', 'packages/sanmou-common/src',
    'packages/pioneer-agent/tests', 'packages/pioneer-agent/tests/unit')) + ':/tmp/sanmou-cr-20261005-6155-deps')

def record(name, args, cwd=ROOT):
    process = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    (OUT / (name + '.json')).write_text(json.dumps({'argv': args, 'cwd': str(cwd),
        'code': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr}, indent=2))
    return process

common = record('common-egg-info', [sys.executable, '-B', '-c',
    "import setuptools; print(setuptools.__version__); setuptools.setup(script_args=['egg_info'])"],
    ROOT / 'packages/sanmou-common')
assert common.returncode == 0, common.stderr
rows = []

def cli(name, expected):
    destination = OUT / name
    process = record(name + '-process', [sys.executable, '-B', '-m', 'pioneer_agent.app.task_eval',
                                       '--output', str(destination)])
    report = json.loads((destination / 'report.json').read_bytes())
    assert process.returncode == (0 if expected else 2), name
    assert report['gate_pass'] is expected and report['source_verified'] is expected, name
    if expected:
        assert len(report['source']['non_source_metadata']['files']) == 10
        assert report['totals']['control_pass'] == 8
    else:
        assert report['cases'] == [] and not report['complete'], name
    rows.append({'name': name, 'expected_pass': expected, 'exit': process.returncode,
                 'source_verified': report['source_verified'], 'gate_pass': report['gate_pass']})

cli('both-packages-positive', True)
for package, egg in (('pioneer-agent', 'pioneer_agent'), ('sanmou-common', 'sanmou_common')):
    directory = ROOT / 'packages' / package / 'src' / (egg + '.egg-info')
    for name in ('extra.py', 'native.so', 'hook.pth', 'unknown.txt', '__pycache__/hidden.py'):
        path = directory / name
        path.parent.mkdir(exist_ok=True)
        with path.open('xb') as handle:
            handle.write(b'# intentional negative fixture\n')
        try:
            cli(package + '-' + name.replace('/', '-'), False)
        finally:
            path.unlink()
            if path.parent.name == '__pycache__':
                path.parent.rmdir()
    metadata = directory / 'PKG-INFO'
    raw, mode = metadata.read_bytes(), stat.S_IMODE(metadata.stat().st_mode)
    metadata.chmod(mode | 0o111)
    try:
        cli(package + '-executable', False)
    finally:
        metadata.chmod(mode)
    target = OUT / (package + '-link-target.txt')
    target.write_bytes(raw)
    for kind in ('symlink', 'hardlink'):
        metadata.unlink()
        try:
            if kind == 'symlink':
                metadata.symlink_to(target)
            else:
                metadata.hardlink_to(target)
            cli(package + '-' + kind, False)
        finally:
            metadata.unlink()
            metadata.write_bytes(raw)
            metadata.chmod(mode)
cli('restored-both-packages-positive', True)
assert not subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain'])
(OUT / 'matrix.json').write_text(json.dumps({'source': SHA, 'cases': rows,
    'metadata_only_no_install': True, 'git_status_clean': True}, indent=2))
print(json.dumps({'formal_cli_matrix_pass': len(rows), 'negative_cases': sum(not r['expected_pass'] for r in rows),
                  'frozen_original_reproducer_passed': True, 'output': str(OUT)}), flush=True)
