"""Hash/source audit of fixed test-only repair evidence, including all locale reds."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPORT = "dacf8a0aea62eef7bd9415779cdcf03e6faffe70"
PREFIX = "docs/test-reports/2026-10-06/q05a-locale-repair/"
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", "/home/lan/projects/sanmou_monorepo", *args])
def blob(relative):
    assert Path(relative).suffix in {".json", ".log", ".md"} and ".." not in Path(relative).parts
    return git("show", REPORT + ":" + PREFIX + relative)
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
mine = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
author_raw = blob("results-e0d9d6e/summary.json")
author = json.loads(author_raw)
assert author["source"] == mine["source"] and author["tree"] == mine["tree"]
assert not git("diff", "--name-only", mine["source"], REPORT, "--", "packages", ".github")
assert author["scope"]["targeted_names"] == mine["test_inventory"]
assert author["results"]["v4"]["sha256"] == mine["report_hashes"]["v4"]
assert author["results"]["q04"]["sha256"] == mine["report_hashes"]["q04"]
verified = []
for command in author["commands"]:
    assert Path(command["log"]).name == command["log"]
    raw = blob("results-e0d9d6e/" + command["log"])
    assert sha(raw) == command["log_sha256"] and len(raw) == command["log_bytes"]
    assert command["exit"] == command["expected_exit"]
    if command["tests"] is not None:
        assert int(re.findall(rb"Ran (\d+) tests? in ", raw)[-1]) == command["tests"]
        skips = re.findall(rb"OK \(skipped=(\d+)\)", raw)
        assert (int(skips[-1]) if skips else 0) == command["skipped"]
        assert re.search(rb"\nRan \d+ tests? in [^\n]+\n\nOK(?: \(skipped=\d+\))?\n", raw)
    verified.append({"name": command["name"], "exit": command["exit"], "tests": command["tests"],
                     "skips": command["skipped"], "sha256": sha(raw)})
locale_records = []
for name, source, expected_exit, footer in (
    ("old-C-red", mine["previous_source"], 1, b"FAILED (failures=1, errors=27)"),
    ("new-C-filesystem-red", mine["source"], 1, b"FAILED (failures=8, errors=2)"),
    ("old-text-open-red", mine["previous_source"], 1, b"FAILED (errors=27)"),
    ("new-text-open-green", mine["source"], 0, b"\nOK\n")):
    record = json.loads(blob(name + "/summary.json"))
    raw = blob(name + "/targeted.log")
    assert record["source"] == source and record["exit"] == expected_exit
    assert sha(raw) == record["log_sha256"] and footer in raw and b"Ran 44 tests" in raw
    assert record["locale"]["utf8_mode"] == 0
    if "text-open" in name:
        assert record["locale"]["filesystem_encoding"] == "utf-8"
        assert record["locale"]["default_open_encoding"] == "ANSI_X3.4-1968"
    locale_records.append({"name": name, "source": source, "exit": expected_exit,
        "locale": record["locale"], "log_sha256": sha(raw)})
assert not author["failures"]
result = {"source": mine["source"], "tree": mine["tree"], "report": REPORT,
    "manifest_sha256": sha(author_raw), "normal_logs_verified": verified,
    "locale_records_verified": locale_records, "native": "pending_final_exact_Hosted"}
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source": mine["source"], "normal_logs": len(verified), "locale_logs": len(locale_records), "passed": True}))
