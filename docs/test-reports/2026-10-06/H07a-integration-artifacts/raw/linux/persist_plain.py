"""Copy only bounded plain H07 evidence. No archive APIs or member reads."""
import hashlib,json,re,stat
from pathlib import Path
ROOT=Path('/tmp/sanmou-h07a-integration-20261006')
OUT=Path('/tmp/h07a-integration-evidence-74654-20261006')
NATIVE=Path('/mnt/c/Users/Lan/AppData/Local/Temp/h07a-integration-native-74654-20261006')
DEST=ROOT/'docs/test-reports/2026-10-06/H07a-integration-artifacts'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def data(path):return json.loads(path.read_bytes())
for base in (OUT/'linux',NATIVE):
    assert data(base/'completion.json')['unexpected_failures']==0
    assert data(base/'source-before.json')==data(base/'source-after.json')
tests={}
for name,total,skips,failures in [('focused',104,0,0),('pioneer-agent-full',1048,2,0),('qa-agent-full',394,0,0),('sanmou-common-full',2,0,0),('independent-original',5,0,1),('independent-canonical',5,0,0),('independent-postconsume',1,0,0),('independent-progression',1,0,0),('native-lock',3,0,0)]:
    path=(NATIVE if name=='native-lock' else OUT/'linux/matrix')/(name+'.log')
    raw=path.read_bytes();text=raw.decode('utf-8',errors='backslashreplace')
    found=re.search(r'Ran (\d+) tests? in ([0-9.]+)s',text);assert found and int(found[1])==total
    if failures:
        assert 'FAILED (failures=1)' in text and "(True, 'failed', 'observation_stale') != (True, 'failed', 'stale_observation')" in text
    else:
        ok=re.search(r'^OK(?: \(skipped=(\d+)\))?\r?$',text,re.M);assert ok and int(ok[1] or 0)==skips
    tests[name]={'total':total,'pass':total-skips-failures,'skip':skips,'failures':failures,'seconds':float(found[2]),'sha256':sha(raw),'historical_oracle_failure':bool(failures)}
summary={'source':'74654b608d54c459636bfbf1eff69b06f4aeb2fb','tree':'459df67d1ef126a9cb8c7895d5cb0a8aa1d7e50b','packages':'46e832a6f4bbfb84e1f49bad517084841dd1b768','tests':tests,'linux_completion':data(OUT/'linux/completion.json'),'native_completion':data(NATIVE/'completion.json'),'h09':data(OUT/'linux/h09-checks.json'),'old_reader':data(OUT/'linux/matrix/old-reader.json'),'old_reader_extra':data(OUT/'linux/old-reader-extra.json'),'qa_v3_sha256':sha((OUT/'linux/matrix/qa-v3.json').read_bytes()),'archive_content_reads':0,'archive_created':False,'q06_candidate_content_accessed':False,'native_scope':'actual stdlib OS lock primitives3 only; not full H07/MCP'}
assert summary['qa_v3_sha256']=='480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8'
DEST.mkdir(exist_ok=False)
records={}
for label,base in [('linux',OUT),('native',NATIVE)]:
    for path in sorted(base.rglob('*')):
        assert not path.is_symlink()
        if path.is_dir():continue
        assert stat.S_ISREG(path.lstat().st_mode)
        assert path.suffix in {'.py','.json','.log','.txt','.lock'},path
        raw=path.read_bytes();assert len(raw)<=8*1024*1024 and b'\0' not in raw
        target=DEST/'raw'/label/path.relative_to(base)
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as f:f.write(raw)
        assert target.read_bytes()==raw
        records[target.relative_to(DEST).as_posix()]={'type':'regular_plain','bytes':len(raw),'sha256':sha(raw)}
with (DEST/'summary.json').open('x') as f:json.dump(summary,f,indent=2)
records['summary.json']={'type':'regular_plain','bytes':(DEST/'summary.json').stat().st_size,'sha256':sha((DEST/'summary.json').read_bytes())}
with (DEST/'manifest.json').open('x') as f:json.dump({'source':summary['source'],'tree':summary['tree'],'files':records,'archive_created':False,'archive_member_reads':0},f,indent=2)
print(json.dumps({'files':len(records),'tests':tests,'manifest_sha256':sha((DEST/'manifest.json').read_bytes())},indent=2))
