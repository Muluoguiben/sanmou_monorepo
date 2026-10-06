"""H08a exact combination replay; frozen probes and assertions unchanged."""
import hashlib,json,platform,re,subprocess,sys
from pathlib import Path
ROOT=Path('/tmp/sanmou-h07a-integration-20261006')
OUT=Path('/tmp/h08a-integration-1dbd7dd-20261006')
CODE='1dbd7dd6ac9b9237cb682b924a278c8bf5a99278'
TREE='89229486f461b4889ff875133e72ada8d213e7c9'
BASE='60e3e002c7b38571e76d344dd100b47d053244e2'
HERE=ROOT/'docs/test-reports/2026-10-06'
def git(*a):return subprocess.check_output(['git','-c','core.autocrlf=false','-C',str(ROOT),*a])
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,v):
    with (OUT/n).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2)
pins={'h08a-independent-verify.py':'55dbe79','h08a-independent-probes.py':'3ce5a9d9d8ad6cd1cf8f5710aa844516a12e4cca','h08a-catalog-probes.py':'749ea5fb6649c5b35ef289911d6d00b9e6fd22e3'}
hashes={}
for n,ref in pins.items():
    b=(HERE/n).read_bytes();assert b==git('show',ref+':docs/test-reports/2026-10-06/'+n);hashes[n]=sha(b)
helper=HERE/'h08a-independent-verify.py';raw=helper.read_text()
assert raw.count('8e0a2a0b370a98824669e5d34bd12576c7822bb5')==1 and raw.count('55eb8c863db183e7dbd2fa9cfb6d845876162315')==1
adapted=raw.replace('8e0a2a0b370a98824669e5d34bd12576c7822bb5',CODE).replace('55eb8c863db183e7dbd2fa9cfb6d845876162315',TREE)
if sys.argv[1]=='matrix':
    sys.argv=[str(helper),str(ROOT),str(OUT/'run')]
    exec(compile(adapted,str(helper)+' (source identity only)','exec'),{'__name__':'__main__','__file__':str(helper)})
    raise SystemExit
assert sys.argv[1]=='main'
def entries(ref):return {r.split(b'\t')[1].decode():r.split(b'\t')[0].decode() for r in git('ls-tree','-rz',ref).split(b'\0') if r}
current=entries(CODE);baseline=entries(BASE)
assert git('rev-parse','HEAD').decode().strip()==CODE and git('rev-parse','HEAD^{tree}').decode().strip()==TREE and not git('status','--porcelain')
assert git('rev-parse','HEAD:packages').decode().strip()=='f45c60e02a9fb0dab036b17127872e780aeff637'
assert git('rev-parse','HEAD:.github').decode().strip()=='55f6c18af999e3e62103b1d5f0fd084c0b68fe6a'
excluded={'.github/workflows/regression.yml','.codex-autonomy/review-iteration-20261005/state.json','.codex-autonomy/review-iteration-20261005/WORKLOG.md','todo-list.md'}
protected={n:m for n,m in baseline.items() if n not in excluded};assert all(current.get(n)==m for n,m in protected.items())
def inputs():
    rows=[]
    for n,m in sorted(current.items()):
        if not n.startswith('packages/') or Path(n).suffix not in ('.py','.json','.yaml','.yml'):continue
        assert m.startswith(('100644 blob ','100755 blob '))
        b=(ROOT/n).read_bytes();oid=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();assert oid==m.split()[2]
        rows.append([n,oid,sha(b),len(b)])
    assert len(rows)==906
    return sha(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode())
before=inputs()
save('source-proof.json',{'source':CODE,'tree':TREE,'baseline':BASE,'helper_pins':pins,'helper_hashes':hashes,'adaptation':'only CODE/TREE identities; no assertion changes','adapted_sha256':sha(adapted.encode()),'ordinary_inputs':906,'before_digest':before,'protected_metadata_paths':len(protected),'old_report_paths':sum(n.startswith('docs/test-reports/') for n in protected),'archive_reads':0,'runtime':{'python':sys.version,'executable':sys.executable,'platform':platform.platform()}})
with (OUT/'driver.log').open('xb') as f:p=subprocess.run([sys.executable,'-B',str(Path(__file__)),'matrix'],stdout=f,stderr=subprocess.STDOUT,timeout=1800)
assert p.returncode==0,'original failure retained'
s=json.loads((OUT/'run/summary.json').read_bytes())
expected={'public-runtime-probes':(9,0),'catalog-probes':(2,0),'new-module':(23,0),'new-module-text-locale':(23,0),'h07':(35,0),'h10':(32,0),'q04':(25,0),'q05':(44,0),'pioneer-agent':(1108,2),'qa-agent':(440,0),'sanmou-common':(2,0)}
for c in s['commands']:
    assert c['exit']==c['expected_exit']
    if c['name'] in expected:assert (c['tests'],c['skips'])==expected[c['name']]
    if c['name'] in ('qa-v1','qa-v2','qa-v3'):assert not (OUT/'run'/(c['name'][3:]+'.json')).exists()
for name in ('new-module','new-module-text-locale','h10'):assert not re.search('RuntimeWarning:|was never awaited',(OUT/'run'/(name+'.log')).read_text())
locale=s['text_locale'];assert locale['locale']=='C' and locale['default_file_encoding']=='ANSI_X3.4-1968' and locale['filesystem_encoding']=='utf-8' and locale['utf8_mode']==0
hraw=(OUT/'run/h09/report.json').read_bytes();h=json.loads(hraw)
assert h['source']['commit']==CODE and h['source']['tree']==TREE and all(h[k] is True for k in ('complete','valid_suite','source_verified','gate_pass'))
assert h['totals']==dict(control_pass=8,goal_success=2,expected_safety_stop=6,infra_error=0,unexpected_goal_success=0,safety_violations=0)
for n,d in h['artifacts'].items():assert sha((OUT/'run/h09'/n).read_bytes())==d
after=inputs();assert before==after and not git('status','--porcelain')
save('completion.json',{'source':CODE,'tree':TREE,'all_expected_results':True,'ordinary_inputs':906,'before_after_digest':after,'h09_artifacts_verified':len(h['artifacts']),'h09_bytes':len(hraw),'h09_sha256':sha(hraw),'native':'not_executed; final Hosted23+25+44/all4 pending','archive_reads':0})
print(json.dumps({'all_green':True,'source':CODE,'ordinary_inputs':906}),flush=True)
