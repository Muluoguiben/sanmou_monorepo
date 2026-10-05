"""Run immutable reviewer probes unchanged; preserve each exit code and hash."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root, probes, output = map(Path, sys.argv[1:4])
source_sha = sys.argv[4] if len(sys.argv) > 4 else "dea73e062b70eb6d34108de87f843e40794d97df"
source_tree = sys.argv[5] if len(sys.argv) > 5 else "4a754c7c1a329357df6ea25842d8219ffa76d3a0"
output.mkdir(parents=True, exist_ok=True)
names = ("test_independent_lifecycle", "test_primary_conflict", "test_concurrent_close",
         "test_independent_store", "test_independent_crash", "test_independent_cli_race",
         "test_shared_external_owner", "test_owner_cleanup_primary", "test_teardown_matrix")
rows = []
for name in names:
    script = probes / f"{name}.py"
    env = dict(os.environ)
    env.update(PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH="../src:../../sanmou-common/src:.:/tmp/sanmou-cr-20261005-6155-deps")
    argv = [sys.executable, "-B", str(script)]
    cwd = root / "packages/pioneer-agent/tests"
    path = output / f"{name}.log"
    with path.open("wb") as handle:
        completed = subprocess.run(argv, cwd=cwd, env=env, stdout=handle,
                                   stderr=subprocess.STDOUT, timeout=60)
    rows.append({"name": name, "probe_sha256": hashlib.sha256(script.read_bytes()).hexdigest(),
        "argv": argv, "cwd": str(cwd), "env": {key: env[key] for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONPATH")},
        "exit_code": completed.returncode, "log_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    print(name, completed.returncode, flush=True)
(output / "probe-metadata.json").write_text(json.dumps({
    "source_sha": source_sha, "source_tree": source_tree, "runs": rows,
    "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "shared_owner_note": "Frozen b4ad6c probe accepts construct-time CheckpointConflict. Check its printed runner/call/charge counts; no probe edits are made.",
}, indent=2) + "\n", encoding="utf-8")
