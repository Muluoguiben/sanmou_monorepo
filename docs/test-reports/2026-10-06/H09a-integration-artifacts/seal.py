import hashlib, json, os, shutil, stat, subprocess, tarfile
from pathlib import Path
ROOT=Path('/tmp/sanmou-h09a-integration-20261006')
OUT=Path('/tmp/h09a-integration-evidence-2d07-20261006-verify')
DEST=ROOT/'docs/test-reports/2026-10-06/H09a-integration-artifacts'
DEST.mkdir(exist_ok=False)
assert json.loads((OUT/'failures.json').read_bytes())==[]
assert not subprocess.check_output(['git','-C',str(ROOT),'status','--porcelain'])
before=json.loads((OUT/'source-before.json').read_bytes())
after=json.loads((OUT/'source-after.json').read_bytes())
assert before==after
reports=[OUT/n/'report.json' for n in ('eval1','eval2','direct')]+[OUT/'metadata-original/report/report.json',OUT/'metadata-boundaries/both-metadata-report/report.json']+[OUT/'metadata-formal'/n/'report.json' for n in ('report','both-packages-positive','restored-both-packages-positive')]
rows=[]
first=json.loads(reports[0].read_bytes())
for path in reports:
    r=json.loads(path.read_bytes())
    assert r['source']['commit']==before['source'] and r['source']['tree']==before['tree']
    assert r['gate_pass'] and r['source_verified'] and r['complete']
    assert r['stable_projection']==first['stable_projection'] and r['inputs']==first['inputs']
    for relative,digest in r['artifacts'].items(): assert hashlib.sha256((path.parent/relative).read_bytes()).hexdigest()==digest
    rows.append({'path':str(path.relative_to(OUT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'totals':r['totals'],'artifact_count':len(r['artifacts']),'stable_projection_sha256':hashlib.sha256(json.dumps(r['stable_projection'],sort_keys=True,separators=(',',':')).encode()).hexdigest()})
with (OUT/'all-positive-audit.json').open('x') as f: json.dump(rows,f,indent=2)
paths=[]
def walk(directory):
    for path in sorted(directory.iterdir()):
        if path==OUT/'metadata-worktree': continue
        paths.append(path)
        if path.is_dir() and not path.is_symlink(): walk(path)
walk(OUT)
for package,egg in [('pioneer-agent','pioneer_agent'),('sanmou-common','sanmou_common')]:
    parent=OUT/'metadata-worktree/packages'/package/'src'/(egg+'.egg-info')
    paths.append(parent); paths.extend(sorted(parent.iterdir()))
inventory=[]
with tarfile.open(DEST/'evidence.tar.gz','w:gz',dereference=False) as tar:
    for path in paths:
        relative=str(path.relative_to(OUT)); mode=path.lstat().st_mode
        if stat.S_ISLNK(mode): row={'path':relative,'type':'symlink','target':os.readlink(path),'followed':False}
        elif stat.S_ISDIR(mode): row={'path':relative,'type':'directory'}
        elif stat.S_ISREG(mode): row={'path':relative,'type':'regular','bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        else: raise AssertionError(relative)
        inventory.append(row); tar.add(path,arcname=relative,recursive=False)
with tarfile.open(DEST/'evidence.tar.gz','r:gz') as tar:
    for member,row in zip(tar.getmembers(),inventory,strict=True):
        assert member.name==row['path']
        if row['type']=='regular': assert hashlib.sha256(tar.extractfile(member).read()).hexdigest()==row['sha256']
        if row['type']=='symlink': assert member.issym() and member.linkname==row['target']
summary={'source':before['source'],'tree':before['tree'],'packages':before['packages'],'protected':before['protected'],'source_byte_records':len(before['files']),'archive_sha256':hashlib.sha256((DEST/'evidence.tar.gz').read_bytes()).hexdigest(),'counts':{kind:sum(r['type']==kind for r in inventory) for kind in ('regular','directory','symlink')},'archive_policy':'no extraction; symlinks recorded, never followed','members':inventory}
with (DEST/'typed-inventory.json').open('x') as f: json.dump(summary,f,indent=2)
for name in ['runner.py','metadata_formal.py','seal.py','runtime.json','current-report-summary.json','all-positive-audit.json','failures.json']:
    shutil.copyfile(OUT/name,DEST/name)
manifest={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(DEST.iterdir())}
with (DEST/'manifest.json').open('x') as f: json.dump(manifest,f,indent=2)
print(json.dumps({k:v for k,v in summary.items() if k!='members'},indent=2))
