# H09b independent review plan (frozen before author delivery)

Frozen on 2026-10-06 against contract/source `cb1509ef36317815f8a454d7dd6a6b1474c46f39`, before inspection of author WIP. Reviewer branch: `codex/h09b-cr-20261006`.

## Finite acceptance matrix

1. Inspect exactly the existing Windows workflow gate, stdlib checker and its unittest changes. Preserve runtime, metadata rules, suite, fixtures, dependencies, permissions, runner/job/actions and original H06 gates.
2. Check actual native Windows process identity and physical local drive checkout/output; reject UNC/network/WSL/reparse aliases. Require current Python subprocess invoking the existing task-eval CLI, argument arrays, timeout, fresh owned parent and nonexistent output child.
3. Bind report to pre/post Git HEAD/tree and GITHUB_SHA, suite/fixture bytes and eight unique case IDs. Reject duplicate/nonfinite JSON, bool-as-int, false aggregate/case consistency, authority/model/pending/provider/live/holdout drift. Expected safety failures must remain accepted where the frozen suite specifies them.
4. Check artifact relative paths, physical file metadata and original byte hashes. Exercise bad bytes, escape/link paths and exit-zero-without-valid-report.
5. Check success and failure report-byte retention, finite report/log budgets and exact byte count/hash. Independently test missing/duplicate/out-of-order/oversize/truncated frames and chunks. Frame completion is not semantic acceptance. Never execute reconstructed content or dump full base64 into model context.
6. Run native Windows stdlib unit tests and independent synthetic-report probes; label mocks as mocks. Linux CLI/negative-platform tests, if run, are Linux evidence only. Preserve raw failures and source-bound logs/probes in the review deliverable.
7. Review fixed immutable author SHA and full report; repairs require a new SHA review. Maximum pre-publication verdict is APPROVE_CODE_SCOPED pending hosted Windows. Exact published final SHA, actual new hosted Windows step and reconstructed log report are separately required for H09b completion.

## Stop boundaries

No push, master merge, CI retry, network/dependency installation, game/provider/.env access or runtime repair. No retroactive enlargement of H09a acceptance. Report real runtime defects to the coordinator for separate scope. This is the sole independent reviewer; no additional reviewer delegation. Finish this bounded slice without starting another project.
