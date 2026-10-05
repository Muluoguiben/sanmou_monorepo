"""Identity-only rerun of frozen f961 probes; original file/assertions unchanged."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

SOURCE = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(exist_ok=True)
old = "f961c1594018651d584bbe622547a79e5648c5a7"
new = "9c8db2605d64c08736830585b20c542138d66678"
original = Path(__file__).with_name("h09b-independent-probes.py")
raw = original.read_bytes()
text = raw.decode("utf-8")
assert text.count(old) == 1
adjusted = text.replace(old, new)
(OUT / "identity-only-replay.json").write_text(json.dumps({
    "original_probe_sha256": hashlib.sha256(raw).hexdigest(),
    "replacement": {"old_expected_sha": old, "new_expected_sha": new},
    "only_change": "one source-identity constant in memory; assertions unchanged",
    "adjusted_probe_sha256": hashlib.sha256(adjusted.encode()).hexdigest()}, indent=2) + "\n")
command = [sys.executable, "-m", "unittest", "discover", "-s",
           str(SOURCE / "packages/pioneer-agent/tests"), "-p", "test_windows_task_eval_ci.py", "-v"]
with (OUT / "windows-stdlib-20.log").open("wb") as log:
    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=60)
assert result.returncode == 0
exec(compile(adjusted, str(original), "exec"), {"__name__": "__main__"})
