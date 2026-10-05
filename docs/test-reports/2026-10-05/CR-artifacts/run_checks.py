import json, os, pathlib, subprocess, sys, time
root = pathlib.Path(__file__).resolve().parents[4]
label, package, source, tree, *args = sys.argv[1:]
output = pathlib.Path(__file__).parent
log = output / (label + '.log')
env = os.environ.copy()
env['PYTHONDONTWRITEBYTECODE'] = '1'
env['PYTHONPATH'] = os.pathsep.join(str(root / p) for p in [
    'packages/pioneer-agent/src', 'packages/qa-agent/src', 'packages/sanmou-common/src',
    'packages/pioneer-agent/tests', 'packages/pioneer-agent/tests/unit', 'packages/qa-agent/tests'])
command = [sys.executable, '-B', *args]
started = time.time()
with log.open('x', encoding='utf-8') as stream:
    result = subprocess.run(command, cwd=root / 'packages' / package, env=env,
                            stdout=stream, stderr=subprocess.STDOUT)
record = dict(source=source, tree=tree, command=command, cwd=str(root / 'packages' / package),
              exit_code=result.returncode, seconds=time.time()-started, python=sys.version)
(output / (label+'.json')).write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record))
print('\n'.join(log.read_text().splitlines()[-10:]))
sys.exit(result.returncode)
