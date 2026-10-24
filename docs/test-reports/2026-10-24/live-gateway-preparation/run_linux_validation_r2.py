import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone

task = Path('/tmp/sanmou-live-gateway-linux.UhQEsM')
root = task/'repo-r2'
out = task/'evidence-r2'
out.mkdir(mode=0o700)
temporary = task/'test-tmp-r2'
temporary.mkdir(mode=0o700)
snapshot_raw = (task/'source-snapshot-r2.json').read_bytes()
snapshot = json.loads(snapshot_raw)
for name, record in snapshot['source_files'].items():
    path = root/name
    raw = path.read_bytes()
    assert len(raw) == record['bytes'] and hashlib.sha256(raw).hexdigest() == record['sha256'], name
environment = {**os.environ, 'TMPDIR':str(temporary), 'PYTHONDONTWRITEBYTECODE':'1',
               'PYTHONPATH':os.pathsep.join([str(root/'packages/pioneer-agent/src'),
                                           str(root/'packages/sanmou-common/src')])}
command = [sys.executable,'-m','unittest','-v',*snapshot['modules']]
started = datetime.now(timezone.utc).isoformat()
log = out/'linux-234.log'
with log.open('x') as stream:
    result = subprocess.run(command,cwd=root/'packages/pioneer-agent/tests',env=environment,
                            stdout=stream,stderr=subprocess.STDOUT)
content = log.read_text()
lines = [line for line in content.splitlines() if re.match(r'^(Ran \d+ tests|OK\b|FAILED\b)',line)]
changed = [name for name,record in snapshot['source_files'].items()
           if hashlib.sha256((root/name).read_bytes()).hexdigest()!=record['sha256']]
metadata = {'schema':'sanmou-linux-test-result-v1','source_snapshot_sha256':hashlib.sha256(snapshot_raw).hexdigest(),
            'source_archive_sha256':snapshot['archive_sha256'],'source_base_head':snapshot['base_head'],
            'source_files':len(snapshot['source_files']),'source_changes_after_tests':changed,
            'platform':platform.platform(),'machine':platform.machine(),'python':sys.version,
            'execution_kind':'local_cpu_linux','colab_calls':0,'gpu_calls':0,
            'command':command,'cwd':str(root/'packages/pioneer-agent/tests'),
            'PYTHONPATH':environment['PYTHONPATH'],'TMPDIR':str(temporary),
            'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat(),
            'exit_code':result.returncode,'summary':lines,
            'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
(out/'result.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(metadata,ensure_ascii=False,indent=2),flush=True)
sys.exit(int(bool(result.returncode or changed)))
