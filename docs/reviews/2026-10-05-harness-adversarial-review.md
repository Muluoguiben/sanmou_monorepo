# Harness batch adversarial review — 2026-10-05

Status: **PENDING_DELIVERIES — no approval**.

## Scope and source

Reviewer branch: `codex/harness-cr-20261005`.
Worktree: `C:\Users\Lan\.codex\worktrees\6155\sanmou_monorepo`.
Dispatch baseline: `965ef6713b58048c0765654e8061c5cffda6c59d`.
Business baseline: `12e7ddc73c86665ccad0764c8aa8aec51de39e3a`.
The worktree was clean at entry. No A/B/C implementation is reviewed yet.
The fetched origin/master manifest still contains null A/B/C thread IDs, A0,
code commits and report commits. This is a delivery prerequisite, not a defect.

## Freeze and combination protocol

1. Obtain current-batch IDs and immutable A0/A/B/C code and report SHAs from
   the coordinator manifest. Read author reports and verify their source binding.
2. Verify A0 ancestry in B and B implementation ancestry in final A; inspect
   actual runtime wiring, not only ancestor membership or stub tests.
3. Combine final A and C in this isolated tree without importing A0/B twice.
   Return source/semantic conflicts to their owners. Record parents, code SHAs,
   report SHAs, combination commit and tree before any approval.
4. Preserve each first failure, command, exit status and raw log digest. Author
   fixes require a new freeze and affected plus combined regression reruns.

## Fault-injection matrix

| Area | Adversarial input / cut point | Required result |
| --- | --- | --- |
| Success | Goal assertion without evidence; three repeated frames; partial domains | No success from rounds, policy assertion or stale evidence |
| Lifecycle | Pause/cancel before reserve, during tool/policy, after return, before checkpoint | No new calls after cancellation; terminal completion only once |
| Restart | Crash around pending/result/checkpoint; malformed or old checkpoint | Reobserve and revalidate identity; no renewed authority or duplicate completed step |
| Binding | Session/device/window/frame mismatch; slow QA/policy exceeding freshness | Fail closed; new evidence cannot inherit old identity |
| Budget | Concurrent reservations, retries, missing usage, provider exception, timeout | Every attempt accounted; unknown remains unknown; exhaustion prevents calls |
| Deadline | Waiting, backoff, cancellation and cleanup consume time | Explicit bounded run/cleanup policy, primary errors preserved |
| Trace | Transport OK + invalid schema; valid schema + business refusal | Distinct transport/contract/business outcomes and run/step/evidence linkage |
| Context | Oversized goal/rules/evidence/images; old inference contradicts fresh facts | Retain authority, goal and provenance or stop; no silent unsafe truncation |
| QA scorer | Correct ID + wrong number/entity; retrieved but uncited ID; uncited claim | Citation and semantic support metrics stay separate; false claims never pass by keyword |
| QA labels | Unreviewed/machine labels, empty evidence, pronoun turn, topic switch | Development labels remain unreviewed; no invented holdout/gold or zero-generation regression |
| Authority | Policy/context/checkpoint attempts to grant control or publish | Game seven/QA six catalogs unchanged; none/false authority preserved |
| Privacy | Synthetic secret markers in errors/context/trace | No credentials or raw private images persisted; no real secrets needed |

## Baseline inspection notes (not new batch findings)

- `agent_harness/loop.py:302-304` validates after `_call`, whose success record
  is emitted at line 350. Verify new trace wiring closes the documented
  transport-versus-contract ambiguity.
- `qa-agent/scripts/chat_regression.py:69-84` accepts IDs from candidate evidence
  and uses substring checks. C must provide a separate honest metric boundary;
  changing this existing production smoke is not required by C ownership.

## Acceptance and evidence

Run focused author tests plus independent negative probes, then Pioneer, QA and
common full suites on the frozen combination. Record Python/dependency versions,
platform, exact commands, counts and skips. Windows-specific semantics require
actual native results; a skipped test is not coverage. Offline fixture/Fake
policy results never establish provider, vision, live action or production quality.
No game input, live provider call, auto-publish, private configuration reads or
master mutation is authorized here.

Findings will include severity, exact source location, reproducer, impact, owner
handoff and repair acceptance. None are asserted before implementation delivery.
