"""Fixed-source H10a verification; plain evidence only, no archive/provider access."""
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT, OUT, CODE, PROBES = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3], Path(sys.argv[4]).resolve()
BASE = "358df146ba184a771d3673428915a70fe8aa4c9c"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
OUT.mkdir(parents=True, exist_ok=False)


def sha(raw): return hashlib.sha256(raw).hexdigest()
def git(*args): return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(ROOT), *args])
def save(name, value):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


assert git("rev-parse", "HEAD").decode().strip() == CODE
TREE = git("rev-parse", "HEAD^{tree}").decode().strip()
assert not git("diff", "--name-only", "HEAD")
changed = git("diff", "--name-only", BASE, CODE).decode().splitlines()
prefix = "packages/pioneer-agent/src/pioneer_agent/agent_harness/"
allowed = {prefix + name for name in ("task_contracts.py", "task_runner.py", "run_trace.py", "task_policy.py", "task_trace.py")}
allowed |= {"packages/pioneer-agent/tests/test_causal_trace.py", "docs/harness-causal-trace-h10a-interface-memo-2026-10-06.md"}
assert set(changed) == allowed, changed
contracts = prefix + "task_contracts.py"
def classes(raw):
    return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(raw).body if isinstance(node, ast.ClassDef)}
before, after = classes(git("show", BASE + ":" + contracts)), classes((ROOT / contracts).read_bytes())
assert all(after[name] == value for name, value in before.items())
input_rows = []
for row in git("ls-tree", "-rz", CODE, "--", "packages").split(b"\0"):
    if not row: continue
    meta, raw_name = row.split(b"\t")
    name = raw_name.decode()
    if Path(name).suffix not in {".py", ".json", ".yaml", ".yml"}: continue
    raw = (ROOT / name).read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert blob == meta.decode().split()[2], name
    input_rows.append([name, blob, sha(raw)])
pinned = {"h10a-independent-probes.py": "2e4bb05676a9bbc30a0136c9d96e243d86034e500ba9ef52e9a5fc27ba69b418",
          "h10a-default-v1-oracle.json": "327ec7ae64a409b234505d8920056db2fa1f951405560cda43b0e3a491825ed6",
          "h10a-independent-targeted.py": "4e2378966f30c818fdcce7a3d59f9a298ed6cbcf8c43bfa9f01db0a006d05063",
          "h10a-independent-trace-context.py": "edc8ff01b960aef71c09493287b8e2a41f69f5054312ae3e26a77f43f911fd8f",
          "h10a-independent-trace-context-short.py": "71cdf2cae37ef8c6fade5c3bc0cf84625a636cbd315fcddc8b33248bddb01234"}
for name, digest in pinned.items(): assert sha((PROBES / name).read_bytes()) == digest
paths = [ROOT / p for p in ("packages/pioneer-agent/src", "packages/qa-agent/src", "packages/sanmou-common/src", "packages/pioneer-agent/tests")]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = ":".join(map(str, paths)) + ":" + DEPS
summary = {"source": CODE, "tree": TREE, "baseline": BASE, "verifier_sha256": sha(Path(__file__).read_bytes()),
    "runtime": {"python": sys.version, "executable": sys.executable, "platform": platform.platform()},
    "scope": {"changed": changed, "old_contract_class_asts_unchanged": sorted(before),
        "old_tests_fixtures_ci_cli_budget_mcp_unchanged": True, "git_byte_verified_inputs": len(input_rows),
        "input_manifest_sha256": sha(json.dumps(input_rows, separators=(",", ":")).encode())},
    "independent_inputs": pinned, "commands": [], "failures": [], "results": {},
    "native": "new H10a module not executed natively; existing H07 Windows35 is not H10 native evidence"}


def run(name, argv, cwd):
    start = time.time()
    path = OUT / (name + ".log")
    with path.open("xb") as handle:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
    raw = path.read_bytes()
    assert len(raw) <= 2 * 1024 * 1024
    output = raw.decode("utf-8", errors="replace")
    count = re.findall(r"^Ran (\d+) tests? in ([\d.]+)s", output, re.MULTILINE)
    skips = re.findall(r"^OK \(skipped=(\d+)\)", output, re.MULTILINE)
    item = {"name": name, "argv": argv, "cwd": str(cwd), "PYTHONPATH": env["PYTHONPATH"], "exit": result.returncode,
        "tests": int(count[-1][0]) if count else None, "skipped": int(skips[-1]) if skips else 0,
        "seconds": time.time() - start, "log": path.name, "log_bytes": len(raw), "log_sha256": sha(raw)}
    summary["commands"].append(item)
    if result.returncode: summary["failures"].append(name)
    print(json.dumps({k: item[k] for k in ("name", "exit", "tests", "skipped", "seconds")}), flush=True)


PY = [sys.executable, "-B"]
pioneer = ROOT / "packages/pioneer-agent"
run("causal-module", PY + ["-m", "unittest", "test_causal_trace", "-v"], pioneer / "tests")
run("independent-probes", PY + [str(PROBES / "h10a-independent-probes.py")], pioneer / "tests")
run("independent-targeted", PY + [str(PROBES / "h10a-independent-targeted.py")], pioneer / "tests")
run("independent-context-short", PY + [str(PROBES / "h10a-independent-trace-context-short.py")], pioneer / "tests")
run("focused", PY + ["-m", "unittest", "test_causal_trace", "test_harness_b", "test_task_contracts", "test_task_runner",
    "test_task_cli", "test_task_approval", "test_checkpoint_ownership", "test_task_cr_regressions", "-v"], pioneer / "tests")
run("h07a-module", PY + ["-m", "unittest", "test_task_approval", "-v"], pioneer / "tests")
for package in ("pioneer-agent", "qa-agent", "sanmou-common"):
    run(package + "-full", PY + ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], ROOT / "packages" / package)
run("h09-cli", PY + ["-m", "pioneer_agent.app.task_eval", "--output", str(OUT / "h09-cli")], ROOT)
run("qa-v3", PY + ["-m", "qa_agent.quality_eval.runner", "--baseline", "v3", "--output", str(OUT / "qa-v3.json")], ROOT / "packages/qa-agent")
raw = (OUT / "h09-cli/report.json").read_bytes()
h09 = json.loads(raw)
assert h09["source"]["commit"] == CODE and h09["source"]["tree"] == TREE
assert h09["complete"] and h09["gate_pass"] and h09["totals"]["control_pass"] == 8
summary["results"]["h09"] = {"complete": True, "gate_pass": True, "totals": h09["totals"],
    "raw_path": str(OUT / "h09-cli/report.json"), "raw_bytes": len(raw), "raw_sha256": sha(raw)}
digest = sha((OUT / "qa-v3.json").read_bytes())
assert digest == "480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8"
summary["results"]["qa_v3"] = {"sha256": digest, "raw_path": str(OUT / "qa-v3.json")}
sys.path[:0] = list(map(str, paths)) + [DEPS]
from test_causal_trace import runner, Fanout, FakeDecisionPolicy, PolicyDecision, InMemoryRunTrace, JsonlRunTrace
memory = InMemoryRunTrace()
sample = OUT / "sample-v2.jsonl"
r = runner(trace=Fanout(memory, JsonlRunTrace(sample)), policy=FakeDecisionPolicy([
    PolicyDecision(action="continue", reason="observe") for _ in range(3)]))
result = asyncio.run(r.run())
assert result.status == "succeeded"
assert [e.model_dump(mode="json") for e in memory.events] == [json.loads(line) for line in sample.read_text().splitlines()]
summary["results"]["sample_v2"] = {"file": sample.name, "bytes": sample.stat().st_size, "sha256": sha(sample.read_bytes()),
    "events": len(memory.events), "ledger_counts": r.budget.summary()["counts"], "status": result.status,
    "execution_authority": result.execution_authority, "executable": result.executable}
assert not git("diff", "--name-only", "HEAD")
assert git("rev-parse", "HEAD").decode().strip() == CODE
save("summary.json", summary)
raise SystemExit(bool(summary["failures"]))
