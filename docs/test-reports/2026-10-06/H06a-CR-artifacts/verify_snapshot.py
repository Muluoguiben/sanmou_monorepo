"""Compare every immutable Git blob with the extracted snapshot; no source writes."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

git_root, snapshot, sha = sys.argv[1:]
git = ["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "-C", git_root]
entries = subprocess.check_output(git + ["ls-tree", "-rz", sha]).split(b"\0")
checked = 0
digest = hashlib.sha256()
process = subprocess.Popen(git + ["cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
for entry in entries:
    if not entry:
        continue
    metadata, name = entry.split(b"\t", 1)
    mode, kind, blob = metadata.split()
    assert kind == b"blob", entry
    process.stdin.write(blob + b"\n")
    process.stdin.flush()
    header = process.stdout.readline().split()
    assert header[:2] == [blob, b"blob"], header
    expected = process.stdout.read(int(header[2]))
    assert process.stdout.read(1) == b"\n"
    actual = (Path(snapshot) / name.decode()).read_bytes()
    assert actual == expected, name
    digest.update(name + b"\0" + hashlib.sha256(actual).digest())
    checked += 1
process.stdin.close()
assert process.wait(timeout=10) == 0
print(json.dumps({"source": sha, "files_verified": checked, "manifest_sha256": digest.hexdigest()}))
