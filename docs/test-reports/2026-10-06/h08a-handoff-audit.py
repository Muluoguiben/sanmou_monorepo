"""Check immutable H08a author evidence after independent fixed-source execution."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPORT = "1071b52e1266f3dca34f321ce2f68b92c7ba854f"
PREFIX = "docs/test-reports/2026-10-06/h08a-selftest/"
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", "/home/lan/projects/sanmou_monorepo", *args])
def blob(name):
    assert Path(name).suffix in {".json", ".log", ".md"} and ".." not in Path(name).parts
    return git("show", REPORT + ":" + PREFIX + name)
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
mine = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
manifest_raw = blob("results-8e0a2a0/summary.json")
author = json.loads(manifest_raw)
assert author["source"] == mine["source"] and author["tree"] == mine["tree"]
assert not git("diff", "--name-only", mine["source"], REPORT, "--", "packages", ".github")
assert author["scope"]["git_byte_verified_inputs"] == mine["git_byte_checked_inputs"]
assert author["scope"]["targeted_names"] == mine["new_test_inventory"]
assert author["results"]["v4_sha256"] == mine["v4_sha256"]
assert author["results"]["q04_sha256"] == mine["q04_sha256"]
assert author["results"]["h09"]["totals"] == mine["h09"]["totals"]
locale = author["results"]["text_locale"]
assert locale["default_open_encoding"] == mine["text_locale"]["default_file_encoding"] == "ANSI_X3.4-1968"
assert locale["utf8_mode"] == mine["text_locale"]["utf8_mode"] == 0
assert locale["filesystem_encoding"] == mine["text_locale"]["filesystem_encoding"] == "utf-8"
verified = []
for command in author["commands"]:
    assert Path(command["log"]).name == command["log"]
    raw = blob("results-8e0a2a0/" + command["log"])
    assert sha(raw) == command["log_sha256"] and len(raw) == command["log_bytes"]
    assert command["exit"] == command["expected_exit"]
    if command["tests"] is not None:
        assert int(re.findall(rb"Ran (\d+) tests? in ", raw)[-1]) == command["tests"]
        skips = re.findall(rb"OK \(skipped=(\d+)\)", raw)
        assert (int(skips[-1]) if skips else 0) == command["skipped"]
        assert re.search(rb"\nRan \d+ tests? in [^\n]+\n\nOK(?: \(skipped=\d+\))?\n", raw)
    if command["name"] == "h08-targeted":
        assert sorted(x.decode() for x in re.findall(rb"^test_\w+ \((test_skill_registry\.\w+\.test_\w+)\) \.\.\. ok$", raw, re.M)) == mine["new_test_inventory"]
    verified.append({"name": command["name"], "exit": command["exit"], "tests": command["tests"],
        "skips": command["skipped"], "bytes": len(raw), "sha256": sha(raw)})
history = []
for suffix, digest, footer in (
    ("01", "2d32c51e1f91f31294b0d920ee552614f362dbf01be8d4d8318b8dc8e37f95da", b"FAILED (errors=1)"),
    ("02", "235cca0452720228b7c413a47cf0b277a055b35b89bc714d622e58640565b228", b"FAILED (failures=1)"),
    ("03", "4d2f5f09c0a8ce7a237116d105186d45fcbc889a7415b97e8e3b68ba5ae6bf4d", b"\nOK\n")):
    name = "h08a-author-targeted-" + suffix + ".log"
    raw = blob(name)
    assert sha(raw) == digest and footer in raw and b"Ran 23 tests" in raw
    history.append({"log": name, "sha256": digest, "bytes": len(raw)})
assert not author["failures"]
result = {"source": mine["source"], "tree": mine["tree"], "author_report": REPORT,
    "manifest_sha256": sha(manifest_raw), "report_sha256": sha(blob("REPORT-8e0a2a0.md")),
    "verified_final_logs": verified, "preserved_author_history": history,
    "agrees_with_independent_execution": True, "native": "pending_exact_final_Hosted"}
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source": mine["source"], "final_logs": len(verified), "history_logs": len(history), "passed": True}))
