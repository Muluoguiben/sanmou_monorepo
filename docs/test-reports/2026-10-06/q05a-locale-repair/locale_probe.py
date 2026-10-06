"""Record actual non-UTF locale and run the unchanged Q05a targeted group."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT, OUT = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True, exist_ok=False)
env = dict(os.environ, LC_ALL="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0",
           PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = str(ROOT / "packages/qa-agent/src") + ":" + str(ROOT / "packages/sanmou-common/src") + ":/tmp/sanmou-cr-20261005-6155-deps"
metadata_argv = [sys.executable, "-B", "-c", "import locale,sys,json; print(json.dumps({'encoding':locale.getencoding(),'utf8_mode':sys.flags.utf8_mode,'filesystem_encoding':sys.getfilesystemencoding(),'stdout_encoding':sys.stdout.encoding}))"]
metadata = subprocess.run(metadata_argv, env=env, capture_output=True, check=True)
locale_state = json.loads(metadata.stdout)
assert locale_state["utf8_mode"] == 0 and locale_state["encoding"].lower() not in {"utf-8", "utf8"}
argv = [sys.executable, "-B", "-m", "unittest", "test_seasonal_retriever", "test_quality_eval", "-v"]
cwd = ROOT / "packages/qa-agent/tests"
log = OUT / "targeted.log"
with log.open("xb") as handle:
    result = subprocess.run(argv, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, timeout=180)
git = lambda *args: subprocess.check_output(["git", "-C", str(ROOT), *args]).decode().strip()
summary = dict(source=git("rev-parse", "HEAD"), tree=git("rev-parse", "HEAD^{tree}"),
    environment={key:env[key] for key in ("LC_ALL","PYTHONUTF8","PYTHONCOERCECLOCALE","PYTHONIOENCODING","PYTHONPATH")},
    metadata_argv=metadata_argv, locale=locale_state, argv=argv, cwd=str(cwd), exit=result.returncode,
    log=log.name, log_bytes=log.stat().st_size, log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
with (OUT / "summary.json").open("x", encoding="utf-8") as stream:
    json.dump(summary, stream, indent=2)
    stream.write("\n")
print(json.dumps(summary), flush=True)
raise SystemExit(result.returncode)
