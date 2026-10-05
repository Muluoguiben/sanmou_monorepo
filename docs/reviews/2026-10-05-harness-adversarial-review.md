# Unified adversarial CR — REQUEST_CHANGES

Review date: 2026-10-05. This decision applies only to the code combination below.
No master integration, game/provider call, or author production-source fix was performed.

## Frozen deliveries and tested combination

| Owner | Code | Report |
| --- | --- | --- |
| A (includes B wiring) | `c902d19601e2b16a4529fa874445fdef3814f5a8` | `262a18343d2966b22b4fb3a4d35e18a9fa2e8544` |
| B | `9430107ab24a740e751321ca41a98c0e282e2954` | `68611c7938911593bc317e9c5bd9e1ec87ce88ba` |
| C | `621cf8baf324902b9e77d056b3b03f288f07baf6` | `bd062f3548026b74798dd8f7178cbb615fe7e9cf` |

A0 is `5269a1a5d09bddcf268d180a3f016f323c27cb95`. B is already an ancestor of A;
CR did not import B twice. Tested local combination commit:
`9189bb10ffb97453730802f7634f68ee1d34bfd4`, tree
`c49f53a86172c8edaf105a972c135e43459ad4e3`. No source conflict resolution.
A/B final report identities were subsequently read without changing tested code.

## Findings (owner A)

### CR01 — P2: explicit cancellation becomes deadline failure

Location: `packages/pioneer-agent/src/pioneer_agent/agent_harness/task_runner.py:282-283,317-320`.
Reproducer: a RunStore.save hook calls runner.cancel() when pending_call first becomes
session_status, after reservation and before client dispatch. B correctly makes remaining
seconds zero. wait_for times out without a call, but the timeout branch unconditionally
maps this to failed/run_deadline. Actual result: `failed, run_deadline, calls=[]`.
The explicit cancelled lifecycle is lost, so persisted/UI outcome cannot distinguish
operator cancellation from an expired task. This violates A0 cancellation semantics.

Repair acceptance: recheck cancellation after checkpoint/pre-dispatch and preserve
cancel_requested/cancelled precedence when classifying timeout. Test tool and policy
boundaries, zero dispatch, settled reservations and cancelled checkpoint after restart.
Do not implement by dispatching despite zero remaining time.

### CR02 — P2: checkpoint-time pause still permits a new tool call

Location: `packages/pioneer-agent/src/pioneer_agent/agent_harness/task_runner.py:280-288`.
Reproducer: the same synchronous checkpoint hook calls runner.pause(). The request is
accepted before the underlying client begins, yet session_status is dispatched; only
its returned response triggers _check. Actual result:
`paused, pause_requested, calls=['session_status']`.
A slow call can therefore continue until the run deadline after the user already paused,
and the task does not honor its pre-call pause boundary. This is a single-owner callback
cut point, not a demand for a cross-process lease or instruction-level cancellation fence.

Repair acceptance: recheck interruption after persistence and before invoking the client
or policy. The deterministic checkpoint hook must yield paused with no underlying calls;
resume must reobserve, retain consumed reservation accounting and preserve the cursor.

### CR03 — P2: policy trace conflates transport and contract failures

Location: `packages/pioneer-agent/src/pioneer_agent/agent_harness/task_runner.py:194-210`.
Reproducer A: policy returns a dict with executable=true. Return transport completed,
then PolicyDecision validation fails; actual trace is error/error instead of ok/error.
Reproducer B: policy raises ConnectionError before any response; actual trace is
error/error instead of error/not_checked. Both use the actual B InMemoryRunTrace.
Every exception is assigned the same policy_error and the trace derives both layers
from that flag. This corrupts H10 error attribution and any later failure metrics/retry
analysis despite the separated schema fields.

Repair acceptance: maintain transport and validation stages independently; add cases
for malformed return, connection failure, timeout, cancellation and valid business stop.
Only execute contract validation after a returned response. Preserve unknown usage.

## Verification and handoff

- Corrected independent adversarial suite: 4 tests, **4 failures**, exit 1. The two
  lifecycle cases plus two trace cases reproduce CR01–CR03 on the frozen combination.
- Pioneer: 926 total, **924 pass / 2 Windows-only skips**, exit 0.
- QA: first run 343 total / 2 existing shell failures caused by CRLF shebang. After
  verifying and restoring the exact Git LF script blob, **343 pass**, exit 0.
- Common: **2 pass**, exit 0. C-focused plus empty-evidence regression: **20 pass**.
- Full logs/commands/exit codes and reproduction script: [CR report](../test-reports/2026-10-05/CR.md).
- WSL only; no native Windows, provider/vision/live-action or production approval.

Author handoff: A owns all three fixes; B and C production changes are not requested.
Do not merge this source. A must commit repairs and a new source-bound report, then CR
must freeze the new A SHA, recombine C and rerun corrected negatives plus focused/full
regressions. Existing green suites do not close these deterministic failures.
No cross-chat write was sent; this report/final handoff is available to the coordinator.

## Review limits and non-findings

Context detachment/mandatory rules, budget atomic reservation and unknown accounting,
restart deadline preservation, canonical catalogs and the C explicit external-label
scoring boundary were inspected. No additional actionable B/C defect was established.
Trace identifier slots are not general secret detectors; callers must provide safe
identifiers, as B documents. No real-secret leak was observed or claimed.
The initial call_soon cancellation/pause probe was invalid: synchronous Fake calls did
not yield until the run completed. Its two lifecycle failures were withdrawn, not used
for CR01/CR02. Corrected probes invoke the pause/cancel hook synchronously at the actual
checkpoint-before-dispatch cut point; all original logs remain preserved.

The CR branch contains C commits whose remote publication was blocked in C's session.
The combined branch has therefore remained local; no upload bypass was attempted.

---

# Historical preparation record (superseded by the decision above)
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

## A0 checkpoint (coordination refresh)

Manifest commit `5e6f575398e5a940b983b2ab30b62eb93f2a5d70` now provides valid
A/B/C thread IDs. The earlier null-ID condition is resolved. A0 fixed source is
`5269a1a5d09bddcf268d180a3f016f323c27cb95`; it is a contract milestone, not final A.
Read-only contract review identifies these integration probes, not proven findings:

- `DecisionPolicy.decide` returns no Usage envelope. This batch excludes real model
  adapters; verify unknown usage is conservatively accounted, never fabricated zero.
- TaskSpec contains mutable nested lists. Assignment validation alone cannot establish
  detached authority/state: verify runner copies/revalidates and policy gets only a
  detached context; clearing success conditions must not yield vacuous success.
- Budget snapshot is opaque at the port: verify B validates restored identity,
  deadline, counters, pending reservations and cancellation without renewing quotas.
- Explicit empty safety_rules is accepted by the request type. Verify builder/runner
  always retain canonical authority and evidence-is-data rules or refuse the context.
- RunState model permits status assignment: terminal absorption, fresh resume and
  increasing timestamps must be enforced by the runner/store, not assumed from types.

An internal read-only reviewer independently checked these ports. No A0 approval
or implementation failure is claimed; the final wiring and negative tests decide.
