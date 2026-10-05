"""Retarget immutable reviewer orchestration, never patch QA implementation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
OLD = OUT.with_name("Q02a-CR-artifacts")
ORIGINAL = "eb895ae4e149a38d65789c19c7e4aebdee0c3c1a"
CODE = "40f46d3ea4525639877ad37a8da4ab6e334523e6"
TREE = "1351c2432adb0a638997ab9faff7bb22725fba4f"
spec = importlib.util.spec_from_file_location("q02a_review_orchestration", OLD / "verify_frozen.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.CODE, m.TREE, m.OUT = CODE, TREE, OUT
_original_verify_blobs = m.verify_blobs

def verify_repair_blobs(root, names, commit=None):
    # The original function's definition-time default is the old code SHA.
    return _original_verify_blobs(root, names, commit=CODE if commit is None else commit)

m.verify_blobs = verify_repair_blobs

def sha(data):
    return hashlib.sha256(data).hexdigest()

def validate_original_assets():
    hashes = {}
    for name in ("guarded_run.py", "test_q02a_contract.py", "test_q02a_adversarial.py", "grammar.json", "verify_frozen.py"):
        original = m.git("show", ORIGINAL + ":docs/test-reports/2026-10-06/Q02a-CR-artifacts/" + name)
        actual = (OLD / name).read_bytes()
        if original != actual:
            raise RuntimeError("original reviewer asset bytes changed: " + name)
        hashes[name] = sha(actual)
    return hashes

def configure_execution():
    root = m.snapshot_root()
    # Absolute paths propagate to official MCP subprocesses, unlike sys.path-only injection.
    m.ENV["PYTHONPATH"] = ":".join(map(str, [root / "packages/qa-agent/src", root / "packages/qa-agent/tests",
        root / "packages/qa-agent", root / "packages/sanmou-common/src", root / "packages/pioneer-agent/src",
        root / "packages/pioneer-agent/tests/unit", Path("/tmp/sanmou-cr-20261005-6155-deps"), OUT]))
    m.guarded = lambda *args: [m.PY, "-B", str(OLD / "guarded_run.py"), str(root), *args]

def main():
    if m.git("rev-parse", CODE + "^{tree}").decode().strip() != TREE:
        raise RuntimeError("unexpected fixed repair tree")
    hashes = validate_original_assets()
    phase = sys.argv[1]
    if phase == "snapshot":
        m.main()
        m.emit("probe-identity.json", dict(original_commit=ORIGINAL, raw_bytes_equal=True, sha256=hashes,
            new_code=CODE, new_tree=TREE, implementation_globals_patched=False))
        return
    configure_execution()
    if phase == "focused":
        m.run("original-independent-26", m.guarded("test_q02a_contract", "test_q02a_adversarial", "-v"))
        m.run("new-repair-scope", m.guarded("test_repair_scope", "-v"))
        m.run("repair-focused", m.guarded("test_referent_resolution", "test_evidence_assessment", "test_quality_eval",
            "test_review_d_regressions.ChatGroundingRegressionTests", "-v"))
    elif phase in {"full", "cross", "eval", "provenance"}:
        m.main()
    elif phase == "author-history":
        report = "005fce84f1eaff4e60a0e04f838c908a9e8da6ae"
        changed = m.git("diff", "--name-only", CODE, report).decode().splitlines()
        if any(not p.startswith("docs/") for p in changed):
            raise RuntimeError("author report successor changed non-doc source")
        prefix = "docs/test-reports/2026-10-06/Q02a-repair-artifacts/"
        blobs = {name: m.git("show", report + ":" + prefix + name) for name in
            ("red.log", "copy-correction.json", "probe-provenance.json", "full-first.log", "full-final.log")}
        m.emit("author-evidence-reference.json", dict(report_commit=report,
            report_tree=m.git("rev-parse", report + "^{tree}").decode().strip(),
            docs_only=True, changed_paths=changed, source_code=CODE,
            blob_sha256={name:sha(blob) for name,blob in blobs.items()},
            first_full_has_missing_qa_agent=b"No module named 'qa_agent'" in blobs["full-first.log"],
            first_full_records_394=b"Ran 394 tests" in blobs["full-first.log"],
            final_full_records_394=b"Ran 394 tests" in blobs["full-final.log"],
            author_outputs_used_as_independent_pass=False))
    elif phase == "integrity":
        info = json.loads((OUT / "snapshot.json").read_text())
        m.verify_blobs(m.snapshot_root(), info["files"])
        if m.git("diff", m.BASE, CODE, "--", "packages/qa-agent/tests/fixtures/quality_eval/v1",
                "packages/qa-agent/tests/fixtures/quality_eval/v2", "docs/test-reports/2026-10-05"):
            raise RuntimeError("prior frozen evidence changed")
        if m.git("diff", "f3cd9b8814fc085d567063ab23e6576b9c24525f", CODE, "--",
                "packages/qa-agent/tests/fixtures/quality_eval/v3/cases.json"):
            raise RuntimeError("v3 case bytes changed")
        if m.git("diff", ORIGINAL, "--", "docs/reviews/2026-10-06-Q02a-adversarial-review.md",
                "docs/test-reports/2026-10-06/Q02a-CR.md", "docs/test-reports/2026-10-06/Q02a-CR-artifacts"):
            raise RuntimeError("old independent red evidence changed")
        m.emit("integrity.json", dict(code_sha=CODE, code_tree=TREE, execution_root=str(m.snapshot_root()),
            post_test_blob_count=len(info["files"]), post_test_mismatches=0,
            original_probe_bytes_unchanged=True, old_red_evidence_unchanged=True,
            v1_v2_unchanged=True, v3_case_bytes_unchanged=True,
            artifacts={p.name:sha(p.read_bytes()) for p in sorted(OUT.iterdir()) if p.is_file()}))
    else:
        raise ValueError("unknown phase")

if __name__ == "__main__":
    main()
