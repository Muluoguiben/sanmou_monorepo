# H08b independent plan (before author memo/code)

Published baseline `155817a444718366c3dbd56ac91fff8d52500fa5`.
Frozen contract `399791ee551a15499af6bd20829a4fbfe4ad52e5`.
Read full contract, code-review skill and complete existing TaskRunner,
task_trace and skill_registry. Applicable AGENTS is unchanged from baseline.
Clean isolated branch: `codex/h08b-recipe-trace-binding-cr-20261006`; old refs kept.
No future author memo/implementation inspected before this plan.

## Interface-first / protected scope

1. Review memo before implementation: keyword-only skill_compilation=None, exact
   accepted input, finite validation error, detached helper result and one shared
   task builder. Non-None binding requires causal_trace is True, not a truthy
   substitute. No binding preserves existing v1/v2 behavior and declarations.
   No inference from task_id/checkpoint/policy/files, no new wire/schema/version.
2. Only registry, runner, trace producer plus dedicated new test and one permitted
   Windows step. TaskSpec/RunState/checkpoint/DSL/budget/ports, default CLI, QA,
   common/KB/R&R, old fixtures/tests remain unchanged. H08a compile/list/resolve
   complete outputs and both digests retain their published oracle.

## Frozen negative dimensions (execute only on fixed implementing source)

3. Validate before EVERY external constructor side effect: store.acquire,
   owner.bind_runner/check/load/save/close, checkpoint bytes/creation, harness
   client installation, trace emission, budget restore/settlement, tool/policy
   calls. Spies and existing external owner must prove invalid binding causes none
   of these. Owner stays active/unbound and usable; harness original client and
   existing checkpoint bytes remain unchanged. Do not test only an in-memory store.
4. Reject unsupported input, blocked/invalid compilation, causal disabled,
   wrong ID/version/admission/authority/flags, unknown/extraneous fields, invalid
   target, wrong template digest, wrong task digest, and actual TaskSpec mismatch.
   Exercise nested mutation/model_copy/model_construct-style bypass of initial
   Pydantic validation, then require detached strict revalidation at the boundary.
5. Require ready/reason/preflight/missing_metrics consistency. Exactly the builtin
   one-condition satisfied declaration is admissible: metric/op/threshold/status
   must match, no empty/replaced/extra condition. Threshold value=1 is not the
   caller's observed chapter. Do not manufacture new metrics to replay a supposedly
   authentic precheck. Reconstruct canonical task via the single builtin builder;
   independently verify both the supplied task and runner task, not just hashes.
6. Validation errors are finite, payload-free. Place short/long secret canaries
   in invalid identity/parameters/task/preflight and inspect str, repr, formatted
   exception, cause/context and trace. Newly wrapped validation failures must not
   expose raw Pydantic input. Preserve genuine pre-existing business/cancel/store
   exceptions rather than laundering them; ambient caller exceptions must not
   suppress new failures. No general traceback-sanitization framework is requested.

## Ownership, copies, provenance and drift

7. The validated task and runner-owned task must derive from the same detached
   snapshot. Mutate caller task, compilation, nested target/conditions/metadata
   after validation/construction (including an acquire hook) and prove no effect
   on owned state, digests, declarations or another runner. Helper results must
   not provide a shared mutable route back into binding/internal registry data.
8. Exact declaration is recipe:chapter-observer@1.0.0#sha256=<template_digest>,
   status=declared and within existing 160 limit. All v2 event kinds/lifetimes
   and memory/JSONL sinks agree. Existing task_digest binds actual task; all other
   provenance fields retain original meaning. A manually reconstructed but valid
   compilation may match content: this never proves compile() was called, human
   review, a signature, trusted observation freshness or an execution grant.
9. Distinguish harmless caller-copy mutation from actual owned-task drift. Freeze
   drift cuts before entry, during store/tool/policy boundaries and after a
   provenance value has been prepared. No event may falsely retain a recipe
   declaration for changed task content, including emit calls supplied with
   precomputed provenance. Failure must latch visibly at existing trace boundaries
   and stop further dispatch as required, without refunds, retries or replacing
   an original primary exception. Earlier valid events remain intact.
10. Three real fresh offline observations still verify target3. Pause/resume,
    active/idle controls and terminal noop preserve current call/trace semantics.
    Fresh runner restoring JsonRunStore must explicitly rebind; omission returns
    old absent/unknown skill declaration even for a recipe-shaped task ID. Verify
    bound/unbound alternation, separate runner/lifetime IDs, no declaration leak,
    and no skill data persisted through a new checkpoint field. Binding cannot
    replace observation/evidence/budget/stop/synthetic-approval guards.

## Compatibility and regression evidence

11. Freeze published default-v1 full event snapshot and unbound-v2 declaration
    controls before new implementation output. Compare no-binding paths exactly
    except predeclared nondeterministic causal IDs/timestamps where applicable;
    do not widen projection to hide fields/events/errors. Retain old H08a outputs.
12. Rerun H10 original F1-F4, short-canary/context, ambient-primary and dispatch
    regressions unchanged: actual policy identity/callable binding, lazy invocation
    timing, budget/freshness/cancel guards, no repeated dispatch or emit after
    trace failure, and genuine primary exception priority. Do not force old tests
    green by changing assertions, fixtures, public protocol or accounting.
13. On fixed SHA/tree verify exact allowed diff/actual Git bytes, run new probes,
    dedicated tests, full Pioneer/QA/common, H07/H08a/H10/H09 actual CLI, original
    Q04/Q05 groups and QA v4/Q04 CLIs. v4 whole c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c
    and Q04 whole b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6 stay;
    v1-v3 remain expected refusals. Compare author raw hashes/counts only after
    independent runs; all claims retain their actual source and environment scope.
14. New text I/O explicit UTF-8; real non-UTF text/UTF-8-filesystem control with
    actual metadata, no PYTHONUTF8=1/read mocks. Do not expand strict-C ASCII-fs
    limitation. Unique new Windows step follows H08a; inverse deletion restores
    whole old YAML/bytes. Final exact Hosted new-name inventory/0skip/exit0,
    existing H08a23/H1032/H0735/Q0425/Q0544 and same-run four jobs remain pending
    until coordinator obtains actual logs. No local dependency installation.

Freeze executable public probes after memo fixes the helper/error shape; never
run the absent baseline keyword to manufacture a product red. Preserve all actual
reds and unchanged repair assertions, in bounded plain evidence only. No reviewer
implementation/CI/main/WIP/push, Q06 payload/ancestry or archive body/member access,
provider/network/game/bridge/.env/credentials/install/KB publish/deploy actions.
Next: send plan SHA, review fixed memo, prepare baseline/public controls, await code.
