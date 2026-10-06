"""Q05a fixed-source matrix and exact predecessor projections; offline only."""
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
BASE = "3711e92d38786418e8e955d19a56cd6c72611389"
PRODUCTION = "27b73de689cc5863ed02a0dd30526fde8533d080"
OLD = Path("/tmp/q05a-3711-baseline-results")
DEPS = "/tmp/sanmou-cr-20261005-6155-deps"
OUT.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, DEPS)
import yaml


def sha(raw): return hashlib.sha256(raw).hexdigest()
def git(*args): return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(ROOT), *args])
def save(name, data):
    with (OUT / name).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


assert git("rev-parse", "HEAD").decode().strip() == CODE
TREE = git("rev-parse", "HEAD^{tree}").decode().strip()
REPAIR_BASE = "3d8257bf03d47bb86fb80994c924987033b1858a"
repair_paths = ["packages/qa-agent/tests/test_quality_eval.py", "packages/qa-agent/tests/test_seasonal_retriever.py"]
assert git("diff", "--name-only", REPAIR_BASE, CODE, "--", "packages", ".github").decode().splitlines() == repair_paths
def strip_io_encoding(module):
    for item in ast.walk(module):
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and item.func.attr in {"read_text", "write_text"}:
            for keyword in item.keywords:
                if keyword.arg == "encoding": assert isinstance(keyword.value, ast.Constant) and keyword.value.value == "utf-8"
            item.keywords = [keyword for keyword in item.keywords if keyword.arg != "encoding"]
    return module
for path in repair_paths:
    old_io = ast.parse(git("show", REPAIR_BASE + ":" + path))
    new_io = ast.parse((ROOT / path).read_bytes())
    assert ast.dump(strip_io_encoding(new_io)) == ast.dump(strip_io_encoding(old_io)), path
assert not git("diff", "--name-only", "HEAD")
assert not git("diff", "--name-only", PRODUCTION, CODE, "--", "packages/qa-agent/src")
qa = ROOT / "packages/qa-agent"
freeze = json.loads((qa / "tests/fixtures/quality_eval/v4/freeze.json").read_bytes())
assert freeze["baseline_commit"] == PRODUCTION
for name in ("v1", "v2", "v3", "claim_spans_v1"):
    path = "packages/qa-agent/tests/fixtures/quality_eval/" + name
    assert git("rev-parse", CODE + ":" + path) == git("rev-parse", BASE + ":" + path)
inputs = []
for row in git("ls-tree", "-rz", CODE, "--", "packages").split(b"\0"):
    if not row: continue
    meta, name = row.split(b"\t")
    name = name.decode()
    if Path(name).suffix not in {".py", ".json", ".yaml", ".yml"}: continue
    raw = (ROOT / name).read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert blob == meta.decode().split()[2], name
    inputs.append([name, blob, sha(raw)])
workflow = ".github/workflows/regression.yml"
before, actual = git("show", BASE + ":" + workflow), (ROOT / workflow).read_bytes()
addition = (b"      - name: Windows Q05a explicit season retrieval\n"
    b"        working-directory: packages/qa-agent/tests\n"
    b"        run: python -B -m unittest test_seasonal_retriever test_quality_eval -v\n")
assert actual.count(addition) == 1 and actual.replace(addition, b"") == before
old_yaml, new_yaml = yaml.load(before, Loader=yaml.BaseLoader), yaml.load(actual, Loader=yaml.BaseLoader)
steps = new_yaml["jobs"]["windows"]["steps"]
index = next(i for i, step in enumerate(steps) if step.get("name") == "Windows Q05a explicit season retrieval")
assert steps[index - 1]["name"] == "Windows Q04b claim span evaluation"
steps.pop(index)
assert new_yaml == old_yaml
lineup = "packages/qa-agent/tests/test_lineup_frame_extractor.py"
expected = git("show", BASE + ":" + lineup).replace(b"                w, h = Image.open(p).size\n",
    b"                with Image.open(p) as image:\n                    w, h = image.size\n")
assert (ROOT / lineup).read_bytes() == expected
quality = "packages/qa-agent/tests/test_quality_eval.py"
old_ast = ast.parse(git("show", BASE + ":" + quality))
new_ast = ast.parse((ROOT / quality).read_bytes())
old_tests = {node.name: node for cls in old_ast.body if isinstance(cls, ast.ClassDef) for node in cls.body if isinstance(node, ast.FunctionDef)}
new_tests = {node.name: node for cls in new_ast.body if isinstance(cls, ast.ClassDef) for node in cls.body if isinstance(node, ast.FunctionDef)}
for name, node in old_tests.items():
    migrated = strip_io_encoding(copy.deepcopy(new_tests[name]))
    for item in ast.walk(migrated):
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            if item.value == "v4": item.value = "v3"
            if item.value == "tests/fixtures/quality_eval/v4": item.value = "tests/fixtures/quality_eval/v3"
    assert ast.dump(migrated) == ast.dump(node), name
expected_names = []
for filename in ("test_seasonal_retriever.py", "test_quality_eval.py"):
    module = ast.parse((qa / "tests" / filename).read_bytes())
    expected_names += [filename[:-3] + "." + cls.name + "." + method.name for cls in module.body if isinstance(cls, ast.ClassDef)
                      for method in cls.body if isinstance(method, ast.FunctionDef) and method.name.startswith("test_")]
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = ":".join(str(ROOT / p) for p in ("packages/pioneer-agent/src", "packages/qa-agent/src",
    "packages/sanmou-common/src", "packages/pioneer-agent/tests")) + ":" + DEPS
summary = dict(source=CODE, tree=TREE, baseline=BASE, frozen_production=PRODUCTION,
    verifier_sha256=sha(Path(__file__).read_bytes()), runtime=dict(executable=sys.executable, python=sys.version),
    scope=dict(git_byte_verified_inputs=len(inputs), input_manifest_sha256=sha(json.dumps(inputs,separators=(",", ":")).encode()),
        old_fixtures_unchanged=True, old_quality_assertion_ast_preserved=True, lineup_only_context_close=True,
        workflow_inverse_bytes_and_yaml_equal=True, targeted_names=sorted(expected_names)),
    commands=[], failures=[], results={}, native="Q05a pending exact-final-SHA Hosted targeted names/0skip/exit0; Q04b native25 is separate")


def run(name, argv, cwd, expected=0):
    path = OUT / (name + ".log")
    started = time.time()
    with path.open("xb") as handle:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
    raw = path.read_bytes()
    assert len(raw) <= 2 * 1024 * 1024
    text = raw.decode("utf-8", errors="replace")
    count = re.findall(r"^Ran (\d+) tests? in ", text, re.MULTILINE)
    skips = re.findall(r"^OK \(skipped=(\d+)\)", text, re.MULTILINE)
    row = dict(name=name, argv=argv, cwd=str(cwd), PYTHONPATH=env["PYTHONPATH"], exit=result.returncode,
        expected_exit=expected, tests=int(count[-1]) if count else None, skipped=int(skips[-1]) if skips else 0,
        seconds=time.time()-started, log=path.name, log_bytes=len(raw), log_sha256=sha(raw))
    summary["commands"].append(row)
    if result.returncode != expected: summary["failures"].append(name)
    print(json.dumps({key:row[key] for key in ("name","exit","expected_exit","tests","skipped")}),flush=True)
    return text


PY = [sys.executable, "-B"]
pioneer = ROOT / "packages/pioneer-agent"
text = run("q05-targeted", PY+["-m","unittest","test_seasonal_retriever","test_quality_eval","-v"],qa/"tests")
assert sorted(re.findall(r"^test_\w+ \(((?:test_seasonal_retriever|test_quality_eval)\.\w+\.test_\w+)\) \.\.\. ok$",text,re.MULTILINE)) == sorted(expected_names)
run("q04-targeted",PY+["-m","unittest","discover","-s","tests","-p","test_claim_spans.py","-v"],qa)
text = run("resource-close",PY+["-W","always::ResourceWarning","-m","unittest","test_lineup_frame_extractor.CropIntoColumnsTests.test_splits_and_upscales","-v"],qa/"tests")
assert "ResourceWarning" not in text
old_warnings = (OLD/"resource-warning.log").read_text().count("ResourceWarning: unclosed file")
assert old_warnings == 3
summary["results"]["resource_warnings"] = dict(old=old_warnings,new=0)
run("h07a",PY+["-m","unittest","test_task_approval","-v"],pioneer/"tests")
text=run("h10-causal",PY+["-W","error::RuntimeWarning","-m","unittest","test_causal_trace","-v"],pioneer/"tests")
assert "RuntimeWarning" not in text and "was never awaited" not in text
for package in ("qa-agent","pioneer-agent","sanmou-common"):
    run(package+"-full",PY+["-m","unittest","discover","-s","tests","-p","test_*.py","-v"],ROOT/"packages"/package)
for version in ("v1","v2","v3","v4"):
    text=run(version+"-cli",PY+["-m","qa_agent.quality_eval.runner","--baseline",version,"--output",str(OUT/(version+".json"))],qa,0 if version=="v4" else 1)
    if version!="v4": assert "frozen KB/production source drift" in text and not (OUT/(version+".json")).exists()
run("q04-cli",PY+["-m","qa_agent.quality_eval.claim_spans","--baseline","claim-spans-v1","--output",str(OUT/"q04.json")],qa)
run("h09-cli",PY+["-m","pioneer_agent.app.task_eval","--output",str(OUT/"h09")],ROOT)
save("commands.json",summary)
v4,old=json.loads((OUT/"v4.json").read_bytes()),json.loads((OLD/"v3.json").read_bytes())
assert sha((OLD/"v3.json").read_bytes())=="db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec"
allowed={"protocol","baseline_commit","cases_sha256","production","eval_source","season"}
assert {k:v for k,v in v4.items() if k not in allowed}=={k:v for k,v in old.items() if k not in allowed}
assert v4["season"]["gate_pass"] and v4["season"]["passed"]==v4["season"]["denominator"]==8
assert v4["kb"]==old["kb"] and v4["production"]==freeze["production"]
q04,oldq=json.loads((OUT/"q04.json").read_bytes()),json.loads((OLD/"q04.json").read_bytes())
news,olds=q04.pop("eval_source"),oldq.pop("eval_source")
assert q04==oldq
newfile="src/qa_agent/quality_eval/season_cases.py"
changedfile="src/qa_agent/quality_eval/runner.py"
assert set(news["files"])-set(olds["files"])=={newfile}
assert {k:v for k,v in news["files"].items() if k not in {newfile,changedfile}}=={k:v for k,v in olds["files"].items() if k!=changedfile}
assert news==v4["eval_source"] and news["algorithm"]==olds["algorithm"]
for manifest in (news,v4["production"],v4["kb"]):
    for path,value in manifest["files"].items(): assert sha((qa/path).read_bytes())==value,path
    assert sha(json.dumps(manifest["files"],sort_keys=True,ensure_ascii=False).encode())==manifest["digest"]
h09=json.loads((OUT/"h09/report.json").read_bytes())
assert h09["source"]["commit"]==CODE and h09["source"]["tree"]==TREE
assert h09["complete"] and h09["gate_pass"] and h09["totals"]["control_pass"]==8
summary["results"].update(v4=dict(sha256=sha((OUT/"v4.json").read_bytes()),allowed_delta=sorted(allowed),inherited_projection_equal=True,season=v4["season"]),
    q04=dict(sha256=sha((OUT/"q04.json").read_bytes()),all_non_source_fields_equal=True,eval_source=news),
    h09=dict(sha256=sha((OUT/"h09/report.json").read_bytes()),totals=h09["totals"]))
assert not git("diff","--name-only","HEAD")
assert sha((OUT/"v4.json").read_bytes())=="c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c"
assert sha((OUT/"q04.json").read_bytes())=="b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6"
summary["scope"]["repair_only_utf8_text_io_ast_equal"] = True
save("summary.json",summary)
raise SystemExit(bool(summary["failures"]))
