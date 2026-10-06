"""CI-only H10b wiring proof and bounded exact-source Linux regression."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

BASE = "a45949233dfc666b91fdbf756b8666d96d93fde3"
CODE = "e062adb7dd45d10bb579165a56f1c0d3ccf901d1"
TREE = "2892d9525642bc4e279c1b2f0835f0f7b5913fa1"
FLOW = ".github/workflows/regression.yml"
TEST = "packages/pioneer-agent/tests/test_causal_trace.py"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
ADDED = b"      - name: Windows H10b causal trace v2\n        working-directory: packages/pioneer-agent/tests\n        run: python -W error::RuntimeWarning -m unittest test_causal_trace -v\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    def git(*argv):
        return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *argv])
    def save(name, value):
        (out / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    assert git("rev-parse", "HEAD").decode().strip() == CODE
    assert git("rev-parse", "HEAD^{tree}").decode().strip() == TREE
    assert git("diff", "--name-only", "c8b096edc5fce6c87e83198b871ab5c576add1db", CODE).decode().splitlines() == [FLOW]
    assert git("rev-parse", BASE + ":packages") == git("rev-parse", CODE + ":packages")
    before, after = git("show", BASE + ":" + FLOW), (root / FLOW).read_bytes()
    assert after.count(ADDED) == 1 and after.replace(ADDED, b"", 1) == before
    sys.path.insert(0, DEPS)
    import yaml
    old, new = yaml.load(before, Loader=yaml.BaseLoader), yaml.load(after, Loader=yaml.BaseLoader)
    step = {"name": "Windows H10b causal trace v2", "working-directory": "packages/pioneer-agent/tests",
            "run": "python -W error::RuntimeWarning -m unittest test_causal_trace -v"}
    assert new["jobs"]["windows"]["steps"].count(step) == 1
    new["jobs"]["windows"]["steps"].remove(step)
    assert old == new
    test_bytes = (root / TEST).read_bytes()
    assert test_bytes == git("show", BASE + ":" + TEST)
    inventory = sorted("test_causal_trace." + node.name + "." + method.name
        for node in ast.parse(test_bytes).body if isinstance(node, ast.ClassDef)
        for method in node.body if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
        and method.name.startswith("test_"))
    assert len(inventory) == 32
    assert not git("diff", "--name-only", "HEAD", "--", "packages", FLOW)
    save("source.json", {"source": CODE, "tree": TREE, "baseline": BASE,
        "packages_tree": git("rev-parse", CODE + ":packages").decode().strip(),
        "workflow_remove_exact_step_equals_baseline_bytes": True, "workflow_structure_otherwise_identical": True,
        "test_module_bytes_unchanged": True, "expected_inventory": inventory,
        "workflow_sha256": hashlib.sha256(after).hexdigest(), "test_module_sha256": hashlib.sha256(test_bytes).hexdigest(),
        "native_status": "pending_exact_sha_hosted_windows", "archive_reads": 0})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join([str(root / p) for p in ("packages/pioneer-agent/src",
        "packages/pioneer-agent/tests", "packages/sanmou-common/src", "packages/qa-agent/src")] + [DEPS])
    failures, commands = [], []
    def run(name, argv, cwd):
        started = time.monotonic()
        with (out / (name + ".log")).open("xb") as handle:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
        raw = (out / (name + ".log")).read_bytes()
        tests = re.findall(rb"Ran (\d+) tests? in ", raw)
        skips = re.findall(rb"OK \(skipped=(\d+)\)", raw)
        item = {"name": name, "source": CODE, "tree": TREE, "argv": argv, "cwd": str(cwd),
            "PYTHONPATH": env["PYTHONPATH"], "exit": result.returncode, "seconds": time.monotonic() - started,
            "tests": int(tests[-1]) if tests else None, "skipped": int(skips[-1]) if skips else 0,
            "log": name + ".log", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        commands.append(item)
        if result.returncode: failures.append(name)
        if name == "causal-module":
            found = sorted(match.decode() for match in re.findall(rb"^test_\w+ \((test_causal_trace\.\w+\.test_\w+)\)", raw, re.M))
            assert found == inventory and item["tests"] == 32 and item["skipped"] == 0
            assert b"... skipped " not in raw and b"RuntimeWarning:" not in raw and b"was never awaited" not in raw
        print(json.dumps({"lane": name, "exit": result.returncode}), flush=True)
    run("causal-module", [sys.executable, "-W", "error::RuntimeWarning", "-m", "unittest", "test_causal_trace", "-v"], root / "packages/pioneer-agent/tests")
    run("h07-module", [sys.executable, "-B", "-m", "unittest", "test_task_approval", "-v"], root / "packages/pioneer-agent/tests")
    for package in ("pioneer-agent", "qa-agent", "sanmou-common"):
        run(package, [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], root / "packages" / package)
    run("h09-cli", [sys.executable, "-B", "-m", "pioneer_agent.app.task_eval", "--output", str(out / "h09-cli")], root)
    run("qa-v3", [sys.executable, "-B", "-m", "qa_agent.quality_eval.runner", "--baseline", "v3", "--output", str(out / "qa-v3.json")], root / "packages/qa-agent")
    assert not git("diff", "--name-only", "HEAD", "--", "packages", FLOW)
    assert git("rev-parse", "HEAD").decode().strip() == CODE
    h09 = json.loads((out / "h09-cli/report.json").read_text())
    save("summary.json", {"source": CODE, "tree": TREE, "failures": failures, "commands": commands,
        "source_record_sha256": hashlib.sha256((out / "source.json").read_bytes()).hexdigest(),
        "h09": {"path": str(out / "h09-cli/report.json"), "sha256": hashlib.sha256((out / "h09-cli/report.json").read_bytes()).hexdigest(),
                "source_verified": h09["source_verified"], "complete": h09["complete"], "gate_pass": h09["gate_pass"], "totals": h09["totals"]},
        "qa_v3": {"path": str(out / "qa-v3.json"), "sha256": hashlib.sha256((out / "qa-v3.json").read_bytes()).hexdigest()},
        "native_status": "pending_exact_sha_hosted_windows"})
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
