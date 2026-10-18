"""Actual ASCII text locale with already-initialized UTF-8 filesystem encoding."""
import json
import locale
import os
from pathlib import Path
import sys
import unittest
from uuid import uuid4

assert sys.flags.utf8_mode == 0
assert sys.getfilesystemencoding().lower().replace("-", "") == "utf8"
locale.setlocale(locale.LC_CTYPE, "C")
path = Path(os.environ["TMPDIR"]) / ("qe0-locale-" + uuid4().hex + ".json")
path.write_text("{}", encoding="utf-8")
with path.open() as stream:  # Deliberate real default-encoding observation.
    encoding = stream.encoding
assert encoding.lower() in ("ascii", "us-ascii", "ansi_x3.4-1968")
metadata = dict(text_locale=locale.setlocale(locale.LC_CTYPE), default_text_encoding=encoding,
    filesystem_encoding=sys.getfilesystemencoding(), utf8_mode=sys.flags.utf8_mode,
    stdout_encoding=sys.stdout.encoding, scope="current test process; subprocess environment remains C.UTF-8")
path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
print(json.dumps(metadata), flush=True)
unittest.main(module=None, argv=["unittest", "test_prepare_e0_review", "-v"])
