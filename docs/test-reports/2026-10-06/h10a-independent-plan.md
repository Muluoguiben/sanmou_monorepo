# H10a independent acceptance plan (before author implementation)

Date: 2026-10-06. Review branch: `codex/h10a-causal-trace-cr-20261006`.
Published baseline: `ae03faf0862f9930c58f7811d625de4b632f05ba`.
Frozen contract: `358df146ba184a771d3673428915a70fe8aa4c9c`, tree
`2e9a42c0682a4a74688fde327e19bbe27a893c00`;
`docs/harness-causal-trace-h10a-2026-10-06.md` read completely.
AGENTS.md, code-review skill and published TraceEvent/run_trace/task_policy/
context-builder plus runner failure boundaries and existing trace assertions were
read. The isolated checkout was clean; previous review branches remain preserved.
No author implementation/WIP was inspected. First review the submitted interface
memo, then wait for immutable implementation SHA/tree and source-bound self-tests.

## Scope / compatibility gates

Expected production scope: task_contracts.py, run_trace.py, task_runner.py, optionally
explicit built-in policy version constants in task_policy.py and one small internal
provenance helper. New causal tests are separate. No edits to old assertions,
TaskSpec/RunState/checkpoint wire formats, budget/approval/ownership semantics,
MCP catalog, QA/common/KB, old evaluation inputs, CLI defaults, CI or dependencies.
Any boundary expansion first needs a reproduced defect and minimal proposal.

Baseline TraceEvent and ordinary memory/JSONL v1 behavior are compatibility oracles,
not objects to update until new tests go green. In particular retain the exact
test_harness_b layered-outcome, detached evidence, secret/privacy, impossible
success and unknown Usage assertions, plus task/CR/ownership/H07 cases.

## Frozen acceptance oracles

1. **Interface/graph convention.** Before implementation review, require the memo
   to define v2 opt-in, strict wire versioning, root/parent identifiers, entry/window/
   invocation events and not-attempted semantics. Actual invocation identifiers and
   budget attempt_id must have different meanings; an intent/pre-dispatch event
   must never be reported as a completed/attempted call. No new grant semantics.
2. **Same producer event, two sinks.** Feed one validated v2 event into both sinks;
   event identity, causal references, source/digest snapshot and layered outcomes
   must match. A sink cannot generate a replacement event_id or silently downgrade
   malformed v2 to v1. Check unknown versions, wrong types, extra fields, missing
   required relationships and impossible transport/contract combinations. Preserve
   v1 field sets/serialization/default runner behavior using baseline comparisons.
3. **Real three-observation run.** Execute actual TaskRunner with existing synthetic
   clients and Rule/Fake policy through at least three new observation windows.
   Independently map raw events to the measured tool/policy call ledger: entry root,
   unique window attempt, observation evidence, invocation, policy and outcome.
   Every referenced parent/root resolves under the documented convention; no cross-
   run/window links, repeated actual-invocation identity or fabricated calls. Rule/
   Fake policies have their own invocation identity but zero model reservations.
4. **Reentry/restart isolation.** Exercise same-object run reentry, fresh runner from
   real checkpoint and repeated step labels after interruption. New entries/windows
   remain distinguishable; restored trace must not invent an old-process parent or
   reuse old observation/context/one-shot response. No trace cursor is added to
   checkpoints and no cross-version recovery prohibition appears. Awaiting/terminal
   no-call paths have no false tool/policy invocation claims. Existing H06/H07 budget
   charges and consumed/revalidated crash distinctions remain intact.
5. **Actual task/context digests.** Independently compute canonical JSON/SHA256 from
   the validated TaskSpec and the exact structured PolicyContext snapshot delivered
   to the policy, not from schema labels or the implementation's own digest helper.
   Content changes affect digests; irrelevant mapping-key order does not. Actual
   prompt/text bytes remain meaningful input, not guessed semantic equivalence.
   Altered context binding fails before policy. Mutable context, task, version or
   policy-output fields cannot rewrite the frozen pre-invocation provenance.
6. **Honest source labels.** Record actual task/checkpoint versions and distinguish
   declared built-in version constants from unknown custom versions. Invalid/fake
   version declarations must not become verified source provenance. Unused model,
   prompt, skill or KB components are absent/unknown, not inferred from model_id or
   policy_id strings. No claim that a digest or declared label authenticates source.
7. **Privacy/sink parity.** Inject synthetic sentinel secrets into free text,
   exception messages, metadata/nesting, context/prompt and attachment-like values.
   Both sinks retain only documented typed/minimized fields with equivalent
   sanitization; no raw sensitive sentinel, image, context or arbitrary attachment
   survives via a new field. Mutation after emit cannot alter stored identity/data.
   Unknown usage remains None/unknown, never estimated usage disguised as measured
   billing or zero real-model cost. Test built-in/fake and missing-version policies.
8. **Failure and primary-error ordering.** Inject tool transport error, invalid tool
   schema, invalid policy output, policy exception, cancellation and budget denial.
   Compare actual call counts and layered transport/contract/business to events.
   In a bounded matrix, fail the trace sink before dispatch, after returned data,
   while reporting an existing primary failure/cancellation/checkpoint error, and
   during final outcome/cleanup. Preserve the original primary object where the
   API propagates it, or its established fail-closed classification where the API
   returns a result. A secondary trace failure cannot replace it, silently report
   success, cause another dispatch, refund quota, or create an unbounded emit retry.
   Failure without an earlier primary is explicit and observable.
9. **No model/runtime expansion.** All new causal exercises use synthetic clients,
   Rule/Fake and zero actual model/provider calls; new tracing adds no model budget
   reservations. Existing fake-model budget controls remain unchanged. No provider,
   real MCP transport, game, bridge, network, .env or credential access is needed.
10. **Regression and source binding.** Freeze independent probes before executing
    them and preserve raw reds/unchanged assertions across fixes. Run new module,
    focused trace/context/budget/task/ownership/CR, full Pioneer/QA/common, H07a 35,
    actual offline H09 eight-case CLI and frozen QA-v3 checks on exact source.
    Keep old fixtures/hash expectations unchanged and list skips separately. Bind
    commands, exit codes, counts, source SHA/tree and bounded plain log hashes.
    The already-completed H07 Hosted Windows35 is historical H07 evidence, not new
    H10 native coverage; no local native dependency exploration or installation.

## Review / reporting boundaries

Prefer small reproducible counterexamples and minimum in-scope fixes; reviewer
does not implement author code or call paid model consultation. Preserve original
exceptions, raw observations/call ledgers and failing assertions in compact plain
text/JSON evidence, not new archives or repeated old matrices. Findings name exact
source locations, trigger, actual/expected result and scoped fix. Self-tests alone
do not replace independent reproduction or final combined-tree validation.

No main checkout changes, pushes, deployments, Q06 payload/ancestry or any archive
body/member reads. Q06 archival access/publication stays paused. Do not reopen
completed H07 development or native environment exploration. All states remain
recommendation-only, execution_authority=none and executable=false. Final approval
is source-specific and cannot imply full H10, distributed exactly-once, real action
authorization, model quality or production readiness.
