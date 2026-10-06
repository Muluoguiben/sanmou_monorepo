"""Bounded Q04a fixed-source matrix and exact legacy report delta audit."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

CODE = "676ac1ed012458ccc00a01df159476747921c181"
TREE = "16b74ba49c8bf44288c7e23d9935e56631fea471"
BASE = "5791ca397507007b9397c78763b3523b8ec16421"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
root, base, out = map(lambda p: Path(p).resolve(), sys.argv[1:4])
out.mkdir(parents=True, exist_ok=False)

def git(where, *args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(where), *args])

def sha(data):
    return hashlib.sha256(data).hexdigest()

def save(name, data):
    (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

assert git(root, "rev-parse", "HEAD").decode().strip() == CODE
assert git(root, "rev-parse", "HEAD^{tree}").decode().strip() == TREE
assert git(base, "rev-parse", "HEAD").decode().strip() == BASE
allowed = {"packages/qa-agent/src/qa_agent/quality_eval/claim_spans.py",
           "packages/qa-agent/tests/test_claim_spans.py",
           "packages/qa-agent/tests/fixtures/quality_eval/claim_spans_v1/cases.json",
           "packages/qa-agent/tests/fixtures/quality_eval/claim_spans_v1/freeze.json"}
assert set(git(root, "diff", "--name-only", BASE, CODE, "--", "packages").decode().splitlines()) == allowed
assert not git(root, "diff", "--name-only", BASE, CODE, "--", ".github")
checked = []
for path in git(root, "ls-tree", "-r", "--name-only", CODE, "--", "packages").decode().splitlines():
    if Path(path).suffix in {".py", ".json", ".yaml", ".yml"}:
        # Ordinary current package source/fixtures only; no archive body/member reads.
        raw = (root / path).read_bytes()
        assert raw == git(root, "show", CODE + ":" + path), path
        checked.append(path)
commands = []

def run(name, where, argv, cwd=None, expected=0):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    env["PYTHONPATH"] = os.pathsep.join([str(where / p) for p in
        ("packages/qa-agent/src", "packages/qa-agent/tests", "packages/pioneer-agent/src",
         "packages/pioneer-agent/tests", "packages/sanmou-common/src")] + [DEPS])
    started = time.monotonic()
    with (out / (name + ".log")).open("xb") as stream:
        result = subprocess.run(argv, cwd=cwd or where, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=900)
    raw = (out / (name + ".log")).read_bytes()
    count = re.findall(rb"Ran (\d+) tests? in ", raw)
    skips = re.findall(rb"OK \(skipped=(\d+)\)", raw)
    item = {"name": name, "source": CODE if where == root else BASE, "argv": argv,
        "cwd": str(cwd or where), "PYTHONPATH": env["PYTHONPATH"], "exit": result.returncode,
        "expected_exit": expected, "seconds": time.monotonic() - started,
        "tests": int(count[-1]) if count else None, "skipped": int(skips[-1]) if skips else 0,
        "log": name + ".log", "bytes": len(raw), "sha256": sha(raw)}
    commands.append(item)
    save("progress.json", commands)
    print(json.dumps({"lane": name, "exit": result.returncode, "tests": item["tests"]}), flush=True)
    assert result.returncode == expected, item
    return raw

py = [sys.executable, "-B"]
probe = Path(__file__).with_name("q04a-independent-probes.py")
integration = Path(__file__).with_name("q04a-independent-integration.py")
run("baseline-manual-oracles", base, py + [str(probe), "--verify-legacy-oracles"])
run("public-probes", root, py + [str(probe), "-v"])
run("integration-probes", root, py + [str(integration), str(root), "-v"])
for label, where in (("old", base), ("new", root)):
    for version in ("v1", "v2", "v3"):
        raw = run(label + "-" + version, where, py + ["-m", "qa_agent.quality_eval.runner",
            "--baseline", version, "--output", str(out / (label + "-" + version + ".json"))], expected=0 if version == "v3" else 1)
        if version != "v3":
            assert b"frozen KB/production source drift; create a reviewed new baseline version" in raw
old_raw, new_raw = (out / "old-v3.json").read_bytes(), (out / "new-v3.json").read_bytes()
assert sha(old_raw) == "480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8"
old, new = json.loads(old_raw), json.loads(new_raw)
old_eval, new_eval = old.pop("eval_source"), new.pop("eval_source")
assert old == new
addition = "src/qa_agent/quality_eval/claim_spans.py"
assert set(new_eval["files"]) - set(old_eval["files"]) == {addition}
assert {k: v for k, v in new_eval["files"].items() if k != addition} == old_eval["files"]
assert old_eval["algorithm"] == new_eval["algorithm"]
for path, digest in new_eval["files"].items():
    raw = git(root, "show", CODE + ":packages/qa-agent/" + path)
    assert sha(raw.decode("utf-8-sig").replace("\r\n", "\n").encode()) == digest
assert sha(json.dumps(new_eval["files"], sort_keys=True, ensure_ascii=False).encode()) == new_eval["digest"]
compatibility = {"old_v3_sha256": sha(old_raw), "new_v3_sha256": sha(new_raw),
    "all_other_fields_equal": True, "old_eval": old_eval, "new_eval": new_eval,
    "old_v1_v2_refusals_unchanged": True}
save("legacy-compatibility.json", compatibility)
for name, module, package in (("claim-module", "test_claim_spans", "qa-agent"),
        ("legacy-module", "test_quality_eval", "qa-agent"),
        ("causal-module", "test_causal_trace", "pioneer-agent"),
        ("h07-module", "test_task_approval", "pioneer-agent")):
    raw = run(name, root, py + ["-W", "error::RuntimeWarning", "-m", "unittest", module, "-v"], root / "packages" / package / "tests")
    assert b"RuntimeWarning:" not in raw and b"... skipped " not in raw
for package in ("qa-agent", "pioneer-agent", "sanmou-common"):
    run(package, root, py + ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], root / "packages" / package)
run("new-cli", root, py + ["-m", "qa_agent.quality_eval.claim_spans", "--baseline", "claim-spans-v1", "--output", str(out / "claim-spans.json")])
run("h09-cli", root, py + ["-m", "pioneer_agent.app.task_eval", "--output", str(out / "h09-cli")])
new_report = json.loads((out / "claim-spans.json").read_bytes())
h09 = json.loads((out / "h09-cli/report.json").read_bytes())
assert new_report["gate_pass"] and new_report["controls"]["denominator"] == 12
assert new_report["eval_source"] == new_eval
assert h09["source_verified"] and h09["complete"] and h09["gate_pass"]
assert not git(root, "diff", "--name-only", "HEAD", "--", "packages", ".github")
save("summary.json", {"source": CODE, "tree": TREE, "baseline": BASE, "package_files_git_bytes_checked": len(checked),
    "protected_package_paths_unchanged": True, "commands": commands, "legacy": compatibility,
    "new_cli_sha256": sha((out / "claim-spans.json").read_bytes()), "h09": {"totals": h09["totals"],
    "sha256": sha((out / "h09-cli/report.json").read_bytes())}, "native_q04": "not_executed",
    "provider_calls": 0, "archive_reads": 0, "execution_authority": "none", "executable": False})
