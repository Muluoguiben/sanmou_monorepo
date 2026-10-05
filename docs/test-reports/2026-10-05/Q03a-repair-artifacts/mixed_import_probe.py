"""Actual two-root import reproducer: A executes, B's manifests are reported.

Only a disposable temp copy is changed; frozen review source is never edited.
No monkeypatch of runner.__file__, snapshot, digest, or Python module globals.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PACKAGE = ROOT / "packages/qa-agent"
child_code = r'''
import importlib.util, json, pathlib, socket, sys
def forbidden(*args, **kwargs):
    raise AssertionError("network forbidden")
socket.socket.connect = forbidden
socket.getaddrinfo = forbidden
b = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("review_runner_b", b / "src/qa_agent/quality_eval/runner.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = module.run(b, baseline="v2")
import qa_agent.retrieval.retriever as loaded
print(json.dumps({"runner_root": str(pathlib.Path(module.__file__).resolve()),
    "actual_retriever_file": str(pathlib.Path(loaded.__file__).resolve()),
    "claimed_production_digest": result["production"]["digest"],
    "baseline_commit": result["baseline_commit"],
    "recall": result["retrieval"]["macro_recall"],
    "assessment_cases": len(result["assessment_cases"]), "provider": result["provider"]}))
'''

with tempfile.TemporaryDirectory(prefix="q03a-cr-import-a-") as d:
    a = Path(d)
    shutil.copytree(PACKAGE / "src", a / "src")
    retriever = a / "src/qa_agent/retrieval/retriever.py"
    original = retriever.read_text(encoding="utf-8-sig")
    needle = "        results: list[RetrievedChunk] = []"
    if original.count(needle) != 1:
        raise AssertionError("unexpected frozen source shape")
    retriever.write_text(original.replace(needle, "        return []  # synthetic version A\n" + needle), encoding="utf-8")
    env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if key in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(a / "src") + ":" + str(ROOT / "packages/sanmou-common/src"))
    completed = subprocess.run([sys.executable, "-B", "-c", child_code, str(PACKAGE)],
        env=env, cwd=a, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sys.stdout.buffer.write(completed.stdout)
    if completed.returncode:
        raise SystemExit(completed.returncode)
    actual = json.loads(completed.stdout)
    if actual["recall"]["value"] != 0 or str(a) not in actual["actual_retriever_file"]:
        raise AssertionError("mixed-root preconditions not met")
    # Expected safety contract: reject the mismatched execution identity.
    raise SystemExit("REPRODUCED: v2 accepted root A execution under root B source identity")
