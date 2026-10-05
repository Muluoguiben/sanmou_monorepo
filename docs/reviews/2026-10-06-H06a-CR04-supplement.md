# H06a CR04 supplemental review: retired harness wrapper damages resume

**REQUEST CHANGES / P2.** This supplemental finding supersedes the earlier no-open-source-blocker disposition for source `96575c30dea99ab58265052987e79bb4e76c0972`, tree `8c305fe09cda5cc9e10e306a05f970f644e735f5`. The historical scoped APPROVE in `26d997bc0d37e05888de4765e09ac66c8468a535` remains unedited; CR01/02/03 closure evidence is also retained. H06a had not yet been integrated/pushed when this follow-up was authorized.

## Finding

`TaskRunner.__init__` saves `harness.game_client` into `self._client` and replaces it with `_TaskClient(self)` (`task_runner.py` near lines 66-67). `close()` releases ownership but leaves that wrapper installed. After the first runner returns paused and closes, a caller following the contract's fresh-runner/fresh-ledger recovery path can reuse the same RecommendationHarness. The new runner then wraps the retired `_TaskClient` as its underlying client. On resume, the stale owner's check fails inside the nested wrapper; no real fake-client call is made, but the fresh runner writes a failed/tool_failure terminal checkpoint and charges additional reservations. This is sequential reuse, not concurrent harness sharing or arbitrary private mutation.

The fresh runner and ledger are legitimate new objects with a new acquired owner, identical run/task, and unchanged client/journal. The contract does not require a fresh harness. At minimum unsupported reuse must be rejected before dispatch/persistence with no checkpoint damage; preferably closing a runner must not leave a retired wrapper contaminating the caller's harness. This narrow issue does not request general concurrent/shared-harness support or a broad refactor.

## Independent reproduction and control

Probe: `docs/test-reports/2026-10-06/H06a-CR-artifacts/test_sequential_harness_reuse.py`.

- First runner makes one observation and pauses, releasing its owner.
- New TaskRunner, new RunBudgetLedger and new JsonRunStore acquire the same checkpoint using the first runner's public harness.
- Actual result: `failed/tool_failure`, **zero additional physical fake tool calls**, total reservations **5 -> 7** (the additional step and tool attempt), paused checkpoint overwritten as failed.
- Control constructs a fresh harness using the same underlying fake client and same checkpoint; result is `succeeded`, observations `obs-1`, `obs-2`, `obs-3`.
- Probe accepts either successful bounded resume or an explicit construction-time ValueError/RuntimeError rejection, but the rejection branch checks zero calls, unchanged checkpoint bytes and successor lock acquisition. An uncaught construction exception is not counted as passing.

Result: **2 tests, 1 pass / 1 failure, 0 skips, 0.725 seconds**. Same immutable byte-verified ext4 snapshot, `/usr/bin/python3` 3.12.3 / WSL Linux. This reproduces an independent auditor's candidate; numbers above are from this reviewer's own probe, not the auditor's log.

```text
wsl -d Ubuntu -- python3 -B /mnt/c/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo/docs/test-reports/2026-10-06/H06a-CR-artifacts/run_independent.py /tmp/h06a-cr-96575c3/source /tmp/h06a-cr-96575c3/supplement test_sequential_harness_reuse
```

Child cwd `/tmp/h06a-cr-96575c3/source/packages/pioneer-agent/tests`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=../src:../../sanmou-common/src:.`; argv uses the unchanged independent launcher and explicit probe path.

- Probe SHA-256: `a7368e2adc57b36aec7408611b30e4b2373e2d06f144e080b0d28b66e35edec8`.
- Original raw log: `docs/test-reports/2026-10-06/H06a-CR-artifacts/96575c3-sequential-harness-red.log`.
- Log SHA-256: `1715955a8d6b2b1b4565733dc2a7bb99ab6486f25055f2a174812dc9560838f3`.

No source changed and the previous 53-artifact manifest was not regenerated or edited; this supplement adds new evidence outside that historical manifest. A narrow author fix requires a new immutable source, original probe recheck and lifecycle/ownership regression. Full Windows lifecycle still requires the exact-final-SHA CI step; this finding does not expand authority or permit publication while unresolved.
