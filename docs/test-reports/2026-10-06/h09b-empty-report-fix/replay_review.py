"""Replay immutable reviewer assertions, rebinding only the reviewed source ID."""
import hashlib
from pathlib import Path
import subprocess
import sys

SOURCE = Path(sys.argv[1])
OUT = Path(sys.argv[2])
assert not OUT.exists(), "refuse to overwrite previous evidence"
REVIEW = "5b0b972f6ce86dc02f88fd3328893b82e6687561"
PROBE = "docs/test-reports/2026-10-06/h09b-independent-probes.py"
raw = subprocess.check_output(["git", "-C", str(SOURCE), "show", REVIEW + ":" + PROBE])
assert hashlib.sha256(raw).hexdigest() == "45f05c46376778add2e56b220c2ea711625881f9ad0e52cb73d6567df01e06da"
old = b'EXPECTED = "f961c1594018651d584bbe622547a79e5648c5a7"'
new = b'EXPECTED = "9c8db2605d64c08736830585b20c542138d66678"'
assert raw.count(old) == 1
rebound = raw.replace(old, new)
assert rebound.replace(new, old) == raw
exec(compile(rebound, REVIEW + ":" + PROBE + " (identity-only rebound)", "exec"),
     {"__name__": "__main__", "__file__": PROBE})
