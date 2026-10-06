"""Cross-check current Q05a plain author artifacts against independent source runs."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPORT = "17e82effff23e8701629c0cbdd5e3f611ada3853"
PREFIX = "docs/test-reports/2026-10-06/q05a-selftest/"
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", "/home/lan/projects/sanmou_monorepo", *args])
def blob(name):
    assert name.startswith(PREFIX) and Path(name).suffix in {".json", ".log", ".md"}
    return git("show", REPORT + ":" + name)
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
mine = json.loads(Path(sys.argv[1]).read_text())
author_raw = blob(PREFIX + "results-3d8257b/summary.json")
author = json.loads(author_raw)
assert author["source"] == mine["source"] and author["tree"] == mine["tree"]
assert not git("diff", "--name-only", mine["source"], REPORT, "--", "packages", ".github")
assert author["scope"]["git_byte_verified_inputs"] == mine["git_byte_checked_inputs"]
assert author["scope"]["targeted_names"] == mine["targeted_inventory"]
assert author["results"]["v4"]["sha256"] == mine["comparisons"]["new_v4_sha256"]
assert author["results"]["q04"]["sha256"] == mine["comparisons"]["new_q04_sha256"]
assert author["results"]["q04"]["eval_source"] == mine["comparisons"]["new_eval_source"]
assert author["results"]["h09"]["totals"] == mine["h09"]["totals"]
verified = []
for command in author["commands"]:
    assert Path(command["log"]).name == command["log"]
    raw = blob(PREFIX + "results-3d8257b/" + command["log"])
    assert sha(raw) == command["log_sha256"] and len(raw) == command["log_bytes"]
    assert command["exit"] == command["expected_exit"]
    if command["tests"] is not None:
        assert int(re.findall(rb"Ran (\d+) tests? in ", raw)[-1]) == command["tests"]
        skips = re.findall(rb"OK \(skipped=(\d+)\)", raw)
        assert (int(skips[-1]) if skips else 0) == command["skipped"]
        assert re.search(rb"\nRan \d+ tests? in [^\n]+\n\nOK(?: \(skipped=\d+\))?\n", raw)
    if command["name"] == "q05-targeted":
        assert sorted(x.decode() for x in re.findall(rb"^test_\w+ \(((?:test_quality_eval|test_seasonal_retriever)\.\w+\.test_\w+)\) \.\.\. ok$", raw, re.M)) == mine["targeted_inventory"]
    verified.append({"name": command["name"], "exit": command["exit"], "tests": command["tests"],
        "skips": command["skipped"], "bytes": len(raw), "sha256": sha(raw)})
baseline = json.loads(blob(PREFIX + "baseline-3711/summary.json"))
assert baseline["source"] == mine["baseline"]
assert baseline["v3_sha256"] == mine["comparisons"]["old_v3_sha256"]
assert baseline["q04_sha256"] == mine["comparisons"]["old_q04_sha256"]
for command in baseline["commands"]:
    assert Path(command["log"]).name == command["log"] and command["exit"] == 0
    assert sha(blob(PREFIX + "baseline-3711/" + command["log"])) == command["log_sha256"]
history = {}
for name, expected in {
    "pre-format-diff-check.log": "0f4fcfa48646ea0484198c1e1b42748f346de74dafe6ea0834a4e1784b4c0f3f",
    "q05a-author-targeted-01.log": "1f393de687cbfe5bbecaa8ffe7e9258a2854acce6e0320f00ce3a6208c720c77",
    "q05a-author-targeted-02.log": "0221ab73fa327fce2acbe1b62180fd5fc23ad4bfd02e33d907c52d9c946b5364"}.items():
    raw = blob(PREFIX + name)
    assert sha(raw) == expected
    if name.endswith("01.log"):
        assert b"Ran 43 tests" in raw and b"FAILED (errors=1)" in raw and b"KeyError: 'pydantic.root_model'" in raw
    history[name] = {"sha256": sha(raw), "bytes": len(raw)}
assert not author["failures"]
result = {"source": mine["source"], "tree": mine["tree"], "author_report": REPORT,
    "manifest_sha256": sha(author_raw), "report_sha256": sha(blob(PREFIX + "REPORT-3d8257b.md")),
    "final_logs_verified": verified, "baseline_log_count": len(baseline["commands"]),
    "preserved_author_history": history, "matches_independent_runs": True, "native": "pending"}
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
