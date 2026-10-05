"""Source-bound coordinator evidence; no provider/game/configuration input."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

LINUX_ROOT = '/tmp/sanmou-h06a-integration-645a413'
SOURCE = '645a413b704a954fe7de573e412b4ed5dda1545e'
PACKAGES = 'f1a11b5e69de7ac040c74a4a4bce98515e4dfee2'
native = os.name == 'nt'
root = Path('//wsl$/Ubuntu' + LINUX_ROOT) if native else Path(LINUX_ROOT)
output = Path(__file__).resolve().parent
label, package, layout, *arguments = sys.argv[1:]
if not re.fullmatch(r'[a-z0-9-]+', label) or package not in {'qa-agent','pioneer-agent','sanmou-common'} or layout not in {'package','tests','native'}:
    raise SystemExit('invalid check identity')
if (layout == 'native') != native:
    raise SystemExit('native checks require a real Windows interpreter')

def git(*args):
    command = (['wsl.exe','-d','Ubuntu','--cd',LINUX_ROOT,'--exec','git'] if native else ['git']) + list(args)
    return subprocess.check_output(command, cwd=None if native else root, text=True).strip()

source, tree, packages_tree = git('rev-parse','HEAD'), git('rev-parse','HEAD^{tree}'), git('rev-parse','HEAD:packages')
if source != SOURCE or packages_tree != PACKAGES:
    raise SystemExit('wrong frozen integration source')
if git('diff','--name-only','HEAD','--','packages','apps','scripts','.github','.agent'):
    raise SystemExit('protected source dirty')
env = {k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('TOKEN','SECRET','PASSWORD','API_KEY','AUTH','COOKIE'))}
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['PYTHONUTF8'] = '1'
if native:
    env.pop('PYTHONPATH',None)
    env['H06A_LOCK_SOURCE'] = str(root/'packages/pioneer-agent/src/pioneer_agent/agent_harness/_checkpoint_lock.py')
    cwd = Path(env.get('TEMP',env.get('TMP','.'))).resolve()
else:
    paths = ('packages/pioneer-agent/src','packages/qa-agent/src','packages/sanmou-common/src',
             'packages/pioneer-agent/tests','packages/pioneer-agent/tests/unit','packages/qa-agent/tests',
             'docs/test-reports/2026-10-06/H06a-CR-artifacts')
    env['PYTHONPATH'] = ':'.join(str(root/p) for p in paths) + ':/tmp/sanmou-cr-20261005-6155-deps'
    cwd = root/'packages'/package
    if layout == 'tests':
        cwd /= 'tests'
command = [sys.executable,'-B',*arguments]
log = output/(label+'.log')
started = time.monotonic()
with log.open('xb') as handle:
    try:
        result = subprocess.run(command,cwd=cwd,env=env,stdout=handle,stderr=subprocess.STDOUT,timeout=300)
        code = result.returncode
    except subprocess.TimeoutExpired:
        code = 124
        handle.write(b'\nCoordinator timeout after 300 seconds.\n')
versions = {}
for name in ('pydantic','PyYAML','mcp','anyio'):
    try:
        versions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        versions[name] = None
record = dict(source=source,tree=tree,packages_tree=packages_tree,command=command,cwd=str(cwd),
              pythonpath=env.get('PYTHONPATH'),python=sys.version,platform=platform.platform(),
              native_windows=native,coverage='lock-primitive-only' if native else 'offline-integration',
              exit_code=code,seconds=time.monotonic()-started,dependencies=versions,
              log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
              runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              source_clean_after=not bool(git('status','--porcelain')))
if native:
    record['helper_sha256'] = hashlib.sha256(Path(env['H06A_LOCK_SOURCE']).read_bytes()).hexdigest()
with (output/(label+'.json')).open('x',encoding='utf-8',newline='\n') as handle:
    json.dump(record,handle,indent=2)
    handle.write('\n')
print(json.dumps(record))
print('\n'.join(log.read_text(encoding='utf-8',errors='replace').splitlines()[-7:]))
raise SystemExit(code)
