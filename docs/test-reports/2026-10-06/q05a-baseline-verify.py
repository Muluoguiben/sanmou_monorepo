"""Record published 3711 old v3/Q04/quality/warning baselines before new code."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BASE = "3711e92d38786418e8e955d19a56cd6c72611389"
root, out = (Path(value).resolve() for value in sys.argv[1:3])
out.mkdir(parents=True, exist_ok=False)
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *args])
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
assert git("rev-parse", "HEAD").decode().strip() == BASE
assert not git("diff", "--name-only", "HEAD", "--", "packages")
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = os.pathsep.join([str(root / "packages/qa-agent/src"),
    str(root / "packages/qa-agent/tests"), str(root / "packages/sanmou-common/src"),
    "/tmp/sanmou-cr-20261005-6155-deps"])
commands = []
def run(name, args):
    with (out / (name + ".log")).open("xb") as stream:
        result = subprocess.run([sys.executable, "-B", *args], cwd=root / "packages/qa-agent",
            env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
    raw = (out / (name + ".log")).read_bytes()
    counts = re.findall(rb"Ran (\d+) tests? in ", raw)
    skips = re.findall(rb"OK \(skipped=(\d+)\)", raw)
    commands.append({"name": name, "argv": [sys.executable, "-B", *args],
        "cwd": str(root / "packages/qa-agent"), "PYTHONPATH": env["PYTHONPATH"],
        "exit": result.returncode, "tests": int(counts[-1]) if counts else None,
        "skips": int(skips[-1]) if skips else 0, "log": name + ".log", "sha256": sha(raw), "bytes": len(raw)})
    print(json.dumps(commands[-1]), flush=True)
    (out / "progress.json").write_text(json.dumps(commands, indent=2) + "\n")
    assert result.returncode == 0

here = Path(__file__).parent
run("ranking-counterexample", [str(here / "q05a-independent-probes.py"), "--verify-baseline-controls"])
run("old-quality", ["-m", "unittest", "test_quality_eval", "-v"])
run("old-v3", ["-m", "qa_agent.quality_eval.runner", "--baseline", "v3", "--output", str(out / "v3.json")])
run("old-q04", ["-m", "qa_agent.quality_eval.claim_spans", "--baseline", "claim-spans-v1", "--output", str(out / "q04.json")])
run("original-resource-warning", [str(here / "q05a-resource-warning-probe.py"), "baseline"])
assert commands[1]["tests"] == 23 and commands[1]["skips"] == 0
v3, q04 = (out / "v3.json").read_bytes(), (out / "q04.json").read_bytes()
assert sha(v3) == "db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec"
assert sha(q04) == "c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120"
assert not git("diff", "--name-only", "HEAD", "--", "packages")
(out / "summary.json").write_text(json.dumps({"source": BASE,
    "tree": git("rev-parse", "HEAD^{tree}").decode().strip(), "commands": commands,
    "v3_sha256": sha(v3), "q04_sha256": sha(q04), "resource_warnings": 3,
    "native": "not_executed", "provider_calls": 0, "archive_reads": 0}, indent=2) + "\n")
