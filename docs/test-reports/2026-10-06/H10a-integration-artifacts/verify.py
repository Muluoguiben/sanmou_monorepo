"""Read-reviewed independent matrix, identity-only rebound; fresh dual-sink sample."""
import asyncio,collections,hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('/tmp/sanmou-h07a-integration-20261006')
OUT=Path('/tmp/h10a-integration-4e3fb5c-20261006')
CODE='4e3fb5c82b7e6f1b36698918731ed52c8fd46117'
TREE='e6cc4cfa4053168d029182937da637b3e8c676e8'
BASE='ae03faf0862f9930c58f7811d625de4b632f05ba'
REVIEW='2313e78ac72888470f66a6ee3ccf121010a85492'
PROBES=ROOT/'docs/test-reports/2026-10-06'
HELPER='docs/test-reports/2026-10-06/h10a-independent-verify-r4.py'
DEPS='/tmp/sanmou-cr-20261005-6155-deps'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def git(*args):return subprocess.check_output(['git','-c','core.autocrlf=false','-C',str(ROOT),*args])
def save(name,obj):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
raw=(ROOT/HELPER).read_bytes()
assert raw==git('show','1a76c4f:'+HELPER)
mapping={'CODE = "2128fb88329b1a38b410ad63e09c37034d08e8c7"':'CODE = "'+CODE+'"','TREE = "3fe1e07f9d2e30b856d95177298fb80692bf396c"':'TREE = "'+TREE+'"'}
rebound=raw.decode()
for old,new in mapping.items():assert rebound.count(old)==1;rebound=rebound.replace(old,new)
if sys.argv[1]=='matrix':
    sys.argv=[str(ROOT/HELPER),str(ROOT),str(OUT/'matrix'),str(PROBES)]
    exec(compile(rebound,str(ROOT/HELPER)+' (identity-only)','exec'),{'__name__':'__main__','__file__':str(ROOT/HELPER)})
    raise SystemExit
assert sys.argv[1]=='main'
def entries(commit):
    result={}
    for row in git('ls-tree','-rz',commit).split(b'\0'):
        if row:
            meta,name=row.split(b'\t');result[name.decode()]=meta.decode()
    return result
def input_digest():
    rows=[]
    for name,meta in sorted(entries(CODE).items()):
        if not name.startswith('packages/') or Path(name).suffix not in ('.py','.json','.yaml','.yml'):continue
        value=(ROOT/name).read_bytes();oid=hashlib.sha1(b'blob '+str(len(value)).encode()+b'\0'+value).hexdigest()
        assert oid==meta.split()[2],name
        rows.append([name,oid,sha(value),len(value)])
    assert len(rows)==895
    return sha(canonical(rows))
assert git('rev-parse','HEAD').decode().strip()==CODE and git('rev-parse','HEAD^{tree}').decode().strip()==TREE
assert git('rev-parse','HEAD:packages').decode().strip()=='3d1c4a78faf912f522be764454762601aa1f7409'
assert git('rev-parse','HEAD:.github').decode().strip()=='7235130b9af9859cec2193f3268b47eb8a4d72ca'
current,baseline=entries(CODE),entries(BASE)
allowed={'packages/pioneer-agent/src/pioneer_agent/agent_harness/'+n+'.py' for n in ('run_trace','task_contracts','task_policy','task_runner','task_trace')}
allowed|={'packages/pioneer-agent/tests/test_causal_trace.py','.codex-autonomy/review-iteration-20261005/state.json','.codex-autonomy/review-iteration-20261005/WORKLOG.md','todo-list.md'}
protected={name:meta for name,meta in baseline.items() if name not in allowed}
assert all(current.get(n)==v for n,v in protected.items())
assert not any('q06' in n.lower() or 'knowledge_snapshot_audit' in n for n in current)
assert subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor','cd6d4929ec611cda1600934dde17aef996142ae0',CODE],capture_output=True).returncode==1
names=['h10a-independent-probes.py','h10a-independent-targeted.py','h10a-independent-trace-context.py','h10a-independent-trace-context-short.py','h10a-independent-ambient-primary.py','h10a-independent-dispatch-deadline.py','h10a-independent-policy-binding.py','h10a-independent-policy-binding-budget-cut.py','h10a-default-v1-oracle.json']
frozen={}
for name in names:
    relative='docs/test-reports/2026-10-06/'+name;value=(PROBES/name).read_bytes()
    assert value==git('show',REVIEW+':'+relative)
    freeze=git('log','-1','--format=%H',REVIEW,'--',relative).decode().strip()
    frozen[name]={'commit':freeze,'sha256':sha(value)}
assert frozen['h10a-default-v1-oracle.json']['sha256']=='327ec7ae64a409b234505d8920056db2fa1f951405560cda43b0e3a491825ed6'
before=input_digest()
save('source-checks.json',{'source':CODE,'tree':TREE,'baseline':BASE,'packages':'3d1c4a78faf912f522be764454762601aa1f7409','github':'7235130b9af9859cec2193f3268b47eb8a4d72ca','input_count':895,'input_digest_before':before,'protected_metadata_count':len(protected),'protected_metadata_sha256':sha(canonical(protected)),'old_report_metadata_count':sum(n.startswith('docs/test-reports/') for n in baseline),'frozen':frozen,'matrix_original_sha256':sha(raw),'matrix_rebound_sha256':sha(rebound.encode()),'mapping':mapping,'assertions_changed':False,'archive_content_reads':0,'q06_ancestry':False})
with (OUT/'matrix-driver.log').open('xb') as f:p=subprocess.run([sys.executable,'-B',str(Path(__file__)),'matrix'],stdout=f,stderr=subprocess.STDOUT,timeout=1200)
assert p.returncode==0,'matrix failed; preserve raw logs'
paths=[str(ROOT/p) for p in ('packages/pioneer-agent/src','packages/pioneer-agent/tests','packages/sanmou-common/src','packages/qa-agent/src')]+[DEPS]
sys.path[:0]=paths
from test_causal_trace import runner,Fanout,FakeDecisionPolicy,PolicyDecision,InMemoryRunTrace,JsonlRunTrace
memory=InMemoryRunTrace();sample=OUT/'sample-v2.jsonl'
policy=FakeDecisionPolicy([PolicyDecision(action='continue',reason='observe') for _ in range(3)])
r=runner(trace=Fanout(memory,JsonlRunTrace(sample)),policy=policy)
task_digest=sha(canonical(r.state.task.model_dump(mode='json')))
result=asyncio.run(r.run());assert result.status=='succeeded'
rows=[event.model_dump(mode='json') for event in memory.events]
disk=[json.loads(line) for line in sample.read_bytes().splitlines()]
assert rows==disk and len(rows)==27
known={}
for row in rows:
    assert row['event_id'] not in known and row['trace_version']==2
    if row['event']=='lifetime_start':assert row['parent_event_id'] is None and row['lifetime_id']==row['event_id']
    else:
        parent=known[row['parent_event_id']];assert parent['lifetime_id']==row['lifetime_id'] and parent['run_id']==row['run_id']
    if row['window_id'] is not None:
        if row['event']=='window_start':assert row['window_id']==row['event_id'] and row['parent_event_id']==row['lifetime_id']
        else:
            assert known[row['window_id']]['event']=='window_start'
            if row['parent_event_id']!=row['lifetime_id']:assert known[row['parent_event_id']]['window_id']==row['window_id']
    assert row['provenance']['task_digest']==task_digest
    known[row['event_id']]=row
tools=[row for row in rows if row['event']=='tool'];policies=[row for row in rows if row['event']=='policy'];observations=[row for row in rows if row['event']=='observation']
assert [row['name'] for row in tools]==r._client.calls and len(tools)==12 and len(policies)==3
assert [row['observation_id'] for row in policies]==[ctx.observation_id for ctx in policy.contexts]
assert [row['observation_id'] for row in observations]==['obs-1','obs-2','obs-3']
digests=[sha(canonical(ctx.model_dump(mode='json'))) for ctx in policy.contexts]
assert [row['provenance']['context_digest'] for row in policies]==digests
ids=[row['invocation_id'] for row in tools+policies];assert all(ids) and len(set(ids))==15
assert all(row['attempt_id'] is None and row['usage'] is None for row in policies)
counts=r.budget.summary()['counts'];assert counts=={'step':3,'tool':12,'model':0}
save('sample-summary.json',{'source':CODE,'tree':TREE,'events':len(rows),'event_counts':dict(collections.Counter(row['event'] for row in rows)),'raw_jsonl_sha256':sha(sample.read_bytes()),'raw_bytes':sample.stat().st_size,'memory_rows_persisted':False,'memory_jsonl_equal_asserted_in_actual_run':True,'canonical_memory_rows_sha256':sha(canonical(rows)),'canonical_jsonl_rows_sha256':sha(canonical(disk)),'actual_tool_calls':r._client.calls,'actual_policy_observation_ids':[ctx.observation_id for ctx in policy.contexts],'actual_context_digests':digests,'task_digest':task_digest,'ledger_counts':counts,'unique_actual_invocation_ids':15,'graph_checked_independently':True,'state':result.status,'execution_authority':result.execution_authority,'executable':result.executable,'native_h10':'not_executed'})
h09_path=OUT/'matrix/h09-cli/report.json';h09=json.loads(h09_path.read_bytes())
assert h09['source']['commit']==CODE and h09['source']['tree']==TREE and all(h09[k] is True for k in ('complete','valid_suite','source_verified','gate_pass'))
assert h09['totals']==dict(control_pass=8,goal_success=2,expected_safety_stop=6,infra_error=0,safety_violations=0,unexpected_goal_success=0)
for path,digest in h09['artifacts'].items():assert sha((OUT/'matrix/h09-cli'/path).read_bytes())==digest
assert sha((OUT/'matrix/qa-v3.json').read_bytes())=='480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8'
after=input_digest();assert before==after and not git('diff','--name-only','HEAD','--','packages','.github','scripts')
save('completion.json',{'source':CODE,'tree':TREE,'matrix_exit':p.returncode,'input_before_after_digest':after,'ordinary_git_inputs':895,'h09':{'source':CODE,'tree':TREE,'totals':h09['totals'],'sha256':sha(h09_path.read_bytes()),'bytes':h09_path.stat().st_size,'artifacts_verified':len(h09['artifacts']),'external_root':str(OUT/'matrix/h09-cli')},'qa_v3_sha256':sha((OUT/'matrix/qa-v3.json').read_bytes()),'sample_graph_and_dual_sink_passed':True,'archive_reads':0,'new_native_h10':'not_executed'})
print(json.dumps({'matrix_exit':0,'sample_events':27,'tools':12,'policies':3,'model':0,'source':CODE}),flush=True)
