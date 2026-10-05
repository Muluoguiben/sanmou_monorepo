import contextlib, hashlib, importlib.util, io, json, os, platform, subprocess, sys, time
from pathlib import Path
MODE=sys.argv[1]
ROOT=Path(sys.argv[2])
OUT=Path(sys.argv[3])
CODE='21e279a7efb44840ad4dbda3c06b8eb3514eed77'
TREE='4ebea5d57dc7871f71d7536879531076a962da01'
PACKAGES='c273943f122e9ced51bc7290d3d80b44a6df5e23'
BASE='b7cee26a23f743df5f6950d4144bfddd67927154'
DEPS='/tmp/sanmou-cr-20261005-6155-deps'
def save(name,data):
    with (OUT/name).open('x',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
def git(*args): return subprocess.check_output(['git','-C',str(ROOT),*args])
def tree(commit):
    entries={}
    for row in git('ls-tree','-rz',commit).split(b'\0'):
        if row:
            meta,name=row.split(b'\t'); mode,kind,oid=meta.decode().split()
            entries[name.decode()]={'mode':mode,'type':kind,'oid':oid}
    return entries
def integrity(label):
    assert git('rev-parse','HEAD').decode().strip()==CODE
    assert git('rev-parse','HEAD^{tree}').decode().strip()==TREE
    assert git('rev-parse','HEAD:packages').decode().strip()==PACKAGES
    assert not git('status','--porcelain')
    records={}
    for name,item in tree(CODE).items():
        path=ROOT/name; raw=os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['oid'],name
        records[name]=dict(item,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    save(label+'.json',{'source':CODE,'tree':TREE,'packages':PACKAGES,'status':'','files':records})
def env():
    result=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
    result['PYTHONPATH']=os.pathsep.join(str(ROOT/p) for p in ['packages/pioneer-agent/src','packages/qa-agent/src','packages/sanmou-common/src','packages/pioneer-agent/tests','packages/pioneer-agent/tests/unit'])
    if os.name!='nt': result['PYTHONPATH']+=':'+DEPS
    return result
def run(name,args,cwd=ROOT,expected=0):
    start=time.time()
    with (OUT/(name+'.log')).open('xb') as f: p=subprocess.run(args,cwd=cwd,env=env(),stdout=f,stderr=subprocess.STDOUT)
    row={'argv':args,'cwd':str(cwd),'PYTHONPATH':env()['PYTHONPATH'],'exit':p.returncode,'expected_exit':expected,'seconds':time.time()-start}
    save(name+'.command.json',row); print(json.dumps(dict(name=name,**row)),flush=True)
    assert p.returncode==expected,name
def load_gate():
    spec=importlib.util.spec_from_file_location('integration_gate',ROOT/'scripts/check_windows_task_eval.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
def codec():
    g=load_gate(); empty=list(g.evidence_lines(b'')); maximum=b'x'*g.MAX_REPORT
    lines=list(g.evidence_lines(maximum))
    assert g.decode_log(['2026-10-06T12:34:56.1234567Z '+x+'\n' for x in lines])==maximum
    assert g.decode_log(empty)==b''
    variants={'negative_length':[empty[0].replace(' 0 ',' -1 ',1),empty[1]],'empty_payload_chunk':[empty[0],'H09B_REPORT_CHUNK '+empty[0].split()[1]+' 1 eA==',empty[1]],'empty_wrong_digest':[s.replace(g.sha(b''),'0'*64) for s in empty],'empty_missing_end':empty[:1],'empty_duplicate_end':empty+empty[-1:]}
    rejected=[]
    for name,lines in variants.items():
        try: g.decode_log(lines)
        except ValueError as e: rejected.append({'name':name,'error':str(e)})
        else: raise AssertionError(name)
    save('codec.json',{'max_report':g.MAX_REPORT,'max_log':g.MAX_LOG,'chunk':g.CHUNK,'maximum_roundtrip':True,'zero_roundtrip':True,'empty_five_rejected':rejected,'evidence_class':'pure data, not native CLI'})
if MODE in ('linux','windows'):
    integrity('source-before')
    save('runtime.json',{'python':sys.version,'executable':sys.executable,'os':os.name,'platform':platform.platform(),'source_root':str(ROOT),'source':CODE,'tree':TREE,'packages':PACKAGES,'mode':MODE})
    if MODE=='linux':
        protected_raw=Path('/tmp/h09a-protected-b338-upcfx4ye/protected-blobs.jsonl').read_bytes()
        assert hashlib.sha256(protected_raw).hexdigest()=='651d4fd446e46c8dd2ae661ce27387016a0ff160ea94ec36f1de2c189531ae3e'
        old=[json.loads(line) for line in protected_raw.splitlines() if json.loads(line)['path']!='.github/workflows/regression.yml']
        added=git('diff','--diff-filter=A','--name-only','b338b73f44699ce6ad93a02c16267c54058df68f',BASE).decode().splitlines()
        assert len(old)==830 and len(added)==584
        baseline=tree(BASE); current=tree(CODE)
        paths={r['path'] for r in old}|set(added)
        assert len(paths)==1414
        for path in paths: assert baseline[path]==current[path],path
        save('protected-1414.json',{'baseline':BASE,'count':len(paths),'records':{p:current[p] for p in sorted(paths)}})
        changed=git('diff','--name-only',BASE,CODE,'--','packages','scripts','.github').decode().splitlines()
        assert changed==['.github/workflows/regression.yml','packages/pioneer-agent/tests/test_windows_task_eval_ci.py','scripts/check_windows_task_eval.py']
        workflow=git('show',BASE+':.github/workflows/regression.yml')
        insertion=b'      # Existing CLI; exact report bytes retained in bounded log chunks.\n      - name: Windows H09b offline task evaluation\n        run: python scripts/check_windows_task_eval.py\n'
        actual=(ROOT/'.github/workflows/regression.yml').read_bytes()
        assert actual.count(insertion)==1 and actual.replace(insertion,b'')==workflow
        save('workflow-scope.json',{'changed':changed,'added_lines':3,'old_workflow_sha256':hashlib.sha256(workflow).hexdigest(),'new_workflow_sha256':hashlib.sha256(actual).hexdigest(),'existing_bytes_exactly_preserved':True})
        for package in ('pioneer-agent','qa-agent','sanmou-common'):
            run(package+'-full',[sys.executable,'-B','-m','unittest','discover','-s','tests','-p','test_*.py','-v'],ROOT/'packages'/package)
        run('linux-cli',[sys.executable,'-B','-m','pioneer_agent.app.task_eval','--output',str(OUT/'linux-cli')])
        run('qa-v3',[sys.executable,'-B','-m','qa_agent.quality_eval.runner','--baseline','v3','--output',str(OUT/'qa-v3.json')],ROOT/'packages/qa-agent')
        assert hashlib.sha256((OUT/'qa-v3.json').read_bytes()).hexdigest()=='480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8'
        run('native-checker-linux-rejection',[sys.executable,'-B',str(ROOT/'scripts/check_windows_task_eval.py')],expected=1)
        g=load_gate(); raw=(OUT/'linux-cli/report.json').read_bytes(); r=g.decode(raw)
        assert r['source']['commit']==CODE and r['source']['tree']==TREE and r['gate_pass'] and len(r['cases'])==8
        for relative,digest in r['artifacts'].items(): assert g.sha((OUT/'linux-cli'/relative).read_bytes())==digest
        _,inputs=g.input_buffers(ROOT); tracked={p:v['oid'] for p,v in tree(CODE).items() if any(p.startswith(d+'/') for d in g.SOURCE_DIRS)}
        args=dict(root=ROOT,output=OUT/'linux-cli',commit=CODE,tree=TREE,executable=sys.executable,inputs=inputs,tracked=tracked)
        try: g.validate_report(raw,**args)
        except ValueError as e: assert str(e)=='report_not_windows'
        else: raise AssertionError('Linux report accepted as native')
        r['environment']['platform']='Windows-SYNTHETIC-DATA-ONLY'
        totals=g.validate_report(json.dumps(r).encode(),**args)
        evidence=list(g.evidence_lines(raw)); assert g.decode_log(evidence)==raw
        with (OUT/'linux-report-codec.log').open('x') as f: f.write('\n'.join(evidence)+'\n')
        save('linux-diagnostic.json',{'source':CODE,'tree':TREE,'report_sha256':g.sha(raw),'report_bytes':len(raw),'totals':totals,'artifacts_verified':len(r['artifacts']),'linux_rejected_as_native':True,'data_only_synthetic_platform_validation':True,'real_native_acceptance':False})
    else:
        assert os.name=='nt' and sys.platform=='win32'
        probe='docs/test-reports/2026-10-06/h09b-independent-probes.py'
        raw=git('show','5b0b972f6ce86dc02f88fd3328893b82e6687561:'+probe)
        assert raw==(ROOT/probe).read_bytes() and hashlib.sha256(raw).hexdigest()=='45f05c46376778add2e56b220c2ea711625881f9ad0e52cb73d6567df01e06da'
        old=b'EXPECTED = "f961c1594018651d584bbe622547a79e5648c5a7"'; new=('EXPECTED = "'+CODE+'"').encode()
        assert raw.count(old)==1; rebound=raw.replace(old,new); assert rebound.replace(new,old)==raw
        save('probe-rebinding.json',{'original_sha256':hashlib.sha256(raw).hexdigest(),'new_source':CODE,'rebound_sha256':hashlib.sha256(rebound).hexdigest(),'only_change':'EXPECTED source SHA; assertions unchanged'})
        sys.argv=[probe,str(ROOT),str(OUT/'probes')]
        with (OUT/'probes.log').open('x',encoding='utf-8') as f,contextlib.redirect_stdout(f): exec(compile(rebound,probe+' (identity-only)','exec'),{'__name__':'__main__','__file__':probe})
        result=json.loads((OUT/'probes/probe-results.json').read_bytes())
        assert len(result['probes'])==20 and all(x['passed'] for x in result['probes'])
    run('stdlib20',[sys.executable,'-B','-m','unittest','discover','-s',str(ROOT/'packages/pioneer-agent/tests'),'-p','test_windows_task_eval_ci.py','-v'])
    codec(); integrity('source-after'); save('completion.json',{'passed':True,'source':CODE,'native_cli_acceptance':False}); print('COMPLETE '+MODE,flush=True)
