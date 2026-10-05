"""Coordinator checks on the clean immutable Q02a integration worktree."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

source_root = Path('/tmp/sanmou-q02a-integration-94e1464')
output = Path(__file__).resolve().parent
label, package, *arguments = sys.argv[1:]
if not re.fullmatch(r'[a-z0-9-]+', label) or package not in {'qa-agent', 'pioneer-agent', 'sanmou-common'}:
    raise SystemExit('invalid check identity')

def git(*args):
    return subprocess.check_output(['git', *args], cwd=source_root, text=True).strip()

source, tree, packages_tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}'), git('rev-parse', 'HEAD:packages')
if source != '94e1464ba3fcff9b5874868138fa2d9f300fb376' or packages_tree != '3c643ef1d3fd0ae376ebea6b055d0aaba564edf8':
    raise SystemExit('wrong integration source')
subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'packages', 'apps', 'scripts', '.agent', '.github'], cwd=source_root, check=True)

env = {key: value for key, value in os.environ.items() if not any(
    secret in key.upper() for secret in ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY', 'AUTH', 'COOKIE'))}
env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
env['PYTHONPATH'] = os.pathsep.join(str(source_root / p) for p in (
    'packages/qa-agent/src', 'packages/pioneer-agent/src', 'packages/sanmou-common/src',
    'packages/qa-agent', 'packages/qa-agent/tests', 'packages/pioneer-agent/tests', 'packages/pioneer-agent/tests/unit',
    'docs/test-reports/2026-10-06/Q02a-CR-artifacts',
    'docs/test-reports/2026-10-06/Q02a-CR-recheck-artifacts')) + os.pathsep + '/tmp/sanmou-cr-20261005-6155-deps'
command = [sys.executable, '-B', *arguments]
log = output / (label + '.log')
started = time.monotonic()
with log.open('x', encoding='utf-8', newline='\n') as stream:
    try:
        result = subprocess.run(command, cwd=source_root / 'packages' / package, env=env,
                                stdout=stream, stderr=subprocess.STDOUT, timeout=300)
        code = result.returncode
    except subprocess.TimeoutExpired:
        code = 124
        stream.write('\nCoordinator timeout after 300 seconds.\n')
record = dict(source=source, tree=tree, packages_tree=packages_tree, command=command,
              cwd=str(source_root / 'packages' / package), pythonpath=env['PYTHONPATH'],
              exit_code=code, seconds=time.monotonic()-started, python=sys.version,
              dependencies={name: importlib.metadata.version(name) for name in ('pydantic', 'PyYAML', 'mcp', 'anyio')},
              log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
              runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
with (output / (label+'.json')).open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(json.dumps(record))
print('\n'.join(log.read_text(encoding='utf-8').splitlines()[-7:]))
raise SystemExit(code)
