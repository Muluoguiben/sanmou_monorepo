"""Published 60e3 QA hashes and existing-runtime controls; no registry import."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SOURCE = "60e3e002c7b38571e76d344dd100b47d053244e2"
root, out = (Path(p).resolve() for p in sys.argv[1:3])
out.mkdir(parents=True, exist_ok=False)
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *args])
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
assert git("rev-parse", "HEAD").decode().strip() == SOURCE
assert not git("diff", "--name-only", "HEAD", "--", "packages", ".github")
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = os.pathsep.join([str(root / p) for p in ("packages/pioneer-agent/src",
    "packages/pioneer-agent/tests", "packages/qa-agent/src", "packages/sanmou-common/src")] + ["/tmp/sanmou-cr-20261005-6155-deps"])
commands = []
def run(name, args, expected=0):
    argv = [sys.executable, "-B", *args]
    with (out / (name + ".log")).open("xb") as stream:
        result = subprocess.run(argv, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
    raw = (out / (name + ".log")).read_bytes()
    counts = re.findall(rb"Ran (\d+) tests? in ", raw)
    commands.append({"name": name, "argv": argv, "cwd": str(root), "PYTHONPATH": env["PYTHONPATH"],
        "exit": result.returncode, "expected_exit": expected, "tests": int(counts[-1]) if counts else None,
        "log": name + ".log", "bytes": len(raw), "sha256": sha(raw)})
    (out / "progress.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(commands[-1]), flush=True)
    assert result.returncode == expected
    return raw
run("runtime-controls", [str(Path(__file__).with_name("h08a-independent-probes.py")), "--verify-baseline-runtime"])
for version in ("v1", "v2", "v3", "v4"):
    raw = run("qa-" + version, ["-m", "qa_agent.quality_eval.runner", "--baseline", version,
        "--output", str(out / (version + ".json"))], 0 if version == "v4" else 1)
    if version != "v4":
        assert b"frozen KB/production source drift" in raw
run("q04-cli", ["-m", "qa_agent.quality_eval.claim_spans", "--baseline", "claim-spans-v1", "--output", str(out / "q04.json")])
assert sha((out / "v4.json").read_bytes()) == "c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c"
assert sha((out / "q04.json").read_bytes()) == "b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6"
(out / "summary.json").write_text(json.dumps({"source": SOURCE, "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
    "commands": commands, "v4_sha256": sha((out / "v4.json").read_bytes()), "q04_sha256": sha((out / "q04.json").read_bytes()),
    "registry_interface_not_imported": True, "provider_calls": 0, "archive_reads": 0}, indent=2) + "\n", encoding="utf-8")
