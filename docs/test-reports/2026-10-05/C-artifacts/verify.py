"""Reproduce the offline C test commands without shell exit-code interpolation."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from importlib.metadata import version

repo = Path(__file__).resolve().parents[4]
package = repo / 'packages/qa-agent'
output = Path(__file__).resolve().parent
# Native Windows Git resolves the app-managed UNC gitdir; WSL Git cannot.
code = (output / 'code-sha.txt').read_text(encoding='utf-8-sig').strip()
if len(code) != 40 or any(c not in '0123456789abcdef' for c in code):
    raise ValueError('invalid native Git source identity')
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH='src:../sanmou-common/src')
commands = {
    'qa-full-bound': [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-v'],
    'focused-bound': [sys.executable, '-B', '-m', 'unittest', 'tests.test_quality_eval', 'tests.test_review_d_regressions.ChatGroundingRegressionTests', '-v'],
}
results = {}
for name, command in commands.items():
    with (output / (name + '.log')).open('x', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=package, env=env, stdout=log, stderr=subprocess.STDOUT)
    results[name] = {'command': command, 'cwd': str(package), 'returncode': result.returncode}
manifest = {'code_commit':code, 'python':sys.version, 'platform':platform.platform(),
            'dependencies':{name:version(name) for name in ('pydantic','PyYAML','mcp')},
            'results':results}
with (output / 'verification.json').open('x', encoding='utf-8') as f:
    json.dump(manifest,f,indent=2)
print(json.dumps(manifest,indent=2))
sys.exit(int(any(r['returncode'] for r in results.values())))
