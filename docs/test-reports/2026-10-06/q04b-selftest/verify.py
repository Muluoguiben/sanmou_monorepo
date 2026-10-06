"""Q04b fixed-source CI-only verification; no installation or archive access."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT, OUT, CODE = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3]
BASE = "b37e7ed34e5c9df63d668349436b198bd8b0b27d"
CONTRACT = "b41aae48bd0b14fdb2ea343183d4cecce253d94d"
PACKAGES = "e849545fc31473d68835618c2c13ec44c35788c0"
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
sys.path.insert(0, DEPS)
import yaml


def sha(raw): return hashlib.sha256(raw).hexdigest()
def git(*args): return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(ROOT), *args])


OUT.mkdir(parents=True, exist_ok=False)
assert git("rev-parse", "HEAD").decode().strip() == CODE
TREE = git("rev-parse", "HEAD^{tree}").decode().strip()
assert not git("diff", "--name-only", "HEAD")
assert git("rev-parse", "HEAD:packages").decode().strip() == PACKAGES
assert git("rev-parse", BASE + ":packages").decode().strip() == PACKAGES
assert git("diff", "--name-only", CONTRACT, CODE).decode().splitlines() == [".github/workflows/regression.yml"]
path = ".github/workflows/regression.yml"
before, actual = git("show", BASE + ":" + path), (ROOT / path).read_bytes()
addition = (b"      - name: Windows Q04b claim span evaluation\n"
    b"        working-directory: packages/qa-agent\n"
    b"        run: python -B -m unittest discover -s tests -p 'test_claim_spans.py' -v\n")
assert actual.count(addition) == 1 and actual.replace(addition, b"") == before
step = {"name": "Windows Q04b claim span evaluation", "working-directory": "packages/qa-agent",
        "run": "python -B -m unittest discover -s tests -p 'test_claim_spans.py' -v"}
old_yaml, new_yaml = yaml.load(before, Loader=yaml.BaseLoader), yaml.load(actual, Loader=yaml.BaseLoader)
steps = new_yaml["jobs"]["windows"]["steps"]
assert steps.count(step) == 1
index = steps.index(step)
assert steps[index - 1]["name"] == "Windows H09b offline task evaluation"
assert steps[index + 1]["name"] == "Desktop dependencies"
restored = copy.deepcopy(new_yaml)
restored["jobs"]["windows"]["steps"].pop(index)
assert restored == old_yaml
test_path = "packages/qa-agent/tests/test_claim_spans.py"
raw_test = (ROOT / test_path).read_bytes()
assert raw_test == git("show", BASE + ":" + test_path)
module = ast.parse(raw_test)
names = [f"test_claim_spans.{cls.name}.{method.name}" for cls in module.body if isinstance(cls, ast.ClassDef)
         for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith("test_")]
assert len(names) == 25 and len(set(names)) == 25
inputs = []
for row in git("ls-tree", "-rz", CODE, "--", "packages/qa-agent").split(b"\0"):
    if not row: continue
    meta, name = row.split(b"\t")
    name = name.decode()
    if Path(name).suffix not in {".py", ".json", ".yaml", ".yml"}: continue
    raw = (ROOT / name).read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert blob == meta.decode().split()[2], name
    inputs.append([name, blob, sha(raw)])
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = str(ROOT / "packages/qa-agent/src") + ":" + str(ROOT / "packages/sanmou-common/src") + ":" + DEPS
summary = {"source": CODE, "tree": TREE, "baseline": BASE, "contract": CONTRACT,
    "packages_tree": PACKAGES, "verifier_sha256": sha(Path(__file__).read_bytes()),
    "runtime": {"executable": sys.executable, "python": sys.version},
    "scope": {"unique_step": step, "step_index": index, "inverse_bytes_equal": True,
        "inverse_yaml_equal": True, "workflow_before_sha256": sha(before), "workflow_after_sha256": sha(actual),
        "test_blob_unchanged": True, "test_ast_sha256": sha(ast.dump(module).encode()), "test_names": sorted(names),
        "git_byte_verified_qa_inputs": len(inputs), "input_manifest_sha256": sha(json.dumps(inputs, separators=(",", ":")).encode())},
    "commands": [], "failures": [], "results": {},
    "native": "pending exact-final-SHA Hosted Windows 25 names/0skip/exit0 plus all four jobs; no local dependency probing/install"}


def run(name, args, expected=0):
    path = OUT / (name + ".log")
    start = time.time()
    with path.open("xb") as handle:
        result = subprocess.run([sys.executable, "-B", *args], cwd=ROOT / "packages/qa-agent", env=env,
                                stdout=handle, stderr=subprocess.STDOUT, timeout=900)
    raw = path.read_bytes()
    assert len(raw) < 2 * 1024 * 1024
    text = raw.decode("utf-8", errors="replace")
    count = re.findall(r"^Ran (\d+) tests? in ", text, re.MULTILINE)
    skipped = re.findall(r"^OK \(skipped=(\d+)\)", text, re.MULTILINE)
    row = {"name": name, "argv": [sys.executable, "-B", *args], "cwd": str(ROOT / "packages/qa-agent"),
           "PYTHONPATH": env["PYTHONPATH"], "exit": result.returncode, "expected_exit": expected,
           "tests": int(count[-1]) if count else None, "skipped": int(skipped[-1]) if skipped else 0,
           "seconds": time.time() - start, "log": path.name, "log_bytes": len(raw), "log_sha256": sha(raw)}
    summary["commands"].append(row)
    if result.returncode != expected: summary["failures"].append(name)
    print(json.dumps({key: row[key] for key in ("name", "exit", "expected_exit", "tests", "skipped")}), flush=True)
    return row, text


targeted, text = run("claim-spans", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_claim_spans.py", "-v"])
actual_names = re.findall(r"^test_\w+ \((test_claim_spans\.\w+\.test_\w+)\) \.\.\. ok$", text, re.MULTILINE)
assert sorted(actual_names) == sorted(names) and targeted["skipped"] == 0
run("old-quality-eval", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_quality_eval.py", "-v"])
run("qa-full", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"])
cli = ["-m", "qa_agent.quality_eval.claim_spans", "--baseline", "claim-spans-v1", "--output", str(OUT / "claim-spans.json")]
run("claim-spans-cli", cli)
original = (OUT / "claim-spans.json").read_bytes()
_, text = run("create-only-existing-output", cli, expected=1)
assert "FileExistsError" in text and (OUT / "claim-spans.json").read_bytes() == original
for baseline in ("v1", "v2"):
    _, text = run("old-" + baseline + "-refusal", ["-m", "qa_agent.quality_eval.runner", "--baseline", baseline,
                  "--output", str(OUT / (baseline + ".json"))], expected=1)
    assert "frozen KB/production source drift" in text and not (OUT / (baseline + ".json")).exists()
run("qa-v3", ["-m", "qa_agent.quality_eval.runner", "--baseline", "v3", "--output", str(OUT / "qa-v3.json")])
actual_v3 = sha((OUT / "qa-v3.json").read_bytes())
assert actual_v3 == "db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec"
claim = json.loads(original)
assert claim["gate_pass"] and claim["controls"]["numerator"] == claim["controls"]["denominator"] == 12
summary["results"] = {"qualified_test_names_equal": True, "create_only_preserved_bytes": True,
    "old_v1_v2_refusal_preserved": True, "qa_v3_sha256": actual_v3,
    "claim_spans": {"sha256": sha(original), "controls": claim["controls"], "provider": claim["provider"], "holdout": claim["holdout"]}}
assert not git("diff", "--name-only", "HEAD")
with (OUT / "summary.json").open("x", encoding="utf-8") as handle:
    json.dump(summary, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
raise SystemExit(bool(summary["failures"]))
