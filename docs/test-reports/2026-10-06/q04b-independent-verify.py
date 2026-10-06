"""Limited Q04b CI-wiring proof and fixed-source offline regression."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BASE = "b37e7ed34e5c9df63d668349436b198bd8b0b27d"
CODE = "ebcd5d12546dc66044d0485089a10e2bdc43e4a8"
TREE = "e6244518555af134d97c7b952be286b71500ac04"
PACKAGES = "e849545fc31473d68835618c2c13ec44c35788c0"
FLOW = ".github/workflows/regression.yml"
TEST = "packages/qa-agent/tests/test_claim_spans.py"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
ADDED = b"      - name: Windows Q04b claim span evaluation\n        working-directory: packages/qa-agent\n        run: python -B -m unittest discover -s tests -p 'test_claim_spans.py' -v\n"
root, out = (Path(p).resolve() for p in sys.argv[1:3])
out.mkdir(parents=True, exist_ok=False)

def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *args])

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def save(name, data):
    (out / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

assert git("rev-parse", "HEAD").decode().strip() == CODE
assert git("rev-parse", "HEAD^{tree}").decode().strip() == TREE
assert git("rev-parse", CODE + ":packages").decode().strip() == PACKAGES
assert git("rev-parse", BASE + ":packages").decode().strip() == PACKAGES
assert git("diff", "--name-only", "b41aae48bd0b14fdb2ea343183d4cecce253d94d", CODE).decode().splitlines() == [FLOW]
before, after = git("show", BASE + ":" + FLOW), (root / FLOW).read_bytes()
assert after == git("show", CODE + ":" + FLOW)
assert after.count(ADDED) == 1 and after.replace(ADDED, b"", 1) == before
sys.path.insert(0, DEPS)
import yaml
old, new = (yaml.load(raw, Loader=yaml.BaseLoader) for raw in (before, after))
steps = new["jobs"]["windows"]["steps"]
step = {"name": "Windows Q04b claim span evaluation", "working-directory": "packages/qa-agent",
        "run": "python -B -m unittest discover -s tests -p 'test_claim_spans.py' -v"}
assert steps.count(step) == 1
index = steps.index(step)
assert steps[index - 1]["name"] == "Windows H09b offline task evaluation"
assert steps[index + 1]["name"] == "Desktop dependencies"
steps.remove(step)
assert new == old
test = (root / TEST).read_bytes()
assert test == git("show", BASE + ":" + TEST)
inventory = sorted("test_claim_spans." + cls.name + "." + method.name
    for cls in ast.parse(test).body if isinstance(cls, ast.ClassDef)
    for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith("test_"))
assert len(inventory) == 25
assert "test_claim_spans.ClaimSpanTests.test_real_cli_create_only_and_explicit_version" in inventory
checked = 0
for raw_name in git("ls-tree", "-rz", "--name-only", CODE, "--", "packages").split(b"\0"):
    if raw_name and Path(raw_name.decode()).suffix in {".py", ".json", ".yaml", ".yml"}:
        name = raw_name.decode()
        assert (root / name).read_bytes() == git("show", CODE + ":" + name)
        checked += 1
commands = []
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = os.pathsep.join([str(root / "packages/qa-agent/src"), str(root / "packages/sanmou-common/src"), DEPS])

def run(name, argv, expected=0):
    with (out / (name + ".log")).open("xb") as stream:
        result = subprocess.run(argv, cwd=root / "packages/qa-agent", env=env,
            stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    raw = (out / (name + ".log")).read_bytes()
    counts = re.findall(rb"Ran (\d+) tests? in ", raw)
    skips = re.findall(rb"OK \(skipped=(\d+)\)", raw)
    commands.append({"name": name, "argv": argv, "cwd": str(root / "packages/qa-agent"),
        "PYTHONPATH": env["PYTHONPATH"], "exit": result.returncode, "expected_exit": expected,
        "tests": int(counts[-1]) if counts else None, "skips": int(skips[-1]) if skips else 0,
        "log": name + ".log", "bytes": len(raw), "sha256": sha(raw)})
    save("progress.json", commands)
    print(json.dumps(commands[-1]), flush=True)
    assert result.returncode == expected
    return raw

py = [sys.executable, "-B"]
for name, pattern, expected_count in (("claim-module", "test_claim_spans.py", 25),
        ("legacy-module", "test_quality_eval.py", 23), ("qa-full", "test_*.py", 419)):
    raw = run(name, py + ["-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"])
    assert commands[-1]["tests"] == expected_count and commands[-1]["skips"] == 0
    if name == "claim-module":
        found = sorted(match.decode() for match in re.findall(rb"^test_\w+ \((test_claim_spans\.\w+\.test_\w+)\) \.\.\. ok$", raw, re.M))
        assert found == inventory
        assert b"... skipped " not in raw
argv = py + ["-m", "qa_agent.quality_eval.claim_spans", "--baseline", "claim-spans-v1", "--output", str(out / "claim-spans.json")]
run("new-cli", argv)
original = (out / "claim-spans.json").read_bytes()
assert json.loads(original)["gate_pass"]
assert b"FileExistsError" in run("new-cli-no-clobber", argv, 1)
assert (out / "claim-spans.json").read_bytes() == original
for version in ("v1", "v2", "v3"):
    raw = run("qa-" + version, py + ["-m", "qa_agent.quality_eval.runner", "--baseline", version,
        "--output", str(out / (version + ".json"))], 0 if version == "v3" else 1)
    if version != "v3":
        assert b"frozen KB/production source drift; create a reviewed new baseline version" in raw
v3_hash = sha((out / "v3.json").read_bytes())
assert v3_hash == "db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec"
assert not git("diff", "--name-only", "HEAD", "--", "packages", FLOW)
save("summary.json", {"source": CODE, "tree": TREE, "baseline": BASE, "packages": PACKAGES,
    "workflow_sha256": sha(after), "remove_step_restores_bytes_and_yaml": True,
    "test_sha256": sha(test), "inventory": inventory, "git_byte_checked_inputs": checked,
    "commands": commands, "v3_sha256": v3_hash, "new_cli_sha256": sha(original),
    "native": "pending_exact_final_sha_hosted_windows_25_zero_skips_all_four_jobs",
    "provider_calls": 0, "archive_reads": 0, "execution_authority": "none", "executable": False})
