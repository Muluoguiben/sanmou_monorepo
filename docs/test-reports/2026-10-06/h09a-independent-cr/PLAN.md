# H09a independent adversarial review: frozen plan

Frozen before receiving implementation: 2026-10-06.
Contract commit: `813ff402e44ed7faca7ced64d45bc66739b0a8af`.
Baseline source: `b338b73f44699ce6ad93a02c16267c54058df68f`.
Reviewer branch: `codex/h09a-cr-20261006`.

Status: PLAN ONLY; no implementation inspected and no review verdict issued.
This plan is independent of the author's work in progress. Later additions will
be labeled supplements; failed probes and initial logs will not be overwritten.

## Authority and evidence boundary

- Read-only offline TaskRunner control evaluation; no provider, .env, network,
  game input, real MCP subprocess, dependency install, CI edit or CI retry.
- Do not alter author implementation, old task cases/static MCP evaluation,
  QA v1/v2/v3 source/input/report, H06 original logs, or main-worktree WIP.
- No push/merge. H06 hosted Windows acceptance remains an external release gate.
- APPROVE, if earned, identifies one exact code commit/tree and tested blobs;
  report commits do not retroactively become the tested source.
- Single independent reviewer. Findings go through the coordinator.

## Receipt and reproducibility

1. Receive immutable code commit/tree plus author report, inspect commit diff and
   scope against the contract before running it. Record protected-file manifests.
2. Export exact Git blobs with CRLF conversion disabled into a fresh ext4 snapshot.
   Verify commit/tree, blob manifests and actual file bytes. Use absolute snapshot
   PYTHONPATH for parent and children; existing Linux dependency directory only.
3. Run documented offline evaluator twice in fresh processes. Preserve commands,
   environment/runtime, exit codes, stdout/stderr and all generated artifacts.
   Compare stable execution projections, not volatile UUID/time/reservation bytes.
4. Read evaluator/CLI/helpers, input schema, all eight case execution/expectation
   data, source validators and relevant existing runner/budget/store contracts.
5. Independently run focused existing tests and new tests on that snapshot. Tests
   alone never substitute for the CLI task-level report or independent probes.

## Eight-case acceptance matrix

| Case | Independently required facts |
| --- | --- |
| Three observations | Real Rule/TaskRunner; chapter 1/2/3; same-frame evidence; succeeded/goal_verified; 3 completed steps, 12 tools, 3 policy calls |
| Missing evidence | Numerically met goal without field_meta fails/step_limit; not goal success |
| Fake success | Chapter 1 plus explicit Fake succeed fails/unverified_success_proposal |
| Replay observation | Second repeated id fails/reused_observation before subsequent state/recommendation calls |
| Tool budget | Limit 5, objective requires 3 windows; fails/budget_exhausted; instrumented lowest client sees exactly no sixth dispatch |
| Pause/resume | No-op without resume; deserialize checkpoint into fresh runner/harness/client/ledger; fresh observation; deadline and budget not refilled; per-stage policy reported |
| Context overflow | Real required context exceeds configured limits; fails/context_overflow; zero policy calls |
| Writable session | Canonical legal envelope with observe_only=false fails/session_permission_violation after one session query; no observe/policy |

For every case independently reconcile bottom-level tool calls, trace, budget
reservations/completions and checkpoint. Check canonical tools, authority=none,
executable=false, pending=0 on normal completion and model_attempts=0. Reserved
steps are not assumed equal to completed_steps. Re-run every terminal runner
and paused runner without resume, checking all side-effect counters unchanged.

## Adversarial probes (must not relax the frozen contract)

- P01 isolation: mutate expected fields only and compare execution facts; mutate
  case id/labels and verify they do not steer fixture supply/policy/stop timing.
  Execution function receives execution only; no expected-driven counts/results.
- P02 denominators: preserve goal=2, safety=6, control=8; correct safety stops are
  neither goal successes nor observed violations. Unexpected success stays wrong.
- P03 infra: unknown tool, exhausted sequence, malformed envelope, checkpoint
  write failure and output failure remain explicit infra/error outcomes in total
  denominators; a partial/invalid report cannot claim a completed green gate.
- P04 freshness: new observation id with equal/decreasing capture time rejected;
  restore cannot inherit an old observation or refill budget/deadline.
- P05 provenance: suite/fixture hash and parse share the same bytes; byte drift,
  missing fixture, traversal and symlink/reparse roots rejected. Related source
  edits and untracked source rejected against original Git blobs.
- P06 import origins: shadow imported modules, package __path__ drift and modules
  lazily imported after initial validation must be checked at assembly, stage/case
  boundaries and before report. Actual common/config dependencies are covered.
- P07 malformed suites: empty/duplicate ids, empty suite, unsupported version,
  oversized/unbounded data, invalid native limits/config fail closed.
- P08 output no-clobber: existing output file/directory and partial-output sentinel
  are not overwritten; distinct retry directories retain original failed artifacts.
- P09 report integrity: completion marker only after all outputs; hashes bind input,
  execution/policy/budget/context and actual artifacts; RunState/stages/checkpoint,
  tool/policy/trace and assertions are complete even when a case fails.
- P10 honesty: offline wall time separate from unmeasured model latency/token/cost;
  development/developer-authored, no holdout/provider/live flags remain explicit.

## Verdict and report requirements

Report exact SHA/tree, tested sources/input/artifact digests, command lines,
runtime/dependencies, pass/fail/skip counts, protected-byte comparison, original
negative logs, findings with reproducible probes and source line references.
Any missing required probe is a limitation, not a pass. Genuine blocking findings
produce REQUEST CHANGES and are sent to the coordinator, not patched in place.
Repaired source receives a new immutable identity and new evidence directory;
prior red evidence remains intact. No conclusion about model quality, human gold,
independent generalization, real client closure or production readiness is implied.
