"""Fixed-source Q05a review matrix and exact inherited-report projections."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

CODE = "3d8257bf03d47bb86fb80994c924987033b1858a"
TREE = "0aa22ba210af5fb112b9ad073939428961511b4d"
PRODUCTION = "27b73de689cc5863ed02a0dd30526fde8533d080"
BASE = "3711e92d38786418e8e955d19a56cd6c72611389"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
root, baseline_results, out = (Path(p).resolve() for p in sys.argv[1:4])
out.mkdir(parents=True, exist_ok=False)
package = root / "packages/qa-agent"
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *args])
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
def save(name, data):
    (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
def snap(paths):
    files = {str(p.relative_to(package)).replace(os.sep, "/"): sha(p.read_text(encoding="utf-8-sig").replace("\r\n", "\n").encode()) for p in sorted(paths)}
    return {"algorithm": "sha256-utf8-lf-v1", "files": files,
            "digest": sha(json.dumps(files, sort_keys=True, ensure_ascii=False).encode())}
assert git("rev-parse", "HEAD").decode().strip() == CODE
assert git("rev-parse", "HEAD^{tree}").decode().strip() == TREE
allowed = {".github/workflows/regression.yml", "packages/qa-agent/src/qa_agent/retrieval/seasonal.py",
    "packages/qa-agent/src/qa_agent/quality_eval/runner.py", "packages/qa-agent/src/qa_agent/quality_eval/season_cases.py",
    "packages/qa-agent/tests/test_seasonal_retriever.py", "packages/qa-agent/tests/test_quality_eval.py",
    "packages/qa-agent/tests/test_lineup_frame_extractor.py"}
allowed.update("packages/qa-agent/tests/fixtures/quality_eval/v4/" + name for name in ("cases.json", "freeze.json", "README.md"))
assert set(git("diff", "--name-only", BASE, CODE, "--", "packages", ".github").decode().splitlines()) == allowed
assert not git("diff", "--name-only", PRODUCTION, CODE, "--", "packages/qa-agent/src")
checked = 0
for raw_name in git("ls-tree", "-rz", "--name-only", CODE, "--", "packages").split(b"\0"):
    if raw_name and Path(raw_name.decode()).suffix in {".py", ".json", ".yaml", ".yml"}:
        name = raw_name.decode()
        assert (root / name).read_bytes() == git("show", CODE + ":" + name)
        checked += 1
flow = ".github/workflows/regression.yml"
old_flow, new_flow = git("show", BASE + ":" + flow), (root / flow).read_bytes()
added = b"      - name: Windows Q05a explicit season retrieval\n        working-directory: packages/qa-agent/tests\n        run: python -B -m unittest test_seasonal_retriever test_quality_eval -v\n"
assert new_flow.count(added) == 1 and new_flow.replace(added, b"", 1) == old_flow
sys.path.insert(0, DEPS)
import yaml
old_yaml, new_yaml = (yaml.load(raw, Loader=yaml.BaseLoader) for raw in (old_flow, new_flow))
steps = new_yaml["jobs"]["windows"]["steps"]
index = next(i for i, item in enumerate(steps) if item.get("name") == "Windows Q05a explicit season retrieval")
assert steps[index - 1]["name"] == "Windows Q04b claim span evaluation"
steps.pop(index)
assert old_yaml == new_yaml
test_path = "packages/qa-agent/tests/test_quality_eval.py"
def methods(raw):
    return {method.name: method for cls in ast.parse(raw).body if isinstance(cls, ast.ClassDef)
            for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith("test_")}
old_methods, new_methods = methods(git("show", BASE + ":" + test_path)), methods((root / test_path).read_bytes())
class VersionMigration(ast.NodeTransformer):
    def visit_Constant(self, node):
        return ast.copy_location(ast.Constant(value="v4"), node) if node.value == "v3" else node
for name, old in old_methods.items():
    assert ast.dump(new_methods[name]) in {ast.dump(old), ast.dump(VersionMigration().visit(copy.deepcopy(old)))}, name
assert set(new_methods) - set(old_methods) == {"test_v3_rejects_new_production_without_changing_its_freeze"}
image_path = "packages/qa-agent/tests/test_lineup_frame_extractor.py"
image_old, image_new = git("show", BASE + ":" + image_path), (root / image_path).read_bytes()
new_line = b"                with Image.open(p) as image:\n                    w, h = image.size\n"
assert image_new.replace(new_line, b"                w, h = Image.open(p).size\n", 1) == image_old
fixtures = package / "tests/fixtures/quality_eval"
old_cases = json.loads((fixtures / "v3/cases.json").read_bytes())
v4 = json.loads((fixtures / "v4/cases.json").read_bytes())
inherited = copy.deepcopy(v4)
assert inherited.pop("version") == 4 and old_cases.pop("version") == 3
season_cases = inherited.pop("season_cases")
assert inherited == old_cases and len(inherited["multiturn_cases"]) == 9
freeze = json.loads((fixtures / "v4/freeze.json").read_bytes())
assert freeze["baseline_commit"] == PRODUCTION
assert freeze["cases_sha256"] == sha((fixtures / "v4/cases.json").read_bytes())
assert freeze["production"] == snap([p for p in (package / "src/qa_agent").rglob("*.py") if "quality_eval" not in p.parts])
assert freeze["kb"] == snap((package / "knowledge_sources").rglob("*.yaml"))
for path in freeze["production"]["files"]:
    assert (package / path).read_bytes() == git("show", PRODUCTION + ":packages/qa-agent/" + path)
old_v3_raw, old_q04_raw = (baseline_results / "v3.json").read_bytes(), (baseline_results / "q04.json").read_bytes()
assert sha(old_v3_raw) == "db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec"
assert sha(old_q04_raw) == "c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120"
commands = []
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = os.pathsep.join([str(root / p) for p in ("packages/qa-agent/src", "packages/qa-agent/tests",
    "packages/pioneer-agent/src", "packages/pioneer-agent/tests", "packages/sanmou-common/src")] + [DEPS])
def run(name, args, cwd=package, expected=0):
    argv = [sys.executable, "-B", *args]
    with (out / (name + ".log")).open("xb") as stream:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=900)
    raw = (out / (name + ".log")).read_bytes()
    counts = re.findall(rb"Ran (\d+) tests? in ", raw)
    skips = re.findall(rb"OK \(skipped=(\d+)\)", raw)
    commands.append({"name": name, "argv": argv, "cwd": str(cwd), "PYTHONPATH": env["PYTHONPATH"],
        "exit": result.returncode, "expected_exit": expected, "tests": int(counts[-1]) if counts else None,
        "skips": int(skips[-1]) if skips else 0, "log": name + ".log", "bytes": len(raw), "sha256": sha(raw)})
    save("progress.json", commands)
    print(json.dumps({k: commands[-1][k] for k in ("name", "exit", "tests", "skips")}), flush=True)
    assert result.returncode == expected, commands[-1]
    return raw
here = Path(__file__).parent
run("public-probes", [str(here / "q05a-independent-probes.py"), "-v"])
run("v4-integration-probes", [str(here / "q05a-v4-integration-probes.py"), str(root), "-v"])
run("resource-warning-fixed", [str(here / "q05a-resource-warning-probe.py"), "fixed"])
target_raw = run("q05-targeted", ["-m", "unittest", "test_seasonal_retriever", "test_quality_eval", "-v"], package / "tests")
inventory = sorted("test_seasonal_retriever.SeasonalRetrieverTests." + name for name in methods((package / "tests/test_seasonal_retriever.py").read_bytes()))
inventory += sorted("test_quality_eval.QualityEvaluationTests." + name for name in new_methods)
found = sorted(m.decode() for m in re.findall(rb"^test_\w+ \(((?:test_seasonal_retriever|test_quality_eval)\.\w+\.test_\w+)\) \.\.\. ok$", target_raw, re.M))
assert found == sorted(inventory) and len(found) == 44 and commands[-1]["skips"] == 0
run("q04-module", ["-m", "unittest", "test_claim_spans", "-v"], package / "tests")
for version in ("v1", "v2", "v3", "v4"):
    raw = run("cli-" + version, ["-m", "qa_agent.quality_eval.runner", "--baseline", version,
        "--output", str(out / (version + ".json"))], expected=0 if version == "v4" else 1)
    if version != "v4":
        assert b"frozen KB/production source drift" in raw
run("q04-cli", ["-m", "qa_agent.quality_eval.claim_spans", "--baseline", "claim-spans-v1", "--output", str(out / "q04.json")])
new_v4_raw, new_q04_raw = (out / "v4.json").read_bytes(), (out / "q04.json").read_bytes()
old_v3, new_v4, old_q04, new_q04 = map(json.loads, (old_v3_raw, new_v4_raw, old_q04_raw, new_q04_raw))
allowed_delta = {"protocol", "baseline_commit", "cases_sha256", "production", "eval_source", "season"}
assert set(new_v4) - set(old_v3) == {"season"}
assert {k: v for k, v in old_v3.items() if k not in allowed_delta} == {k: v for k, v in new_v4.items() if k not in allowed_delta}
assert new_v4["season"]["gate_pass"] and new_v4["season"]["passed"] == new_v4["season"]["denominator"] == len(season_cases)
old_eval, new_eval = old_q04.pop("eval_source"), new_q04.pop("eval_source")
assert old_q04 == new_q04 and new_eval == new_v4["eval_source"]
new_file = "src/qa_agent/quality_eval/season_cases.py"
changed_file = "src/qa_agent/quality_eval/runner.py"
assert set(new_eval["files"]) - set(old_eval["files"]) == {new_file}
assert {k for k in old_eval["files"] if old_eval["files"][k] != new_eval["files"][k]} == {changed_file}
assert new_eval == snap((package / "src/qa_agent/quality_eval").glob("*.py"))
comparisons = {"inherited_v4_projection_equal": True, "allowed_v4_top_level_differences": sorted(allowed_delta),
    "old_v3_sha256": sha(old_v3_raw), "new_v4_sha256": sha(new_v4_raw), "old_q04_sha256": sha(old_q04_raw),
    "new_q04_sha256": sha(new_q04_raw), "q04_other_fields_equal": True, "old_eval_source": old_eval, "new_eval_source": new_eval}
save("comparisons.json", comparisons)
for name, module in (("h07", "test_task_approval"), ("h10", "test_causal_trace")):
    run(name, ["-W", "error::RuntimeWarning", "-m", "unittest", module, "-v"], root / "packages/pioneer-agent/tests")
for name in ("qa-agent", "pioneer-agent", "sanmou-common"):
    run(name, ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], root / "packages" / name)
run("h09-cli", ["-m", "pioneer_agent.app.task_eval", "--output", str(out / "h09-cli")], root)
h09 = json.loads((out / "h09-cli/report.json").read_bytes())
assert h09["source_verified"] and h09["complete"] and h09["gate_pass"]
assert not git("diff", "--name-only", "HEAD", "--", "packages", ".github")
save("summary.json", {"source": CODE, "tree": TREE, "production_freeze_commit": PRODUCTION,
    "baseline": BASE, "git_byte_checked_inputs": checked, "scope_checks": "passed",
    "old_test_ast_only_literal_version_migration": True, "image_test_only_context_manager_delta": True,
    "workflow_inverse_bytes_yaml_equal": True, "targeted_inventory": sorted(inventory), "commands": commands,
    "comparisons": comparisons, "season_controls": new_v4["season"]["denominator"],
    "h09": {"totals": h09["totals"], "sha256": sha((out / "h09-cli/report.json").read_bytes())},
    "native": "pending_final_exact_hosted_25_and_q05_targeted_44", "provider_calls": 0,
    "execution_authority": "none", "executable": False, "archive_reads": 0})
