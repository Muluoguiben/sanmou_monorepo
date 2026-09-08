"""Record the loaded client module and exact runtime versions, without secrets."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

import pioneer_agent.agent_harness.stdio_client as client

path = Path(client.__file__).resolve()
source = path.read_bytes()
canonical = source.replace(b"\r\n", b"\n")
blob = b"blob " + str(len(canonical)).encode() + b"\0" + canonical
identity = {
    "module": str(path),
    "python": platform.python_version(),
    "executable": sys.executable,
    "PYTHONNOUSERSITE": os.environ.get("PYTHONNOUSERSITE"),
    "PYTHONDONTWRITEBYTECODE": os.environ.get("PYTHONDONTWRITEBYTECODE"),
    "raw_sha256": hashlib.sha256(source).hexdigest(),
    "canonical_lf_git_blob": hashlib.sha1(blob).hexdigest(),
    "versions": {
        name: importlib.metadata.version(name)
        for name in ("mcp", "anyio", "pydantic", "fastapi")
    },
}
print(json.dumps(identity, indent=2))
assert identity["canonical_lf_git_blob"] == "fe742211fb9a14614b977c0551c431d1cf3cf9db"
