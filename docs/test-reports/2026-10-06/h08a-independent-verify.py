"""Fixed H08a registry source audit, original probes and bounded offline matrix."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

CODE = "8e0a2a0b370a98824669e5d34bd12576c7822bb5"
TREE = "55eb8c863db183e7dbd2fa9cfb6d845876162315"
BASE = "60e3e002c7b38571e76d344dd100b47d053244e2"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
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
module = "packages/pioneer-agent/src/pioneer_agent/agent_harness/skill_registry.py"
test = "packages/pioneer-agent/tests/test_skill_registry.py"
flow = ".github/workflows/regression.yml"
assert set(git("diff", "--name-only", BASE, CODE, "--", "packages", ".github").decode().splitlines()) == {module, test, flow}
assert git("rev-parse", BASE + ":packages/qa-agent") == git("rev-parse", CODE + ":packages/qa-agent")
assert git("rev-parse", BASE + ":packages/sanmou-common") == git("rev-parse", CODE + ":packages/sanmou-common")
checked = 0
for raw_name in git("ls-tree", "-rz", "--name-only", CODE, "--", "packages").split(b"\0"):
    if raw_name and Path(raw_name.decode()).suffix in {".py", ".json", ".yaml", ".yml"}:
        name = raw_name.decode()
        assert (root / name).read_bytes() == git("show", CODE + ":" + name)
        checked += 1
old_flow, new_flow = git("show", BASE + ":" + flow), (root / flow).read_bytes()
added = b"      - name: Windows H08a readonly skill registry\n        working-directory: packages/pioneer-agent/tests\n        run: python -B -W error::RuntimeWarning -m unittest test_skill_registry -v\n"
assert new_flow.count(added) == 1 and new_flow.replace(added, b"", 1) == old_flow
sys.path.insert(0, DEPS)
import yaml
before, after = (yaml.load(raw, Loader=yaml.BaseLoader) for raw in (old_flow, new_flow))
steps = after["jobs"]["windows"]["steps"]
index = next(i for i, step in enumerate(steps) if step.get("name") == "Windows H08a readonly skill registry")
assert steps[index - 1]["name"] == "Windows Q05a explicit season retrieval"
steps.pop(index)
assert before == after
test_ast = ast.parse((root / test).read_bytes())
inventory = sorted("test_skill_registry." + cls.name + "." + method.name
    for cls in test_ast.body if isinstance(cls, ast.ClassDef)
    for method in cls.body if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith("test_"))
assert len(inventory) == 23
for node in ast.walk(test_ast):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"read_text", "write_text"}:
        assert any(key.arg == "encoding" and isinstance(key.value, ast.Constant) and key.value.value == "utf-8" for key in node.keywords)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = os.pathsep.join([str(root / p) for p in ("packages/pioneer-agent/src", "packages/pioneer-agent/tests",
    "packages/qa-agent/src", "packages/qa-agent/tests", "packages/sanmou-common/src")] + [DEPS])
commands = []
def run(name, args, cwd=root, expected=0, environment=None):
    argv = [sys.executable, "-B", *args]
    actual_env = environment or env
    with (out / (name + ".log")).open("xb") as stream:
        result = subprocess.run(argv, cwd=cwd, env=actual_env, stdout=stream, stderr=subprocess.STDOUT, timeout=900)
    raw = (out / (name + ".log")).read_bytes()
    counts = re.findall(rb"Ran (\d+) tests? in ", raw)
    skips = re.findall(rb"OK \(skipped=(\d+)\)", raw)
    commands.append({"name": name, "argv": argv, "cwd": str(cwd), "PYTHONPATH": actual_env["PYTHONPATH"],
        "exit": result.returncode, "expected_exit": expected, "tests": int(counts[-1]) if counts else None,
        "skips": int(skips[-1]) if skips else 0, "log": name + ".log", "bytes": len(raw), "sha256": sha(raw)})
    save("progress.json", commands)
    print(json.dumps({k: commands[-1][k] for k in ("name", "exit", "tests", "skips")}), flush=True)
    assert result.returncode == expected, commands[-1]
    return raw
here = Path(__file__).parent
run("public-runtime-probes", ["-W", "error::RuntimeWarning", str(here / "h08a-independent-probes.py"), "-v"])
run("catalog-probes", [str(here / "h08a-catalog-probes.py"), "-v"])
raw = run("new-module", ["-W", "error::RuntimeWarning", "-m", "unittest", "test_skill_registry", "-v"], root / "packages/pioneer-agent/tests")
found = sorted(x.decode() for x in re.findall(rb"^test_\w+ \((test_skill_registry\.\w+\.test_\w+)\) \.\.\. ok$", raw, re.M))
assert found == inventory and commands[-1]["skips"] == 0
assert b"RuntimeWarning:" not in raw and b"was never awaited" not in raw
locale_env = dict(env, LC_ALL="C.UTF-8", LANG="C.UTF-8", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0", PYTHONIOENCODING="utf-8")
bootstrap = """import json, locale, sys, unittest
from pathlib import Path
assert sys.flags.utf8_mode == 0 and sys.getfilesystemencoding().lower().replace('-', '') == 'utf8'
locale.setlocale(locale.LC_CTYPE, 'C')
p = Path(sys.argv[1])
p.write_text('{}', encoding='utf-8')
with p.open() as stream: encoding = stream.encoding
assert encoding.lower() in ('ascii', 'us-ascii', 'ansi_x3.4-1968')
data = dict(locale=locale.setlocale(locale.LC_CTYPE), default_file_encoding=encoding, filesystem_encoding=sys.getfilesystemencoding(), utf8_mode=sys.flags.utf8_mode, stdout_encoding=sys.stdout.encoding, scope='target test process only; spawned processes would inherit C.UTF-8 environment')
p.write_text(json.dumps(data, indent=2)+'\\n', encoding='utf-8')
unittest.main(module=None, argv=['unittest', 'test_skill_registry', '-v'])
"""
raw = run("new-module-text-locale", ["-W", "error::RuntimeWarning", "-c", bootstrap, str(out / "text-locale.json")],
    root / "packages/pioneer-agent/tests", environment=locale_env)
assert commands[-1]["tests"] == 23 and commands[-1]["skips"] == 0
for name, modules, package in (("h07", ["test_task_approval"], "pioneer-agent"),
        ("h10", ["test_causal_trace"], "pioneer-agent"), ("q04", ["test_claim_spans"], "qa-agent"),
        ("q05", ["test_seasonal_retriever", "test_quality_eval"], "qa-agent")):
    run(name, ["-W", "error::RuntimeWarning", "-m", "unittest", *modules, "-v"], root / "packages" / package / "tests")
for package in ("pioneer-agent", "qa-agent", "sanmou-common"):
    run(package, ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], root / "packages" / package)
for version in ("v1", "v2", "v3", "v4"):
    raw = run("qa-" + version, ["-m", "qa_agent.quality_eval.runner", "--baseline", version,
        "--output", str(out / (version + ".json"))], expected=0 if version == "v4" else 1)
    if version != "v4": assert b"frozen KB/production source drift" in raw
run("q04-cli", ["-m", "qa_agent.quality_eval.claim_spans", "--baseline", "claim-spans-v1", "--output", str(out / "q04.json")])
v4_sha, q04_sha = (sha((out / (name + ".json")).read_bytes()) for name in ("v4", "q04"))
assert v4_sha == "c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c"
assert q04_sha == "b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6"
run("h09-cli", ["-m", "pioneer_agent.app.task_eval", "--output", str(out / "h09")])
h09 = json.loads((out / "h09/report.json").read_bytes())
assert h09["source_verified"] and h09["complete"] and h09["gate_pass"]
assert not git("diff", "--name-only", "HEAD", "--", "packages", ".github")
save("summary.json", {"source": CODE, "tree": TREE, "baseline": BASE, "git_byte_checked_inputs": checked,
    "only_package_additions": [module, test], "old_package_files_unchanged": True,
    "workflow_inverse_bytes_and_yaml_equal": True, "new_test_inventory": inventory,
    "commands": commands, "text_locale": json.loads((out / "text-locale.json").read_text(encoding="utf-8")),
    "v4_sha256": v4_sha, "q04_sha256": q04_sha,
    "h09": {"totals": h09["totals"], "sha256": sha((out / "h09/report.json").read_bytes())},
    "provider_calls": 0, "archive_reads": 0, "execution_authority": "none", "executable": False,
    "native": "pending_exact_final_Hosted_new23_and_existing25_44_all_four_jobs"})
