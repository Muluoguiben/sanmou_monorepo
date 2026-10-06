"""Exact Q05a coordinator replay; original frozen assertions unchanged."""
import ast,copy,hashlib,json,platform,re,subprocess,sys
from pathlib import Path
ROOT=Path('/tmp/sanmou-h07a-integration-20261006')
OUT=Path('/tmp/q05a-integration-a0e71c6-20261006')
BASE_ROOT=Path('/tmp/q05a-cr-baseline-3711-20261006')
BASE='3711e92d38786418e8e955d19a56cd6c72611389'
CODE='a0e71c62c042e15877a5942b2d6e22611c40b301'
TREE='570510cf9480178b1a523b0334dac6475a1fa6e4'
REVIEW='52b2642cc0956a59b5dd573bcd838dc3c91ef8c6'
HERE=ROOT/'docs/test-reports/2026-10-06'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git','-c','core.autocrlf=false','-C',str(ROOT),*args])
def save(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2)
files=['q05a-independent-verify.py','q05a-baseline-verify.py','q05a-independent-probes.py','q05a-v4-integration-probes.py','q05a-resource-warning-probe.py']
hashes={}
for name in files:
    raw=(HERE/name).read_bytes();assert raw==git('show',REVIEW+':docs/test-reports/2026-10-06/'+name);hashes[name]=sha(raw)
assert (HERE/'q05a-v4-integration-probes.py').read_bytes()==git('show','51497c3341e5ad2062ac4922c9b6e216c5f52d79:docs/test-reports/2026-10-06/q05a-v4-integration-probes.py')
REPAIR_BASE='3d8257bf03d47bb86fb80994c924987033b1858a'
repair_paths=['packages/qa-agent/tests/test_quality_eval.py','packages/qa-agent/tests/test_seasonal_retriever.py']
assert git('diff','--name-only',REPAIR_BASE,CODE,'--','packages','.github').decode().splitlines()==repair_paths
additions=[]
def paired(old,new,path):
    assert type(old) is type(new),(path,type(old),type(new))
    if isinstance(old,ast.AST):
        if isinstance(old,ast.Call) and isinstance(old.func,ast.Attribute) and old.func.attr in {'read_text','write_text'} and len(new.keywords)==len(old.keywords)+1:
            extra=[k for k in new.keywords if k.arg=='encoding' and not any(x.arg=='encoding' for x in old.keywords)]
            assert len(extra)==1 and isinstance(extra[0].value,ast.Constant) and extra[0].value.value=='utf-8',path
            new.keywords.remove(extra[0]);additions.append(path)
        for (key,a),(key2,b) in zip(ast.iter_fields(old),ast.iter_fields(new)):
            assert key==key2;paired(a,b,path+'/'+key)
    elif isinstance(old,list):
        assert len(old)==len(new),(path,len(old),len(new))
        for i,(a,b) in enumerate(zip(old,new)):paired(a,b,path+'/'+str(i))
    else:assert old==new,(path,old,new)
for path in repair_paths:
    a=ast.parse(git('show',REPAIR_BASE+':'+path));b=ast.parse((ROOT/path).read_bytes())
    paired(a,b,path);assert ast.dump(a)==ast.dump(b)
assert len(additions)==15
locale_probe=HERE/'q05a-file-locale-probe.py'
assert locale_probe.read_bytes()==git('show','8bb4a1dc7f6183daf883045bfd1a81c2bf79f9dc:docs/test-reports/2026-10-06/q05a-file-locale-probe.py')
hashes[locale_probe.name]=sha(locale_probe.read_bytes())
if sys.argv[1]=='matrix':
    path=HERE/'q05a-independent-verify.py';raw=path.read_text()
    assert raw.count('3d8257bf03d47bb86fb80994c924987033b1858a')==1 and raw.count('0aa22ba210af5fb112b9ad073939428961511b4d')==1
    adapted=raw.replace('3d8257bf03d47bb86fb80994c924987033b1858a',CODE).replace('0aa22ba210af5fb112b9ad073939428961511b4d',TREE)
    original_gate='old_methods, new_methods = methods(git("show", BASE + ":" + test_path)), methods((root / test_path).read_bytes())'
    repair_gate='old_methods, new_methods = methods(git("show", BASE + ":" + test_path)), methods(git("show", "3d8257bf03d47bb86fb80994c924987033b1858a:" + test_path))'
    assert adapted.count(original_gate)==1
    adapted=adapted.replace(original_gate,repair_gate)
    sys.argv=[str(path),str(ROOT),str(OUT/'baseline'),str(OUT/'run')]
    exec(compile(adapted,str(path)+' (combo identity only)','exec'),{'__name__':'__main__','__file__':str(path)})
    raise SystemExit
assert sys.argv[1]=='main'
def entries(commit):return {r.split(b'\t')[1].decode():r.split(b'\t')[0].decode() for r in git('ls-tree','-rz',commit).split(b'\0') if r}
current=entries(CODE);base=entries(BASE)
assert git('rev-parse','HEAD').decode().strip()==CODE and git('rev-parse','HEAD^{tree}').decode().strip()==TREE
assert not git('status','--porcelain')
assert git('rev-parse','HEAD:packages').decode().strip()=='00e356dcae98b08a2c26a91fb0f8b728c8cd96fb'
assert git('rev-parse','HEAD:.github').decode().strip()=='20db19b28ae98b89bcfdd5444bddbe2652eeb878'
changes=set(git('diff','--name-only',BASE,CODE,'--','packages','.github').decode().splitlines())
excluded=changes|{'.codex-autonomy/review-iteration-20261005/state.json','.codex-autonomy/review-iteration-20261005/WORKLOG.md','todo-list.md'}
protected={n:m for n,m in base.items() if n not in excluded};assert all(current.get(n)==m for n,m in protected.items())
def inputs():
    rows=[]
    for name,meta in sorted(current.items()):
        if not name.startswith('packages/') or Path(name).suffix not in ('.py','.json','.yaml','.yml'):continue
        assert meta.startswith(('100644 blob ','100755 blob '))
        raw=(ROOT/name).read_bytes();oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();assert oid==meta.split()[2]
        rows.append([name,oid,sha(raw),len(raw)])
    assert len(rows)==904
    return sha(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode())
before=inputs()
assert subprocess.check_output(['git','-C',str(BASE_ROOT),'rev-parse','HEAD']).decode().strip()==BASE
assert not subprocess.check_output(['git','-C',str(BASE_ROOT),'status','--porcelain'])
save('source-proof.json',{'source':CODE,'tree':TREE,'baseline':BASE,'baseline_root':str(BASE_ROOT),'helper_hashes':hashes,'adaptation':'CODE/TREE plus transitive AST gate: entire current two-test AST equals3d after exactly15 added UTF8 keywords; original3711-to3d literal assertion gate retained; probes unchanged','encoding_additions':additions,'ordinary_inputs':904,'before_digest':before,'protected_metadata_paths':len(protected),'old_report_paths':sum(n.startswith('docs/test-reports/') for n in protected),'archive_body_reads':0,'runtime':{'executable':sys.executable,'python':sys.version,'platform':platform.platform()}})
for name,argv,timeout in [('baseline',[sys.executable,'-B',str(HERE/'q05a-baseline-verify.py'),str(BASE_ROOT),str(OUT/'baseline')],600),('matrix',[sys.executable,'-B',str(Path(__file__)),'matrix'],1800)]:
    with (OUT/(name+'-driver.log')).open('xb') as f:result=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
    assert result.returncode==0,(name,result.returncode)
    print(json.dumps({'phase':name,'exit':result.returncode}),flush=True)
locale_results={}
for name,root,source,expected in [('text-locale-original',Path('/tmp/q05a-cr-3d8257b-20261006'),REPAIR_BASE,1),('text-locale-fixed',ROOT,CODE,0)]:
    with (OUT/(name+'-driver.log')).open('xb') as f:p=subprocess.run([sys.executable,'-B',str(locale_probe),str(root),str(OUT/name),source],stdout=f,stderr=subprocess.STDOUT,timeout=700)
    assert p.returncode==expected,(name,p.returncode)
    record=json.loads((OUT/name/'summary.json').read_bytes())
    assert record['exit']==expected and record['locale']['tests_run']==44 and record['locale']['skips']==0
    assert record['locale']['target_test_process']['utf8_mode']==0 and record['locale']['target_test_process']['filesystem_encoding']=='utf-8'
    assert record['locale']['target_test_process']['file_encoding']=='ANSI_X3.4-1968'
    assert record['locale']['spawned_interpreter']['locale']=='C.UTF-8'
    assert record['locale']['errors']==(27 if expected else 0) and record['locale']['failures']==0
    locale_results[name]=record
    print(json.dumps({'phase':name,'exit':p.returncode,'errors':record['locale']['errors']}),flush=True)
save('locale-comparison.json',{'results':locale_results,'scope':'real POSIX ASCII text locale with UTF8 filesystem; children CLIs C.UTF8; not Windows; strictC ASCII filesystem remains unfixed and was not rerun'})
s=json.loads((OUT/'run/summary.json').read_bytes())
expected={'public-probes':(5,0),'v4-integration-probes':(4,0),'resource-warning-fixed':(1,0),'q05-targeted':(44,0),'q04-module':(25,0),'h07':(35,0),'h10':(32,0),'qa-agent':(440,0),'pioneer-agent':(1085,2),'sanmou-common':(2,0)}
for row in s['commands']:
    assert row['exit']==row['expected_exit']
    if row['name'] in expected:assert (row['tests'],row['skips'])==expected[row['name']]
    if row['name'] in ('cli-v1','cli-v2','cli-v3'):assert not (OUT/'run'/(row['name'][4:]+'.json')).exists()
assert not re.search('RuntimeWarning|was never awaited',(OUT/'run/h10.log').read_text())
assert s['season_controls']==8
hraw=(OUT/'run/h09-cli/report.json').read_bytes();h=json.loads(hraw)
assert h['source']['commit']==CODE and h['source']['tree']==TREE
assert all(h[k] is True for k in ('complete','valid_suite','source_verified','gate_pass'))
assert h['totals']==dict(control_pass=8,goal_success=2,expected_safety_stop=6,infra_error=0,unexpected_goal_success=0,safety_violations=0)
for n,digest in h['artifacts'].items():assert sha((OUT/'run/h09-cli'/n).read_bytes())==digest
after=inputs();assert before==after and not git('status','--porcelain')
save('completion.json',{'source':CODE,'tree':TREE,'all_expected_results':True,'ordinary_inputs':904,'before_after_digest':after,'h09_artifacts_verified':len(h['artifacts']),'h09_bytes':len(hraw),'h09_sha256':sha(hraw),'native':'not_executed; final Hosted25+44 pending','archive_reads':0})
print(json.dumps({'all_green':True,'source':CODE,'ordinary_inputs':904}),flush=True)
