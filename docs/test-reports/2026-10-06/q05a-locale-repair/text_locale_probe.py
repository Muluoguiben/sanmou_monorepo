"""Supplemental real ASCII text I/O with UTF-8 filesystem; not native Windows."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT, OUT = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=False)
env = dict(os.environ, LC_ALL="C.UTF-8", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0",
           PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = str(ROOT / "packages/qa-agent/src") + ":" + str(ROOT / "packages/sanmou-common/src") + ":/tmp/sanmou-cr-20261005-6155-deps"
bootstrap = """import json,locale,sys,unittest
locale.setlocale(locale.LC_CTYPE, 'C')
metadata = dict(encoding=locale.getencoding(), utf8_mode=sys.flags.utf8_mode,
                filesystem_encoding=sys.getfilesystemencoding(), stdout_encoding=sys.stdout.encoding)
with open('test_quality_eval.py') as check:
    metadata['default_open_encoding'] = check.encoding
print(json.dumps(metadata), flush=True)
assert metadata['encoding'] == 'ANSI_X3.4-1968' and metadata['utf8_mode'] == 0
assert metadata['filesystem_encoding'] == 'utf-8'
assert metadata['default_open_encoding'] == metadata['encoding']
unittest.main(module=None, argv=['text-locale', 'test_seasonal_retriever', 'test_quality_eval', '-v'])
"""
argv = [sys.executable, "-B", "-c", bootstrap]
cwd = ROOT / "packages/qa-agent/tests"
path = OUT / "targeted.log"
with path.open("xb") as log:
    result = subprocess.run(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
git = lambda *args: subprocess.check_output(["git", "-C", str(ROOT), *args]).decode().strip()
summary = dict(source=git("rev-parse", "HEAD"), tree=git("rev-parse", "HEAD^{tree}"),
    argv=argv, cwd=str(cwd), exit=result.returncode,
    environment={key:env[key] for key in ("LC_ALL","PYTHONUTF8","PYTHONCOERCECLOCALE","PYTHONIOENCODING","PYTHONPATH")},
    locale=json.loads(path.read_text(encoding="utf-8").splitlines()[0]),
    limitation="Linux supplemental default-text-locale probe; filesystem stays UTF-8. Child CLI processes inherit startup C.UTF-8. Not native Windows.",
    log=path.name, log_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
with (OUT / "summary.json").open("x", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)
    handle.write("\n")
print(json.dumps(summary), flush=True)
raise SystemExit(result.returncode)
