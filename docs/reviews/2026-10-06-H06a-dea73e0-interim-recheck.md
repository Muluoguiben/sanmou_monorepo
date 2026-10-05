# H06a dea73e0 interim recheck

Source `dea73e062b70eb6d34108de87f843e40794d97df`, tree `4a754c7c1a329357df6ea25842d8219ffa76d3a0`. Still REQUEST CHANGES for CR01 owned-teardown error priority; this report does not approve another revision.

Unchanged original probes were rerun on the verified 1557-file ext4 snapshot. Logs are separately preserved under `docs/test-reports/2026-10-06/H06a-CR-artifacts/dea73e0-recheck/`; no original red file was edited.

| Probe | Tests / result | Seconds |
| --- | --- | --- |
| independent lifecycle | 6 pass (3 independent + 3 imported existing CLI tests) | 0.948 |
| primary conflict plus MCP cleanup | 1 pass | 0.101 |
| concurrent old close | 1 test, both memory/JSON subcases pass | 0.005 |
| shared external owner | 1 pass, second admission refused; 4 actual and 4 charged calls | 0.210 |
| independent store | 5 pass | 7.630 |
| independent three crash boundaries | 1 test / 3 subcases pass | 7.749 |
| independent CLI race | 1 test / 2 process scenarios pass | 9.860 |
| new shared-owner admission | 1 pass | 0.189 |
| new owned-teardown priority matrix | 6 tests: successful-body cleanup fault surfaces (pass); 5 primary-preservation tests fail, producing 6 ERROR records because pause/cancel has two subcases | 0.336 |

All have zero skips. The original instruction-line close scheduler now pauses after `_released` was set and the serialized OS release completed, so both successor-owner assertions pass without timeout; code inspection confirms the one-time transition occurs under an RLock. This closes the original CR02 interleaving for this source, not a claim about arbitrary same-user mutation.

CR03 admission is additionally checked with `test_shared_owner_admission.py`: second construction raises CheckpointConflict with zero calls and no checkpoint change; incumbent owner still checks valid, a separate JsonRunStore cannot acquire, the first runner executes/persists four charged calls, external lifetime remains owned after runner return, and explicit context exit permits a successor. This is affirmative post-rejection evidence, not interpreting a construct-time script crash as success.

CR01 MCP-client cleanup cases pass. Its outer owned-teardown branch remains open: independent `test_teardown_matrix.py` reproduces primary exception replacement for owner-context CAS conflict, direct-runner cancellation, constructor identity mismatch, reacquire/reload conflict, and idle pause/cancel save failure. In each case the injected fault first calls real LocalLock.close, then raises secondary OSError. The success-body case verifies cleanup errors must still surface when no primary exists. Raw matrix log SHA-256 `7722ec96b56127d8dc2e344ee25cc6c54de5fafed46ebf0753b4733a7161e5ff`.

Execution is through the new argv-safe `run_independent.py`, invoked as:

```text
wsl -d Ubuntu -- python3 -B <review-artifact-dir>/run_independent.py /tmp/h06a-cr-dea73e0/source /tmp/h06a-cr-dea73e0/recheck <probe stems listed above>
```

The launcher records real argv, cwd, exit, Python/platform and per-log SHA-256 to stdout, sets `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=../src:../../sanmou-common/src:.`, cwd `<source>/packages/pioneer-agent/tests`, and bounds each child at 90 seconds. Runtime remains Python 3.12.3 / Linux 6.6.87.2-microsoft-standard-WSL2. An initial PowerShell-to-bash loop expanded shell variables incorrectly and attempted to run `.py`; its setup error log is preserved separately. It is not counted as a source failure or a test result. The Python launcher avoids that quoting path.

Full-package and native full-integration conclusions are not yet made for this still-blocked source. Remaining repair/re-review and exact-source Windows H06a CI are required. No packages/source, fixtures, QA/KB, game or remote state changed.
