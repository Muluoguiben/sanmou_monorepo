"""Read-only local Git/blob verification, separate from evaluator execution."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[4]
WIN_ROOT='C:/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo'
GIT='/mnt/c/Program Files/Git/cmd/git.exe'
freeze=json.loads((ROOT/'packages/qa-agent/tests/fixtures/quality_eval/v3/freeze.json').read_text())
sha=freeze['baseline_commit']
command=[GIT,'-C',WIN_ROOT]
actual_sha=subprocess.check_output([*command,'rev-parse',sha+'^{commit}']).decode().strip()
if actual_sha!=sha: raise ValueError('source commit did not resolve exactly')
files={**freeze['kb']['files'],**freeze['production']['files']}
refs=[sha+':packages/qa-agent/'+name for name in files]
data=subprocess.check_output([*command,'cat-file','--batch'],input=('\n'.join(refs)+'\n').encode())
offset=0
for name,expected in files.items():
    end=data.index(b'\n',offset)
    header=data[offset:end].decode().split()
    if len(header)!=3 or header[1]!='blob': raise ValueError('not a blob: '+name)
    size=int(header[2]); start=end+1
    text=data[start:start+size].decode('utf-8-sig').replace('\r\n','\n')
    if hashlib.sha256(text.encode()).hexdigest()!=expected: raise ValueError('blob mismatch: '+name)
    offset=start+size+1
paths=subprocess.check_output([*command,'ls-tree','-rz','--name-only',sha,'--',
    'packages/qa-agent/src/qa_agent','packages/qa-agent/knowledge_sources']).decode().split('\0')
selected={p.removeprefix('packages/qa-agent/') for p in paths if
    (p.endswith('.py') and '/quality_eval/' not in p) or p.endswith('.yaml')}
if selected!=set(files): raise ValueError('manifest file set mismatch')
print(json.dumps({'source_commit':sha,'verified_blobs':len(files),'mismatches':0,
    'method':'existing local Git commit and exact KB/production blob set; no signature claim'},indent=2))
