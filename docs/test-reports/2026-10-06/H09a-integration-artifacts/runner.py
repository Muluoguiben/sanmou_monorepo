import hashlib, json, os, platform, subprocess, sys, time
from pathlib import Path

ROOT = Path('/tmp/sanmou-h09a-integration-20261006')
OUT = Path('/tmp/h09a-integration-evidence-2d07-20261006-verify')
CODE = '2d07e1b82de3d09ab809ad9018b70dc3095ff5bb'
TREE = '12bbc84a2a159d30f3691e6786a7584615686c8e'
PACKAGES = 'fee69c4090f882c87b48857cc8a251a2de3dfdbc'
REVIEW = ROOT / 'docs/test-reports/2026-10-06/h09a-independent-cr'
DEPS = '/tmp/sanmou-cr-20261005-6155-deps'
def env(root=ROOT):
    return dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=':'.join(str(root / p) for p in ['packages/pioneer-agent/src','packages/qa-agent/src','packages/sanmou-common/src','packages/pioneer-agent/tests','packages/pioneer-agent/tests/unit']) + ':' + DEPS, TMPDIR=str(OUT))
def git(*args):
    return subprocess.check_output(['git','-C',str(ROOT),*args])
def save(name,obj):
    with (OUT / name).open('x') as f: json.dump(obj,f,ensure_ascii=False,indent=2)
def integrity(label):
    assert git('rev-parse','HEAD').decode().strip()==CODE
    assert git('rev-parse','HEAD^{tree}').decode().strip()==TREE
    assert git('rev-parse','HEAD:packages').decode().strip()==PACKAGES
    assert not git('status','--porcelain')
    entries={}
    for row in git('ls-tree','-r','-z',CODE).split(b'\0'):
        if not row: continue
        meta,name=row.split(b'\t'); mode,kind,oid=meta.decode().split(); name=name.decode()
        entries[name]={'mode':mode,'type':kind,'oid':oid}
    manifest=Path('/tmp/h09a-protected-b338-upcfx4ye/protected-blobs.jsonl').read_bytes()
    assert hashlib.sha256(manifest).hexdigest()=='651d4fd446e46c8dd2ae661ce27387016a0ff160ea94ec36f1de2c189531ae3e'
    protected=[json.loads(x) for x in manifest.splitlines()]
    for r in protected: assert entries[r['path']]=={k:r[k] for k in ('mode','type','oid')}
    checked={}
    for name,item in entries.items():
        if not name.startswith('packages/') and name not in {r['path'] for r in protected}: continue
        path=ROOT/name
        raw=os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['oid'],name
        checked[name]=hashlib.sha256(raw).hexdigest()
    save(label+'.json',{'source':CODE,'tree':TREE,'packages':PACKAGES,'protected':len(protected),'files':checked,'status':''})
def run(name,args,cwd=ROOT,root=ROOT):
    start=time.time()
    with (OUT/(name+'.log')).open('xb') as log:
        p=subprocess.run(args,cwd=cwd,env=env(root),stdout=log,stderr=subprocess.STDOUT)
    record={'name':name,'argv':args,'cwd':str(cwd),'PYTHONPATH':env(root)['PYTHONPATH'],'exit':p.returncode,'seconds':time.time()-start}
    save(name+'.command.json',record); print(json.dumps(record),flush=True)
    return p.returncode
def frozen(name,commit='0c40a7b426f16930dc1928abd903e2d249f14b2a'):
    p=REVIEW/(name+'.py'); raw=p.read_bytes()
    assert raw==git('show',commit+':'+str(p.relative_to(ROOT)))
    return raw.decode()

if sys.argv[1]=='main':
    integrity('source-before')
    save('runtime.json',{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'environment_keys':sorted(env()),'dependencies':subprocess.check_output([sys.executable,'-B','-c','import importlib.metadata as m,json; print(json.dumps({n:m.version(n) for n in ["pydantic","PyYAML","mcp","anyio","setuptools"]}))'],env=env()).decode()})
    failures=[]
    for package in ('pioneer-agent','qa-agent','sanmou-common'):
        if run(package+'-full',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_*.py','-v'],ROOT/'packages'/package): failures.append(package)
    for name,entry in [('eval1',['-m','pioneer_agent.app.task_eval']),('eval2',['-m','pioneer_agent.app.task_eval']),('direct',[str(ROOT/'packages/pioneer-agent/src/pioneer_agent/app/task_eval.py')])]:
        if run(name,[sys.executable,'-B',*entry,'--output',str(OUT/name)]): failures.append(name)
    if run('qa-v3',[sys.executable,'-B','-m','qa_agent.quality_eval.runner','--baseline','v3','--output',str(OUT/'qa-v3.json')],ROOT/'packages/qa-agent'): failures.append('qa-v3')
    for mode in ('probes','report-checks','metadata'):
        if run(mode,[sys.executable,'-B',str(Path(__file__)),mode]): failures.append(mode)
    integrity('source-after')
    save('failures.json',failures)
    raise SystemExit(bool(failures))
elif sys.argv[1]=='probes':
    import types, unittest, tempfile
    tests=unittest.TestSuite()
    for name,cls in [('probes','Independent'),('supplemental_probes','Supplements'),('finalization_probes_2cc','Finalization'),('committed_finalization_2cc','CommittedFinalization'),('final_boundaries_fece','FinalBoundaries')]:
        raw=frozen(name); mod=types.ModuleType(name); mod.__file__=str(REVIEW/(name+'.py')); sys.modules[name]=mod
        exec(compile(raw,mod.__file__,'exec'),mod.__dict__)
        mod.ROOT=ROOT; mod.DATA=ROOT/'packages/pioneer-agent/evaluation/task/development-v1'
        tests.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(getattr(mod,cls)))
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful())
elif sys.argv[1]=='report-checks':
    source=frozen('source_report_checks_2cc','74d711e29db0a1e86e781bd65e420787a1cb2210')
    source=source.replace('/tmp/h09a-cr-2cc7b2f8-20261006',str(ROOT)).replace('2cc7b2f885b3d33b46c719b89fb3c85d2ade2e96',CODE).replace('73309b5d5bf61b0c02765eb833e1c308bd04eec0',TREE).replace('/tmp/h09a-cr-2cc7b2f8-',str(OUT)+'/')
    exec(compile(source,'source_report_checks_rebound.py','exec'),{})
    reports=[json.loads((OUT/name/'report.json').read_bytes()) for name in ('eval1','eval2','direct')]
    assert reports[0]['inputs']==reports[1]['inputs']==reports[2]['inputs']
    qa=hashlib.sha256((OUT/'qa-v3.json').read_bytes()).hexdigest()
    assert qa=='480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8',qa
    save('current-report-summary.json',{'source':CODE,'tree':TREE,'QA_v3_sha256':qa,'runs':[{k:r[k] for k in ('totals','denominators','source_verified','gate_pass','complete','inputs')} for r in reports]})
elif sys.argv[1]=='metadata':
    meta=OUT/'metadata-worktree'
    subprocess.run(['git','-C',str(ROOT),'-c','core.autocrlf=false','-c','core.eol=lf','worktree','add','--detach',str(meta),CODE],check=True)
    source=frozen('editable_metadata_fece').replace('/tmp/h09a-cr-fece-editable-metadata-evidence',str(OUT/'metadata-original')).replace('/tmp/h09a-cr-fece-editable-metadata',str(meta)).replace('fece4163d04af5057493549da2db74a8fa65ed06',CODE)
    save('metadata-rebinding.json',{'source_commit':CODE,'original_sha256':hashlib.sha256(frozen('editable_metadata_fece').encode()).hexdigest(),'rebound_sha256':hashlib.sha256(source.encode()).hexdigest(),'root':str(meta),'out':str(OUT/'metadata-original')})
    exec(compile(source,'editable_metadata_rebound.py','exec'),{})
    if run('metadata-boundaries',[sys.executable,'-B',str(Path(__file__)),'metadata-boundaries'],root=meta): raise SystemExit(1)
elif sys.argv[1]=='metadata-boundaries':
    source=frozen('metadata_boundaries_103','74d711e29db0a1e86e781bd65e420787a1cb2210')
    source=source.replace('/tmp/h09a-cr-103d-editable-metadata',str(OUT/'metadata-worktree')).replace('/tmp/h09a-cr-103d-metadata-boundaries',str(OUT/'metadata-boundaries'))
    exec(compile(source,'metadata_boundaries_rebound.py','exec'),{})
