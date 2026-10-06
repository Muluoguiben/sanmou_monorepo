# Q05a-P1 — REQUEST CHANGES: test fixture text I/O depends on file locale

Source `3d8257bf03d47bb86fb80994c924987033b1858a`, tree
`0aa22ba210af5fb112b9ad073939428961511b4d`. Severity HIGH for the newly enabled
Windows targeted gate; publication is blocked by coordinator. This is an additive
portability review, not a rewrite of the prior source-specific Linux approval.

Frozen independent probe: `faefc08f0dd055ff2abfb8e9fc56c9b7063dc61d`.
It runs the original command and all original assertions on unchanged source:

```text
LC_ALL=C LANG=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 PYTHONIOENCODING=utf-8
python3 -B -m unittest test_seasonal_retriever test_quality_eval -v
```

Actual child metadata records utf8_mode=0, locale/preferred/default file encoding
ANSI_X3.4-1968, and stdout encoding UTF-8. Output encoding is deliberately not
claimed as file encoding. v4 fixture has 1116 non-ASCII bytes; default read_text
raises UnicodeDecodeError(ascii, start=175). The original test run exits 1:
`Ran 44 tests ... FAILED (failures=1, errors=27)`. Raw log and exact command/locale/
source/fixture/log hashes are retained under `q05a-nonutf-original-results/`.

## Direct source evidence / minimal correction

- `packages/qa-agent/tests/test_quality_eval.py:21`: default read_text in setUp
  cannot decode the UTF-8 fixture, causing all 24 quality methods to error before
  their assertions. Additional default reads/writes at 157, 186, 190, 197, 198,
  210 have the same portability assumption.
- `packages/qa-agent/tests/test_seasonal_retriever.py:172`, 180, 181, 223, 227,
  236: fixture/report reads also omit encoding. Three seasonal test errors on
  the actual run point directly to fixture reads. Line 212 has another default
  report read, even though its current content need not contain non-ASCII text.

Use explicit encoding="utf-8" only on Path.read_text/write_text calls in these
two already-modified test files. Preserve all 44 test names, assertions, inputs,
production readers, fixtures/freeze and CI/environment settings. Do not silence
errors, skip tests or force process UTF-8 mode to conceal the issue. The narrow
AST allowance for verification is adding only this encoding keyword to these
TextIO calls; strip only that addition when comparing to original 3d ASTs.

## Separate POSIX startup side effect / next verification

The additional one failure is not labelled a second product finding. Strict C
startup also gives POSIX Python an ASCII filesystem encoding. A non-ASCII source
filename becomes surrogate-escaped, and snapshot digest raises "utf-8 ... surrogates
not allowed" before the foreign-module guard. This differs from Windows' Unicode
filesystem path handling and may persist after the test-only I/O correction.

Keep this original run unchanged. A supplemental real file-locale control should
start with UTF-8 filesystem encoding, then set LC_CTYPE=C in the child before
running the same tests, with utf8_mode still 0 and actual default file encoding
recorded as non-UTF. This is a proposed environment-isolation control, not a mock
reader or permission to modify production/fixtures for POSIX ASCII filenames.
Final Windows success still requires exact final SHA Hosted logs; Linux locale
controls do not supply that native evidence. Root separately reported cp936
default-read failure on Windows; that was not this reviewer's execution.

No local native dependency exploration/install, production repair, old-report
rewrite, main/push, Q06/archive/provider/game/.env access. Await fixed test-only
source and retain all original red evidence for repair verification.
