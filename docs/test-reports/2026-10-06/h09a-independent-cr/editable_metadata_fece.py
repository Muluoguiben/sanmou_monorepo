"""Generate ordinary local setuptools metadata only; no pip, installs or network."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/tmp/h09a-cr-fece-editable-metadata')
OUT = Path('/tmp/h09a-cr-fece-editable-metadata-evidence')
OUT.mkdir(exist_ok=False)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=f'{ROOT}/packages/pioneer-agent/src:{ROOT}/packages/sanmou-common/src:/tmp/sanmou-cr-20261005-6155-deps')
def record(name, args, cwd):
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    obj = {'argv': args, 'cwd': str(cwd), 'code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
    (OUT / (name + '.json')).write_text(json.dumps(obj, indent=2))
    return p
assert subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD']).decode().strip() == 'fece4163d04af5057493549da2db74a8fa65ed06'
build = record('setuptools-egg-info', [sys.executable, '-B', '-c', "from setuptools import setup; setup(script_args=['egg_info'])"], ROOT / 'packages/pioneer-agent')
assert build.returncode == 0, build.stderr
metadata = {}
for path in sorted((ROOT / 'packages/pioneer-agent/src/pioneer_agent.egg-info').iterdir()):
    raw = path.read_bytes()
    metadata[str(path.relative_to(ROOT))] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
assert metadata
status = subprocess.check_output(['git', '-C', str(ROOT), 'status', '--porcelain']).decode()
cli = record('committed-cli', [sys.executable, '-B', '-m', 'pioneer_agent.app.task_eval', '--output', str(OUT / 'report')], ROOT)
diagnostic = record('source-diagnostic', [sys.executable, '-B', '-c', 'from pathlib import Path; from pioneer_agent.agent_harness import task_eval; task_eval.SourceBinding(Path(' + repr(str(ROOT)) + '))'], ROOT)
report = json.loads((OUT / 'report/report.json').read_bytes())
result = {'source_commit': 'fece4163d04af5057493549da2db74a8fa65ed06', 'git_status_porcelain': status,
          'generated_metadata': metadata, 'cli_exit': cli.returncode, 'source_verified': report['source_verified'],
          'gate_pass': report['gate_pass'], 'diagnostic': diagnostic.stderr,
          'expected_behavior': 'ordinary non-source setuptools metadata should not invalidate otherwise unchanged committed source'}
(OUT / 'summary.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
assert cli.returncode == 0 and report['gate_pass'], 'ordinary generated egg-info metadata prevents documented committed CLI evaluation'
