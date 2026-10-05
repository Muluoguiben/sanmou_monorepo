"""Independent repair review. Never edits the frozen author worktree."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time

OUT = Path(__file__).resolve().parent
CR = OUT.parents[3]
DEV = Path("/mnt/c/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo")
WIN_DEV = r"C:\Users\Lan\.codex\worktrees\qa-evidence-q03-20261005\sanmou_monorepo"
WIN_CR = r"C:\Users\Lan\.codex\worktrees\qa-q03a-review-20261005\sanmou_monorepo"
GIT = "/mnt/c/Program Files/Git/cmd/git.exe"
CODE = "3b2b137679bd6b72a5681874bf9ab6ea0ac8f0c9"
TREE = "ec1d8f04ff42156c90a151b4d0e4c3fbddf765c6"
HEAD = "3986047adafa6a5334bc7a27a055d0800ddf259d"
OLD_CR = "a10472972de2e6a5fca675b363f086ab1372e003"
PROBE_REL = "docs/test-reports/2026-10-05/Q03a-repair-artifacts"
PROBES = ("mixed_import_probe.py", "test_independent_q03a.py", "test_q03a_extra.py")
PY = sys.executable
ENV = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ}
ENV.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH="src:../sanmou-common/src:tests:/tmp/sanmou-cr-20261005-6155-deps")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def git(*args, cr=False, input=None):
    return subprocess.run([GIT, "-C", WIN_CR if cr else WIN_DEV, *args], input=input,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout

def emit(name, payload):
    with (OUT / name).open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

def check_source():
    actual = git("rev-parse", "HEAD").decode().strip()
    if actual != HEAD or git("rev-parse", CODE + "^{tree}").decode().strip() != TREE:
        raise RuntimeError("frozen author source moved")
    changed = git("diff", "--name-only", CODE, HEAD).decode().splitlines()
    if any(not p.startswith("docs/") for p in changed):
        raise RuntimeError("report successor changed production")
    if git("diff", HEAD, "--", "packages", "scripts"):
        raise RuntimeError("author production has uncommitted changes")
    return actual

def run(name, command, root=DEV):
    before = check_source()
    started = time.monotonic()
    result = subprocess.run(command, cwd=root / "packages/qa-agent", env=ENV,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - started
    with (OUT / (name + ".log")).open("xb") as stream:
        stream.write(result.stdout)
    emit(name + ".json", dict(command=command, cwd=str(root / "packages/qa-agent"),
        execution_root=str(root), reviewed_code=CODE, reviewed_tree=TREE,
        author_head_before=before, author_head_after=check_source(),
        exit_code=result.returncode, elapsed_s=elapsed, log_sha256=sha(result.stdout)))
    print(json.dumps(dict(name=name, exit_code=result.returncode, elapsed_s=elapsed,
        log_sha256=sha(result.stdout))), flush=True)
    return result

def guarded(root, *args):
    return [PY, "-B", str(OUT / "guarded_recheck.py"), str(root), *args]

def provenance():
    check_source()
    copied = {}
    for name in PROBES:
        original = git("show", OLD_CR + ":docs/test-reports/2026-10-05/Q03a-CR-artifacts/" + name, cr=True)
        actual = (DEV / PROBE_REL / name).read_bytes()
        if original != actual:
            raise RuntimeError("original/copy probe byte mismatch: " + name)
        copied[name] = sha(actual)
    qa = DEV / "packages/qa-agent"
    frozen = json.loads((qa / "tests/fixtures/quality_eval/v2/freeze.json").read_text(encoding="utf-8-sig"))
    source_commit = frozen["baseline_commit"]
    resolved = git("rev-parse", "--verify", source_commit + "^{commit}").decode().strip()
    refs = [(area, p, h) for area in ("kb", "production") for p, h in sorted(frozen[area]["files"].items())]
    data = git("cat-file", "--batch", input="".join(source_commit + ":packages/qa-agent/" + p + "\n" for _, p, _ in refs).encode())
    offset = 0
    for area, path, expected in refs:
        end = data.index(b"\n", offset)
        header = data[offset:end].decode().split()
        if len(header) != 3 or header[1] != "blob":
            raise RuntimeError("missing source blob")
        size = int(header[2])
        blob = data[end + 1:end + 1 + size]
        offset = end + 1 + size + 1
        if sha(blob.decode("utf-8-sig").replace("\r\n", "\n").encode()) != expected:
            raise RuntimeError("manifest/source mismatch: " + path)
    old = json.loads(git("show", "3f81519d34063d438af918a3750bcc38a535b6b7:packages/qa-agent/tests/fixtures/quality_eval/v2/freeze.json"))
    changes = [p for p in set(old["production"]["files"]) | set(frozen["production"]["files"])
        if old["production"]["files"].get(p) != frozen["production"]["files"].get(p)]
    emit("provenance.json", dict(reviewed_code=CODE, reviewed_tree=TREE,
        actual_author_head=HEAD, actual_author_tree=git("rev-parse", "HEAD^{tree}").decode().strip(),
        report_only_paths=git("diff", "--name-only", CODE, HEAD).decode().splitlines(),
        author_status=git("status", "--short").decode(), probe_sha256=copied,
        baseline_commit=source_commit, resolved_commit=resolved, manifest_blob_count=len(refs),
        manifest_mismatches=0, production_digest=frozen["production"]["digest"],
        production_changed_paths=changes, kb_unchanged=old["kb"] == frozen["kb"],
        cases_hash_unchanged=old["cases_sha256"] == frozen["cases_sha256"],
        limitation="Local commit/blob check; runtime commit label remains format-only"))

def main():
    mode = sys.argv[1]
    check_source()
    if mode == "provenance":
        provenance()
    elif mode == "targeted":
        run("original-independent-replay", guarded(DEV, "test_independent_q03a", "test_q03a_extra.ApplicabilityBoundaryTests", "-v"))
        run("repair-focused", guarded(DEV, "test_evidence_assessment", "test_quality_eval", "test_review_d_regressions.ChatGroundingRegressionTests", "-v"))
        run("new-lazy-and-scope-negatives", guarded(DEV, "test_repair_boundaries", "-v"))
        result = run("mixed-import-original-probe", [PY, "-B", str(DEV / PROBE_REL / "mixed_import_probe.py")])
        text = result.stdout.decode()
        rejected = result.returncode != 0 and "ValueError: QA execution source mismatch" in text and '"claimed_production_digest"' not in text and "REPRODUCED: v2 accepted" not in text
        emit("mixed-import-interpretation.json", dict(expected_rejection=rejected,
            child_exit=result.returncode, explicit_source_mismatch="ValueError: QA execution source mismatch" in text,
            returned_wrong_identity='"claimed_production_digest"' in text))
        if not rejected:
            raise RuntimeError("mixed-root original probe did not reject correctly")
    elif mode == "cross":
        run("cross-advisor-api", guarded(DEV, "test_advisor_api", "-v"))
    elif mode == "eval":
        run("v2-eval", [PY, "-B", "-m", "qa_agent.quality_eval.runner", "--baseline", "v2", "--output", str(OUT / "v2-result.json")])
        run("v1-expected-drift", [PY, "-B", "-m", "qa_agent.quality_eval.runner", "--output", str(OUT / "v1-must-not-exist.json")])
    elif mode in {"full", "full-complete"}:
        paths = (["."] if mode == "full-complete" else ["packages", "scripts"]) + [":(exclude)packages/qa-agent/.env.example"]
        archive_args = ["-c", "core.autocrlf=false", "-c", "core.eol=lf", "archive", "--format=tar", CODE, *paths]
        archive = git(*archive_args)
        root = Path(tempfile.mkdtemp(prefix="q03a-cr-recheck-"))
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            if any(Path(m.name).name.lower().startswith(".env") for m in stream.getmembers()):
                raise RuntimeError("config unexpectedly included in archive")
            stream.extractall(root, filter="data")
        # Verify every extracted regular file against its exact immutable Git blob.
        files = sorted(p for p in root.rglob("*") if p.is_file() or p.is_symlink())
        refs = [p.relative_to(root).as_posix() for p in files]
        data = git("cat-file", "--batch", input="".join(CODE + ":" + p + "\n" for p in refs).encode())
        offset = 0
        for path, name in zip(files, refs):
            end = data.index(b"\n", offset)
            header = data[offset:end].decode().split()
            if len(header) != 3 or header[1] != "blob":
                raise RuntimeError("archive contains non-blob")
            size = int(header[2])
            blob = data[end + 1:end + 1 + size]
            offset = end + 1 + size + 1
            actual = os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
            if actual != blob:
                raise RuntimeError("archive blob mismatch: " + name)
        identity_name = "archive-full-identity.json" if mode == "full-complete" else "archive-identity.json"
        emit(identity_name, dict(root=str(root), code=CODE, tree=TREE,
            archive_command=[GIT, "-C", WIN_DEV, *archive_args],
            archive_sha256=sha(archive), verified_file_count=len(files),
            verified_symlink_count=sum(p.is_symlink() for p in files), blob_mismatches=0,
            excluded_config="packages/qa-agent/.env.example", reviewer_source_edit=False))
        run("qa-full-complete-snapshot" if mode == "full-complete" else "qa-full-ext4-snapshot",
            guarded(root, "discover", "-s", "tests", "-p", "test_*.py", "-v"), root=root)
        if any(p.read_bytes() != git("show", CODE + ":" + p.relative_to(root).as_posix()) for p in (root / "packages/qa-agent/src/qa_agent/chat/agent.py", root / "packages/qa-agent/src/qa_agent/chat/evidence_assessment.py")):
            raise RuntimeError("tested production changed")
    elif mode == "integrity":
        protected = ["packages/qa-agent/tests/fixtures/quality_eval/v1", "packages/qa-agent/tests/fixtures/quality_eval/v2/cases.json",
            "docs/test-reports/2026-10-05/C.md", "docs/test-reports/2026-10-05/C-artifacts", "docs/test-reports/2026-10-05/CR.md", "docs/test-reports/2026-10-05/CR-artifacts",
            "docs/test-reports/2026-10-05/integration.md", "docs/test-reports/2026-10-05/integration-artifacts"]
        if git("diff", "3f81519d34063d438af918a3750bcc38a535b6b7", "--", *protected):
            raise RuntimeError("protected author artifacts changed")
        if git("diff", OLD_CR, "--", "docs/reviews/2026-10-05-Q03a-adversarial-review.md", "docs/test-reports/2026-10-05/Q03a-CR.md", "docs/test-reports/2026-10-05/Q03a-CR-artifacts", cr=True):
            raise RuntimeError("old independent red evidence changed")
        snapshot_root = Path(json.loads((OUT / "archive-full-identity.json").read_text())["root"])
        tracked = [p.decode() for p in git("ls-tree", "-r", "-z", "--name-only", CODE).split(b"\0") if p]
        tracked = [p for p in tracked if p != "packages/qa-agent/.env.example"]
        data = git("cat-file", "--batch", input="".join(CODE + ":" + p + "\n" for p in tracked).encode())
        offset = 0
        for name in tracked:
            end = data.index(b"\n", offset)
            header = data[offset:end].decode().split()
            if len(header) != 3 or header[1] != "blob":
                raise RuntimeError("unsupported snapshot object")
            size = int(header[2])
            blob = data[end + 1:end + 1 + size]
            offset = end + 1 + size + 1
            path = snapshot_root / name
            actual = os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
            if actual != blob:
                raise RuntimeError("post-test snapshot changed: " + name)
        emit("integrity.json", dict(actual_author_head=check_source(), reviewed_code=CODE, reviewed_tree=TREE,
            protected_author_diff_empty=True, original_CR_evidence_diff_empty=True,
            post_test_snapshot_root=str(snapshot_root), post_test_blob_count=len(tracked), post_test_mismatches=0,
            author_status=git("status", "--short").decode(),
            artifacts={p.name:sha(p.read_bytes()) for p in sorted(OUT.iterdir()) if p.is_file()}))
    else:
        raise ValueError("unknown phase")

if __name__ == "__main__":
    main()
