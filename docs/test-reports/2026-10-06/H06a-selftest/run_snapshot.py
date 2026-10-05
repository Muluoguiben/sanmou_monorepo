"""Reproducible offline source-bound self-test driver; no credentials/providers."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys


root, manifest, output = map(Path, sys.argv[1:4])
dependency_path = sys.argv[4] if len(sys.argv) > 4 else ""
output.mkdir(parents=True, exist_ok=True)
source_sha = sys.argv[5] if len(sys.argv) > 5 else "44ad8aa82c7a8d7cd4ac48abcc8fb42af91046f7"
source_tree = sys.argv[6] if len(sys.argv) > 6 else "2a9952dd892ba91e43caa32825094792ca94d7c1"


def verify():
    count = 0
    mismatches = []
    for line in manifest.read_text(encoding="utf-8-sig").splitlines():
        info, name = line.split("\t", 1)
        mode, kind, expected = info.split()
        assert kind == "blob", (kind, name)
        path = root / name
        data = os.fsencode(os.readlink(path)) if mode == "120000" else path.read_bytes()
        actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if actual != expected:
            mismatches.append(name)
        count += 1
    assert not mismatches, mismatches
    return {"blobs_verified": count, "mismatches": mismatches}


metadata = {
    "source_sha": source_sha, "source_tree": source_tree,
    "root": str(root), "python": sys.version, "executable": sys.executable,
    "platform": platform.platform(), "os": os.name,
    "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "driver_argv": sys.argv,
    "dependencies": {name: importlib.metadata.version(name) for name in ("pydantic", "mcp", "anyio", "PyYAML")},
    "before": verify(), "runs": [],
}
jobs = [
    ("focused", "pioneer-agent", ["test_checkpoint_lock_native", "test_checkpoint_ownership",
        "test_task_runner", "test_task_cli", "test_task_cr_regressions"]),
    ("pioneer-full", "pioneer-agent", ["discover", "-s", "tests", "-p", "test_*.py"]),
    ("qa-full", "qa-agent", ["discover", "-s", "tests", "-p", "test_*.py"]),
    ("common-full", "sanmou-common", ["discover", "-s", "tests", "-p", "test_*.py"]),
]
for name, package, selection in jobs:
    cwd = root / "packages" / package
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH="src:../sanmou-common/src:tests")
    if dependency_path:
        env["PYTHONPATH"] += ":" + dependency_path
    argv = [sys.executable, "-B", "-m", "unittest", *selection, "-v"]
    with (output / f"{name}.log").open("wb") as handle:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=handle,
                                stderr=subprocess.STDOUT, timeout=300)
    metadata["runs"].append({"name": name, "cwd": str(cwd), "argv": argv,
        "env": {key: env[key] for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONPATH")},
        "exit_code": result.returncode,
        "log_sha256": hashlib.sha256((output / f"{name}.log").read_bytes()).hexdigest()})
    print(name, result.returncode, flush=True)
metadata["after"] = verify()
(output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata, indent=2), flush=True)
sys.exit(any(item["exit_code"] for item in metadata["runs"]))
