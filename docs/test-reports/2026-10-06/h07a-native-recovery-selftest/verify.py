"""Bounded Linux follow-up verification; no archive access or new dependencies."""
import ast
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
BASE = "ecf50e0012c336c131f75b9bc6c102530a0d1876"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
TEST = "packages/pioneer-agent/tests/test_task_approval.py"
WORKFLOW = ".github/workflows/regression.yml"
OUT.mkdir(parents=True, exist_ok=False)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(ROOT), *args])


def save(name, value):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def functions(body, prefix=""):
    result = {}
    for item in body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[prefix + item.name] = ast.dump(item, include_attributes=False)
        elif isinstance(item, ast.ClassDef):
            result.update(functions(item.body, prefix + item.name + "."))
    return result


assert git("rev-parse", "HEAD").decode().strip() == CODE
TREE = git("rev-parse", "HEAD^{tree}").decode().strip()
assert not git("diff", "--name-only", "HEAD")
changed = git("diff", "--name-only", BASE, CODE).decode().splitlines()
assert changed == [WORKFLOW, TEST], changed
old = functions(ast.parse(git("show", BASE + ":" + TEST)).body)
new = functions(ast.parse((ROOT / TEST).read_bytes()).body)
assert all(new.get(name) == value for name, value in old.items())
old_tests = sum(name.split(".")[-1].startswith("test_") for name in old)
new_tests = sum(name.split(".")[-1].startswith("test_") for name in new)
assert (old_tests, new_tests) == (30, 35)
addition = (b"      - name: Windows H07a synthetic approval lifecycle\n"
    b"        working-directory: packages/pioneer-agent/tests\n"
    b"        run: python -m unittest test_task_approval -v\n")
workflow = (ROOT / WORKFLOW).read_bytes()
assert workflow.count(addition) == 1
assert workflow.replace(addition, b"") == git("show", BASE + ":" + WORKFLOW)
inputs = []
for row in git("ls-tree", "-rz", CODE, "--", "packages").split(b"\0"):
    if not row:
        continue
    meta, name = row.split(b"\t")
    path = name.decode()
    if Path(path).suffix not in {".py", ".json", ".yaml", ".yml"}:
        continue
    raw = (ROOT / path).read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert blob == meta.decode().split()[2], path
    inputs.append([path, blob, sha(raw)])

env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env["PYTHONPATH"] = ":".join(str(ROOT / part) for part in (
    "packages/pioneer-agent/src", "packages/qa-agent/src", "packages/sanmou-common/src",
    "packages/pioneer-agent/tests")) + ":" + DEPS
summary = {"source": CODE, "tree": TREE, "baseline": BASE,
    "runtime": {"python": sys.version, "executable": sys.executable, "platform": platform.platform()},
    "verifier_sha256": sha(Path(__file__).read_bytes()),
    "scope": {"changed": changed, "old_test_methods_preserved": old_tests, "new_test_methods": new_tests - old_tests,
        "old_function_asts_preserved": True, "ci_only_exact_three_line_addition": True,
        "production_unchanged": True, "git_byte_verified_inputs": len(inputs),
        "input_manifest_sha256": sha(json.dumps(inputs, ensure_ascii=False, separators=(",", ":")).encode())},
    "commands": [], "failures": [], "results": {}}


def run(name, argv, cwd):
    started = time.time()
    path = OUT / (name + ".log")
    with path.open("xb") as handle:
        process = subprocess.run(argv, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
    raw = path.read_bytes()
    assert len(raw) <= 2 * 1024 * 1024, name
    output = raw.decode("utf-8", errors="replace")
    count = re.findall(r"^Ran (\d+) tests? in ([\d.]+)s", output, re.MULTILINE)
    skipped = re.findall(r"^OK \(skipped=(\d+)\)", output, re.MULTILINE)
    result = {"name": name, "argv": argv, "cwd": str(cwd), "PYTHONPATH": env["PYTHONPATH"],
        "exit": process.returncode, "seconds": time.time() - started,
        "tests": int(count[-1][0]) if count else None, "skipped": int(skipped[-1]) if skipped else 0,
        "log": path.name, "log_bytes": len(raw), "log_sha256": sha(raw)}
    summary["commands"].append(result)
    if process.returncode:
        summary["failures"].append(name)
    print(json.dumps({key: result[key] for key in ("name", "exit", "tests", "skipped", "seconds")}), flush=True)


PY = [sys.executable, "-B"]
pioneer = ROOT / "packages/pioneer-agent"
run("approval-module", PY + ["-m", "unittest", "test_task_approval", "-v"], pioneer / "tests")
run("focused", PY + ["-m", "unittest", "test_task_approval", "test_task_runner", "test_task_contracts",
    "test_task_cli", "test_checkpoint_ownership", "test_task_cr_regressions", "-v"], pioneer)
for package in ("pioneer-agent", "qa-agent", "sanmou-common"):
    run(package + "-full", PY + ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], ROOT / "packages" / package)
run("h09-cli", PY + ["-m", "pioneer_agent.app.task_eval", "--output", str(OUT / "h09-cli")], ROOT)
run("qa-v3", PY + ["-m", "qa_agent.quality_eval.runner", "--baseline", "v3", "--output", str(OUT / "qa-v3.json")], ROOT / "packages/qa-agent")
raw = (OUT / "h09-cli/report.json").read_bytes()
h09 = json.loads(raw)
assert h09["source"]["commit"] == CODE and h09["source"]["tree"] == TREE
assert h09["complete"] and h09["gate_pass"] and h09["totals"]["control_pass"] == 8
summary["results"]["h09"] = {"complete": h09["complete"], "gate_pass": h09["gate_pass"], "totals": h09["totals"],
    "raw_path": str(OUT / "h09-cli/report.json"), "raw_sha256": sha(raw), "raw_bytes": len(raw)}
qa_digest = sha((OUT / "qa-v3.json").read_bytes())
assert qa_digest == "480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8"
summary["results"]["qa_v3"] = {"raw_path": str(OUT / "qa-v3.json"), "sha256": qa_digest}
summary["native"] = {"status": "pending_hosted_windows_ci", "local_module_executed": False,
    "local_limitation": "Coordinator's bounded existing-environment probe found missing pywintypes/rpds.rpds; no installation or mocked imports attempted."}
assert not git("diff", "--name-only", "HEAD")
assert git("rev-parse", "HEAD").decode().strip() == CODE
save("summary.json", summary)
raise SystemExit(bool(summary["failures"]))
