"""H10b fixed-source CI-only validation; no archive access or native workaround."""
import copy
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
BASE = "c8b096edc5fce6c87e83198b871ab5c576add1db"
PUBLISHED = "a45949233dfc666b91fdbf756b8666d96d93fde3"
PACKAGES = "3d1c4a78faf912f522be764454762601aa1f7409"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
OUT.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, DEPS)
import yaml


def sha(raw): return hashlib.sha256(raw).hexdigest()
def git(*args): return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(ROOT), *args])
def save(name, data):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


assert git("rev-parse", "HEAD").decode().strip() == CODE
TREE = git("rev-parse", "HEAD^{tree}").decode().strip()
assert not git("diff", "--name-only", "HEAD")
changed = git("diff", "--name-only", BASE, CODE).decode().splitlines()
assert changed == [".github/workflows/regression.yml"], changed
assert git("rev-parse", CODE + ":packages").decode().strip() == PACKAGES
assert git("rev-parse", PUBLISHED + ":packages").decode().strip() == PACKAGES
path = ".github/workflows/regression.yml"
before, actual = git("show", BASE + ":" + path), (ROOT / path).read_bytes()
addition = (b"      - name: Windows H10b causal trace v2\n"
    b"        working-directory: packages/pioneer-agent/tests\n"
    b"        run: python -W error::RuntimeWarning -m unittest test_causal_trace -v\n")
assert actual.count(addition) == 1
assert actual.replace(addition, b"") == before
expected_step = {"name": "Windows H10b causal trace v2", "working-directory": "packages/pioneer-agent/tests",
                 "run": "python -W error::RuntimeWarning -m unittest test_causal_trace -v"}
old_yaml, new_yaml = yaml.load(before, Loader=yaml.BaseLoader), yaml.load(actual, Loader=yaml.BaseLoader)
steps = new_yaml["jobs"]["windows"]["steps"]
assert steps.count(expected_step) == 1
index = steps.index(expected_step)
assert steps[index - 1]["name"] == "Windows H07a synthetic approval lifecycle"
assert steps[index + 1]["name"] == "Windows H09b offline task evaluation"
normalized = copy.deepcopy(new_yaml)
normalized["jobs"]["windows"]["steps"].pop(index)
assert normalized == old_yaml
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
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = ":".join(str(ROOT / p) for p in ("packages/pioneer-agent/src", "packages/qa-agent/src",
    "packages/sanmou-common/src", "packages/pioneer-agent/tests")) + ":" + DEPS
summary = {"source": CODE, "tree": TREE, "baseline": BASE, "published": PUBLISHED, "packages_tree": PACKAGES,
    "verifier_sha256": sha(Path(__file__).read_bytes()),
    "runtime": {"executable": sys.executable, "python": sys.version, "platform": platform.platform()},
    "scope": {"changed": changed, "unique_step": expected_step, "step_index": index,
        "removal_preserves_original_bytes": True, "removal_preserves_yaml_object": True,
        "workflow_before_sha256": sha(before), "workflow_after_sha256": sha(actual),
        "packages_and_tests_unchanged": True, "git_byte_verified_inputs": len(input_rows),
        "input_manifest_sha256": sha(json.dumps(input_rows, separators=(",", ":")).encode())},
    "commands": [], "failures": [], "results": {},
    "native": "pending exact-final-SHA Hosted Windows causal32/0skip and warning-free logs; no local native execution/install/mock"}


def run(name, argv, cwd):
    started = time.time()
    path = OUT / (name + ".log")
    with path.open("xb") as handle:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
    raw = path.read_bytes()
    assert len(raw) <= 2 * 1024 * 1024
    output = raw.decode("utf-8", errors="replace")
    count = re.findall(r"^Ran (\d+) tests? in ([\d.]+)s", output, re.MULTILINE)
    skips = re.findall(r"^OK \(skipped=(\d+)\)", output, re.MULTILINE)
    row = {"name": name, "argv": argv, "cwd": str(cwd), "PYTHONPATH": env["PYTHONPATH"], "exit": result.returncode,
        "tests": int(count[-1][0]) if count else None, "skipped": int(skips[-1]) if skips else 0,
        "seconds": time.time() - started, "log": path.name, "log_bytes": len(raw), "log_sha256": sha(raw)}
    summary["commands"].append(row)
    if result.returncode: summary["failures"].append(name)
    if name == "causal-module":
        warnings = [line for line in output.splitlines() if re.search(r"RuntimeWarning|was never awaited", line)]
        summary["results"]["causal_runtime_warning_lines"] = warnings
        assert (row["exit"], row["tests"], row["skipped"], warnings) == (0, 32, 0, [])
    if name == "h07a-module": assert (row["exit"], row["tests"], row["skipped"]) == (0, 35, 0)
    print(json.dumps({key: row[key] for key in ("name", "exit", "tests", "skipped", "seconds")}), flush=True)


PY = [sys.executable]
pioneer = ROOT / "packages/pioneer-agent"
run("causal-module", PY + ["-W", "error::RuntimeWarning", "-m", "unittest", "test_causal_trace", "-v"], pioneer / "tests")
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
summary["results"]["qa_v3"] = {"raw_path": str(OUT / "qa-v3.json"), "sha256": digest}
assert not git("diff", "--name-only", "HEAD")
assert git("rev-parse", "HEAD").decode().strip() == CODE
save("summary.json", summary)
raise SystemExit(bool(summary["failures"]))
