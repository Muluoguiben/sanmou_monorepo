"""Source-bound Q02a CR; only immutable Git objects feed the execution tree."""
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
WIN_REPO = r"C:\Users\Lan\.codex\worktrees\qa-q03a-review-20261005\sanmou_monorepo"
GIT = "/mnt/c/Program Files/Git/cmd/git.exe"
CODE = "f3cd9b8814fc085d567063ab23e6576b9c24525f"
TREE = "b73cf4b49fc311d55b50b7caf56a7a7b2fb0b01e"
BASE = "e17d937a39944b036e90701fecefb6611b1d88d6"
PLAN = "0b9d514c1ffe76d85de209dc9f8802dcf2c2aba7"
PY = sys.executable
ENV = {k: os.environ[k] for k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if k in os.environ}
ENV.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH="src:../sanmou-common/src:tests:/tmp/sanmou-cr-20261005-6155-deps")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def git(*args, input=None):
    return subprocess.run([GIT, "-C", WIN_REPO, *args], input=input, capture_output=True, check=True).stdout

def emit(name, value):
    with (OUT / name).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")

def verify_blobs(root, names, commit=CODE):
    data = git("cat-file", "--batch", input="".join(commit + ":" + p + "\n" for p in names).encode())
    offset = 0
    for name in names:
        end = data.index(b"\n", offset)
        header = data[offset:end].decode().split()
        if len(header) != 3 or header[1] != "blob":
            raise RuntimeError("missing blob: " + name)
        size = int(header[2])
        blob = data[end + 1:end + 1 + size]
        offset = end + 1 + size + 1
        path = root / name
        actual = os.readlink(path).encode() if path.is_symlink() else path.read_bytes()
        if actual != blob:
            raise RuntimeError("source byte mismatch: " + name)

def snapshot_root():
    return Path(json.loads((OUT / "snapshot.json").read_text())["root"])

def run(name, command):
    root = snapshot_root()
    start = time.monotonic()
    result = subprocess.run(command, cwd=root / "packages/qa-agent", env=ENV,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with (OUT / (name + ".log")).open("xb") as stream:
        stream.write(result.stdout)
    record = dict(command=command, cwd=str(root / "packages/qa-agent"), execution_root=str(root),
        code_sha=CODE, code_tree=TREE, plan_commit=PLAN, exit_code=result.returncode,
        elapsed_s=time.monotonic() - start, log_sha256=sha(result.stdout))
    emit(name + ".json", record)
    print(json.dumps({k: record[k] for k in ("exit_code", "elapsed_s", "log_sha256")} | {"check": name}), flush=True)
    return result

def guarded(*args):
    return [PY, "-B", str(OUT / "guarded_run.py"), str(snapshot_root()), *args]

def main():
    if git("rev-parse", CODE + "^{tree}").decode().strip() != TREE:
        raise RuntimeError("unexpected code tree")
    phase = sys.argv[1]
    if phase == "snapshot":
        archive_args = ["-c", "core.autocrlf=false", "-c", "core.eol=lf", "archive", "--format=tar", CODE,
            ".", ":(exclude)packages/qa-agent/.env.example"]
        archive = git(*archive_args)
        root = Path(tempfile.mkdtemp(prefix="q02a-independent-"))
        with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
            if any(Path(m.name).name.lower().startswith(".env") for m in stream.getmembers()):
                raise RuntimeError("config unexpectedly in archive")
            stream.extractall(root, filter="data")
        names = [p.decode() for p in git("ls-tree", "-r", "-z", "--name-only", CODE).split(b"\0") if p]
        names = [p for p in names if p != "packages/qa-agent/.env.example"]
        verify_blobs(root, names)
        emit("snapshot.json", dict(root=str(root), code_sha=CODE, code_tree=TREE, verified_blob_count=len(names),
            blob_mismatches=0, archive_sha256=sha(archive), archive_command=[GIT, "-C", WIN_REPO, *archive_args],
            files=names, excluded_config="packages/qa-agent/.env.example", author_moving_tree_used=False))
    elif phase == "focused":
        run("independent-frozen-plan", guarded("test_q02a_contract", "-v"))
        run("independent-supplemental", guarded("test_q02a_adversarial", "-v"))
        run("author-focused-recheck", guarded("test_referent_resolution", "test_evidence_assessment", "test_quality_eval",
            "test_review_d_regressions.ChatGroundingRegressionTests", "-v"))
    elif phase == "full":
        run("qa-full", guarded("discover", "-s", "tests", "-p", "test_*.py", "-v"))
    elif phase == "cross":
        run("cross-advisor-api", guarded("test_advisor_api", "-v"))
    elif phase == "eval":
        for baseline in ("v3", "v1", "v2"):
            run(baseline + "-eval", [PY, "-B", "-m", "qa_agent.quality_eval.runner", "--baseline", baseline,
                "--output", str(OUT / (baseline + "-result.json"))])
    elif phase == "provenance":
        frozen = json.loads(git("show", CODE + ":packages/qa-agent/tests/fixtures/quality_eval/v3/freeze.json"))
        source = frozen["baseline_commit"]
        resolved = git("rev-parse", "--verify", source + "^{commit}").decode().strip()
        refs = [(area, name, expected) for area in ("kb", "production") for name, expected in sorted(frozen[area]["files"].items())]
        for commit in (source, CODE):
            data = git("cat-file", "--batch", input="".join(commit + ":packages/qa-agent/" + name + "\n" for _, name, _ in refs).encode())
            offset = 0
            for area, name, expected in refs:
                end = data.index(b"\n", offset)
                header = data[offset:end].decode().split()
                if len(header) != 3 or header[1] != "blob":
                    raise RuntimeError("source binding blob missing")
                size = int(header[2])
                body = data[end + 1:end + 1 + size]
                offset = end + 1 + size + 1
                if sha(body.decode("utf-8-sig").replace("\r\n", "\n").encode()) != expected:
                    raise RuntimeError("source commit/manifest mismatch: " + name)
        v2 = json.loads(git("show", BASE + ":packages/qa-agent/tests/fixtures/quality_eval/v2/cases.json"))
        v3 = json.loads(git("show", CODE + ":packages/qa-agent/tests/fixtures/quality_eval/v3/cases.json"))
        inherited = {k: v2[k] == v3[k] for k in ("queries", "top_k", "scoring_cases", "assessment_cases")}
        if not all(inherited.values()):
            raise RuntimeError("historical case semantics changed")
        emit("source-provenance.json", dict(code_sha=CODE, code_tree=TREE, source_commit=source,
            resolved_commit=resolved, manifest_entries=len(refs), compared_blobs=len(refs) * 2,
            mismatches=0, inherited_case_sections_equal=inherited,
            scope="Local source/blob evidence; runtime SHA string check is not Git authentication or a remote signature"))
    elif phase == "integrity":
        info = json.loads((OUT / "snapshot.json").read_text())
        verify_blobs(snapshot_root(), info["files"])
        protected = ["packages/qa-agent/tests/fixtures/quality_eval/v1", "packages/qa-agent/tests/fixtures/quality_eval/v2",
            "docs/reviews/2026-10-05-Q03a-adversarial-review.md", "docs/reviews/2026-10-05-Q03a-adversarial-recheck.md",
            "docs/test-reports/2026-10-05"]
        if git("diff", BASE, CODE, "--", *protected):
            raise RuntimeError("protected source history changed")
        for name in ("test_q02a_contract.py", "grammar.json", "preparation.json", "README.md"):
            old = git("show", PLAN + ":docs/test-reports/2026-10-06/Q02a-CR-artifacts/" + name)
            if (OUT / name).read_bytes() != old:
                raise RuntimeError("frozen plan asset changed: " + name)
        emit("integrity.json", dict(code_sha=CODE, code_tree=TREE, execution_root=str(snapshot_root()),
            post_test_blob_count=len(info["files"]), post_test_mismatches=0, protected_diff_empty=True,
            prepared_assets_unchanged=True, artifacts={p.name: sha(p.read_bytes()) for p in sorted(OUT.iterdir()) if p.is_file()}))
    else:
        raise ValueError("unknown phase")

if __name__ == "__main__":
    main()
