"""Verify recorded evidence hashes against files and staged Git blob bytes."""
import hashlib
import json
from pathlib import Path
import subprocess

base = Path(__file__).resolve().parent
prefix = "docs/test-reports/2026-10-06/H06a-selftest/"
manifest = json.loads((base / "artifact-hashes.json").read_text(encoding="utf-8-sig"))
for entry in manifest["files"]:
    local = (base / entry["path"]).read_bytes()
    staged = subprocess.check_output(["git", "cat-file", "blob", ":" + prefix + entry["path"]])
    assert hashlib.sha256(local).hexdigest() == entry["sha256"], entry["path"]
    assert staged == local, entry["path"]
print(json.dumps({"source_sha": manifest["source_sha"], "files_verified": len(manifest["files"]),
                  "local_and_staged_bytes_match": True}))
