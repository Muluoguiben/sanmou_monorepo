"""Inventory archive members without extraction or following archived links."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile

archive, target = map(Path, sys.argv[1:])
rows = []
with tarfile.open(archive, 'r:gz') as handle:
    for member in handle.getmembers():
        row = {'name': member.name, 'mode': member.mode, 'size': member.size}
        if member.isfile():
            raw = handle.extractfile(member).read()
            row.update(type='regular', sha256=hashlib.sha256(raw).hexdigest())
        elif member.issym():
            row.update(type='symlink', linkname=member.linkname)
        elif member.isdir():
            row.update(type='directory')
        else:
            row.update(type='other', tar_type=repr(member.type), linkname=member.linkname)
        rows.append(row)
result = {'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
          'counts': {kind: sum(row['type'] == kind for row in rows) for kind in ('regular', 'symlink', 'directory', 'other')},
          'safety': 'Read regular tar members only; do not extract wholesale or follow absolute archived symlinks. Links are negative-test artifacts, not trusted input files.',
          'members': rows}
with target.open('x') as stream:
    json.dump(result, stream, indent=2)
print(json.dumps({'archive': result['archive'], 'counts': result['counts'], 'sha256': result['sha256']}))
