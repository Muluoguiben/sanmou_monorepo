"""Read immutable author evidence as data; never execute their audit wrapper."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(sys.argv[1])
SOURCE = Path(sys.argv[2])
OUT = Path(sys.argv[3])
HANDOFF = "1abcaac29697420de6de0663f2bc8e244f456336"
CODE = "9c8db2605d64c08736830585b20c542138d66678"
TREE = "a7d1114304936416cb86d6d8428ccef68a1be0d8"
ROOT = "docs/test-reports/2026-10-06/h09b-empty-report-fix/"

def blob(path):
    return subprocess.check_output(["git", "-C", str(REPO), "show", HANDOFF + ":" + path])

spec = importlib.util.spec_from_file_location("reviewed_gate", SOURCE / "scripts/check_windows_task_eval.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
report = blob(ROOT + "REPORT.md").decode()
files = []
data_by_name = {}
for name, length, digest in re.findall(r"^\| ([^|]+?) \| (\d+) \| `([0-9a-f]{64})` \|$", report, re.M):
    data = blob(ROOT + "raw/" + name)
    assert len(data) == int(length)
    assert hashlib.sha256(data).hexdigest() == digest
    files.append({"name": name, "bytes": len(data), "sha256": digest, "matched": True})
    data_by_name[name] = data
assert len(files) == 8
linux = gate.decode(data_by_name["linux-diagnostic-9c8db26-report.json"])
assert linux["source"]["commit"] == CODE and linux["source"]["tree"] == TREE
assert linux["environment"]["platform"].startswith("Linux-")
assert linux["gate_pass"] is True and len(linux["cases"]) == 8
assert linux["totals"] == dict(goal_success=2, expected_safety_stop=6, control_pass=8,
                              infra_error=0, unexpected_goal_success=0, safety_violations=0)
expected_runs = {"pioneer-9c8db26.log": 1018, "qa-9c8db26.log": 394,
                 "common-9c8db26.log": 2, "native-stdlib-9c8db26.log": 20}
for name, count in expected_runs.items():
    text = data_by_name[name].decode("utf-8")
    assert re.search(rf"Ran {count} tests in ", text) and re.search(r"^OK(?: \(skipped=2\))?\r?$", text, re.M)
replay = gate.decode(data_by_name["original-probes/probe-results.json"])
assert replay["source_commit"] == CODE and replay["source_tree"] == TREE
assert len(replay["probes"]) == 20 and all(p["passed"] is True for p in replay["probes"])
empty = list(gate.evidence_lines(b""))
rejected = []
variants = {
    "negative_length": [empty[0].replace(" 0 ", " -1 ", 1), empty[1]],
    "empty_payload_chunk": [empty[0], "H09B_REPORT_CHUNK " + empty[0].split()[1] + " 1 eA==", empty[1]],
    "empty_wrong_digest": [s.replace(gate.sha(b""), "0" * 64) for s in empty],
    "empty_missing_end": empty[:1],
    "empty_duplicate_end": empty + empty[-1:],
}
for name, lines in variants.items():
    try:
        gate.decode_log(lines)
    except ValueError:
        rejected.append(name)
    else:
        raise AssertionError(name)
summary = {"handoff_commit": HANDOFF, "reviewed_source": CODE, "source_tree": TREE,
           "raw_files": files, "author_test_counts_verified": expected_runs,
           "linux_report_only": True, "author_replay": "20/20",
           "independent_empty_frame_negative_probes": rejected,
           "unknown_author_scripts_executed": False,
           "hosted_windows_acceptance": "pending"}
OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"raw_files_matched": len(files), "negative_probes_rejected": len(rejected),
                  "hosted_windows_acceptance": "pending"}))
