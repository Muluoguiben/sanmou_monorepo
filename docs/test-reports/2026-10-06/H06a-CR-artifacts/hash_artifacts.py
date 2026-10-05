"""Hash frozen evidence; output is generated metadata, never source mutation."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
destination = root / "96575c3-artifact-manifest.json"
items = {}
for path in sorted(root.rglob("*")):
    if path.is_file() and path != destination and "__pycache__" not in path.parts:
        items[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
destination.write_text(json.dumps({
    "source": "96575c30dea99ab58265052987e79bb4e76c0972",
    "source_tree": "8c305fe09cda5cc9e10e306a05f970f644e735f5",
    "artifacts": items,
}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"artifacts": len(items), "manifest_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}))
