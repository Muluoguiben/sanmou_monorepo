"""Compact exact-source independent H10a regression; no archive/provider/native probe."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = "ae03faf0862f9930c58f7811d625de4b632f05ba"
CODE = "2128fb88329b1a38b410ad63e09c37034d08e8c7"
TREE = "3fe1e07f9d2e30b856d95177298fb80692bf396c"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
HARNESS = "packages/pioneer-agent/src/pioneer_agent/agent_harness/"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("probes", type=Path)
    args = parser.parse_args()
    root, out, probes = args.root.resolve(), args.output.resolve(), args.probes.resolve()
    out.mkdir(parents=True, exist_ok=False)
    def git(*argv):
        return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *argv])
    def save(name, value):
        (out / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    assert git("rev-parse", "HEAD").decode().strip() == CODE
    assert git("rev-parse", "HEAD^{tree}").decode().strip() == TREE
    assert not git("diff", "--name-only", "HEAD", "--", "packages", ".github", "scripts")
    changed = git("diff", "--name-only", BASE, CODE, "--", "packages", ".github", "scripts").decode().splitlines()
    expected = {HARNESS + name + ".py" for name in ("task_contracts", "task_runner", "task_policy", "task_trace", "run_trace")}
    expected.add("packages/pioneer-agent/tests/test_causal_trace.py")
    assert set(changed) == expected
    def nodes(raw):
        return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(raw).body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
    before = nodes(git("show", BASE + ":" + HARNESS + "task_contracts.py"))
    after = nodes((root / (HARNESS + "task_contracts.py")).read_bytes())
    assert all(after.get(name) == value for name, value in before.items())
    old_trace = nodes(git("show", BASE + ":" + HARNESS + "run_trace.py"))
    new_trace = nodes((root / (HARNESS + "run_trace.py")).read_bytes())
    assert old_trace["_safe_event"] == new_trace["_safe_event"]
    probe_names = ["h10a-independent-probes.py", "h10a-independent-targeted.py",
        "h10a-independent-trace-context.py", "h10a-independent-trace-context-short.py",
        "h10a-independent-ambient-primary.py", "h10a-independent-dispatch-deadline.py",
        "h10a-independent-policy-binding.py", "h10a-independent-policy-binding-budget-cut.py"]
    save("source.json", {"source": CODE, "tree": TREE, "baseline": BASE, "changed": changed,
        "old_contract_definitions_ast_unchanged": sorted(before), "default_safe_event_ast_unchanged": True,
        "old_tests_checkpoints_budget_qa_common_ci_unchanged": True,
        "source_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in changed},
        "probe_sha256": {name: hashlib.sha256((probes / name).read_bytes()).hexdigest() for name in probe_names + ["h10a-default-v1-oracle.json"]},
        "native_h10": "not_executed", "archive_reads": 0})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join([str(root / p) for p in ("packages/pioneer-agent/src",
        "packages/pioneer-agent/tests", "packages/sanmou-common/src", "packages/qa-agent/src")] + [DEPS])
    failures = []
    def run(name, argv, cwd):
        started = time.monotonic()
        with (out / (name + ".log")).open("xb") as handle:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
        save(name + ".command.json", {"source": CODE, "tree": TREE, "argv": argv, "cwd": str(cwd),
            "PYTHONPATH": env["PYTHONPATH"], "exit": result.returncode, "seconds": time.monotonic() - started})
        print(json.dumps({"lane": name, "exit": result.returncode}), flush=True)
        if result.returncode: failures.append(name)
    for name in probe_names:
        run(name.removesuffix(".py"), [sys.executable, "-B", str(probes / name)], root)
    run("causal-module", [sys.executable, "-B", "-m", "unittest", "test_causal_trace", "-v"], root / "packages/pioneer-agent/tests")
    run("h07-module", [sys.executable, "-B", "-m", "unittest", "test_task_approval", "-v"], root / "packages/pioneer-agent/tests")
    run("focused", [sys.executable, "-B", "-m", "unittest", "test_causal_trace", "test_harness_b",
        "test_task_approval", "test_task_runner", "test_task_contracts", "test_task_cli", "test_checkpoint_ownership",
        "test_task_cr_regressions", "-v"], root / "packages/pioneer-agent/tests")
    for package in ("pioneer-agent", "qa-agent", "sanmou-common"):
        run(package, [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], root / "packages" / package)
    run("h09-cli", [sys.executable, "-B", "-m", "pioneer_agent.app.task_eval", "--output", str(out / "h09-cli")], root)
    run("qa-v3", [sys.executable, "-B", "-m", "qa_agent.quality_eval.runner", "--baseline", "v3", "--output", str(out / "qa-v3.json")], root / "packages/qa-agent")
    assert git("rev-parse", "HEAD").decode().strip() == CODE
    assert not git("diff", "--name-only", "HEAD", "--", "packages", ".github", "scripts")
    files = {}
    for path in sorted(out.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            assert len(raw) < 8 * 1024 * 1024
            files[str(path.relative_to(out))] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    save("manifest.json", {"source": CODE, "tree": TREE, "failures": failures, "files": files,
                           "native_h10": "not_executed"})
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
