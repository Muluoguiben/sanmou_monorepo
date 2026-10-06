"""Q05a-P1: real non-UTF file locale, UTF-8 stdout only, original targeted tests."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

root, out = (Path(value).resolve() for value in sys.argv[1:3])
source = sys.argv[3]
out.mkdir(parents=True, exist_ok=False)
def git(*args):
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-C", str(root), *args])
def sha(raw):
    return hashlib.sha256(raw).hexdigest()
assert git("rev-parse", "HEAD").decode().strip() == source
tree = git("rev-parse", "HEAD^{tree}").decode().strip()
assert not git("diff", "--name-only", "HEAD", "--", "packages", ".github")
env = dict(os.environ, LC_ALL="C", LANG="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0",
           PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
env.pop("SANMOU_CAPTURE_TOKEN", None)
env["PYTHONPATH"] = os.pathsep.join([str(root / "packages/qa-agent/src"),
    str(root / "packages/sanmou-common/src"), "/tmp/sanmou-cr-20261005-6155-deps"])
fixture = root / "packages/qa-agent/tests/fixtures/quality_eval/v4/cases.json"
metadata_code = """import json, locale, sys
from pathlib import Path
p = Path(sys.argv[1])
with p.open() as stream:
    file_encoding = stream.encoding
error = None
try:
    p.read_text()
except UnicodeDecodeError as exc:
    error = {'encoding': exc.encoding, 'start': exc.start, 'end': exc.end, 'reason': exc.reason}
print(json.dumps({'locale_encoding': locale.getencoding(), 'preferred_encoding': locale.getpreferredencoding(False),
    'utf8_mode': sys.flags.utf8_mode, 'stdout_encoding': sys.stdout.encoding, 'file_text_encoding': file_encoding,
    'nonascii_fixture_bytes': sum(byte >= 128 for byte in p.read_bytes()), 'default_read_error': error}))
"""
metadata_argv = [sys.executable, "-B", "-c", metadata_code, str(fixture)]
preflight = subprocess.run(metadata_argv, env=env, capture_output=True, timeout=30)
(out / "locale-preflight.log").write_bytes(preflight.stdout + preflight.stderr)
assert preflight.returncode == 0
metadata = json.loads(preflight.stdout)
assert metadata["utf8_mode"] == 0
assert metadata["file_text_encoding"].lower().replace("-", "") not in {"utf8", "utf8sig"}
assert metadata["default_read_error"] is not None and metadata["nonascii_fixture_bytes"] > 0
argv = [sys.executable, "-B", "-m", "unittest", "test_seasonal_retriever", "test_quality_eval", "-v"]
cwd = root / "packages/qa-agent/tests"
with (out / "targeted-nonutf.log").open("xb") as stream:
    result = subprocess.run(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
raw = (out / "targeted-nonutf.log").read_bytes()
counts = re.findall(rb"Ran (\d+) tests? in ", raw)
names = re.findall(rb"^test_\w+ \(((?:test_seasonal_retriever|test_quality_eval)\.\w+\.test_\w+)\)", raw, re.M)
record = {"issue": "Q05a-P1", "source": source, "tree": tree, "locale": metadata,
    "locale_environment": {key: env[key] for key in ("LC_ALL", "LANG", "PYTHONUTF8", "PYTHONCOERCECLOCALE", "PYTHONIOENCODING")},
    "preflight_argv": metadata_argv, "argv": argv, "cwd": str(cwd), "PYTHONPATH": env["PYTHONPATH"],
    "exit": result.returncode, "tests": int(counts[-1]) if counts else None,
    "qualified_test_names": sorted(name.decode() for name in names),
    "log_sha256": sha(raw), "log_bytes": len(raw), "fixture_sha256": sha(fixture.read_bytes()),
    "unicode_decode_error_occurrences": raw.count(b"UnicodeDecodeError:"),
    "native_windows": "not_executed; real Linux C file locale portability control"}
(out / "summary.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: record[k] for k in ("issue", "source", "locale", "exit", "tests", "unicode_decode_error_occurrences")}), flush=True)
assert record["tests"] == 44 and len(names) == 44
assert result.returncode == 0, "targeted tests must work without UTF-8 file locale"
assert b"... skipped " not in raw and b"UnicodeDecodeError:" not in raw
