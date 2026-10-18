"""Read-only exact Git-byte and authorized-diff audit; no archive content."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[3]
BASE = "155817a444718366c3dbd56ac91fff8d52500fa5"
FIXED = "f2017c826a9bd798c66be404e99b8e3f8b0ffa50"
gitdir = (ROOT / ".git").read_text(encoding="utf-8").strip().removeprefix("gitdir: ")
if gitdir.lower().startswith("//wsl$/ubuntu/"):
    gitdir = "/" + gitdir[len("//wsl$/ubuntu/"):]
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-c", "core.filemode=false",
        "--git-dir=" + gitdir, "--work-tree=" + str(ROOT), *args])
allowed = {".github/workflows/regression.yml", "packages/pioneer-agent/tests/test_skill_trace_binding.py"}
allowed.update("packages/pioneer-agent/src/pioneer_agent/agent_harness/" + name + ".py"
    for name in ("skill_registry", "task_runner", "task_trace", "run_trace"))
assert set(git("diff", "--name-only", BASE, FIXED, "--", "packages", ".github").decode().splitlines()) == allowed
assert git("rev-parse", "HEAD:packages") == git("rev-parse", FIXED + ":packages")
assert git("rev-parse", "HEAD:.github") == git("rev-parse", FIXED + ":.github")
checked = []
text_suffixes = {".py", ".json", ".jsonl", ".yaml", ".yml", ".md", ".toml", ".txt", ".ini", ".cfg", ".csv", ".tsv", ".sh", ".ps1", ".bat"}
for item in git("ls-files", "-s", "-z", "--", "packages", ".github").split(b"\0"):
    if not item:
        continue
    header, raw_path = item.split(b"\t", 1)
    path = raw_path.decode()
    mode, oid, stage = header.decode().split()
    if mode not in {"100644", "100755"} or (Path(path).suffix not in text_suffixes and Path(path).name not in {".gitattributes", ".gitignore"}):
        continue
    raw = (ROOT / path).read_bytes()
    actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert actual == oid, path
    checked.append(path)
flow = ".github/workflows/regression.yml"
old, new = git("show", BASE + ":" + flow), (ROOT / flow).read_bytes()
added = b"      - name: Windows H08b recipe trace binding\n        working-directory: packages/pioneer-agent/tests\n        run: python -B -W error::RuntimeWarning -m unittest test_skill_trace_binding -v\n"
assert new.count(added) == 1 and new.replace(added, b"", 1) == old
old_yaml, new_yaml = (yaml.load(raw, Loader=yaml.BaseLoader) for raw in (old, new))
steps = new_yaml["jobs"]["windows"]["steps"]
index = next(i for i, step in enumerate(steps) if step.get("name") == "Windows H08b recipe trace binding")
assert steps[index - 1]["name"] == "Windows H08a readonly skill registry"
steps.pop(index)
assert old_yaml == new_yaml
tree = ast.parse((ROOT / "packages/pioneer-agent/tests/test_skill_trace_binding.py").read_text(encoding="utf-8"))
inventory = sorted("test_skill_trace_binding." + cls.name + "." + method.name
    for cls in tree.body if isinstance(cls, ast.ClassDef)
    for method in cls.body if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith("test_"))
assert len(inventory) == 31
for call in ast.walk(tree):
    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr in {"read_text", "write_text"}:
        assert any(key.arg == "encoding" and isinstance(key.value, ast.Constant) and key.value.value == "utf-8" for key in call.keywords)
print(json.dumps(dict(source=FIXED, review_head=git("rev-parse", "HEAD").decode().strip(),
    packages_tree=git("rev-parse", "HEAD:packages").decode().strip(), checked_exact_text_files=len(checked),
    workflow_inverse_bytes_and_yaml=True, new_test_inventory=inventory,
    allowed_product_paths=sorted(allowed)), indent=2))
