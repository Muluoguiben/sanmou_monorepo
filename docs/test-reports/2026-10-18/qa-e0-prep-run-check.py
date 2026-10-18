"""Source-bound, create-only plain evidence for Q-E0 offline review commands."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
FIXED = "81c4a315d36e08979c76f1b9395045ed75cd3e76"
tag, *args = sys.argv[1:]
assert re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", tag)
out = Path(__file__).with_name("qa-e0-prep-independent-results")
out.mkdir(exist_ok=True)
log, metadata_path = out / (tag + ".log"), out / (tag + ".json")
assert not log.exists() and not metadata_path.exists()
gitdir = (ROOT / ".git").read_text(encoding="utf-8").strip().removeprefix("gitdir: ")
if gitdir.lower().startswith("//wsl$/ubuntu/"):
    gitdir = "/" + gitdir[len("//wsl$/ubuntu/"):]
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-c", "core.filemode=false",
        "--git-dir=" + gitdir, "--work-tree=" + str(ROOT), *args])
source = git("rev-parse", "HEAD").decode().strip()
tree = git("rev-parse", "HEAD^{tree}").decode().strip()
packages_tree = git("rev-parse", "HEAD:packages").decode().strip()
assert packages_tree == git("rev-parse", FIXED + ":packages").decode().strip()
allowed = {
    "packages/qa-agent/scripts/prepare_e0_review.py",
    "packages/qa-agent/tests/test_prepare_e0_review.py",
    "packages/qa-agent/tests/fixtures/quality_eval/e0_review_prep_v1/freeze.json",
    "packages/qa-agent/tests/fixtures/quality_eval/e0_review_prep_v1/synthetic.json",
}
assert set(git("diff", "--name-only", "88bd5a0", FIXED, "--", "packages", ".github").decode().splitlines()) == allowed
checked = 0
for row in git("ls-files", "-s", "-z", "--", "packages/qa-agent", "scripts/bilibili_video_knowledge_workflow.sh").split(b"\0"):
    if not row:
        continue
    header, name = row.split(b"\t", 1)
    path = name.decode()
    mode, oid, stage = header.decode().split()
    if mode not in {"100644", "100755"} or Path(path).suffix not in {".py", ".json", ".yaml", ".yml", ".sh", ".toml"}:
        continue
    raw = (ROOT / path).read_bytes()
    assert hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == oid, path
    checked += 1
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = os.pathsep.join(str(ROOT / path) for path in
    ("packages/qa-agent/src", "packages/qa-agent/tests", "packages/sanmou-common/src", "packages/pioneer-agent/src"))
cwd = (ROOT / env.get("QE0_CHECK_CWD", ".")).resolve()
assert cwd.is_relative_to(ROOT) and cwd.is_dir()
argv = [sys.executable, "-B", "-W", "error::RuntimeWarning", *args]
timed_out = False
with log.open("xb") as stream:
    try:
        code = subprocess.run(argv, cwd=cwd, env=env, stdout=stream,
            stderr=subprocess.STDOUT, timeout=300).returncode
    except subprocess.TimeoutExpired:
        timed_out, code = True, 124
raw = log.read_bytes()
assert len(raw) <= 1_000_000
counts = re.findall(rb"Ran (\d+) tests? in", raw)
metadata = dict(product_source=FIXED, review_source=source, review_tree=tree,
    packages_tree=packages_tree, exact_text_files=checked, command=argv, cwd=str(cwd),
    python=sys.version, environment={key: env.get(key) for key in
        ("PYTHONPATH", "TMPDIR", "LANG", "LC_ALL", "PYTHONUTF8", "GIT_DIR", "GIT_WORK_TREE")},
    exit=code, timed_out=timed_out, tests=int(counts[-1]) if counts else None,
    bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), log=log.name)
with metadata_path.open("x", encoding="utf-8") as stream:
    json.dump(metadata, stream, ensure_ascii=False, indent=2)
    stream.write("\n")
print(json.dumps(metadata, ensure_ascii=True), flush=True)
print(raw.decode("utf-8", errors="replace")[-5000:], flush=True)
sys.exit(code)
