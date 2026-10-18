"""Bounded plain evidence for an explicitly selected offline Python command."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
tag, *args = sys.argv[1:]
assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", tag)
out = Path(__file__).with_name("h08b-independent-results")
out.mkdir(exist_ok=True)
log, record = out / (tag + ".log"), out / (tag + ".json")
assert not log.exists() and not record.exists(), "never overwrite original evidence"
environment = dict(os.environ)
environment["PYTHONDONTWRITEBYTECODE"] = "1"
environment.pop("SANMOU_CAPTURE_TOKEN", None)
command = [sys.executable, "-B", "-W", "error::RuntimeWarning", *args]
gitdir = (ROOT / ".git").read_text(encoding="utf-8").strip().removeprefix("gitdir: ")
if gitdir.lower().startswith("//wsl$/ubuntu/"):
    gitdir = "/" + gitdir[len("//wsl$/ubuntu/"):]
git = lambda *parts: subprocess.check_output(
    ["git", "--git-dir=" + gitdir, "--work-tree=" + str(ROOT), *parts]).decode().strip()
source, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
product_status = git("status", "--short", "--", "packages", ".github")
assert not product_status, "require fixed clean product/CI source before execution"
with log.open("xb") as stream:
    result = subprocess.run(command, cwd=ROOT, env=environment,
        stdout=stream, stderr=subprocess.STDOUT, timeout=300)
raw = log.read_bytes()
assert len(raw) <= 1_000_000, "evidence exceeds bounded plain log limit"
counts = re.findall(rb"Ran (\d+) tests? in", raw)
metadata = dict(source=source, tree=tree,
    product_status=product_status,
    command=command, cwd=str(ROOT), python=sys.version,
    environment={key: environment.get(key) for key in
        ("PYTHONPATH", "TMPDIR", "LC_ALL", "LANG", "PYTHONUTF8", "PYTHONDONTWRITEBYTECODE")},
    exit=result.returncode, tests=int(counts[-1]) if counts else None,
    bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), log=log.name)
with record.open("x", encoding="utf-8") as stream:
    json.dump(metadata, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps(metadata, ensure_ascii=True), flush=True)
print(raw.decode("utf-8", errors="replace")[-5000:], flush=True)
sys.exit(result.returncode)
