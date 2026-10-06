"""Read only final H10a plain Git blobs and explicit fresh JSON outputs."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

HANDOFF = "b8ef01a7f777c1232f0f62639794fe256d478746"
CODE = "9e6a8bd7ec1b72318c0bd00637be4b92f3483aa8"
TREE = "83fae646d1d89ae16b65de99eff2e41a86df8a28"
PREFIX = "docs/test-reports/2026-10-06/h10a-selftest/"
ROOT = PREFIX + "results-9e6a8bd/"
OWN = Path("/tmp/h10a-cr-9e6a8bd-results")


def blob(path):
    assert path.startswith(PREFIX) and Path(path).suffix in {".json", ".jsonl", ".log", ".py"}
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C",
        "/home/lan/projects/sanmou_monorepo", "show", HANDOFF + ":" + path])


summary_raw = blob(ROOT + "summary.json")
summary = json.loads(summary_raw)
assert (summary["source"], summary["tree"], summary["failures"]) == (CODE, TREE, [])
assert hashlib.sha256(blob(PREFIX + "verify.py")).hexdigest() == summary["verifier_sha256"]
observed = {}
for command in summary["commands"]:
    raw = blob(ROOT + command["log"])
    assert len(raw) == command["log_bytes"]
    assert hashlib.sha256(raw).hexdigest() == command["log_sha256"]
    assert command["exit"] == 0
    if command["tests"] is not None:
        assert re.search(rb"Ran " + str(command["tests"]).encode() + rb" tests? in ", raw)
        assert b"\nOK" in raw and b"\nFAILED" not in raw
        if command["skipped"]:
            assert ("OK (skipped=%d)" % command["skipped"]).encode() in raw
        else:
            assert b"... skipped " not in raw
    observed[command["name"]] = {key: command[key] for key in ("tests", "skipped", "exit")}
own_source = json.loads((OWN / "source.json").read_text())
assert all(own_source["probe_sha256"][name] == value for name, value in summary["independent_inputs"].items())
h09 = summary["results"]["h09"]
assert h09["raw_path"] == "/tmp/h10a-9e6a8bd-results/h09-cli/report.json"
raw = Path(h09["raw_path"]).read_bytes()
assert len(raw) == h09["raw_bytes"] and hashlib.sha256(raw).hexdigest() == h09["raw_sha256"]
report = json.loads(raw)
assert report["source_verified"] and CODE in json.dumps(report["source"]) and TREE in json.dumps(report["source"])
assert report["stable_projection"] == json.loads((OWN / "h09-cli/report.json").read_text())["stable_projection"]
qa = summary["results"]["qa_v3"]
assert qa["raw_path"] == "/tmp/h10a-9e6a8bd-results/qa-v3.json"
raw = Path(qa["raw_path"]).read_bytes()
assert raw == (OWN / "qa-v3.json").read_bytes() and hashlib.sha256(raw).hexdigest() == qa["sha256"]
sample = summary["results"]["sample_v2"]
raw = blob(ROOT + sample["file"])
assert len(raw) == sample["bytes"] and hashlib.sha256(raw).hexdigest() == sample["sha256"]
rows = [json.loads(line) for line in raw.splitlines()]
seen = {}
for row in rows:
    assert row["trace_version"] == 2 and row["event_id"] not in seen
    if row["event"] == "lifetime_start":
        assert row["parent_event_id"] is None and row["lifetime_id"] == row["event_id"]
    else:
        parent = seen[row["parent_event_id"]]
        assert parent["run_id"] == row["run_id"] and parent["lifetime_id"] == row["lifetime_id"]
    if row["window_id"] and row["event"] != "window_start":
        assert seen[row["window_id"]]["event"] == "window_start"
        if row["parent_event_id"] != row["lifetime_id"]:
            assert seen[row["parent_event_id"]]["window_id"] == row["window_id"]
    seen[row["event_id"]] = row
counts = Counter(row["event"] for row in rows)
assert len(rows) == sample["events"] == 27
assert (counts["window_start"], counts["tool"], counts["policy"], counts["observation"]) == (3, 12, 3, 3)
tools = [row for row in rows if row["event"] == "tool"]
policies = [row for row in rows if row["event"] == "policy"]
assert [row["name"] for row in tools] == ["session_status", "observe_game", "get_runtime_state", "list_action_candidates"] * 3
assert [row["observation_id"] for row in policies] == ["obs-1", "obs-2", "obs-3"]
assert len({row["invocation_id"] for row in tools + policies}) == 15
assert all(row["attempt_id"] is None and row["usage"] is None for row in policies)
assert all(row["provenance"]["model"]["status"] == "absent" for row in policies)
assert len({row["provenance"]["context_digest"] for row in policies}) == 3
assert sample["ledger_counts"] == {"step": 3, "tool": 12, "model": 0}
assert (sample["execution_authority"], sample["executable"]) == ("none", False)
print(json.dumps({"handoff": HANDOFF, "source": CODE, "tree": TREE,
    "summary_sha256": hashlib.sha256(summary_raw).hexdigest(), "verified_logs": observed,
    "h09_source_and_stable_equal": True, "qa_v3_bytes_equal": True,
    "frozen_input_hashes_equal": True, "sample_counts": dict(counts),
    "sample_graph_and_invocations_valid": True, "archive_reads": 0,
    "native_h10": "not_executed"}, indent=2))
