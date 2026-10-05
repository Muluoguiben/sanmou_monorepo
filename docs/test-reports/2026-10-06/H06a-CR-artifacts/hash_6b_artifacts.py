"""New final manifest; preserve the previous 96575c3 manifest verbatim."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
destination = root / "6b7b5ca-artifact-manifest.json"
items = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
         for path in sorted(root.rglob("*"))
         if path.is_file() and path != destination and "__pycache__" not in path.parts}
destination.write_text(json.dumps({
    "source": "6b7b5caad1cbffc59692d3fe9df6a3b3d88dfa9c",
    "source_tree": "bb2636242bad0e796ded0b43d6fc1a5142a839f9",
    "artifacts": items,
}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"artifacts": len(items), "manifest_sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}))
