# Harness task/context contract v1 (A0)

Authoritative Python port: `pioneer_agent.agent_harness.task_contracts`.
This is an internal versioned contract, not another MCP schema or Runbook DSL.
Game seven-tool and QA six-tool services remain unchanged. This task runner uses
only the existing Game catalog; the old single-window QA route remains compatible.

## Ownership and dependency direction

A owns task_contracts.py, task runner/store/policy, loop.py and app/game_agent.py.
B owns independent context, budget and trace implementation modules and B tests.
B imports task_contracts; it must not import the runner. A injects B implementations
through ContextBuilder, RunBudget, RunTrace. B documents concrete constructor names
and integration examples in its report; no production fallback stub is accepted.

## Task and lifecycle

TaskSpec v1: task_id, goal, nonempty success_when, stop_when, required_domains,
allowed_tools, max_steps, wait_seconds and fixed none/false authority. Conditions
are existing Runbook Condition objects; evaluate_all(success) and evaluate_any(stop)
use current validated RuntimeState data. Missing metrics are UNKNOWN, never success.
The runner, not the policy, verifies success. PolicyDecision is continue/wait/pause/
stop/succeed with a reason and immutable authority values. A succeed proposal without
fresh matching evidence cannot succeed. DecisionPolicy exposes policy_id, uses_model
and async decide(PolicyContext); this batch supplies deterministic Rule/Fake policies.

RunState v1 checkpoints contain task, run identity, status/reason, completed step
cursor, pending call, all accepted observation IDs, session/window identity, last
capture timestamp, evidence references and opaque budget_state. No persisted
observation, journal, policy text or pending call grants execution authority.
created -> running; running -> waiting/paused/succeeded/failed/cancelled;
waiting -> running/paused/cancelled/failed; paused -> running/cancelled.
Terminal states are absorbing, including after restart. Only a completed decision
advances completed_steps. An interrupted read-only step is reobserved, not counted
as completed. Every resumed nonterminal run obtains a fresh observation and verifies
session/window identity, increasing capture time and unseen observation ID before
policy evaluation. No actuator or exactly-once side effect claim exists.

## Context boundary

ContextBuilder.build(ContextRequest) -> PolicyContext is synchronous and pure.
Request contains run_id/step_id, complete TaskSpec, observation_id, validated current
authoritative_state, evidence_refs, optional history/images and mandatory safety_rules.
Images are synthetic metadata only this batch (count/width/height/estimated tokens;
no raw images). B should accept width/height/token_estimate in each metadata object.
Builder prioritizes safety, goal/conditions/permissions, latest state and provenance.
It may drop old history or optional evidence but must raise ContextOverflow if the
mandatory payload cannot fit. PolicyContext supplies text, identity, evidence refs,
estimated_input_tokens, reserved_output_tokens, truncated. It is a detached projection:
policy changes cannot modify TaskSpec, authoritative state or checkpoint evidence.
Builder output is not a success/authorization oracle. A rechecks freshness after policy.

## Budget and cancellation injection

RunBudget is synchronous; reserve is atomic under concurrent workers. BudgetRequest
identifies run/step, kind step/tool/model, name, estimated input and reserved output
tokens. reserve returns unique reservation ID or raises BudgetExceeded before dispatch.
All attempts consume counts, including retries/failures. No hidden model retries are
allowed in DecisionPolicy: one decide is at most one model attempt when uses_model=true.
This batch has no model adapter. Rule/Fake policy calls consume step but no model count.

A reserves one step before a decision window, each tool before its client call, and
each model attempt after context build and before decide. A persists reservation
snapshot and pending_call before dispatch. settle(id, Usage, outcome=...) occurs once
in finally after success/error/cancel. Unknown token/price usage remains None; reserved
unknown tokens remain conservatively charged, never treated as measured zero.
Step/tool settlements use Usage() (not fabricated model usage). remaining_seconds()
includes wall time since budget creation, waits and downtime after restore. A bounds
calls/policy/waits by that remaining time. At exhaustion no new calls are permitted;
cleanup cannot start new calls and uses existing transport's bounded cleanup. A records
terminal deadline outcome even if transport cleanup completes after that deadline.
cancel prevents all later reservations. snapshot/restore must retain consumed counts,
unknown usage and absolute deadline; unsettled pre-crash reservations remain consumed.
Restoring a checkpoint must never refresh quota or deadline.

No automatic retries are required in A's runner. B may provide an opt-in bounded
read-only retry helper; every retry reserves separately. Schema/authority/binding
errors are nonretryable. Cancellation/pause is checked before every next tool, before
policy and after await. CancelledError is persisted as cancelled and re-raised; an
explicit cancel request yields cancelled without further dispatch. Pause preserves
budget/cursor; resume reobserves. Single-owner execution is required for checkpoints;
cross-process lease/CAS remains H06 and is not claimed here.

## Trace boundary and compatibility

RunTrace.emit(TraceEvent) receives run/step/event, name/attempt, observation/evidence,
separate transport, contract and business results, error class and optional Usage.
Transport ok is not contract ok or business success. The validated-tool event is
emitted only after canonical response validation; schema failure is contract=error.
Metadata carries policy/version and safe identifiers, never prompt secrets/raw images.
B may provide in-memory and JSONL sinks. A emits lifecycle, tool and policy outcomes.
Existing ToolLog remains compatible; A moves Game schema validation inside its call
logging boundary so legacy success does not precede schema validation.

Unknown checkpoint versions fail closed. Changes to required port signatures require
an explicit versioned contract update agreed with B; additions with defaults preserve
v1. Old run_decision_window and CLI without --task-spec retain their single-window
behavior and regression coverage. CLI task wiring uses B's real implementations.

## A1 evidence boundary

Task goal success requires an exact `field_meta[condition.metric]` entry bound to
the current observation ID and capture timestamp, with a positive confidence and
`vision.<domain>` source present in that observation's completed domains. Required
domains and nonempty structured evidence are also checked. Aggregate metadata (for
example only `progress.chapter_panel` for a `progress.current_chapter_id` condition)
is deliberately insufficient in v1: no guessed prefix-to-field provenance mapping.
Such tasks stop at their bound rather than claim success. Full model or live vision
support for every possible Condition path is not claimed by the offline cases.

Checkpoints are local trusted application state, atomically replaced by one owner.
They provide neither untrusted-checkpoint authenticity nor cross-process CAS/lease.
Trace and budget failures fail closed; automatic retries are not enabled by A.
