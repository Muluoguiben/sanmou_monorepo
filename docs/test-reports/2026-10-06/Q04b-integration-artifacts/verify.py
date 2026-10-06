"""Bounded Q04b exact combination; adapt the frozen CI-only H10b matrix."""
import ast, hashlib, json, re, subprocess, sys
from pathlib import Path
ROOT=Path('/tmp/sanmou-h07a-integration-20261006')
OUT=Path('/tmp/q04b-integration-658be76-20261006')
CODE='658be762abf192799e4b4711b8b85d05f0c79ea9'
TREE='09f146c54cd15d7290ba2136a6e80b42058ad918'
BASE='b37e7ed34e5c9df63d668349436b198bd8b0b27d'
HELPER='docs/test-reports/2026-10-06/h10b-selftest/verify.py'
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.check_output(['git','-c','core.autocrlf=false','-C',str(ROOT),*a])
def save(n,v):
    with (OUT/n).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2)
raw=(ROOT/HELPER).read_bytes();assert raw==git('show',BASE+':'+HELPER)
text=raw.decode()
replacements=[
('c8b096edc5fce6c87e83198b871ab5c576add1db',BASE),
('a45949233dfc666b91fdbf756b8666d96d93fde3',BASE),
('3d1c4a78faf912f522be764454762601aa1f7409','e849545fc31473d68835618c2c13ec44c35788c0'),
('changed = git("diff", "--name-only", BASE, CODE).decode().splitlines()', 'changed = git("diff", "--name-only", BASE, CODE, "--", "packages", "scripts", ".github").decode().splitlines()'),
('Windows H10b causal trace v2','Windows Q04b claim span evaluation'),
('working-directory: packages/pioneer-agent/tests','working-directory: packages/qa-agent'),
('python -W error::RuntimeWarning -m unittest test_causal_trace -v',"python -B -m unittest discover -s tests -p 'test_claim_spans.py' -v"),
('"working-directory": "packages/pioneer-agent/tests"','"working-directory": "packages/qa-agent"'),
('assert steps[index - 1]["name"] == "Windows H07a synthetic approval lifecycle"','assert steps[index - 1]["name"] == "Windows H09b offline task evaluation"'),
('assert steps[index + 1]["name"] == "Windows H09b offline task evaluation"','assert steps[index + 1]["name"] == "Desktop dependencies"'),
('"packages/sanmou-common/src", "packages/pioneer-agent/tests"','"packages/sanmou-common/src", "packages/pioneer-agent/tests", "packages/pioneer-agent/tests/unit"'),
('PY = [sys.executable]','PY = [sys.executable, "-B"]\nrun("claim-module", PY + ["-m", "unittest", "discover", "-s", "tests", "-p", "test_claim_spans.py", "-v"], ROOT / "packages/qa-agent")'),
('480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8','db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec'),
('pending exact-final-SHA Hosted Windows causal32/0skip and warning-free logs; no local native execution/install/mock','pending exact-final-SHA Hosted Windows claim25/0skip/exact names and all four jobs; no local native execution/install/mock')]
for old,new in replacements:
    assert old in text,old
    text=text.replace(old,new)
if sys.argv[1]=='matrix':
    sys.argv=[str(ROOT/HELPER),str(ROOT),str(OUT/'run'),CODE]
    exec(compile(text, str(ROOT/HELPER)+' (Q04b bounded adaptation)','exec'),{'__name__':'__main__','__file__':str(ROOT/HELPER)})
    raise SystemExit
assert sys.argv[1]=='main'
def entries(commit):
    return {row.split(b'\t')[1].decode():row.split(b'\t')[0].decode() for row in git('ls-tree','-rz',commit).split(b'\0') if row}
current=entries(CODE);baseline=entries(BASE)
excluded={'.github/workflows/regression.yml','.codex-autonomy/review-iteration-20261005/state.json','.codex-autonomy/review-iteration-20261005/WORKLOG.md','todo-list.md'}
protected={n:m for n,m in baseline.items() if n not in excluded}
assert all(current.get(n)==m for n,m in protected.items())
assert git('rev-parse','HEAD').decode().strip()==CODE and git('rev-parse','HEAD^{tree}').decode().strip()==TREE
assert git('rev-parse','HEAD:.github').decode().strip()=='60cbfa8ec001678a08d3c38a14a875c37c938393'
assert not git('status','--porcelain')
def inputs():
    result=[]
    for n,m in sorted(current.items()):
        if not n.startswith('packages/') or Path(n).suffix not in ('.py','.json','.yaml','.yml'):continue
        assert m.startswith('100644 blob ') or m.startswith('100755 blob ')
        b=(ROOT/n).read_bytes();oid=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();assert oid==m.split()[2]
        result.append([n,oid,sha(b),len(b)])
    assert len(result)==899
    return sha(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())
tp='packages/qa-agent/tests/test_claim_spans.py';tr=(ROOT/tp).read_bytes();assert tr==git('show',BASE+':'+tp)
names=sorted('test_claim_spans.'+c.name+'.'+m.name for c in ast.parse(tr).body if isinstance(c,ast.ClassDef) for m in c.body if isinstance(m,ast.FunctionDef) and m.name.startswith('test_'))
assert len(names)==25
before=inputs()
save('source-proof.json',{'source':CODE,'tree':TREE,'baseline':BASE,'ordinary_inputs':899,'before_digest':before,'protected_metadata_paths':len(protected),'old_report_paths':sum(n.startswith('docs/test-reports/') for n in protected),'archive_content_reads':0,'helper_git_bytes_verified':True,'original_helper_sha256':sha(raw),'adapted_helper_sha256':sha(text.encode()),'replacements':replacements,'test_sha256':sha(tr),'test_ast_sha256':sha(ast.dump(ast.parse(tr)).encode()),'qualified_names':names})
with (OUT/'driver.log').open('xb') as f:p=subprocess.run([sys.executable,'-B',str(Path(__file__)),'matrix'],stdout=f,stderr=subprocess.STDOUT,timeout=1800)
assert p.returncode==0,'matrix failed: original raw retained'
s=json.loads((OUT/'run/summary.json').read_bytes());assert s['failures']==[] and len(s['commands'])==8
expected={'claim-module':(25,0),'causal-module':(32,0),'h07a-module':(35,0),'pioneer-agent-full':(1085,2),'qa-agent-full':(419,0),'sanmou-common-full':(2,0)}
for row in s['commands']:
    assert row['exit']==0
    if row['name'] in expected:assert (row['tests'],row['skipped'])==expected[row['name']]
actual=sorted(re.findall(r'^test_\w+ \((test_claim_spans\.\w+\.test_\w+)\) \.\.\. ok$',(OUT/'run/claim-module.log').read_text(),re.M));assert actual==names
h=json.loads((OUT/'run/h09-cli/report.json').read_bytes());assert all(h[k] is True for k in ('complete','valid_suite','source_verified','gate_pass'))
assert h['totals']==dict(control_pass=8,goal_success=2,expected_safety_stop=6,infra_error=0,unexpected_goal_success=0,safety_violations=0)
for n,d in h['artifacts'].items():assert sha((OUT/'run/h09-cli'/n).read_bytes())==d
after=inputs();assert before==after and not git('status','--porcelain')
save('completion.json',{'source':CODE,'tree':TREE,'matrix_exit':0,'ordinary_inputs':899,'before_after_digest':after,'all_25_names_match':True,'h09_artifact_hashes':len(h['artifacts']),'native':'not_executed; final Hosted gate pending','archive_reads':0})
print(json.dumps({'all_green':True,'source':CODE,'lanes':8,'ordinary_inputs':899}),flush=True)
