"""Compare all evidence hashes with disk and staged Git bytes in one batch."""
import hashlib
import json
from pathlib import Path
import subprocess

base = Path(__file__).resolve().parent
prefix = "docs/test-reports/2026-10-06/H06a-CR04-selftest/"
manifest = json.loads((base / "artifact-hashes.json").read_text(encoding="utf-8-sig"))
requests = "".join(":" + prefix + item["path"] + "\n" for item in manifest["files"])
data = subprocess.check_output(["git", "cat-file", "--batch"], input=requests.encode(), timeout=30)
position = 0
for item in manifest["files"]:
    end = data.index(b"\n", position)
    identity, kind, size = data[position:end].split()
    assert kind == b"blob", (item["path"], kind)
    position = end + 1
    staged = data[position:position + int(size)]
    position += int(size) + 1
    local = (base / item["path"]).read_bytes()
    assert local == staged, item["path"]
    assert hashlib.sha256(local).hexdigest() == item["sha256"], item["path"]
print(json.dumps({"source_sha": manifest["source_sha"], "files_verified": len(manifest["files"]),
                  "local_and_staged_bytes_match": True}))
