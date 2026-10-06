"""Cross-check immutable author plain evidence; never reads archive members."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = "/home/lan/projects/sanmou_monorepo"
REPORT = "0530fbbc32804de2e1d2f9176f524fa70227c902"
CODE = "676ac1ed012458ccc00a01df159476747921c181"
PREFIX = "docs/test-reports/2026-10-06/q04a-selftest/"

def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", REPO, *args])

def blob(path):
    assert path.startswith(PREFIX) and Path(path).suffix in {".json", ".log", ".md", ".py"}
    return git("show", REPORT + ":" + path)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

mine = json.loads(Path(sys.argv[1]).read_text())
manifest_raw = blob(PREFIX + "results-676ac1e/summary.json")
manifest = json.loads(manifest_raw)
assert manifest["source"] == mine["source"] == CODE
assert manifest["tree"] == mine["tree"]
assert git("rev-parse", REPORT + ":packages") == git("rev-parse", CODE + ":packages")
assert not git("diff", "--name-only", CODE, REPORT, "--", "packages", ".github")
verified = []
for entry in manifest["commands"]:
    assert entry["exit"] == 0
    assert Path(entry["log"]).name == entry["log"]
    raw = blob(PREFIX + "results-676ac1e/" + entry["log"])
    assert len(raw) == entry["log_bytes"] and sha(raw) == entry["log_sha256"]
    if entry["tests"] is not None:
        counts = re.findall(rb"Ran (\d+) tests? in ", raw)
        assert int(counts[-1]) == entry["tests"]
        skipped = re.findall(rb"OK \(skipped=(\d+)\)", raw)
        assert (int(skipped[-1]) if skipped else 0) == entry["skipped"]
        # unittest writes stderr; buffered test stdout may follow its summary.
        assert re.search(rb"\nRan \d+ tests? in [^\n]+\n\nOK(?: \(skipped=\d+\))?\n", raw)
    verified.append({"name": entry["name"], "exit": entry["exit"], "tests": entry["tests"],
                     "skipped": entry["skipped"], "sha256": sha(raw), "bytes": len(raw)})
assert manifest["results"]["qa_v3"]["actual_sha256"] == mine["legacy"]["new_v3_sha256"]
assert manifest["results"]["qa_v3"]["new_eval_source"] == mine["legacy"]["new_eval"]
assert manifest["results"]["claim_spans"]["raw_sha256"] == mine["new_cli_sha256"]
raw_report = blob(PREFIX + "results-676ac1e/claim-spans.json")
assert sha(raw_report) == mine["new_cli_sha256"]
assert manifest["results"]["h09"]["totals"] == mine["h09"]["totals"]
assert not manifest["failures"]
result = {"source": CODE, "tree": mine["tree"], "author_handoff": REPORT,
    "packages_tree": git("rev-parse", CODE + ":packages").decode().strip(),
    "manifest_sha256": sha(manifest_raw), "author_logs_verified": verified,
    "source_and_semantic_reports_match_independent_run": True,
    "author_report_sha256": sha(blob(PREFIX + "REPORT-676ac1e.md")),
    "native_q04": "not_executed_by_reviewer", "archive_reads": 0}
Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
