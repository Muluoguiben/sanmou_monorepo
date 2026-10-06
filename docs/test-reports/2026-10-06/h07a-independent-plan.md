# H07a independent acceptance plan (frozen before implementation)

Date: 2026-10-06. Reviewer: independent Codex GPT-6 Astra.
Published code baseline: `110bd7594e095c3ea0e1940ab2fc4bec5f4d7a77`.
Contract/review start: `47cfd6f35fd7aeadf7f4001abe59bc63a4bb9a45`, tree `071e5ffcab6d0bce9044b05b169dddfcb0ee363e`.
Branch: `codex/h07a-cr-20261006`; isolated review checkout.

This plan was prepared from the 55-line H07a contract, AGENTS.md, and baseline
task_contracts.py, task_runner.py, run_store.py, run_budget.py and game_agent.py.
No author WIP or H07 implementation was inspected. Wait for immutable code SHA/tree
and self-test handoff before evaluating implementation. This file is a plan, not a pass.

## Frozen probes and acceptance oracles

1. **Scope and synthetic-only authority.** Diff against the published baseline:
   only the contract-listed original modules plus one small task_approval helper,
   tests and necessary coordination/report files. TaskSpec DSL/catalog/none-false
   permissions unchanged; no dispatch grant, executor, QA/common/KB, old eval
   inputs, dependencies, CI or provider access. Default opt-out preserves behavior.
   Policy may supply only request intent/reason, never runner-owned bindings.
2. **Request creation and priority.** Validated observation precedes runner-created
   request; independently compare run/step/task canonical digest/session/window/
   observation/frame/evidence/timestamps to source state. Stop conditions defeat
   request_approval; explicit pause-like priority remains. Failed request save must
   raise the original error and expose no usable request.
3. **Waiting is inert.** Same runner and fresh runner, run/resume false/true, and CLI
   --resume-task all produce zero added tool calls, policy calls and client enters
   while awaiting a response. Repeated attempts do not reissue a request. Normal
   paused behavior remains unchanged. CLI inspection includes construction order,
   not merely a final status assertion.
4. **Response binding and lifetime.** Individually alter request/run/task digest,
   observation/frame/session/window/evidence/step and timing, origin or scope where
   represented. Reject each wrong binding, denial, expiry boundary, old response,
   duplicate consumption, clock rollback and non-synthetic authority. Trace and
   stored outcomes must be deterministic, with no automatic retry/approval.
5. **Budget continuity.** Real RunBudgetLedger with controlled wall/monotonic
   clocks: waiting and fresh-process restore keep old deadline and reservations;
   step/tool/model/token/cost caps never replenish. Expired TTL/deadline, rollback,
   cancelled ledger and exhausted quotas cannot dispatch. All executed probes use
   Rule/Fake policy and model_attempts=0; no paid-provider validation.
6. **Consumption transaction.** Inject failure exactly at consumed-state save;
   original failure survives cleanup, zero later tools/policy run, and no success
   is reported. Crash after consumption commit but before/during revalidation:
   fresh runner must explicitly fail/hand back, never reuse the response. Preserve
   the raw failing probe and rerun the identical assertion after each author fix.
7. **Fresh revalidation.** Accepted response first starts a new observation window;
   replayed observation, nonincreasing capture time, changed session/window,
   insufficient current evidence and changed original task conditions cannot be
   overridden by approval. Check tool/policy event order and call counts. Fresh
   validated goal evidence may succeed; response alone cannot prove success.
8. **Real process ownership/CAS.** Two OS processes contend for one JsonRunStore
   checkpoint and one synthetic response using a bounded rendezvous. Exactly one
   may consume; loser has no subsequent tool/policy calls. Preserve process PIDs,
   exit codes, ledger and checkpoint revisions. Existing lock/CAS regressions run
   unchanged. This proves neither a device lease nor exactly-once game effects.
9. **Serialization matrix.** Baseline-generated v1 flat/envelope loads preserve
   bytes on read and ordinary write representation/behavior. Only entering approval
   emits explicit v2. Test version/state inconsistency and v1 approval-field
   smuggling; baseline reader rejects v2. Terminal states cannot regress via
   save, run, resume, response or pause. No load-time migration or weakened legacy
   assertion is accepted as compatibility.
10. **Regression and provenance.** Run focused/new independent probes, full
    Pioneer/QA/common suites, actual H09 offline CLI eight cases and unchanged old
    QA v3 through their documented entrypoints. Bind every result to exact commit
    and tree; record command, exit code, counts and skips separately. Exercise
    native Windows only with existing environment; never describe skips as passes
    or claim an unavailable full MCP runtime. Final approval concerns exact source
    only; coordinator must independently verify the final combined tree.

## Execution and findings protocol

- Use existing `/tmp/sanmou-cr-20261005-6155-deps`; no install, network, .env,
  real game, bridge, credentials or history archives. Q06a remains excluded; no
  restricted archive member reads, alternate routes or delegated retries.
- New evidence is bounded raw text/JSON plus hashes, never tar/zip. Freeze each
  independent probe before execution; retain original red output and assertions.
- Findings require a reproducible trigger, actual/expected behavior, precise
  source location and smallest in-scope fix. Reviewer does not implement author
  source, push, merge or mutate main checkout. New scope/authority needs escalation.
- APPROVE requires all mandatory exercised gates green and no unresolved high-risk
  finding; environmental omissions remain explicit and cannot silently become pass.
- This work proves synthetic read-only handoff only, not human authentication,
  real approval, actuator transactions, broker readiness or production readiness.
