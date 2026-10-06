"""Pre-Q05a published source observations, without changing historical evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path("/tmp/q05a-3711-baseline")
OUT = Path("/tmp/q05a-3711-baseline-results")
SHA = "3711e92d38786418e8e955d19a56cd6c72611389"
OUT.mkdir(exist_ok=False)
def git(*args): return subprocess.check_output(["git", "-C", str(ROOT), *args]).decode().strip()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
assert git("rev-parse", "HEAD") == SHA
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT / "packages/qa-agent/src") + ":/tmp/sanmou-cr-20261005-6155-deps")
env.pop("SANMOU_CAPTURE_TOKEN", None)
rows = []
commands = [
    ("old-quality", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_quality_eval.py", "-v"], ROOT / "packages/qa-agent"),
    ("old-v3", ["-m", "qa_agent.quality_eval.runner", "--baseline", "v3", "--output", str(OUT / "v3.json")], ROOT / "packages/qa-agent"),
    ("old-q04", ["-m", "qa_agent.quality_eval.claim_spans", "--baseline", "claim-spans-v1", "--output", str(OUT / "q04.json")], ROOT / "packages/qa-agent"),
    ("resource-warning", ["-W", "always::ResourceWarning", "-m", "unittest", "test_lineup_frame_extractor.CropIntoColumnsTests.test_splits_and_upscales", "-v"], ROOT / "packages/qa-agent/tests"),
]
for name, args, cwd in commands:
    path = OUT / (name + ".log")
    argv = [sys.executable, "-B", *args]
    with path.open("xb") as log:
        process = subprocess.run(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    rows.append(dict(name=name, argv=argv, cwd=str(cwd), exit=process.returncode, log=path.name, log_sha256=sha(path)))
    print(json.dumps(rows[-1]), flush=True)
assert sha(OUT / "v3.json") == "db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec"
with (OUT / "summary.json").open("x") as stream:
    json.dump(dict(source=SHA, tree=git("rev-parse", "HEAD^{tree}"), commands=rows,
        v3_sha256=sha(OUT / "v3.json"), q04_sha256=sha(OUT / "q04.json")), stream, indent=2)
assert all(row["exit"] == 0 for row in rows)
