"""Narrow Q05a-P1 encoding-only repair audit; old source reports remain immutable."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

OLD = "3d8257bf03d47bb86fb80994c924987033b1858a"
CODE = "e0d9d6ef6083f5dc8f3c71daae6e46ed0793c750"
TREE = "94abdeb7aa1e391c02eefaf415893b23eb7d741a"
root, out = (Path(p).resolve() for p in sys.argv[1:3])
out.mkdir(parents=True, exist_ok=False)
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *args])
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
def save(name, value):
    (out / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
assert git("rev-parse", "HEAD").decode().strip() == CODE
assert git("rev-parse", "HEAD^{tree}").decode().strip() == TREE
paths = ["packages/qa-agent/tests/test_quality_eval.py", "packages/qa-agent/tests/test_seasonal_retriever.py"]
assert git("diff", "--name-only", OLD, CODE).decode().splitlines() == paths
unchanged = {}
for path in ("packages/qa-agent/src", "packages/qa-agent/tests/fixtures", ".github",
             "packages/pioneer-agent", "packages/sanmou-common"):
    assert git("rev-parse", OLD + ":" + path) == git("rev-parse", CODE + ":" + path)
    unchanged[path] = git("rev-parse", CODE + ":" + path).decode().strip()
additions = []
inventory = []
for path in paths:
    old = ast.parse(git("show", OLD + ":" + path))
    raw = (root / path).read_bytes()
    assert raw == git("show", CODE + ":" + path)
    new = ast.parse(raw)
    inventory.extend(Path(path).stem + "." + cls.name + "." + method.name
        for cls in new.body if isinstance(cls, ast.ClassDef)
        for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith("test_"))
    old_calls = [node for node in ast.walk(old) if isinstance(node, ast.Call)]
    new_calls = [node for node in ast.walk(new) if isinstance(node, ast.Call)]
    assert len(old_calls) == len(new_calls)
    for before, after in zip(old_calls, new_calls):
        if not isinstance(after.func, ast.Attribute) or after.func.attr not in {"read_text", "write_text"}:
            continue
        old_encoding = [key for key in before.keywords if key.arg == "encoding"]
        new_encoding = [key for key in after.keywords if key.arg == "encoding"]
        assert len(new_encoding) == 1 and isinstance(new_encoding[0].value, ast.Constant) and new_encoding[0].value.value == "utf-8"
        if not old_encoding:
            after.keywords.remove(new_encoding[0])
            additions.append({"path": path, "line": after.lineno, "call": after.func.attr})
    assert ast.dump(old) == ast.dump(new), path
assert len(inventory) == 44 and len(additions) == 15
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", LC_ALL="C.UTF-8", LANG="C.UTF-8", PYTHONUTF8="0")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = os.pathsep.join([str(root / "packages/qa-agent/src"), str(root / "packages/qa-agent/tests"),
    str(root / "packages/sanmou-common/src"), "/tmp/sanmou-cr-20261005-6155-deps"])
commands = []
def run(name, args, cwd=None):
    argv = [sys.executable, "-B", *args]
    cwd = cwd or root / "packages/qa-agent"
    with (out / (name + ".log")).open("xb") as stream:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    raw = (out / (name + ".log")).read_bytes()
    counts = re.findall(rb"Ran (\d+) tests? in ", raw)
    skips = re.findall(rb"OK \(skipped=(\d+)\)", raw)
    commands.append({"name": name, "argv": argv, "cwd": str(cwd), "PYTHONPATH": env["PYTHONPATH"],
        "exit": result.returncode, "tests": int(counts[-1]) if counts else None, "skips": int(skips[-1]) if skips else 0,
        "log": name + ".log", "bytes": len(raw), "sha256": sha(raw)})
    save("progress.json", commands)
    print(json.dumps({k: commands[-1][k] for k in ("name", "exit", "tests", "skips")}), flush=True)
    assert result.returncode == 0
    return raw
here = Path(__file__).parent
run("public-probes", [str(here / "q05a-independent-probes.py"), "-v"])
run("v4-integration-probes", [str(here / "q05a-v4-integration-probes.py"), str(root), "-v"])
raw = run("targeted-normal", ["-m", "unittest", "test_seasonal_retriever", "test_quality_eval", "-v"])
assert commands[-1]["tests"] == 44 and commands[-1]["skips"] == 0
assert sorted(x.decode() for x in re.findall(rb"^test_\w+ \(((?:test_quality_eval|test_seasonal_retriever)\.\w+\.test_\w+)\) \.\.\. ok$", raw, re.M)) == sorted(inventory)
run("qa-full", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])
assert commands[-1]["tests"] == 440 and commands[-1]["skips"] == 0
run("v4-cli", ["-m", "qa_agent.quality_eval.runner", "--baseline", "v4", "--output", str(out / "v4.json")])
run("q04-cli", ["-m", "qa_agent.quality_eval.claim_spans", "--baseline", "claim-spans-v1", "--output", str(out / "q04.json")])
hashes = {name: sha((out / (name + ".json")).read_bytes()) for name in ("v4", "q04")}
assert hashes == {"v4": "c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c",
    "q04": "b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6"}
assert not git("diff", "--name-only", "HEAD", "--", "packages", ".github")
save("summary.json", {"source": CODE, "tree": TREE, "previous_source": OLD, "unchanged_trees": unchanged,
    "only_ast_delta": "15 explicit encoding=utf-8 keywords on existing read_text/write_text calls",
    "encoding_additions": additions, "test_inventory": sorted(inventory), "commands": commands,
    "report_hashes": hashes, "native": "pending_final_Hosted_25_and_44", "strict_C_ASCII_filesystem": "still_fails; not hidden"})
