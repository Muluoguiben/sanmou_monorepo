"""Verify real CLI source-drift rejection in isolated negative-only worktrees."""
import json
import os
from pathlib import Path
import subprocess
import sys

results = []
for kind, reason in [('byte-drift', 'source_byte_drift:'), ('untracked', 'untracked_source:')]:
    root = Path('/tmp/h09a-cr-2cc-' + kind)
    output = Path('/tmp/h09a-cr-2cc-' + kind + '-verified-output')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=f'{root}/packages/pioneer-agent/src:{root}/packages/sanmou-common/src:/tmp/sanmou-cr-20261005-6155-deps')
    args = [sys.executable, '-B', '-m', 'pioneer_agent.app.task_eval', '--output', str(output)]
    process = subprocess.run(args, env=env, capture_output=True, text=True)
    report = json.loads((output / 'report.json').read_bytes())
    diagnostic = subprocess.run([sys.executable, '-B', '-c',
        'from pathlib import Path; from pioneer_agent.agent_harness import task_eval; task_eval.SourceBinding(Path(' + repr(str(root)) + '))'], env=env, capture_output=True, text=True)
    record = {'kind': kind, 'argv': args, 'code': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr,
              'report': report, 'diagnostic_code': diagnostic.returncode, 'diagnostic_stderr': diagnostic.stderr}
    results.append(record)
    assert process.returncode == 2, record
    assert not report['source_verified'] and not report['gate_pass'] and not report['complete'], record
    assert not report['cases'], record
    assert reason in diagnostic.stderr, record
print(json.dumps(results, indent=2))
