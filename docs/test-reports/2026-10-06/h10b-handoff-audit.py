"""Fixed plain-log cross-check; not a native execution claim."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

HANDOFF = "3b31752ecd5c566c8e995c14834c6b736d71f776"
CODE = "e062adb7dd45d10bb579165a56f1c0d3ccf901d1"
TREE = "2892d9525642bc4e279c1b2f0835f0f7b5913fa1"
PREFIX = "docs/test-reports/2026-10-06/h10b-selftest/"
OWN = Path("/tmp/h10b-cr-e062adb-results")


def git_blob(path):
    assert path.startswith(PREFIX) and Path(path).suffix in {".json", ".log", ".py"}
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C",
        "/home/lan/projects/sanmou_monorepo", "show", HANDOFF + ":" + path])


raw_summary = git_blob(PREFIX + "results-e062adb/summary.json")
summary = json.loads(raw_summary)
assert (summary["source"], summary["tree"], summary["failures"]) == (CODE, TREE, [])
assert hashlib.sha256(git_blob(PREFIX + "verify.py")).hexdigest() == summary["verifier_sha256"]
own = json.loads((OWN / "summary.json").read_text())
source = json.loads((OWN / "source.json").read_text())
assert own["failures"] == [] and source["packages_tree"] == summary["packages_tree"]
assert source["workflow_sha256"] == summary["scope"]["workflow_after_sha256"]
checked = {}
for command in summary["commands"]:
    raw = git_blob(PREFIX + "results-e062adb/" + command["log"])
    assert len(raw) == command["log_bytes"] and hashlib.sha256(raw).hexdigest() == command["log_sha256"]
    assert command["exit"] == 0
    if command["tests"] is not None:
        assert re.search(rb"Ran " + str(command["tests"]).encode() + rb" tests? in ", raw)
        assert b"\nOK" in raw and b"\nFAILED" not in raw
    if command["name"] == "causal-module":
        assert command["argv"][1:] == ["-W", "error::RuntimeWarning", "-m", "unittest", "test_causal_trace", "-v"]
        assert command["cwd"].endswith("/packages/pioneer-agent/tests")
        inventory = sorted(value.decode() for value in re.findall(rb"^test_\w+ \((test_causal_trace\.\w+\.test_\w+)\)", raw, re.M))
        assert inventory == source["expected_inventory"] and (command["tests"], command["skipped"]) == (32, 0)
        assert b"... skipped " not in raw and b"RuntimeWarning:" not in raw and b"was never awaited" not in raw
    checked[command["name"]] = {key: command[key] for key in ("exit", "tests", "skipped")}
h = summary["results"]["h09"]
assert h["raw_path"] == "/tmp/h10b-e062adb-results/h09-cli/report.json"
raw = Path(h["raw_path"]).read_bytes()
assert len(raw) == h["raw_bytes"] and hashlib.sha256(raw).hexdigest() == h["raw_sha256"]
h09 = json.loads(raw)
assert h09["source_verified"] and CODE in json.dumps(h09["source"]) and TREE in json.dumps(h09["source"])
assert h09["stable_projection"] == json.loads((OWN / "h09-cli/report.json").read_text())["stable_projection"]
q = summary["results"]["qa_v3"]
assert q["raw_path"] == "/tmp/h10b-e062adb-results/qa-v3.json"
assert Path(q["raw_path"]).read_bytes() == (OWN / "qa-v3.json").read_bytes()
assert hashlib.sha256((OWN / "qa-v3.json").read_bytes()).hexdigest() == q["sha256"]
print(json.dumps({"handoff": HANDOFF, "source": CODE, "tree": TREE,
    "summary_sha256": hashlib.sha256(raw_summary).hexdigest(), "checked_logs": checked,
    "actual_causal_method_inventory_matched": 32, "warning_lines": [],
    "h09_source_and_stable_equal": True, "qa_v3_bytes_equal": True,
    "native_status": "pending_exact_sha_hosted_windows", "archive_reads": 0}, indent=2))
