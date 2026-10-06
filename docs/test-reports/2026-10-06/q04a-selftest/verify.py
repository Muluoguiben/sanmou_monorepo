"""Fixed-source Q04a offline matrix; preserve old results and all raw outcomes."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT, OUT, CODE = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3]
BASE = "9e35b34e2540923bd7b253f71b3d1f49da1093fb"
OLD_V3 = Path("/tmp/h10b-e062adb-results/qa-v3.json")
OLD_SHA = "480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
OUT.mkdir(parents=True, exist_ok=False)


def sha(raw): return hashlib.sha256(raw).hexdigest()
def git(*args): return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(ROOT), *args])
def save(name, value):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


assert git("rev-parse", "HEAD").decode().strip() == CODE
TREE = git("rev-parse", "HEAD^{tree}").decode().strip()
assert not git("diff", "--name-only", "HEAD")
changed = git("diff", "--name-only", BASE, CODE).decode().splitlines()
allowed = ["docs/qa-claim-spans-q04a-interface-2026-10-06.md",
    "packages/qa-agent/src/qa_agent/quality_eval/claim_spans.py",
    "packages/qa-agent/tests/fixtures/quality_eval/claim_spans_v1/cases.json",
    "packages/qa-agent/tests/fixtures/quality_eval/claim_spans_v1/freeze.json",
    "packages/qa-agent/tests/test_claim_spans.py"]
assert changed == allowed, changed
inputs = []
for row in git("ls-tree", "-rz", CODE, "--", "packages").split(b"\0"):
    if not row: continue
    meta, raw_name = row.split(b"\t")
    name = raw_name.decode()
    if Path(name).suffix not in {".py", ".json", ".yaml", ".yml"}: continue
    raw = (ROOT / name).read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert blob == meta.decode().split()[2], name
    inputs.append([name, blob, sha(raw)])
assert sha(OLD_V3.read_bytes()) == OLD_SHA
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = ":".join(str(ROOT / path) for path in (
    "packages/pioneer-agent/src", "packages/qa-agent/src", "packages/sanmou-common/src",
    "packages/pioneer-agent/tests")) + ":" + DEPS
summary = {"source": CODE, "tree": TREE, "baseline": BASE,
    "verifier_sha256": sha(Path(__file__).read_bytes()),
    "runtime": {"executable": sys.executable, "python": sys.version, "platform": platform.platform()},
    "scope": {"changed": changed, "git_byte_verified_inputs": len(inputs),
              "input_manifest_sha256": sha(json.dumps(inputs, separators=(",", ":")).encode())},
    "commands": [], "failures": [], "results": {},
    "native": "Q04a not run natively; H10b native results do not validate this new module; no dependency install/mock"}


def run(name, argv, cwd):
    path = OUT / (name + ".log")
    started = time.time()
    with path.open("xb") as handle:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
    raw = path.read_bytes()
    assert len(raw) <= 2 * 1024 * 1024
    text = raw.decode("utf-8", errors="replace")
    count = re.findall(r"^Ran (\d+) tests? in ([\d.]+)s", text, re.MULTILINE)
    skipped = re.findall(r"^OK \(skipped=(\d+)\)", text, re.MULTILINE)
    row = {"name": name, "argv": argv, "cwd": str(cwd), "PYTHONPATH": env["PYTHONPATH"],
        "exit": result.returncode, "tests": int(count[-1][0]) if count else None,
        "skipped": int(skipped[-1]) if skipped else 0, "seconds": time.time() - started,
        "log": path.name, "log_bytes": len(raw), "log_sha256": sha(raw)}
    summary["commands"].append(row)
    if result.returncode: summary["failures"].append(name)
    print(json.dumps({key: row[key] for key in ("name", "exit", "tests", "skipped", "seconds")}), flush=True)
    if name == "causal-module":
        summary["results"]["causal_warning_lines"] = [line for line in text.splitlines() if re.search(r"RuntimeWarning|was never awaited", line)]


PY = [sys.executable]
qa, pioneer = ROOT / "packages/qa-agent", ROOT / "packages/pioneer-agent"
for pattern, name in (("test_claim_spans.py", "claim-spans"), ("test_quality_eval.py", "old-quality-eval")):
    run(name, PY + ["-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"], qa)
run("causal-module", PY + ["-W", "error::RuntimeWarning", "-m", "unittest", "test_causal_trace", "-v"], pioneer / "tests")
run("h07a-module", PY + ["-m", "unittest", "test_task_approval", "-v"], pioneer / "tests")
for package in ("qa-agent", "pioneer-agent", "sanmou-common"):
    run(package + "-full", PY + ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], ROOT / "packages" / package)
run("claim-spans-cli", PY + ["-m", "qa_agent.quality_eval.claim_spans", "--baseline", "claim-spans-v1", "--output", str(OUT / "claim-spans.json")], qa)
run("h09-cli", PY + ["-m", "pioneer_agent.app.task_eval", "--output", str(OUT / "h09-cli")], ROOT)
run("qa-v3", PY + ["-m", "qa_agent.quality_eval.runner", "--baseline", "v3", "--output", str(OUT / "qa-v3.json")], qa)
# Preserve the command outcomes even if subsequent report assertions fail.
save("commands.json", summary)
h09_path = OUT / "h09-cli/report.json"
h09 = json.loads(h09_path.read_bytes())
assert h09["source"]["commit"] == CODE and h09["source"]["tree"] == TREE
assert h09["complete"] and h09["gate_pass"] and h09["totals"]["control_pass"] == 8
summary["results"]["h09"] = {"complete": True, "gate_pass": True, "totals": h09["totals"],
    "raw_path": str(h09_path), "raw_sha256": sha(h09_path.read_bytes())}
new_v3 = json.loads((OUT / "qa-v3.json").read_bytes())
old_v3 = json.loads(OLD_V3.read_bytes())
new_source, old_source = new_v3.pop("eval_source"), old_v3.pop("eval_source")
assert new_v3 == old_v3
new_file = "src/qa_agent/quality_eval/claim_spans.py"
assert set(new_source["files"]) - set(old_source["files"]) == {new_file}
assert {key: value for key, value in new_source["files"].items() if key != new_file} == old_source["files"]
assert new_source["algorithm"] == old_source["algorithm"]
for path, value in new_source["files"].items():
    assert sha((qa / path).read_bytes()) == value
assert sha(json.dumps(new_source["files"], sort_keys=True, ensure_ascii=False).encode()) == new_source["digest"]
summary["results"]["qa_v3"] = {"historical_sha256": OLD_SHA,
    "actual_sha256": sha((OUT / "qa-v3.json").read_bytes()), "all_other_fields_equal": True,
    "old_eval_source_digest": old_source["digest"], "new_eval_source": new_source}
claim_path = OUT / "claim-spans.json"
claim = json.loads(claim_path.read_bytes())
assert claim["gate_pass"] and claim["controls"]["numerator"] == claim["controls"]["denominator"] == 12
assert claim["eval_source"] == new_source
summary["results"]["claim_spans"] = {"controls": claim["controls"], "gate_pass": True,
    "provider": claim["provider"], "holdout": claim["holdout"], "fixture": claim["fixture"],
    "raw_path": str(claim_path), "raw_sha256": sha(claim_path.read_bytes())}
assert not git("diff", "--name-only", "HEAD")
assert git("rev-parse", "HEAD").decode().strip() == CODE
save("summary.json", summary)
raise SystemExit(bool(summary["failures"]))
