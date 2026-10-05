"""Coordinator-only offline checks; adapted from the reviewed CR runner."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[4]
label, package, *args = sys.argv[1:]
if not re.fullmatch(r"[a-z0-9-]+", label) or package not in {
    "pioneer-agent", "qa-agent", "sanmou-common"
}:
    raise SystemExit("invalid check identity")
def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=root, text=True).strip()
source, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
packages_tree = git("rev-parse", "HEAD:packages")
if packages_tree != "94186df4485421eec6ddf116a4777d7a393cd789":
    raise SystemExit("packages differ from approved source")
subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", "packages", "apps", "scripts", ".agent", ".github"], cwd=root, check=True)
output = Path(__file__).parent
log = output / f"{label}.log"
env = {key: value for key, value in os.environ.items()
       if not any(part in key.upper() for part in ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "AUTH", "COOKIE"))}
env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
env["PYTHONPATH"] = os.pathsep.join(str(root / p) for p in [
    "packages/pioneer-agent/src", "packages/qa-agent/src", "packages/sanmou-common/src",
    "packages/pioneer-agent/tests", "packages/pioneer-agent/tests/unit", "packages/qa-agent/tests"
]) + os.pathsep + "/tmp/sanmou-cr-20261005-6155-deps"
command = [sys.executable, "-B", *args]
started = time.monotonic()
timed_out = False
with log.open("x", encoding="utf-8", newline="\n") as stream:
    try:
        result = subprocess.run(command, cwd=root / "packages" / package, env=env,
                                stdout=stream, stderr=subprocess.STDOUT, timeout=300)
        exit_code = result.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        exit_code = 124
        stream.write("\nCoordinator check exceeded 300 seconds.\n")
record = dict(source=source, tree=tree, packages_tree=packages_tree, command=command,
              cwd=str(root / "packages" / package), pythonpath=env["PYTHONPATH"],
              exit_code=exit_code, timed_out=timed_out, seconds=time.monotonic()-started,
              python=sys.version, dependencies={name: importlib.metadata.version(name)
                  for name in ("pydantic", "PyYAML", "mcp", "anyio")},
              log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
              runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
with (output / f"{label}.json").open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(record, stream, indent=2)
    stream.write("\n")
print(json.dumps(record))
print("\n".join(log.read_text(encoding="utf-8").splitlines()[-8:]))
raise SystemExit(exit_code)
