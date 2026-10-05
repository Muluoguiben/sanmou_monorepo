import hashlib, json, os, subprocess, sys
from pathlib import Path
ROOT=Path('/tmp/sanmou-h09a-integration-20261006')
OUT=Path('/tmp/h09a-integration-evidence-2d07-20261006-verify')
CODE='2d07e1b82de3d09ab809ad9018b70dc3095ff5bb'
relative='docs/test-reports/2026-10-06/h09a-cr05-selftest/metadata_cli_regression.py'
raw=(ROOT/relative).read_bytes()
assert raw==subprocess.check_output(['git','-C',str(ROOT),'show','4b1aef41d0265de6ed61062483aecdf41d70ea24:'+relative])
mapping={'103d0d1594a11af905515182913731d2d8bb4ac9':CODE,'/tmp/h09a-frozen-probes-0c40a7b/docs/test-reports/2026-10-06/h09a-independent-cr/editable_metadata_fece.py':str(ROOT/'docs/test-reports/2026-10-06/h09a-independent-cr/editable_metadata_fece.py')}
source=raw.decode()
for a,b in mapping.items():
    assert a in source
    source=source.replace(a,b)
with (OUT/'metadata-formal-mapping.json').open('x') as f: json.dump({'mapping':mapping,'original_sha256':hashlib.sha256(raw).hexdigest(),'rebound_sha256':hashlib.sha256(source.encode()).hexdigest(),'assertions_changed':False},f,indent=2)
sys.argv=[str(ROOT/relative),str(OUT/'metadata-worktree'),str(OUT/'metadata-formal')]
exec(compile(source,'author_formal_metadata_rebound.py','exec'),{'__name__':'__main__'})
