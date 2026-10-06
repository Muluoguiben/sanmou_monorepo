# H07a independent review, round 1

Verdict: **REQUEST CHANGES**. Two blocking correctness findings, reproduced by
three independent frozen assertions. No author implementation edits by reviewer.

Author source `8232c420b5c3a7533975293c9cd00380b439386e`, tree
`49d47d87d261cfef68632b66feded7a40baff0d0`; published baseline `110bd759`.
Plan frozen at `eeda927c945e765c78ea0512c3b78cf91c210082` before WIP inspection.
Independent probes frozen at `339aa56156cced5fe0b8ea274695a943f5cab576`, SHA256
`9c047a03ac85df4ba188025fd37225af5e6ed1d90d448d0154253834d3172d12`.
Review checkout packages were checked byte-identical by `git diff --exit-code
8232c420b5c3a7533975293c9cd00380b439386e -- packages` (exit 0).

## F1 [P1]: direct fresh-goal completion bypasses post-save safety checks

Source: `packages/pioneer-agent/src/pioneer_agent/agent_harness/task_runner.py:365-382`.
After the new observation checkpoint is saved, revalidation checks field provenance
but not current freshness or budget. The direct `goal_verified` branch returns
before the later `_check()` and post-policy observation check. A slow synchronous
checkpoint write can therefore turn already expired evidence or an elapsed run
deadline into a successful task result.

Two probes advance the controlled clock inside the actual store write after the
new observation was persisted, without changing its payload. Advancing observation
time by 120 seconds produces `succeeded/goal_verified` rather than
`failed/stale_observation`; advancing ledger time by 31 seconds against a 30-second
deadline produces the same false success rather than `failed/run_deadline`.
No sleep, provider, device or real effect is involved.

Smallest fix: recheck cancellation/budget and observation freshness after potentially
slow persistence and before declaring revalidation/goal completion or calling policy;
keep the original goal predicates and all legacy assertions. Check both persistence
boundaries, including the approval_revalidated save itself.

## F2 [P2]: waiting clock rollback above creation time is accepted

Source: `packages/pioneer-agent/src/pioneer_agent/agent_harness/task_runner.py:270-279`.
Awaiting checks only `now < request.created_at`. A no-response run at t+10 records
no monotonic approval-time watermark. Moving the clock back to t+5 (still above
creation) and submitting the original valid response is accepted. The independent
probe records four new tool calls and one policy call, ending `policy_stop`, instead
of `approval_clock_rollback` with zero downstream calls. The real ledger retains
quotas, but that does not satisfy the separate explicit clock-rollback rejection.

Smallest fix: retain/check an approval-clock high-water mark within the v2 lifecycle
and persist it when accepting a later waiting-time observation; reject regression
before consumption/tools/policy, including a fresh runner. Keep immutable request
creation/expiry unchanged and do not reset deadlines or introduce a new clock system.

## Reproduction and raw evidence

Working directory:
`/mnt/c/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo`.

```
env PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src:packages/pioneer-agent/tests:/tmp/sanmou-cr-20261005-6155-deps \
python3 docs/test-reports/2026-10-06/h07a-independent-probes.py
```

Executed via `wsl.exe -d Ubuntu --cd <directory> -- env ...` without shell wrapper:
exit **1**, Python 3.12.3, 5 tests, 2 pass / 3 fail / 0 skip. Earlier capture used a
shell wrapper which incorrectly returned 0; it is not a success signal. Its retained
unittest output has the same three failures and was independently reconfirmed with
the direct process exit above.

Raw first-run output: `h07a-independent-8232c42-red.log`, SHA256
`0ab91e28e6295c903b73d61cbd14002d7ba8764573f0fe797cedc63e14c4fe7b`.
Passing independent probes confirm consume-save plus cleanup preserves the original
exception with zero subsequent calls, and shallow-mutated returned evidence cannot
alter the persisted request or obtain a matching response.

The original frozen probes/log remain unchanged for fixes. Focused baseline and
author H07a regressions are being independently rerun. Full suites/eval/native
evidence are not yet a final acceptance claim; prototype 96-pass output cannot
override these reproducible failures. No Q06 content or archive member was read.
