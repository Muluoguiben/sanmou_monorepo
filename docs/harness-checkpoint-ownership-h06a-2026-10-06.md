# H06a: local checkpoint ownership and conditional save

Date: 2026-10-06. Base `751df8ee867479b9ad272c9c64ab190f76cd0934`; exact-SHA CI run37352030235 passed all four jobs. Q02a closes only its bounded offline slice; the continuing engineering route returns to harness reliability.

## Observed problem

`JsonRunStore.save` fsyncs and atomically replaces a JSON file, but has no process owner or revision comparison. `RunState.version=1` is a schema version, not a CAS revision. `TaskRunner.__init__` loads/restores the checkpoint, `_active` protects only one instance, and the CLI reads state before opening MCP. Two cooperative processes can therefore load the same budget/cursor, make duplicate read-only calls and overwrite each other's progress or terminal state.

This slice protects one supported local checkpoint path. It does not implement cross-checkpoint device ownership, distributed lease, TTL takeover, account reset or an effect ledger.

## Scope and compatibility

- Production scope: `agent_harness/run_store.py`, `task_contracts.py`, `task_runner.py`, `app/game_agent.py`; a small private ownership helper is allowed only if it keeps platform code focused. Add targeted/multiprocess tests and an internal checkpoint contract. No broad runtime refactor, new dependency or generic framework.
- Keep TaskSpec/PolicyContext v1 and the inner RunState meaning. If storage needs a new versioned envelope, migrate legacy RunState v1 only while holding ownership; preserve run/task identity, budget reservations/counters/deadline, completed steps, pending call, observation/capture refs, status and reason. Unknown/malformed formats fail closed. Do not confuse schema version with monotonic storage revision.
- Ownership acquisition must precede CLI checkpoint reads, budget restoration and MCP connection, and last through final save and CLI-owned MCP cleanup. Direct runner use must not bypass protection of its own load/restore/dispatch/save; do not claim to control a caller's externally opened client before runner creation or after its owned lifetime.
- Use a stable sidecar OS lock, not the inode replaced by checkpoint save. Acquisition is nonblocking or explicitly bounded. Process exit releases the kernel lock; never unlink an active sidecar to force takeover. Unsupported locking must reject task mode, not warn and proceed as the old Runbook fallback does.
- Save validates the active owner, run identity and expected revision. Reject stale/foreign saves without writing the checkpoint. An ownership/CAS conflict must not enter a generic `_finish()` path that overwrites the winner's state or refunds the losing process's budget.
- Pause/cancel/resume/reuse and failed construction/connection/cleanup need explicit lifetime behavior; no leaked owner or stale in-memory reload. Resume preserves deadline and spent/reserved budget, reobserves before decisions and inherits no stale execution grants.
- State filesystem/backend support must be explicit. POSIX and Windows backends require actual platform tests when claimed supported. Do not promise network-filesystem, hardlink/alias or mixed Windows/WSL-kernel coordination without evidence; document/reject unsupported cases. This is cooperative local-process coordination, not defense against arbitrary same-user filesystem sabotage.
- Keep all seven Game MCP tools, six QA MCP tools, `execution_authority=none`, `executable=false`, recommendation-only mode and hard-disabled game execution unchanged. No QA source/KB change, real model/provider call, secret/Downloads read, client/game action, account setting or deployment.

## Offline acceptance

1. Two real independent processes rendezvous on the same checkpoint. Exactly one enters fake MCP; the loser has zero connect/tool calls and zero checkpoint mutation. Also cover same-process independent runners, independent checkpoints, and exception cleanup.
2. Old revision, old/released owner and wrong run/task identity cannot save; revision is strict/monotonic and terminal state cannot be rolled back by a loser. Validate actual persisted budget/deadline, not only exception type.
3. Kill a disposable child at controlled boundaries: persisted reservation before dispatch, temporary file complete before replace, and after replace. A successor reacquires, sees valid durable JSON, never gains budget, and resumes with a fresh observation. Use deterministic synchronization, not sleep-only races. No real MCP/game process is killed.
4. CLI and direct-runner pause/cancel/async cancellation, runtime/connection/cleanup failures release ownership correctly. Terminal restart produces no MCP connection/calls. Conflicts have a distinct safe outcome and do not invoke an unsafe finish/save retry.
5. Legacy checkpoint migration preserves all safety/budget/freshness fields under lock; malformed/unknown data is not rewritten. Existing A/B lifecycle, cancellation/trace/budget tests and full package regression must remain. Preserve original failures and never relax deadlines/assertions to make concurrency tests pass.
6. Include supported POSIX/Windows native backend checks, plus fail-closed unsupported backend tests. If Windows testing cannot run with existing dependencies, report that gap rather than silently skipping/claiming success; a narrowly targeted CI step may be proposed with evidence.

## Work allocation and delivery

- Fresh GPT-6 Astra implementation agent `/root/h06a_implementation`; clean reused worktree `C:/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo`, branch `codex/harness-checkpoint-h06a-20261006`. Directory name is legacy; immutable commit is authoritative.
- Fresh GPT-6 Astra independent reviewer `/root/h06a_review`; separate reused worktree `C:/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo`, branch `codex/h06a-cr-20261006`. Freeze a review/fault-injection plan before reading new implementation.
- Both read AGENTS, current task/todo, canonical design docs and operating model. The 2026-10-05 harness/Advisor-first review overrides historical automatic-execution milestones. Coordinator has read the six canonical design docs; no historical text grants live authority.
- Source/report commits must be separate and immutable, with exact commands, platform/runtime, test counts/skips, first failures, raw logs/hashes, source identity and unverified boundaries. Prefer one byte-verified full ext4 snapshot for Linux tests; never change fixture hashes for CRLF. Windows checks use a disposable native local path and no game process.
- Authors/reviewer do not push or merge. Coordinator verifies exact approved combined source, audits publication scope, pushes under standing authorization and checks exact-final-SHA CI. H06a does not mark full H06/device lease or production readiness complete.
