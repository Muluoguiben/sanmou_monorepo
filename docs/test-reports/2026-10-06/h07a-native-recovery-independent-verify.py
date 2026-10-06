"""Bounded source-bound Linux reviewer checks for the two-file recovery slice."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = "ca04ae1ef396576c5983f887502bf20b7d6f0015"
CODE = "b785458e9b322707e38f0b424ab78a9512abd8d1"
TREE = "726d99e49ab3fe0822b0bc306870f7d98d319cb0"
TEST = "packages/pioneer-agent/tests/test_task_approval.py"
FLOW = ".github/workflows/regression.yml"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("probe", type=Path)
    args = parser.parse_args()
    root, out, probe = args.root.resolve(), args.output.resolve(), args.probe.resolve()
    out.mkdir(parents=True, exist_ok=False)
    def git(*argv):
        return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *argv])
    def save(name, value):
        (out / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    assert git("rev-parse", "HEAD").decode().strip() == CODE
    assert git("rev-parse", "HEAD^{tree}").decode().strip() == TREE
    assert not git("diff", "--name-only", "HEAD")
    assert set(git("diff", "--name-only", "ecf50e0012c336c131f75b9bc6c102530a0d1876", CODE).decode().splitlines()) == {TEST, FLOW}
    def definitions(raw):
        result = {}
        for node in ast.parse(raw).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                result[node.name] = ast.dump(node, include_attributes=False)
            elif isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        result[node.name + "." + member.name] = ast.dump(member, include_attributes=False)
        return result
    old = definitions(git("show", BASE + ":" + TEST))
    new = definitions((root / TEST).read_bytes())
    assert all(new.get(name) == value for name, value in old.items())
    old_tests = [name for name in old if ".test_" in name]
    new_tests = [name for name in new if ".test_" in name]
    assert len(old_tests) == 30 and len(new_tests) == 35
    sys.path.insert(0, DEPS)
    import yaml
    before = yaml.load(git("show", BASE + ":" + FLOW), Loader=yaml.BaseLoader)
    after = yaml.load((root / FLOW).read_bytes(), Loader=yaml.BaseLoader)
    steps = after["jobs"]["windows"]["steps"]
    added = [step for step in steps if step.get("name") == "Windows H07a synthetic approval lifecycle"]
    assert added == [{"name": "Windows H07a synthetic approval lifecycle",
        "working-directory": "packages/pioneer-agent/tests", "run": "python -m unittest test_task_approval -v"}]
    steps.remove(added[0])
    assert before == after
    save("source.json", {"source": CODE, "tree": TREE, "baseline": BASE,
        "old_test_methods_unchanged": len(old_tests), "total_test_methods": len(new_tests),
        "added_tests": sorted(set(new_tests) - set(old_tests)), "old_workflow_unchanged": True,
        "production_code_changed": False, "native_status": "pending_hosted_windows_ci",
        "files_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in (TEST, FLOW)},
        "probe_sha256": hashlib.sha256(probe.read_bytes()).hexdigest(), "archive_reads": 0})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join([str(root / p) for p in (
        "packages/pioneer-agent/src", "packages/pioneer-agent/tests", "packages/sanmou-common/src", "packages/qa-agent/src")] + [DEPS])
    failures = []
    def run(name, argv, cwd):
        started = time.monotonic()
        with (out / (name + ".log")).open("xb") as handle:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
        item = {"source": CODE, "tree": TREE, "argv": argv, "cwd": str(cwd),
                "PYTHONPATH": env["PYTHONPATH"], "exit": result.returncode, "seconds": time.monotonic() - started}
        save(name + ".command.json", item)
        print(json.dumps({"lane": name, "exit": result.returncode}), flush=True)
        if result.returncode: failures.append(name)
    run("boundaries-and-negative-controls", [sys.executable, "-B", str(probe)], root)
    run("approval-module", [sys.executable, "-B", "-m", "unittest", "test_task_approval", "-v"], root / "packages/pioneer-agent/tests")
    run("focused", [sys.executable, "-B", "-m", "unittest", "test_task_approval", "test_task_runner",
        "test_task_contracts", "test_task_cli", "test_checkpoint_ownership", "test_task_cr_regressions", "-v"], root / "packages/pioneer-agent/tests")
    for package in ("pioneer-agent", "qa-agent", "sanmou-common"):
        run(package, [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], root / "packages" / package)
    run("h09-cli", [sys.executable, "-B", "-m", "pioneer_agent.app.task_eval", "--output", str(out / "h09-cli")], root)
    run("qa-v3", [sys.executable, "-B", "-m", "qa_agent.quality_eval.runner", "--baseline", "v3", "--output", str(out / "qa-v3.json")], root / "packages/qa-agent")
    assert not git("diff", "--name-only", "HEAD")
    assert git("rev-parse", "HEAD").decode().strip() == CODE
    files = {}
    for path in sorted(out.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            assert len(raw) < 8 * 1024 * 1024
            files[str(path.relative_to(out))] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    save("manifest.json", {"source": CODE, "tree": TREE, "failures": failures, "files": files,
        "native_status": "pending_hosted_windows_ci"})
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
