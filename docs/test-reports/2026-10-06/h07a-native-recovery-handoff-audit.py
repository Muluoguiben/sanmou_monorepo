"""Audit only the new fixed plain-text handoff and its explicit JSON artifacts."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

HANDOFF = "61132b6962f45c95d5adb916bc90ff1c4319950b"
CODE = "b785458e9b322707e38f0b424ab78a9512abd8d1"
TREE = "726d99e49ab3fe0822b0bc306870f7d98d319cb0"
PREFIX = "docs/test-reports/2026-10-06/h07a-native-recovery-selftest/"
ROOT = PREFIX + "results-b785458/"
OWN = Path("/tmp/h07a-native-cr-b785458-results")


def blob(path):
    assert path.startswith(PREFIX) and Path(path).suffix in {".json", ".log", ".py"}
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C",
        "/home/lan/projects/sanmou_monorepo", "show", HANDOFF + ":" + path])


raw_summary = blob(ROOT + "summary.json")
summary = json.loads(raw_summary)
assert (summary["source"], summary["tree"], summary["failures"]) == (CODE, TREE, [])
assert hashlib.sha256(blob(PREFIX + "verify.py")).hexdigest() == summary["verifier_sha256"]
assert summary["native"]["status"] == "pending_hosted_windows_ci"
assert summary["native"]["local_module_executed"] is False
observed = {}
for command in summary["commands"]:
    raw = blob(ROOT + command["log"])
    assert len(raw) == command["log_bytes"]
    assert hashlib.sha256(raw).hexdigest() == command["log_sha256"]
    assert command["exit"] == 0
    if command["tests"] is not None:
        assert re.search(rb"Ran " + str(command["tests"]).encode() + rb" tests", raw)
        assert b"\nOK" in raw and b"\nFAILED" not in raw
        if command["skipped"]:
            assert ("OK (skipped=%d)" % command["skipped"]).encode() in raw
        else:
            assert b"... skipped " not in raw
    observed[command["name"]] = {key: command[key] for key in ("tests", "skipped", "exit")}
h09 = summary["results"]["h09"]
h09_path = Path(h09["raw_path"])
assert str(h09_path) == "/tmp/h07a-followup-b785458-results/h09-cli/report.json"
raw = h09_path.read_bytes()
assert len(raw) == h09["raw_bytes"] and hashlib.sha256(raw).hexdigest() == h09["raw_sha256"]
report = json.loads(raw)
assert report["source_verified"] and CODE in json.dumps(report["source"]) and TREE in json.dumps(report["source"])
assert report["stable_projection"] == json.loads((OWN / "h09-cli/report.json").read_text())["stable_projection"]
qa_path = Path(summary["results"]["qa_v3"]["raw_path"])
assert str(qa_path) == "/tmp/h07a-followup-b785458-results/qa-v3.json"
assert qa_path.read_bytes() == (OWN / "qa-v3.json").read_bytes()
assert hashlib.sha256(qa_path.read_bytes()).hexdigest() == summary["results"]["qa_v3"]["sha256"]
print(json.dumps({"handoff": HANDOFF, "source": CODE, "tree": TREE,
    "summary_sha256": hashlib.sha256(raw_summary).hexdigest(), "verified_logs": observed,
    "verifier_hash_matched": True, "h09_source_and_stable_matched": True,
    "qa_v3_bytes_matched": True, "native_status": "pending_hosted_windows_ci",
    "archive_reads": 0}, indent=2))
