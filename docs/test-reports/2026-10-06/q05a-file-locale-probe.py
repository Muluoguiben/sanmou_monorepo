"""Real non-UTF text locale with Unicode filesystem paths; not Windows execution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root, out = (Path(p).resolve() for p in sys.argv[1:3])
source = sys.argv[3]
out.mkdir(parents=True, exist_ok=False)
git = lambda *args: subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *args])
assert git("rev-parse", "HEAD").decode().strip() == source
env = dict(os.environ, LC_ALL="C.UTF-8", LANG="C.UTF-8", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0",
           PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = os.pathsep.join([str(root / "packages/qa-agent/src"),
    str(root / "packages/sanmou-common/src"), "/tmp/sanmou-cr-20261005-6155-deps"])
metadata_path = out / "runtime-locale.json"
fixture = root / "packages/qa-agent/tests/fixtures/quality_eval/v4/cases.json"
bootstrap = """import json, locale, subprocess, sys, unittest
from pathlib import Path
startup = {'locale': locale.setlocale(locale.LC_CTYPE), 'filesystem_encoding': sys.getfilesystemencoding(),
           'utf8_mode': sys.flags.utf8_mode}
assert startup['filesystem_encoding'].lower().replace('-', '') == 'utf8'
assert startup['utf8_mode'] == 0
locale.setlocale(locale.LC_CTYPE, 'C')
with Path(sys.argv[1]).open() as stream:
    file_encoding = stream.encoding
runtime = {'locale': locale.setlocale(locale.LC_CTYPE), 'locale_encoding': locale.getencoding(),
           'file_encoding': file_encoding, 'filesystem_encoding': sys.getfilesystemencoding(),
           'utf8_mode': sys.flags.utf8_mode, 'stdout_encoding': sys.stdout.encoding}
assert runtime['file_encoding'].lower() in ('ansi_x3.4-1968', 'ascii', 'us-ascii')
assert runtime['filesystem_encoding'].lower().replace('-', '') == 'utf8' and runtime['utf8_mode'] == 0
# In-memory setlocale is NOT inherited by newly spawned interpreters. Record this
# explicitly; the target tests' CLI subprocesses inherit the same C.UTF-8 env.
child_code = 'import json,locale,sys; print(json.dumps(dict(locale=locale.setlocale(locale.LC_CTYPE),file_encoding=locale.getencoding(),filesystem_encoding=sys.getfilesystemencoding(),utf8_mode=sys.flags.utf8_mode)))'
spawned = json.loads(subprocess.check_output([sys.executable, '-B', '-c', child_code]))
record = {'startup': startup, 'target_test_process': runtime, 'spawned_interpreter': spawned,
          'scope': '44 tests execute under C text locale; nested CLI processes inherit C.UTF-8 environment'}
Path(sys.argv[2]).write_text(json.dumps(record, indent=2)+'\\n', encoding='utf-8')
print(json.dumps(record), flush=True)
result = unittest.main(module=None, argv=['unittest', 'test_seasonal_retriever', 'test_quality_eval', '-v'], exit=False).result
record['tests_run'] = result.testsRun
record['failures'] = len(result.failures)
record['errors'] = len(result.errors)
record['skips'] = len(result.skipped)
Path(sys.argv[2]).write_text(json.dumps(record, indent=2)+'\\n', encoding='utf-8')
raise SystemExit(0 if result.wasSuccessful() and result.testsRun == 44 and not result.skipped else 1)
"""
argv = [sys.executable, "-B", "-c", bootstrap, str(fixture), str(metadata_path)]
cwd = root / "packages/qa-agent/tests"
with (out / "targeted-file-locale.log").open("xb") as stream:
    result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
raw = (out / "targeted-file-locale.log").read_bytes()
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
record = {"issue": "Q05a-P1", "source": source, "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
    "argv": argv, "cwd": str(cwd), "PYTHONPATH": env["PYTHONPATH"],
    "environment": {key: env[key] for key in ("LC_ALL", "LANG", "PYTHONUTF8", "PYTHONCOERCECLOCALE", "PYTHONIOENCODING")},
    "locale": metadata, "exit": result.returncode, "log_bytes": len(raw),
    "log_sha256": hashlib.sha256(raw).hexdigest(), "native_windows": "not_executed"}
(out / "summary.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"source": source, "locale": metadata, "exit": result.returncode}), flush=True)
assert result.returncode == 0, "targeted tests must pass under real non-UTF text locale"
