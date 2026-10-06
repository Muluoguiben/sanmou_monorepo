# H07a independent review, round 2

Verdict: **REQUEST CHANGES**, one remaining clock-rollback boundary.
Fixed source: `a23ccf13049d289bcf827265b726bff2956a6948`, tree
`dd12dbcab10648314a8aefd8f8929dc4df442d68`; verified in fresh detached ext4 checkout
`/tmp/h07a-cr-a23-20261006`.

R1 findings are fixed for their original triggers. Immutable original probes have
4 pass and the sole documented spelling-only mismatch (exit 1, actual stale result
`failed/observation_stale`). Canonical probes have 5 pass, exit 0. Independent
focused tests have 100 pass, exit 0. Full source-bound verification is still running;
no final approval is implied by these component passes.

## F3 [P2]: consumed approval time is not enforced during revalidation

Source: `packages/pioneer-agent/src/pioneer_agent/agent_harness/task_runner.py:485-492`
(`_check_approval_observation`), called after new-observation/revalidated saves.

The new watermark is checked in awaiting state, but the revalidation helper checks
only remaining budget and frame freshness. If the clock rolls back after the
consumption record is durable while remaining later than the new captured_at, both
checks pass and the task can claim `goal_verified`.

Frozen probe `h07a-independent-postconsume-clock.py`, commit
`d9ade7a7b3e473c7be30b1280086e24a1405d8f1`, SHA256
`7a122fc02ff4cb012b3c2ed7105734b8fc38eab47aab442cf23ab3088f6fef0d`:
old capture t+1; request created t+2; approval consumed t+3; store write returns
with clock t+2.5; next capture t+2. The capture is new, strictly newer than the old
capture and not in the future, so this isolates the previously observed approval
clock regression rather than replay/future-frame behavior. Actual result is
`succeeded/goal_verified`, expected `failed/approval_clock_rollback`; zero policy is
also asserted. Direct process exit **1**, one test, one failure, zero skips.

This is the original plan's clock-rollback plus post-consumption revalidation gate,
not a new domain or permission requirement. Minimum fix: make the existing
revalidation safety helper compare current approval clock to its persisted
last_checked_at/consumed_at and reject regression before success/policy. Retain
existing budget module and do not lower the watermark or reset request expiry.

Reproduction, cwd `/tmp/h07a-cr-a23-20261006`:

```
env PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src:packages/pioneer-agent/tests:/tmp/sanmou-cr-20261005-6155-deps \
python3 /mnt/c/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo/docs/test-reports/2026-10-06/h07a-independent-postconsume-clock.py
```

Raw output is `h07a-independent-a23ccf1-postconsume-red.log`. Original five probes
and canonical override remain unchanged. No author code was edited by reviewer.

## Environment note

Initial full verifier attempt on the existing Windows checkout stopped at source
preflight: WSL Git saw historical CRLF files different from LF blobs (for example
AGENTS.md 305 added/305 removed), while Windows Git status was clean. Modified
task_runner raw blob matched its source tree. No old files were rewritten and no
assertion was relaxed. A fresh, previously nonexistent ext4 detached worktree was
created at the exact author SHA, which passed source-byte preflight and is running
the actual tests. No Q06 or historical archive member was inspected.
