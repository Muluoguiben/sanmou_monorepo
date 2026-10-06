# H07a native recovery: independent acceptance plan

Frozen before author WIP/source inspection, 2026-10-06.
Published baseline: `ca04ae1ef396576c5983f887502bf20b7d6f0015`, tree
`ba42dc04f2eebde1bd1b36b3063e126b50112cd9`.
Reviewer branch: `codex/h07a-native-recovery-cr-20261006` in the existing clean
isolated review checkout. Prior `codex/h07a-cr-20261006` branch is preserved.

Read before freezing: current AGENTS.md, code-review skill, published workflow,
approval tests and TaskRunner/RunBudget recovery boundaries. This plan follows the
coordinator's explicit small-slice instructions. The subsequently received frozen
contract `ecf50e0012c336c131f75b9bc6c102530a0d1876` was read completely before any
author source/WIP: it matches these oracles and specifies the full regression lanes
and local-fixed-disk Windows checkpoint requirement below.
This is a plan, not new implementation or a passing-result claim.

## Scope and immutable legacy oracles

Expected implementation delta is two new persistence/process recovery tests in
`packages/pioneer-agent/tests/test_task_approval.py` and a separate existing-Windows-
job step in `.github/workflows/regression.yml` invoking
`python -m unittest test_task_approval -v` from the tests directory.
Necessary plain reports and bounded raw evidence are allowed. Production modules
are unchanged unless a new test reproduces a defect and a minimal fix is explicitly
reported before implementation. No new runtime framework or test bypass.

Baseline approval test blob: `2fd326d73f2fe616c261fd4c23eeb656c10843fb` (30 tests).
Baseline workflow blob: `d5f6f69237d25e99ac618c7ee3f0975c7793b72b`.
Preserve all old assertions/helper behavior, existing workflow steps, permissions,
dependencies, timeouts and checkout LF settings. Review AST/method-level old-test
diffs as well as normal Git diffs; green from weakened old assertions is rejected.

## Frozen acceptance oracles

1. **Durable awaiting update.** Use actual JsonRunStore, not only MemoryRunStore.
   Generate one valid synthetic awaiting request; advance waiting time and persist
   last_checked_at. Release the first lifetime, read through a new store/owner and
   resume with a fresh runner/ledger. Check request/response state, original expiry,
   same watermark or monotonic increase, revision, original absolute deadline and
   complete preexisting reservations/charges. Remaining time must decrease with
   elapsed time; step/tool/model quotas cannot refill. Waiting performs zero new
   tool/policy calls. A separate OS process is required for any claimed process-
   restart coverage; a same-object or same-process test must not be mislabeled.
2. **Rollback/deadline negative controls.** Reuse the real saved awaiting checkpoint
   with controlled clocks to check approval-clock regression and elapsed ledger
   deadline independently. Expect safe stop or the established restore rejection,
   zero tools/policy and no lowered watermark/refreshed deadline. Check persisted
   state, not merely the returned object. Preserve previously charged reservations;
   do not invent a requirement that pending reservations become zero.
3. **Crash after durable revalidation.** Start a real multiprocessing spawn child,
   use actual JsonRunStore and synthetic clients, and rendezvous only after the
   approval_revalidated checkpoint write succeeds but before policy. Verify the
   durable checkpoint is running with the consumed response and a new revalidated
   observation. Terminate/join this disposable child; record PID/exit and assert
   that its policy was not invoked. A fabricated checkpoint is not this proof.
4. **Fresh restart ordering.** A fresh runner from that running checkpoint must
   execute a new observation window before policy/goal evaluation. Its observation,
   frame/time and policy context must not reuse the crashed child's observation or
   old context. The prior response remains consumed and cannot be used again.
   Existing consumed-but-not-revalidated crash test still fails closed with zero
   calls. Charged/pending step reservations survive without refund; resumed calls
   are accounted for against the old deadline/limits.
5. **Native complete module and CI wiring.** Run the entire updated approval test
   module on actual Windows with existing dependencies and zero skips (expected
   32 tests if exactly two methods are added), recording exact source SHA/tree,
   interpreter, command, cwd, exit and raw unittest output. Windows checkpoints use
   a local fixed-disk temp directory, not the UNC source directory. Confirm the new CI step
   really selects this module with usable imports and failure propagation. Preserve
   old Windows steps; no install or dependency changes within this task. Synthetic
   clients on Windows prove native lifecycle behavior, not real MCP transport,
   device I/O or real approval authority. If no existing runtime can execute the
   module, report the specific environment blocker rather than claiming a skip pass.
6. **Regression/provenance.** Re-run targeted new tests plus the full module on Linux
   and Windows; run existing focused ownership/task/CLI regressions and proportionate
   full Pioneer/QA/common, actual H09 eight-case CLI and frozen QA-v3 regression on
   fixed source as required by the frozen contract. Check source hashes and unchanged prior
   oracles. Preserve raw failures before fixes and rerun unchanged assertions. New
   acceptance evidence supersedes neither earlier source-bound results nor separate
   hosted-CI status; report only actually observed checks for the exact revision.

## Boundaries and handoff

Use existing runtimes only. Review evidence is bounded plain text/JSON plus hashes,
not tar/zip; do not open any archive member/body, Q06 payload or Q06 ancestry. Do not
touch the main checkout's three WIP files. No credentials, .env, provider, game,
bridge, installation, deployment, push or permission expansion. Keep none/false.

After plan commit, wait for immutable author SHA/tree plus
actual self-test logs. Independently review and reproduce findings; do not repair
author production code. Final recommendation names exact source, counts/skips,
remaining limitations and the report commit. A previous APPROVE or CI pass is not
proof of this new source; the coordinator owns any later combined-tree verification.
