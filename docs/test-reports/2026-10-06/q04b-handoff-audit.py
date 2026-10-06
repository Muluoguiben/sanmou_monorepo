"""Audit fixed Q04b author's bounded plain evidence against independent results."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPORT = "a9abfee3290406c3d8e9fc54da200b3ecb1f4a02"
PREFIX = "docs/test-reports/2026-10-06/q04b-selftest/"
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", "/home/lan/projects/sanmou_monorepo", *args])
def blob(path):
    assert path.startswith(PREFIX) and Path(path).suffix in {".json", ".log", ".md"}
    return git("show", REPORT + ":" + path)
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
mine = json.loads(Path(sys.argv[1]).read_text())
raw = blob(PREFIX + "results-ebcd5d1/summary.json")
author = json.loads(raw)
assert author["source"] == mine["source"] and author["tree"] == mine["tree"]
assert not git("diff", "--name-only", mine["source"], REPORT, "--", "packages", ".github")
assert author["packages_tree"] == mine["packages"]
assert author["scope"]["workflow_after_sha256"] == mine["workflow_sha256"]
assert author["scope"]["test_names"] == mine["inventory"]
assert author["results"]["qa_v3_sha256"] == mine["v3_sha256"]
assert author["results"]["claim_spans"]["sha256"] == mine["new_cli_sha256"]
verified = []
for command in author["commands"]:
    assert Path(command["log"]).name == command["log"]
    log = blob(PREFIX + "results-ebcd5d1/" + command["log"])
    assert len(log) == command["log_bytes"] and sha(log) == command["log_sha256"]
    assert command["exit"] == command["expected_exit"]
    if command["tests"] is not None:
        assert int(re.findall(rb"Ran (\d+) tests? in ", log)[-1]) == command["tests"]
        assert command["skipped"] == 0 and b"... skipped " not in log
        assert re.search(rb"\nRan \d+ tests? in [^\n]+\n\nOK\n", log)
    if command["name"] == "claim-spans":
        assert sorted(m.decode() for m in re.findall(rb"^test_\w+ \((test_claim_spans\.\w+\.test_\w+)\) \.\.\. ok$", log, re.M)) == mine["inventory"]
    verified.append({"name": command["name"], "exit": command["exit"], "tests": command["tests"],
                     "skips": command["skipped"], "sha256": sha(log), "bytes": len(log)})
assert not author["failures"]
result = {"source": mine["source"], "tree": mine["tree"], "author_report": REPORT,
    "author_manifest_sha256": sha(raw), "report_sha256": sha(blob(PREFIX + "REPORT-ebcd5d1.md")),
    "verified_logs": verified, "matches_independent_run": True, "native": "pending"}
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
