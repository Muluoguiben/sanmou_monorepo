"""Q04a exact combination using frozen probes and complete NUL Git inventory."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path('/tmp/sanmou-h07a-integration-20261006')
BASE_ROOT=Path('/tmp/q04a-cr-baseline-5791-20261006')
OUT=Path('/tmp/q04a-integration-7562b42-20261006')
CODE='7562b425aa0dd88882f14205399f2f7a8694b46d'
TREE='f95667e7fac80866fc17a4d7ff41e1ae425ddf81'
BASE='5791ca397507007b9397c78763b3523b8ec16421'
REVIEW='962408d5ad23cb7c3084fd771335d088eb428229'
HELPER='docs/test-reports/2026-10-06/q04a-independent-verify.py'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.autocrlf=false','-C',str(ROOT),*args])
def save(name,obj):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
raw=(ROOT/HELPER).read_bytes();assert raw==git('show',REVIEW+':'+HELPER)
mapping={'CODE = "676ac1ed012458ccc00a01df159476747921c181"':'CODE = "'+CODE+'"','TREE = "16b74ba49c8bf44288c7e23d9935e56631fea471"':'TREE = "'+TREE+'"','for path in git(root, "ls-tree", "-r", "--name-only", CODE, "--", "packages").decode().splitlines():':'for row in git(root, "ls-tree", "-rz", CODE, "--", "packages").split(b"\\0"):\n    if not row: continue\n    path = row.split(b"\\t", 1)[1].decode("utf-8")'}
adapted=raw.decode()
for old,new in mapping.items():assert adapted.count(old)==1;adapted=adapted.replace(old,new)
if sys.argv[1]=='matrix':
    sys.argv=[str(ROOT/HELPER),str(ROOT),str(BASE_ROOT),str(OUT/'matrix')]
    exec(compile(adapted,str(ROOT/HELPER)+' (source identities + NUL inventory)','exec'),{'__name__':'__main__','__file__':str(ROOT/HELPER)})
    raise SystemExit(0)
assert sys.argv[1]=='main'
def entries(commit):
    out={}
    for row in git('ls-tree','-rz',commit).split(b'\0'):
        if row:
            meta,name=row.split(b'\t');out[name.decode()]=meta.decode()
    return out
def inventory():
    rows=[]
    for name,meta in sorted(entries(CODE).items()):
        if not name.startswith('packages/') or Path(name).suffix not in ('.py','.json','.yaml','.yml'):continue
        value=(ROOT/name).read_bytes();oid=hashlib.sha1(b'blob '+str(len(value)).encode()+b'\0'+value).hexdigest();assert oid==meta.split()[2],name
        rows.append([name,oid,sha(value),len(value)])
    assert len(rows)==899
    return sha(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode())
assert git('rev-parse','HEAD').decode().strip()==CODE and git('rev-parse','HEAD^{tree}').decode().strip()==TREE
assert git('rev-parse','HEAD:packages').decode().strip()=='e849545fc31473d68835618c2c13ec44c35788c0'
assert git('rev-parse','HEAD:.github').decode().strip()=='29fca0bedd0ea3cefdd1b88c033b8b9a4dd9516a'
baseline,current=entries(BASE),entries(CODE)
coord={'.codex-autonomy/review-iteration-20261005/state.json','.codex-autonomy/review-iteration-20261005/WORKLOG.md','todo-list.md'}
protected={n:v for n,v in baseline.items() if n not in coord};assert all(current.get(n)==v for n,v in protected.items())
assert not any('q06' in n.lower() or 'knowledge_snapshot_audit' in n for n in current)
assert subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor','cd6d4929ec611cda1600934dde17aef996142ae0',CODE],capture_output=True).returncode==1
frozen={}
for name,commit in [('q04a-independent-probes.py','39bdb13ae1676e75b974abebdcf4b2cad0d21c25'),('q04a-independent-integration.py','41cca94156fd55b3e0ba38c00853c7a800a583f8')]:
    relative='docs/test-reports/2026-10-06/'+name;value=(ROOT/relative).read_bytes();assert value==git('show',commit+':'+relative)
    frozen[name]={'commit':commit,'sha256':sha(value)}
reference=Path('/tmp/q04a-cr-676ac1e-rerun-results/old-v3.json');assert sha(reference.read_bytes())=='480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8'
before=inventory()
save('source-proof.json',{'source':CODE,'tree':TREE,'baseline':BASE,'baseline_root':str(BASE_ROOT),'baseline_v3_reference':str(reference),'input_count':899,'input_before_sha256':before,'protected_metadata_count':len(protected),'protected_metadata_sha256':sha(json.dumps(protected,sort_keys=True).encode()),'old_report_metadata_count':sum(n.startswith('docs/test-reports/') for n in baseline),'original_helper_sha256':sha(raw),'adapted_helper_sha256':sha(adapted.encode()),'mapping':mapping,'assertions_unchanged':True,'frozen_probes':frozen,'original_bad_root_probe_retained_not_product_gate':'12c7e4d315bf1a252b51d1fbcc5d4343b4eea725','archive_reads':0})
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');env.pop('SANMOU_CAPTURE_TOKEN',None)
with (OUT/'driver.log').open('xb') as f:p=subprocess.run([sys.executable,'-B',str(Path(__file__)),'matrix'],env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1200)
assert p.returncode==0,'matrix failed; raw logs retained'
summary=json.loads((OUT/'matrix/summary.json').read_bytes());assert summary['package_files_git_bytes_checked']==899
expected={'public-probes':5,'integration-probes':4,'claim-module':25,'legacy-module':23,'causal-module':32,'h07-module':35,'qa-agent':419,'pioneer-agent':1085,'sanmou-common':2}
for command in summary['commands']:
    assert command['exit']==command['expected_exit']
    if command['name'] in expected:assert command['tests']==expected[command['name']] and command['skipped']==(2 if command['name']=='pioneer-agent' else 0)
assert (OUT/'matrix/old-v3.json').read_bytes()==reference.read_bytes()
new=json.loads((OUT/'matrix/claim-spans.json').read_bytes());assert new['gate_pass'] is True and new['controls']['numerator']==new['controls']['denominator']==12
assert new['provider']['calls']==0 and new['execution_authority']=='none' and new['executable'] is False
h09=json.loads((OUT/'matrix/h09-cli/report.json').read_bytes());assert h09['source']['commit']==CODE and h09['source']['tree']==TREE
assert all(h09[k] is True for k in ('complete','valid_suite','source_verified','gate_pass'))
assert h09['totals']==dict(control_pass=8,goal_success=2,expected_safety_stop=6,infra_error=0,safety_violations=0,unexpected_goal_success=0)
for path,digest in h09['artifacts'].items():assert sha((OUT/'matrix/h09-cli'/path).read_bytes())==digest
after=inventory();assert before==after and not git('diff','--name-only','HEAD','--','packages','.github','scripts')
save('completion.json',{'source':CODE,'tree':TREE,'matrix_exit':0,'input_before_after_sha256':after,'git_inputs':899,'new_cli_controls':12,'new_cli_sha256':sha((OUT/'matrix/claim-spans.json').read_bytes()),'legacy':summary['legacy'],'h09_sha256':sha((OUT/'matrix/h09-cli/report.json').read_bytes()),'h09_bytes':(OUT/'matrix/h09-cli/report.json').stat().st_size,'h09_artifacts_verified':len(h09['artifacts']),'native_q04':'no coordinator native execution; prior root missing-yaml import exit1,zero newtests; not pass/not product failure','archive_reads':0})
print(json.dumps({'source':CODE,'matrix_exit':0,'ordinary_inputs':899,'new_controls':12,'legacy_delta':'exact new eval_source entry and digest only'}),flush=True)
