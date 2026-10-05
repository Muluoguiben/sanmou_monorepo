# H06a CR01 remains open: ownership teardown masks cancellation

Interim REQUEST CHANGES on repair source `dea73e062b70eb6d34108de87f843e40794d97df`, tree `4a754c7c1a329357df6ea25842d8219ffa76d3a0`. The full 1557-file archive was verified against Git blobs before testing; manifest SHA-256 `7fe177700f6d8b42bdc3c0a92eb2a7599ddd9a65304241ad63ac9f47254e8546`.

CR01's MCP lifetime repair does not cover the outer owner context manager. `RunOwnership.__exit__` (`run_store.py:44-45`) calls `close()` (`:50-66`) without preserving the active exception; `_release()` failure replaces primary cancellation. The independent probe runs a real CLI cancellation with normal fake-client cleanup, then performs the actual LocalLock.close before injecting a secondary OSError. Observed result is OSError instead of CancelledError. Using post-release injection deliberately avoids leaking the test lock and isolates exception priority, not lock implementation or a new filesystem threat model.

This is the already-required R08 primary-error/cleanup gate, not a new feature request. The same error-preservation review applies to direct-runner finally and constructor cleanup paths. No assertion is made here that every such path has been reproduced. Retain cancellation/conflict identity and secondary cleanup diagnostics while keeping ownership cleanup bounded; do not silently claim successful cleanup.

Exact execution:

```bash
cd /tmp/h06a-cr-dea73e0/source/packages/pioneer-agent/tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../src:../../sanmou-common/src:. python3 -B \
 /mnt/c/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo/docs/test-reports/2026-10-06/H06a-CR-artifacts/test_owner_cleanup_primary.py
```

Runtime `/usr/bin/python3`, Linux/WSL ext4, Python 3.12.3. Result: 1 test, 1 ERROR, 0 skips, 0.110 seconds. Original raw log `../test-reports/2026-10-06/H06a-CR-artifacts/dea73e0-owner-cleanup-red.log`; probe `test_owner_cleanup_primary.py` in the same directory. The log shows the original CancelledError followed by `RunOwnership.__exit__ -> close -> _release -> OSError`; the outer exception contract is not preserved by traceback context alone.

No source or existing red evidence changed. This interim finding is sent promptly while the remaining immutable-source checks proceed; it does not close CR02/CR03 or establish native full integration. Any next repair requires new immutable source identity and re-review.
