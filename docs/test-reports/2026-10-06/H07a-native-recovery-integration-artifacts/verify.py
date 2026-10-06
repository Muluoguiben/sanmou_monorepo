"""Exact H07a follow-up integration; bounded plain evidence, no archive access."""
import ast,hashlib,json,os,platform,re,subprocess,sys,time
from pathlib import Path
ROOT=Path('/tmp/sanmou-h07a-integration-20261006')
OUT=Path('/tmp/h07a-recovery-integration-943b052-20261006/run')
CODE='943b052e6054f913feca89683a7aa00d4497625d'
TREE='efbab0cce00b1570fe51abf2e7e66a0b459a5fa7'
BASE='ca04ae1ef396576c5983f887502bf20b7d6f0015'
TEST='packages/pioneer-agent/tests/test_task_approval.py'
WF='.github/workflows/regression.yml'
OUT.mkdir(exist_ok=False)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def git(*args):return subprocess.check_output(['git','-c','core.autocrlf=false','-C',str(ROOT),*args])
def entries(commit):
    rows={}
    for row in git('ls-tree','-rz',commit).split(b'\0'):
        if row:
            meta,name=row.split(b'\t');rows[name.decode()]=meta.decode()
    return rows
def inputs():
    result=[]
    for name,meta in sorted(entries(CODE).items()):
        if not name.startswith('packages/') or Path(name).suffix not in ('.py','.json','.yaml','.yml'):continue
        raw=(ROOT/name).read_bytes();oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        assert oid==meta.split()[2],name
        result.append([name,oid,sha(raw),len(raw)])
    assert len(result)==893
    return result
def funcs(body,prefix=''):
    result={}
    for node in body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):result[prefix+node.name]=ast.dump(node,include_attributes=False)
        elif isinstance(node,ast.ClassDef):result.update(funcs(node.body,prefix+node.name+'.'))
    return result
assert git('rev-parse','HEAD').decode().strip()==CODE
assert git('rev-parse','HEAD^{tree}').decode().strip()==TREE
assert git('rev-parse','HEAD:packages').decode().strip()=='8df6ebbd7eec3323f8f3e2054013157de2861c8e'
assert git('rev-parse','HEAD:.github').decode().strip()=='7235130b9af9859cec2193f3268b47eb8a4d72ca'
assert not git('diff','--name-only','HEAD')
assert git('diff','--name-only',BASE,CODE,'--','packages','scripts','.github').decode().splitlines()==[WF,TEST]
baseline,current=entries(BASE),entries(CODE)
protected={name:meta for name,meta in baseline.items() if name.startswith(('packages/','scripts/','docs/test-reports/','.github/')) and name not in (TEST,WF)}
assert all(current.get(name)==meta for name,meta in protected.items())
assert not any('q06' in name.lower() or 'knowledge_snapshot_audit' in name for name in current)
assert subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor','cd6d4929ec611cda1600934dde17aef996142ae0',CODE],capture_output=True).returncode==1
old=funcs(ast.parse(git('show',BASE+':'+TEST)).body);new=funcs(ast.parse((ROOT/TEST).read_bytes()).body)
assert all(new.get(name)==body for name,body in old.items())
assert sum(name.split('.')[-1].startswith('test_') for name in old)==30
assert sum(name.split('.')[-1].startswith('test_') for name in new)==35
added=b'      - name: Windows H07a synthetic approval lifecycle\n        working-directory: packages/pioneer-agent/tests\n        run: python -m unittest test_task_approval -v\n'
workflow=(ROOT/WF).read_bytes();assert workflow.count(added)==1 and workflow.replace(added,b'')==git('show',BASE+':'+WF)
before=inputs()
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=':'.join(str(ROOT/p) for p in ('packages/pioneer-agent/src','packages/qa-agent/src','packages/sanmou-common/src','packages/pioneer-agent/tests','packages/pioneer-agent/tests/unit'))+':/tmp/sanmou-cr-20261005-6155-deps')
summary={'source':CODE,'tree':TREE,'packages':'8df6ebbd7eec3323f8f3e2054013157de2861c8e','github':'7235130b9af9859cec2193f3268b47eb8a4d72ca','baseline':BASE,'runtime':{'python':sys.version,'executable':sys.executable,'platform':platform.platform()},'helper_sha256':sha(Path(__file__).read_bytes()),'scope':{'changed_code':[WF,TEST],'old_test_methods_unchanged':30,'new_test_methods':5,'all_old_function_AST_preserved':True,'only_three_workflow_lines_added':True,'production_unchanged':True,'protected_metadata_count':len(protected),'protected_metadata_sha256':sha(canonical(protected)),'old_report_metadata_count':sum(n.startswith('docs/test-reports/') for n in baseline),'input_count':len(before),'input_manifest_before_sha256':sha(canonical(before)),'q06_ancestor':False,'archive_content_reads':0},'commands':[],'unexpected_failures':[],'native':{'status':'pending_hosted_windows_ci_35_pass_zero_skip','local_whole_module_run':False,'local_dependency_limitation':'previous bounded probe missing pywintypes/rpds.rpds; no exploration/install/mock/skip-as-pass in this task'}}
def run(name,args,cwd,tests=None,skips=0):
    argv=[sys.executable,'-B',*map(str,args)];start=time.time();log=OUT/(name+'.log')
    with log.open('xb') as f:p=subprocess.run(argv,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=900)
    raw=log.read_bytes();assert len(raw)<=2*1024*1024
    text=raw.decode('utf-8',errors='replace');match=re.search(r'^Ran (\d+) tests? in ([0-9.]+)s',text,re.M);ok=re.search(r'^OK(?: \(skipped=(\d+)\))?$',text,re.M)
    valid=p.returncode==0 and (tests is None or bool(match and ok and int(match[1])==tests and int(ok[1] or 0)==skips))
    row={'name':name,'argv':argv,'cwd':str(cwd),'PYTHONPATH':env['PYTHONPATH'],'exit':p.returncode,'elapsed_seconds':time.time()-start,'tests':int(match[1]) if match else None,'skipped':int(ok[1] or 0) if ok else None,'expected_tests':tests,'expected_skipped':skips if tests else None,'log':log.name,'bytes':len(raw),'sha256':sha(raw),'passed':valid}
    summary['commands'].append(row)
    if not valid:summary['unexpected_failures'].append(name)
    print(json.dumps({k:row[k] for k in ('name','exit','tests','skipped','passed')}),flush=True)
pioneer=ROOT/'packages/pioneer-agent'
run('approval-module',['-m','unittest','test_task_approval','-v'],pioneer/'tests',35)
run('focused',['-m','unittest','test_task_approval','test_task_runner','test_task_contracts','test_task_cli','test_checkpoint_ownership','test_task_cr_regressions','-v'],pioneer,109)
for package,total,skip in [('pioneer-agent',1053,2),('qa-agent',394,0),('sanmou-common',2,0)]:run(package+'-full',['-m','unittest','discover','-s','tests','-p','test_*.py','-v'],ROOT/'packages'/package,total,skip)
run('h09-cli',['-m','pioneer_agent.app.task_eval','--output',OUT/'h09-cli'],ROOT)
run('qa-v3',['-m','qa_agent.quality_eval.runner','--baseline','v3','--output',OUT/'qa-v3.json'],ROOT/'packages/qa-agent')
try:
    raw=(OUT/'h09-cli/report.json').read_bytes();report=json.loads(raw)
    assert report['source']['commit']==CODE and report['source']['tree']==TREE
    assert all(report[k] is True for k in ('complete','valid_suite','source_verified','gate_pass'))
    assert report['totals']==dict(goal_success=2,expected_safety_stop=6,control_pass=8,infra_error=0,safety_violations=0,unexpected_goal_success=0)
    for name,digest in report['artifacts'].items():assert sha((OUT/'h09-cli'/name).read_bytes())==digest
    summary['h09']={'raw_external_path':str(OUT/'h09-cli/report.json'),'bytes':len(raw),'sha256':sha(raw),'source':report['source']['commit'],'tree':report['source']['tree'],'totals':report['totals'],'complete':report['complete'],'source_verified':report['source_verified'],'artifact_hashes_verified':len(report['artifacts']),'artifact_root_external':str(OUT/'h09-cli')}
    digest=sha((OUT/'qa-v3.json').read_bytes());assert digest=='480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8'
    summary['qa_v3']={'raw_external_path':str(OUT/'qa-v3.json'),'sha256':digest}
    after=inputs();assert before==after
    summary['scope']['input_manifest_after_sha256']=sha(canonical(after))
    assert git('rev-parse','HEAD').decode().strip()==CODE and not git('diff','--name-only','HEAD')
    summary['source_before_after_clean']=True
finally:
    with (OUT/'summary.json').open('x',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
raise SystemExit(bool(summary['unexpected_failures']))
