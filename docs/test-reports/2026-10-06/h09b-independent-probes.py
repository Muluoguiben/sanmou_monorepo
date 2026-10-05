"""Bounded independent probes; synthetic reports are NOT native CLI evidence."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

SOURCE = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(exist_ok=True)
EXPECTED = "f961c1594018651d584bbe622547a79e5648c5a7"
head = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
assert head == EXPECTED
spec = importlib.util.spec_from_file_location("author_fixture", SOURCE / "packages/pioneer-agent/tests/test_windows_task_eval_ci.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
gate = fixture.gate
rows = []

def check(name, action, reject=False):
    try:
        result = action()
    except Exception as exc:
        rows.append({"name": name, "expected_rejection": reject, "passed": reject,
                     "error": type(exc).__name__ + ":" + str(exc)[:160]})
    else:
        rows.append({"name": name, "expected_rejection": reject, "passed": not reject})

check("native_local_checkout_physical", lambda: gate.local_windows_path(str(SOURCE)))
raw = b"x" * gate.MAX_REPORT
lines = list(gate.evidence_lines(raw))
check("max_report_roundtrip_with_ci_timestamps", lambda: gate.exact(gate.decode_log([
    "2026-10-06T12:34:56.1234567Z " + line + "\n" for line in lines]), raw, "bytes"))
for name, bad in (
    ("truncated_last_payload", lines[:-2] + [lines[-2][:-4], lines[-1]]),
    ("wrong_digest", [lines[0].replace(gate.sha(raw), "0" * 64)] + lines[1:]),
    ("mixed_second_frame", lines + list(gate.evidence_lines(b"other"))),
    ("chunk_after_end", lines + [lines[1]]),
    ("unexpected_marker", lines[:1] + ["H09B_REPORT_UNKNOWN"] + lines[1:]),
    ("no_begin", lines[1:]),
    ("no_end", lines[:-1]),
    ("duplicate_chunk", lines[:2] + [lines[1]] + lines[2:]),
    ("swapped_chunks", lines[:1] + [lines[2], lines[1]] + lines[3:]),
):
    check(name, lambda bad=bad: gate.decode_log(bad), reject=True)
check("empty_report_evidence_roundtrip", lambda: gate.exact(
    gate.decode_log(list(gate.evidence_lines(b""))), b"", "empty"))

def synthetic(name, mutate, reject=True):
    test = fixture.WindowsTaskEvalCITests()
    test.setUp()
    try:
        mutate(test)
        test.save_artifacts()
        check(name, test.validate, reject)
    finally:
        test.doCleanups()

synthetic("aggregate_green_case_false", lambda t: t.report["cases"][0]["score"].update(control_pass=False))
synthetic("checkpoint_authority_drift", lambda t: t.report["cases"][0]["actual"]["checkpoint"]["state"].update(execution_authority="execute"))
synthetic("nested_boolean_model_limit", lambda t: t.report["cases"][0]["actual"]["phases"][0]["budget_snapshot"]["limits"].update(max_model_attempts=False))
synthetic("phase_budget_pending_boolean", lambda t: t.report["cases"][0]["actual"]["phases"][0]["budget"].update(pending=False))
synthetic("linux_report", lambda t: t.report["environment"].update(platform="Linux-6.8"))
synthetic("source_tree_drift", lambda t: t.report["source"].update(tree="c" * 40))
synthetic("holdout_drift", lambda t: t.report["suite"].update(independent_holdout=True))

def empty_report_process():
    test = fixture.WindowsTaskEvalCITests()
    test.setUp()
    try:
        original = test.save_artifacts
        def empty():
            original()
            (test.output / "report.json").write_bytes(b"")
        test.save_artifacts = empty
        code, log, _ = test.orchestration()
        (OUT / "empty-report-original.log").write_text(log, encoding="utf-8")
        assert code == 1, "empty report falsely passed"
        gate.exact(gate.decode_log(log.splitlines()), b"", "retained_empty_report")
    finally:
        test.doCleanups()
check("mock_exit_zero_empty_report_retention", empty_report_process)
metadata = {"source_commit": head, "source_tree": subprocess.check_output([
    "git", "-C", str(SOURCE), "rev-parse", "HEAD^{tree}"], text=True).strip(),
    "checker_sha256": hashlib.sha256((SOURCE / "scripts/check_windows_task_eval.py").read_bytes()).hexdigest(),
    "python": sys.version, "executable": sys.executable, "os_name": os.name,
    "evidence_class": "native stdlib + synthetic checker probes, NOT actual evaluator CLI",
    "probes": rows}
(OUT / "probe-results.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source": head, "passed": sum(r["passed"] for r in rows),
                  "total": len(rows), "failed": [r for r in rows if not r["passed"]]}))
