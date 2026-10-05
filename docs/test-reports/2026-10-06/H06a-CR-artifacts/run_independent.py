"""Bounded runner, separate raw logs, argv/runtime identity; no source writes."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

source, output, *names = sys.argv[1:]
source, output = Path(source).resolve(), Path(output).resolve()
output.mkdir(parents=True, exist_ok=True)
cwd = source / "packages/pioneer-agent/tests"
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH="../src:../../sanmou-common/src:.")
failed = False
for name in names:
    argv = [sys.executable, "-B", str(Path(__file__).parent / (name + ".py"))]
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=90)
    data = result.stdout + result.stderr
    (output / (name + ".log")).write_bytes(data)
    record = {"probe": name, "argv": argv, "cwd": str(cwd), "python": sys.version,
              "platform": platform.platform(), "exit": result.returncode,
              "log_sha256": hashlib.sha256(data).hexdigest()}
    print(json.dumps(record), flush=True)
    print(data.decode(errors="replace")[-500:], flush=True)
    failed |= result.returncode != 0
raise SystemExit(int(failed))
