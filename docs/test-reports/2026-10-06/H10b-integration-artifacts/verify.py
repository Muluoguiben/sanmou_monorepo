"""CI-only H10b combination; reviewed helper adapted only for new report paths."""
import ast,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path('/tmp/sanmou-h07a-integration-20261006')
OUT=Path('/tmp/h10b-integration-ed158e3-20261006')
CODE='ed158e35a34c80aa99be2597bdddc300a6cff62f'
TREE='3f1223fbd43b54948c169cf55f562e0522c2bfe3'
BASE='a45949233dfc666b91fdbf756b8666d96d93fde3'
HELPER='docs/test-reports/2026-10-06/h10b-selftest/verify.py'
WF='.github/workflows/regression.yml'
TEST='packages/pioneer-agent/tests/test_causal_trace.py'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.autocrlf=false','-C',str(ROOT),*args])
def save(name,obj):
    with (OUT/name).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
raw=(ROOT/HELPER).read_bytes();assert raw==git('show','3b31752ecd5c566c8e995c14834c6b736d71f776:'+HELPER)
old='changed = git("diff", "--name-only", BASE, CODE).decode().splitlines()'
new='changed = git("diff", "--name-only", BASE, CODE, "--", "packages", "scripts", ".github").decode().splitlines()'
assert raw.decode().count(old)==1;adapted=raw.decode().replace(old,new)
if sys.argv[1]=='matrix':
    sys.argv=[str(ROOT/HELPER),str(ROOT),str(OUT/'run'),CODE]
    exec(compile(adapted,str(ROOT/HELPER)+' (implementation-scope only)','exec'),{'__name__':'__main__','__file__':str(ROOT/HELPER)})
    raise SystemExit
assert sys.argv[1]=='main'
def entries(commit):
    result={}
    for row in git('ls-tree','-rz',commit).split(b'\0'):
        if row:
            meta,name=row.split(b'\t');result[name.decode()]=meta.decode()
    return result
def inputs():
    values=[]
    for name,meta in sorted(entries(CODE).items()):
        if not name.startswith('packages/') or Path(name).suffix not in ('.py','.json','.yaml','.yml'):continue
        data=(ROOT/name).read_bytes();oid=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();assert oid==meta.split()[2]
        values.append([name,oid,sha(data),len(data)])
    assert len(values)==895
    return sha(json.dumps(values,ensure_ascii=False,separators=(',',':')).encode())
assert git('rev-parse','HEAD').decode().strip()==CODE and git('rev-parse','HEAD^{tree}').decode().strip()==TREE
assert git('rev-parse','HEAD:.github').decode().strip()=='29fca0bedd0ea3cefdd1b88c033b8b9a4dd9516a'
assert git('rev-parse','HEAD:packages').decode().strip()==git('rev-parse',BASE+':packages').decode().strip()=='3d1c4a78faf912f522be764454762601aa1f7409'
assert git('show','c8b096edc5fce6c87e83198b871ab5c576add1db:'+WF)==git('show',BASE+':'+WF)
baseline,current=entries(BASE),entries(CODE)
excluded={WF,'.codex-autonomy/review-iteration-20261005/state.json','.codex-autonomy/review-iteration-20261005/WORKLOG.md','todo-list.md'}
protected={n:v for n,v in baseline.items() if n not in excluded};assert all(current.get(n)==v for n,v in protected.items())
assert not any('q06' in n.lower() or 'knowledge_snapshot_audit' in n for n in current)
assert subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor','cd6d4929ec611cda1600934dde17aef996142ae0',CODE],capture_output=True).returncode==1
test_raw=(ROOT/TEST).read_bytes();assert test_raw==git('show',BASE+':'+TEST)
inventory=sorted(cls.name+'.'+method.name for cls in ast.parse(test_raw).body if isinstance(cls,ast.ClassDef) for method in cls.body if isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)) and method.name.startswith('test_'))
assert len(inventory)==32
before=inputs()
save('source-proof.json',{'source':CODE,'tree':TREE,'baseline':BASE,'packages_unchanged':True,'helper_original_sha256':sha(raw),'helper_adapted_sha256':sha(adapted.encode()),'adaptation':{'before':old,'after':new,'reason':'new combination contains report additions; code/CI-only assertion unchanged'},'old_reports_and_other_baseline_metadata_preserved':len(protected),'ordinary_git_inputs':895,'input_before_digest':before,'test_file_sha256':sha(test_raw),'causal_32_inventory':inventory,'q06_ancestor':False,'archive_reads':0})
with (OUT/'driver.log').open('xb') as f:p=subprocess.run([sys.executable,'-B',str(Path(__file__)),'matrix'],stdout=f,stderr=subprocess.STDOUT,timeout=1200)
assert p.returncode==0,'real matrix failure retained in raw log'
summary=json.loads((OUT/'run/summary.json').read_bytes());assert summary['failures']==[] and len(summary['commands'])==7
expected={'causal-module':(32,0),'h07a-module':(35,0),'pioneer-agent-full':(1085,2),'qa-agent-full':(394,0),'sanmou-common-full':(2,0)}
for command in summary['commands']:
    assert command['exit']==0
    if command['name'] in expected:assert (command['tests'],command['skipped'])==expected[command['name']]
text=(OUT/'run/causal-module.log').read_text();import re
actual=sorted(re.findall(r'^test_\w+ \(test_causal_trace\.([^()]+)\)',text,re.M))
assert actual==inventory and summary['results']['causal_runtime_warning_lines']==[]
h09_path=OUT/'run/h09-cli/report.json';h09=json.loads(h09_path.read_bytes())
assert h09['source']['commit']==CODE and h09['source']['tree']==TREE
assert all(h09[k] is True for k in ('complete','valid_suite','source_verified','gate_pass'))
assert h09['totals']==dict(control_pass=8,goal_success=2,expected_safety_stop=6,infra_error=0,unexpected_goal_success=0,safety_violations=0)
for name,digest in h09['artifacts'].items():assert sha((OUT/'run/h09-cli'/name).read_bytes())==digest
assert sha((OUT/'run/qa-v3.json').read_bytes())=='480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8'
after=inputs();assert before==after
save('completion.json',{'source':CODE,'tree':TREE,'matrix_exit':0,'input_before_after_digest':after,'actual_causal_names_match_ast':True,'runtime_coroutine_warnings':[],'h09_artifact_hashes_verified':len(h09['artifacts']),'h09_report_sha256':sha(h09_path.read_bytes()),'h09_report_bytes':h09_path.stat().st_size,'native_status':'pending_final_hosted32_0skip_warningfree_alljobs','local_native_executed':False,'archive_reads':0})
print(json.dumps({'source':CODE,'matrix_exit':0,'actual_causal_tests':32,'warnings':0,'packages_unchanged':True}),flush=True)
