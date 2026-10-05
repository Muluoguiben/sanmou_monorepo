import hashlib,json,os,re,shutil,stat,subprocess,tarfile
from pathlib import Path
ROOT=Path('/tmp/sanmou-h09b-integration-20261006')
OUT=Path('/tmp/h09b-integration-evidence-21e279a-20261006')
WIN=Path('/mnt/c/Users/Lan/AppData/Local/Temp/h09b-integration-evidence-21e279a-20261006')
DEST=ROOT/'docs/test-reports/2026-10-06/H09b-integration-artifacts'
assert not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'])
summary={}
for name,directory in [('linux',OUT/'linux'),('windows',WIN)]:
    before=json.loads((directory/'source-before.json').read_bytes()); after=json.loads((directory/'source-after.json').read_bytes())
    assert before==after
    assert json.loads((directory/'completion.json').read_bytes())['passed']
    summary[name]={'source':before['source'],'tree':before['tree'],'packages':before['packages'],'source_byte_records':len(before['files']),'status_before_after':'clean','runtime':json.loads((directory/'runtime.json').read_bytes()),'codec':json.loads((directory/'codec.json').read_bytes())}
summary['protected_records']=json.loads((OUT/'linux/protected-1414.json').read_bytes())['count']
summary['linux_diagnostic']=json.loads((OUT/'linux/linux-diagnostic.json').read_bytes())
summary['qa_v3_sha256']=hashlib.sha256((OUT/'linux/qa-v3.json').read_bytes()).hexdigest()
summary['workflow_scope']=json.loads((OUT/'linux/workflow-scope.json').read_bytes())
summary['tests']={}
for name,path,count,skip in [('pioneer',OUT/'linux/pioneer-agent-full.log',1018,2),('qa',OUT/'linux/qa-agent-full.log',394,0),('common',OUT/'linux/sanmou-common-full.log',2,0),('linux_stdlib',OUT/'linux/stdlib20.log',20,0),('windows_stdlib',WIN/'stdlib20.log',20,0)]:
    text=path.read_text(); match=re.search(r'Ran (\d+) tests in ([0-9.]+)s',text)
    assert match and int(match[1])==count
    assert re.search(r'^OK'+(r' \(skipped=2\)' if skip else '')+r'$',text,re.M)
    summary['tests'][name]={'total':count,'pass':count-skip,'skip':skip,'failure':0,'seconds':float(match[2]),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
probes=json.loads((WIN/'probes/probe-results.json').read_bytes())
assert len(probes['probes'])==20 and all(x['passed'] for x in probes['probes'])
summary['frozen_original_probes']=20
summary['hosted_native_cli_acceptance']='pending; no native evaluator or CI invocation in this task'
DEST.mkdir(exist_ok=False)
paths=[]
for prefix,directory in [('linux-evidence',OUT),('windows-evidence',WIN)]:
    def walk(parent):
        for path in sorted(parent.iterdir()):
            paths.append((prefix+'/'+path.relative_to(directory).as_posix(),path))
            if path.is_dir() and not path.is_symlink(): walk(path)
    walk(directory)
inventory=[]
with tarfile.open(DEST/'evidence.tar.gz','w:gz',dereference=False) as tar:
    for name,path in paths:
        mode=path.lstat().st_mode
        if stat.S_ISREG(mode): row={'path':name,'type':'regular','bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        elif stat.S_ISDIR(mode): row={'path':name,'type':'directory'}
        elif stat.S_ISLNK(mode): row={'path':name,'type':'symlink','target':os.readlink(path)}
        else: raise AssertionError(name)
        inventory.append(row); tar.add(path,arcname=name,recursive=False)
with tarfile.open(DEST/'evidence.tar.gz','r:gz') as tar:
    for member,row in zip(tar.getmembers(),inventory,strict=True):
        assert member.name==row['path']
        if row['type']=='regular': assert hashlib.sha256(tar.extractfile(member).read()).hexdigest()==row['sha256']
summary['archive_sha256']=hashlib.sha256((DEST/'evidence.tar.gz').read_bytes()).hexdigest()
summary['archive_counts']={kind:sum(row['type']==kind for row in inventory) for kind in ('regular','directory','symlink')}
with (DEST/'typed-inventory.json').open('x') as f: json.dump({'no_extraction':True,'members':inventory},f,indent=2)
with (DEST/'summary.json').open('x') as f: json.dump(summary,f,indent=2)
for name in ('verify.py','seal.py'): shutil.copyfile(OUT/name,DEST/name)
manifest={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(DEST.iterdir())}
with (DEST/'manifest.json').open('x') as f: json.dump(manifest,f,indent=2)
print(json.dumps({k:summary[k] for k in ('tests','archive_sha256','archive_counts','protected_records','qa_v3_sha256')},indent=2))
