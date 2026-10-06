"""Fixed-source H08a offline regression and real non-UTF text locale check."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT, OUT, CODE = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), sys.argv[3]
BASE = "60e3e002c7b38571e76d344dd100b47d053244e2"
CONTRACT = "df8447ae8807e2baa97a05ada3b209bfb7e3688b"
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
assert not git("diff", "--name-only", "HEAD")
changed = git("diff", "--name-only", CONTRACT, CODE).decode().splitlines()
assert changed == [".github/workflows/regression.yml",
    "docs/harness-readonly-skill-registry-h08a-interface-2026-10-06.md",
    "packages/pioneer-agent/src/pioneer_agent/agent_harness/skill_registry.py",
    "packages/pioneer-agent/tests/test_skill_registry.py"]
for path in ("packages/qa-agent", "packages/sanmou-common", "packages/pioneer-agent/tests/fixtures"):
    assert git("rev-parse", BASE + ":" + path) == git("rev-parse", CODE + ":" + path)
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
addition = (b"      - name: Windows H08a readonly skill registry\n"
    b"        working-directory: packages/pioneer-agent/tests\n"
    b"        run: python -B -W error::RuntimeWarning -m unittest test_skill_registry -v\n")
assert actual.count(addition) == 1 and actual.replace(addition, b"") == before
old_yaml, new_yaml = yaml.load(before, Loader=yaml.BaseLoader), yaml.load(actual, Loader=yaml.BaseLoader)
steps = new_yaml["jobs"]["windows"]["steps"]
index = next(i for i, step in enumerate(steps) if step.get("name") == "Windows H08a readonly skill registry")
assert steps[index-1]["name"] == "Windows Q05a explicit season retrieval"
steps.pop(index)
assert old_yaml == new_yaml
module = ast.parse((ROOT / "packages/pioneer-agent/tests/test_skill_registry.py").read_bytes())
names = ["test_skill_registry." + cls.name + "." + method.name for cls in module.body if isinstance(cls, ast.ClassDef)
         for method in cls.body if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) and method.name.startswith("test_")]
assert len(names) == 23
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = ":".join(str(ROOT / p) for p in ("packages/pioneer-agent/src", "packages/qa-agent/src",
    "packages/sanmou-common/src", "packages/pioneer-agent/tests")) + ":" + DEPS
summary = dict(source=CODE, tree=TREE, baseline=BASE, contract=CONTRACT,
    verifier_sha256=sha(Path(__file__).read_bytes()), runtime=dict(executable=sys.executable, python=sys.version),
    scope=dict(changed=changed, unchanged_qa_common_old_fixtures=True, workflow_inverse_bytes_yaml_equal=True,
               git_byte_verified_inputs=len(inputs), input_manifest_sha256=sha(json.dumps(inputs,separators=(",", ":")).encode()),
               targeted_names=sorted(names)), commands=[], failures=[], results={},
    native="pending exact-final-SHA Hosted H08a 23 qualified names/0skip/exit0 and all existing gates; no local native install/mock")


def run(name, argv, cwd, expected=0, overrides=None):
    path = OUT / (name + ".log")
    started = time.time()
    local_env = {**env, **(overrides or {})}
    with path.open("xb") as handle:
        result = subprocess.run(argv, cwd=cwd, env=local_env, stdout=handle, stderr=subprocess.STDOUT, timeout=900)
    raw = path.read_bytes()
    assert len(raw) <= 2 * 1024 * 1024
    text = raw.decode("utf-8", errors="replace")
    count = re.findall(r"^Ran (\d+) tests? in ", text, re.MULTILINE)
    skips = re.findall(r"^OK \(skipped=(\d+)\)", text, re.MULTILINE)
    row = dict(name=name, argv=argv, cwd=str(cwd), PYTHONPATH=env["PYTHONPATH"], environment_overrides=overrides or {},
        exit=result.returncode, expected_exit=expected, tests=int(count[-1]) if count else None,
        skipped=int(skips[-1]) if skips else 0, seconds=time.time()-started,
        log=path.name, log_bytes=len(raw), log_sha256=sha(raw))
    summary["commands"].append(row)
    if result.returncode != expected: summary["failures"].append(name)
    print(json.dumps({key:row[key] for key in ("name","exit","expected_exit","tests","skipped")}),flush=True)
    if name in {"h08-targeted", "h08-nonutf-text"}:
        assert sorted(re.findall(r"^test_\w+ \((test_skill_registry\.\w+\.test_\w+)\) \.\.\. ok$",text,re.MULTILINE)) == sorted(names)
        assert "RuntimeWarning" not in text and "was never awaited" not in text
    return text


PY = [sys.executable, "-B"]
pioneer,qa = ROOT/"packages/pioneer-agent",ROOT/"packages/qa-agent"
run("h08-targeted",PY+["-W","error::RuntimeWarning","-m","unittest","test_skill_registry","-v"],pioneer/"tests")
bootstrap = """import json,locale,sys,unittest
locale.setlocale(locale.LC_CTYPE,'C')
with open('test_skill_registry.py') as handle: default_open_encoding=handle.encoding
metadata=dict(encoding=locale.getencoding(),default_open_encoding=default_open_encoding,utf8_mode=sys.flags.utf8_mode,filesystem_encoding=sys.getfilesystemencoding())
print(json.dumps(metadata),flush=True)
assert metadata['encoding']==metadata['default_open_encoding']=='ANSI_X3.4-1968'
assert metadata['utf8_mode']==0 and metadata['filesystem_encoding']=='utf-8'
unittest.main(module=None,argv=['nonutf-text','test_skill_registry','-v'])
"""
text=run("h08-nonutf-text",PY+["-W","error::RuntimeWarning","-c",bootstrap],pioneer/"tests",
    overrides=dict(LC_ALL="C.UTF-8",PYTHONUTF8="0",PYTHONCOERCECLOCALE="0",PYTHONIOENCODING="utf-8"))
summary["results"]["text_locale"] = json.loads(text.splitlines()[0])
run("h07a",PY+["-m","unittest","test_task_approval","-v"],pioneer/"tests")
run("h10-causal",PY+["-W","error::RuntimeWarning","-m","unittest","test_causal_trace","-v"],pioneer/"tests")
run("q04-targeted",PY+["-m","unittest","discover","-s","tests","-p","test_claim_spans.py","-v"],qa)
run("q05-targeted",PY+["-m","unittest","test_seasonal_retriever","test_quality_eval","-v"],qa/"tests")
for package in ("pioneer-agent","qa-agent","sanmou-common"):
    run(package+"-full",PY+["-m","unittest","discover","-s","tests","-p","test_*.py","-v"],ROOT/"packages"/package)
run("h09-cli",PY+["-m","pioneer_agent.app.task_eval","--output",str(OUT/"h09")],ROOT)
for version in ("v1","v2","v3","v4"):
    text=run(version+"-cli",PY+["-m","qa_agent.quality_eval.runner","--baseline",version,"--output",str(OUT/(version+".json"))],qa,0 if version=="v4" else 1)
    if version!="v4": assert "frozen KB/production source drift" in text and not (OUT/(version+".json")).exists()
run("q04-cli",PY+["-m","qa_agent.quality_eval.claim_spans","--baseline","claim-spans-v1","--output",str(OUT/"q04.json")],qa)
save("commands.json",summary)
v4,q04=sha((OUT/"v4.json").read_bytes()),sha((OUT/"q04.json").read_bytes())
assert v4=="c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c"
assert q04=="b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6"
h09=json.loads((OUT/"h09/report.json").read_bytes())
assert h09["source"]["commit"]==CODE and h09["source"]["tree"]==TREE
assert h09["complete"] and h09["gate_pass"] and h09["totals"]["control_pass"]==8
summary["results"].update(v4_sha256=v4,q04_sha256=q04,h09=dict(sha256=sha((OUT/"h09/report.json").read_bytes()),totals=h09["totals"]))
assert not git("diff","--name-only","HEAD")
save("summary.json",summary)
raise SystemExit(bool(summary["failures"]))
