"""H07-only coordinator verification; plain evidence, no archive content access."""
import hashlib,json,os,platform,subprocess,sys,time,types
from pathlib import Path
MODE=sys.argv[1]
ROOT=Path('/tmp/sanmou-h07a-integration-20261006') if MODE=='linux' else Path(r'\\wsl$\Ubuntu\tmp\sanmou-h07a-integration-20261006')
OUT=Path(sys.argv[2]);OUT.mkdir(exist_ok=False)
CODE='74654b608d54c459636bfbf1eff69b06f4aeb2fb'
TREE='459df67d1ef126a9cb8c7895d5cb0a8aa1d7e50b'
PACKAGES='46e832a6f4bbfb84e1f49bad517084841dd1b768'
BASE='110bd7594e095c3ea0e1940ab2fc4bec5f4d7a77'
REPO=ROOT if MODE=='linux' else Path(r'\\wsl$\Ubuntu\home\lan\projects\sanmou_monorepo')
DEPS='/tmp/sanmou-cr-20261005-6155-deps'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.autocrlf=false','-C',str(REPO),*args])
def entries(commit):
    result={}
    for row in git('ls-tree','-rz',commit).split(b'\0'):
        if row:
            meta,path=row.split(b'\t');result[path.decode()]=meta.decode()
    return result
def save(name,obj):
    with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
def archive(name):return name.lower().endswith(('.tar','.tar.gz','.tgz','.zip','.gz','.7z','.rar','.bz2','.xz'))
def integrity(label):
    current=entries(CODE);base=entries(BASE)
    assert git('rev-parse',CODE+'^{tree}').decode().strip()==TREE
    assert git('rev-parse',CODE+':packages').decode().strip()==PACKAGES
    protected={p:v for p,v in base.items() if p.startswith(('packages/qa-agent/','packages/sanmou-common/','.github/','scripts/','docs/test-reports/')) or archive(p)}
    assert all(current.get(p)==v for p,v in protected.items())
    assert not any('q06' in p.lower() or 'knowledge_snapshot_audit' in p for p in current)
    ancestry=subprocess.run(['git','-C',str(REPO),'merge-base','--is-ancestor','cd6d4929ec611cda1600934dde17aef996142ae0',CODE],capture_output=True)
    assert ancestry.returncode==1
    records={}
    chosen=[p for p in current if p.startswith('packages/') and Path(p).suffix in {'.py','.json','.yaml','.yml'} and not archive(p)] if MODE=='linux' else ['packages/pioneer-agent/tests/test_checkpoint_lock_native.py','packages/pioneer-agent/src/pioneer_agent/agent_harness/_checkpoint_lock.py']
    for name in chosen:
        raw=(ROOT/name).read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        assert blob==current[name].split()[2],name
        records[name]={'blob':blob,'sha256':sha(raw),'bytes':len(raw)}
    if MODE=='linux':assert git('rev-parse','HEAD').decode().strip()==CODE
    save(label+'.json',{'source':CODE,'tree':TREE,'packages':PACKAGES,'input_bytes':records,'protected_git_metadata':protected,'historical_archive_git_metadata':{p:v for p,v in current.items() if archive(p)},'archive_content_reads':0,'q06_files_present':False,'q06_candidate_ancestor':False})
    return records
before=integrity('source-before')
paths=[str(ROOT/p) for p in ['packages/pioneer-agent/src','packages/qa-agent/src','packages/sanmou-common/src','packages/pioneer-agent/tests','packages/pioneer-agent/tests/unit']]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=os.pathsep.join(paths+([DEPS] if MODE=='linux' else [])))
save('runtime.json',{'mode':MODE,'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'PYTHONPATH':env['PYTHONPATH'],'native_scope':'stdlib lock3 only; not full H07/MCP' if MODE=='native' else 'offline Rule/Fake full regression'})
def run(name,args,cwd):
    start=time.time()
    with (OUT/(name+'.log')).open('xb') as log:p=subprocess.run(args,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=900)
    save(name+'.command.json',{'argv':args,'cwd':str(cwd),'exit':p.returncode,'seconds':time.time()-start,'PYTHONPATH':env['PYTHONPATH']})
    print(json.dumps({'name':name,'exit':p.returncode}),flush=True)
    return p.returncode
if MODE=='native':
    assert os.name=='nt'
    code=run('native-lock',[sys.executable,'-B','-m','unittest','discover','-s',str(ROOT/'packages/pioneer-agent/tests'),'-p','test_checkpoint_lock_native.py','-v'],Path(os.environ['TEMP']))
    assert code==0
else:
    helper='docs/test-reports/2026-10-06/h07a-selftest/verify.py'
    raw=(ROOT/helper).read_bytes();assert raw==git('show','f04646cc72cc92f8ea928942dd287b88667fe749:'+helper)
    probes={'h07a-independent-probes.py':'339aa56156cced5fe0b8ea274695a943f5cab576','h07a-independent-probes-canonical.py':'dcba32214ddce912bd9713f3f06b7711a1734202','h07a-independent-postconsume-clock.py':'d9ade7a7b3e473c7be30b1280086e24a1405d8f1','h07a-independent-watermark-progression.py':'f7e32f0d90504cf87c8a79ead7773e5a13feaaa8'}
    for name,commit in probes.items():
        relative='docs/test-reports/2026-10-06/'+name;assert (ROOT/relative).read_bytes()==git('show',commit+':'+relative)
    save('reused-helper.json',{'path':helper,'commit':'f04646cc72cc92f8ea928942dd287b88667fe749','sha256':sha(raw),'new_actual_runs':True,'probe_commits':probes,'assertions_changed':False})
    code=run('actual-matrix',[sys.executable,'-B',str(ROOT/helper),str(ROOT),str(OUT/'matrix'),CODE,'--probe-dir',str(ROOT/'docs/test-reports/2026-10-06')],ROOT)
    assert code==0,'unexpected matrix failure; raw log retained'
    report=json.loads((OUT/'matrix/h09-cli/report.json').read_bytes())
    assert report['source']['commit']==CODE and report['source']['tree']==TREE
    assert all(report[k] is True for k in ('complete','valid_suite','source_verified','gate_pass'))
    assert report['totals']==dict(control_pass=8,expected_safety_stop=6,goal_success=2,infra_error=0,safety_violations=0,unexpected_goal_success=0)
    for relative,digest in report['artifacts'].items():assert sha((OUT/'matrix/h09-cli'/relative).read_bytes())==digest
    assert sha((OUT/'matrix/qa-v3.json').read_bytes())=='480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8'
    previous=json.loads(git('show','5bcbe8d1500c61536d16385b6dff53f33e0119e8:docs/test-reports/2026-10-06/h07a-independent-b3-full/h09-cli/report.json'))
    assert report['stable_projection']==previous['stable_projection']
    save('h09-checks.json',{'source':CODE,'tree':TREE,'totals':report['totals'],'artifact_hashes_verified':len(report['artifacts']),'stable_projection_equals_reviewed_b3':True,'report_sha256':sha((OUT/'matrix/h09-cli/report.json').read_bytes())})
    sys.path[:0]=paths+[DEPS]
    from pioneer_agent.agent_harness.run_store import JsonRunStore
    fixture=(ROOT/'packages/pioneer-agent/tests/fixtures/agent_harness/h07a_v1_compat.json').read_bytes();legacy=json.loads(fixture)
    fresh=OUT/'current-reader-v1.json';fresh.write_bytes(fixture)
    new_state=JsonRunStore(fresh).load();assert fresh.read_bytes()==fixture
    contracts=types.ModuleType('integration_actual_110bd_contracts');sys.modules[contracts.__name__]=contracts
    old_code=git('show',BASE+':packages/pioneer-agent/src/pioneer_agent/agent_harness/task_contracts.py');exec(compile(old_code,'actual110bd/task_contracts.py','exec'),contracts.__dict__)
    key='pioneer_agent.agent_harness.task_contracts';original=sys.modules[key];sys.modules[key]=contracts
    try:
        store=types.ModuleType('integration_actual_110bd_store');sys.modules[store.__name__]=store
        old_store=git('show',BASE+':packages/pioneer-agent/src/pioneer_agent/agent_harness/run_store.py');exec(compile(old_store,'actual110bd/run_store.py','exec'),store.__dict__)
        path=OUT/'actual-110bd-reader-v1.json';path.write_bytes(fixture)
        loaded=store.JsonRunStore(path).load()
        assert loaded.model_dump(mode='json')==legacy and path.read_bytes()==fixture
        assert new_state.model_dump(mode='json')==legacy
        save('old-reader-extra.json',{'source':BASE,'v1_actual_old_load_exact':True,'v1_actual_old_load_bytes_unchanged':True,'v1_current_load_exact':True,'v1_current_load_bytes_unchanged':True,'v2_actual_old_reject_and_no_rewrite':'matrix/old-reader.json','contracts_sha256':sha(old_code),'store_sha256':sha(old_store)})
    finally:sys.modules[key]=original
after=integrity('source-after');assert before==after
save('completion.json',{'source':CODE,'mode':MODE,'unexpected_failures':0,'historical_original_probe_expected_exit':1 if MODE=='linux' else None,'source_input_records':len(before),'archive_content_reads':0,'archive_created':False})
