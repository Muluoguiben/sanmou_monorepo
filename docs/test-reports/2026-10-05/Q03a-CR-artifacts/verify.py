"""Local reviewer-only provenance runner; generated files use exclusive creation."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
WIN_ROOT = "C:\\Users\\Lan\\.codex\\worktrees\\qa-q03a-review-20261005\\sanmou_monorepo"
GIT = "/mnt/c/Program Files/Git/cmd/git.exe"
CODE = "3f81519d34063d438af918a3750bcc38a535b6b7"
TREE = "d165dda6ff9ba8c2fd39a604406b5cfee84449c5"
BASE = "f879915ab43aa9148496a17f5277725c8c913403"
QA = ROOT / "packages/qa-agent"
PY = sys.executable
ENV = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if key in os.environ}
ENV.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH="src:../sanmou-common/src:tests:/tmp/sanmou-cr-20261005-6155-deps")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def git(*args):
    return subprocess.run([GIT, "-C", WIN_ROOT, *args], capture_output=True, check=True).stdout

def emit(name, payload):
    with (OUT / name).open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        stream.write("\n")

def run(name, command, cwd=QA):
    before = git("rev-parse", "HEAD").decode().strip()
    if before != CODE:
        raise RuntimeError("source SHA changed before test")
    started = time.monotonic()
    result = subprocess.run(command, cwd=cwd, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - started
    with (OUT / (name + ".log")).open("xb") as stream:
        stream.write(result.stdout)
    record = dict(command=command, cwd=str(cwd), code_sha=before, tree=TREE,
                  exit_code=result.returncode, elapsed_s=elapsed, log_sha256=sha(result.stdout),
                  after_code_sha=git("rev-parse", "HEAD").decode().strip())
    emit(name + ".json", record)
    print(json.dumps({"name": name, "exit_code": result.returncode, "elapsed_s": elapsed,
                      "log_sha256": record["log_sha256"]}), flush=True)
    return result

def guarded(*args):
    return [PY, "-B", str(OUT / "guarded_tests.py"), *args]

def main():
    if git("rev-parse", "HEAD").decode().strip() != CODE or git("rev-parse", "HEAD^{tree}").decode().strip() != TREE:
        raise RuntimeError("unexpected review input")
    phase = sys.argv[1]
    if phase == "focused":
        run("independent-initial", guarded("test_independent_q03a", "-v"))
        run("author-focused-recheck", guarded("test_evidence_assessment", "test_quality_eval",
            "test_review_d_regressions.ChatGroundingRegressionTests", "-v"))
    elif phase == "full":
        result = run("qa-full-original-format", guarded("discover", "-s", "tests", "-p", "test_*.py", "-v"))
        if result.returncode:
            target = ROOT / "scripts/bilibili_video_knowledge_workflow.sh"
            original = target.read_bytes()
            canonical = git("show", CODE + ":scripts/bilibili_video_knowledge_workflow.sh")
            if original.replace(b"\r\n", b"\n") != canonical:
                raise RuntimeError("script is not a pure CRLF presentation of frozen Git source")
            emit("format-verification.json", dict(path=str(target), original_sha256=sha(original),
                canonical_sha256=sha(canonical), normalized_equals_git=True,
                git_blob=git("rev-parse", CODE + ":scripts/bilibili_video_knowledge_workflow.sh").decode().strip()))
            try:
                target.write_bytes(canonical)
                run("qa-full-canonical-lf", guarded("discover", "-s", "tests", "-p", "test_*.py", "-v"))
            finally:
                target.write_bytes(original)
                if target.read_bytes() != original:
                    raise RuntimeError("original checkout formatting not restored")
    elif phase in {"full-final", "full-verified"}:
        target = ROOT / "scripts/bilibili_video_knowledge_workflow.sh"
        original = target.read_bytes()
        canonical = git("show", CODE + ":scripts/bilibili_video_knowledge_workflow.sh")
        if original.replace(b"\r\n", b"\n") != canonical:
            raise RuntimeError("script is not a pure CRLF presentation of frozen Git source")
        suffix = "verified" if phase == "full-verified" else "final"
        emit("format-verification-" + suffix + ".json", dict(path=str(target), original_sha256=sha(original),
            canonical_sha256=sha(canonical), normalized_equals_git=True,
            git_blob=git("rev-parse", CODE + ":scripts/bilibili_video_knowledge_workflow.sh").decode().strip(),
            launcher_correction="QA root import path; audit-hook credential guard preserves os.open capability identity; prior logs retained"))
        try:
            target.write_bytes(canonical)
            run("qa-full-" + suffix + "-canonical-lf", guarded("discover", "-s", "tests", "-p", "test_*.py", "-v"))
        finally:
            target.write_bytes(original)
            if target.read_bytes() != original:
                raise RuntimeError("original checkout formatting not restored")
    elif phase == "provenance":
        frozen = json.loads((QA / "tests/fixtures/quality_eval/v2/freeze.json").read_text(encoding="utf-8-sig"))
        baseline = frozen["baseline_commit"]
        resolved = git("rev-parse", "--verify", baseline + "^{commit}").decode().strip()
        refs = [(area, path, expected) for area in ("kb", "production")
                for path, expected in sorted(frozen[area]["files"].items())]
        batch = "".join(baseline + ":packages/qa-agent/" + path + "\n" for _, path, _ in refs).encode()
        output = subprocess.run([GIT, "-C", WIN_ROOT, "cat-file", "--batch"], input=batch,
            capture_output=True, check=True).stdout
        cursor = 0
        mismatches = []
        for area, path, expected in refs:
            end = output.index(b"\n", cursor)
            header = output[cursor:end].decode().split()
            if len(header) != 3 or header[1] != "blob":
                raise RuntimeError("missing source blob")
            size = int(header[2])
            body = output[end + 1:end + 1 + size]
            cursor = end + 1 + size + 1
            actual = sha(body.decode("utf-8-sig").replace("\r\n", "\n").encode())
            if actual != expected:
                mismatches.append(dict(area=area, path=path, expected=expected, actual=actual))
        if mismatches:
            raise RuntimeError(mismatches)
        before = json.loads((QA / "tests/fixtures/quality_eval/v1/cases.json").read_text(encoding="utf-8-sig"))
        after = json.loads((QA / "tests/fixtures/quality_eval/v2/cases.json").read_text(encoding="utf-8-sig"))
        emit("source-provenance.json", dict(reviewed_code=CODE, reviewed_tree=TREE,
            frozen_baseline_commit=baseline, resolved_commit=resolved,
            verified_blob_count=len(refs), mismatches=mismatches,
            inherited_queries_equal=before["queries"] == after["queries"],
            inherited_scoring_equal=before["scoring_cases"] == after["scoring_cases"],
            inherited_top_k_equal=before["top_k"] == after["top_k"],
            limitation="Independent local Git blob verification, not performed by production eval runner; no remote signature claim"))
    elif phase == "cross":
        run("cross-advisor-api", guarded("test_advisor_api", "-v"), ROOT / "packages/pioneer-agent")
    elif phase == "extra":
        run("extra-boundaries", guarded("test_q03a_extra.ApplicabilityBoundaryTests", "-v"))
        run("mixed-import-roots", [PY, "-B", str(OUT / "mixed_import_probe.py")])
    elif phase == "eval":
        run("v2-eval", [PY, "-B", "-m", "qa_agent.quality_eval.runner", "--baseline", "v2",
            "--output", str(OUT / "v2-result.json")])
        run("v1-expected-drift", [PY, "-B", "-m", "qa_agent.quality_eval.runner", "--baseline", "v1",
            "--output", str(OUT / "v1-must-not-exist.json")])
    elif phase in {"integrity", "integrity-final"}:
        import importlib.metadata
        import platform
        protected = ["packages/qa-agent/tests/fixtures/quality_eval/v1",
            "docs/test-reports/2026-10-05/C.md", "docs/test-reports/2026-10-05/C-artifacts",
            "docs/test-reports/2026-10-05/CR.md", "docs/test-reports/2026-10-05/CR-artifacts",
            "docs/test-reports/2026-10-05/integration.md", "docs/test-reports/2026-10-05/integration-artifacts"]
        unchanged = git("diff", BASE, "--", *protected)
        production = git("diff", CODE, "--", "packages", "scripts")
        if unchanged or production:
            raise RuntimeError("protected or production source changed")
        emit(phase + ".json", dict(code_sha=CODE, tree=TREE, protected_paths=protected,
            protected_diff_empty=True, production_diff_empty=True,
            python=sys.version, platform=platform.platform(),
            dependencies={name: importlib.metadata.version(name) for name in ("pydantic", "PyYAML", "mcp")},
            branch=git("branch", "--show-current").decode().strip(),
            status=git("status", "--short").decode(),
            hashes={p.name: sha(p.read_bytes()) for p in sorted(OUT.iterdir()) if p.is_file()}))
    else:
        raise ValueError("unknown phase")

if __name__ == "__main__":
    main()
