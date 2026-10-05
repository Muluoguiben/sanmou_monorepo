# H06a independent review and fault-injection plan

Frozen before reading the new implementation. Date: 2026-10-06.

## Identity and scope

- Review base: `751df8ee867479b9ad272c9c64ab190f76cd0934`.
- Task contract read from immutable author document commit `ab34886e6402a8f793e03e965b5a47401b99c85a`, path `docs/harness-checkpoint-ownership-h06a-2026-10-06.md`.
- Reviewer branch: `codex/h06a-cr-20261006`; isolated Windows worktree `C:/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo`. The legacy directory name is not source identity.
- This document is a plan, not approval or evidence that H06a passes. Formal review waits for a coordinator-supplied immutable source commit and tree. No moving author implementation has been inspected.
- Only review reports and independent probes may be changed. No source/packages/state/todo/shared-memory changes, merge, push, dependency installation, provider call, real MCP/game/capture, knowledge publication or account changes.
- Current harness/RAG reviews and the H06a task contract override historical automation milestones. Preserve Game seven-tool and QA six-tool contracts, recommendation-only, `execution_authority=none`, `executable=false` and hard-disabled `--execute`.

## Evidence protocol

1. Record exact source SHA/tree, diff paths and immutable author report separately. Never execute old report-worktree packages as the new source.
2. Produce a complete Git archive with explicit `-c core.autocrlf=false -c core.eol=lf`, extract to a disposable WSL/ext4 directory and verify every tracked file byte-for-byte against Git blobs before and after tests. Do not alter expected fixture hashes for CRLF.
3. Store independent probes and raw logs under `docs/test-reports/2026-10-06/H06a-CR-artifacts/`. Bind real argv, cwd, Python executable/version, OS/backend/filesystem, exit status, counts/skips, timing, source identity and SHA-256 log hashes. Keep red, green and environment/setup failures in distinct report sections; never overwrite original red evidence.
4. Synchronize real child processes with explicit event/pipe/barrier handshakes and bounded waits. A timeout is a failure, not race evidence. Only terminate owned disposable child PIDs; retain child stdout/stderr and exit status. Fake MCP records independent connect/call/cleanup counters.
5. Test actual POSIX and native Windows backends if declared supported. Windows paths must be native disposable local paths; WSL on `/mnt/c`, mocked `os.name`, and existing Windows API/Electron CI are not native harness-lock proof. Missing existing dependencies become an explicit coverage gap, not a silent pass or installation request.

## Frozen adversarial matrix

| ID | Experiment | Required oracle |
| --- | --- | --- |
| R01 | Two independently spawned CLI processes, same checkpoint, synchronized ownership contention; repeat with checkpoint initially absent and present | Exactly one owner enters fake MCP; loser connects/calls/writes zero times. Winner JSON/budget/revision remain unchanged by loser. Capture loser exception/exit and hash before/after. |
| R02 | Hold owner through checkpoint replacement and MCP cleanup; contend at both boundaries | Stable sidecar remains the locked object. Replacement never opens a second-owner window. No active sidecar unlink. Second process cannot connect while first CLI cleanup is pending. |
| R03 | Direct runner load/restore/dispatch/save, two instances in one process, same-instance recursive/concurrent invocation | No unowned load or budget restore; no duplicate dispatch; nested rejection cannot release the outer owner's lock. Distinguish runner-owned lifetime from externally owned client lifetime. |
| R04 | Independent checkpoint paths; release then reuse same store/runner and fresh runner | Independent paths proceed; released path is reusable, owner identity changes appropriately, state is reloaded under lock rather than stale in-memory resurrection. |
| R05 | Save with old revision, old/released/foreign owner, wrong run identity and wrong task identity | Every rejection is nonmutating. Revision is a strict integer and strictly increases on successful persistence, not schema version. Winner terminal status and budget cannot be rolled back. |
| R06 | Inject ownership/CAS conflict during normal work and generic failure/finish paths | Distinct safe conflict outcome; no `_finish` retry writes, refund, replacement of winner or loss of primary error. Check persisted bytes, not just raised class. |
| R07 | CLI and direct-runner pause, cancel, async cancellation, terminal restart | Owner releases after last owned persistence/cleanup; successor reacquires. Resume spends preserved budget and gets new observation before decisions. Terminal restart performs zero MCP connect/call. |
| R08 | Constructor, state validation/load, budget restore, fake MCP connect/runtime/cleanup failures; combine primary and cleanup errors | No lock leak; primary error is preserved; cleanup failure does not release prematurely or hide a write conflict. Successor can acquire. Cancellation during cleanup also terminates boundedly. |
| R09 | Kill child after persisted call reservation but before dispatch | Successor reacquires through OS release, loads valid JSON, retains spent/reserved budget and original deadline, and observes before any policy decision. No automatic budget replenishment or fabricated prior success. |
| R10 | Kill child when temporary JSON is complete but before atomic replace | Surviving committed checkpoint is valid and exact; incomplete/uncommitted temp is never promoted merely because it exists. Prior reservations cannot disappear. Successor reobserves. |
| R11 | Kill child immediately after replace, before in-memory completion bookkeeping | New durable revision wins; successor cannot replay stale snapshot over it, refund reservation or use stale observation. Check monotonic counters and original absolute deadline. |
| R12 | Legacy RunState v1 migration with non-default safety fields, paused/pending and terminal cases | Migration occurs only under ownership; semantic comparison preserves run/task, spent/reserved counters, deadline, cursor/completed steps, pending call, observation/capture provenance, status/reason, TaskSpec/PolicyContext meaning. Terminal migration has zero calls. |
| R13 | Unknown envelope/inner versions, malformed/truncated JSON, invalid revision types/ranges, mismatched task/run, unsupported locking/backend | Fail closed before client connection and state rewrite. Existing checkpoint bytes remain unchanged. No warning-and-continue fallback. |
| R14 | Documented path/backend limits and existing lifecycle regressions | Claimed support matches behavior/evidence. Do not claim distributed, network-FS, mixed Windows/WSL-kernel, cross-checkpoint device lease, alias/hardlink coordination or action exactly-once. Existing lifecycle A/B, budget, trace, cancellation and package tests stay intact. |

## Probe independence and review decision

Independent black-box probes will exercise public CLI/runner/store behavior with local fakes. Fault hooks may wrap durable write boundaries in disposable test processes, but cannot replace the lock/CAS algorithm with a mock. Source inspection supplements probes for ordering, exception paths, OS lock semantics, ownership release and scope drift; author tests alone cannot close a gate.

For each crash case, the parent records the last acknowledged durable boundary before terminating the child, then launches a distinct successor. Capture reservation/call counters both before crash and after recovery, including unknown-cost state, without assuming exception equality proves durability. A failed handshake is setup failure, never a passed crash test.

Additional cross-checks: after owner A releases and owner B acquires, call A's delayed/repeated close/release and attempt A's stale save; B must remain exclusive and intact. Exercise failed acquire followed by teardown, as well as revision/owner ABA attempts across release/reacquire. There is no TTL takeover in this scope: a live held owner prevents B from acquiring, including between validation and replacement. The cross-check reviewer provided generic fault patterns only, did not read the author implementation, and made no code finding.

Freeze the smallest reproducing red probe and report blocking findings promptly so the author can repair independently. Do not supply author implementation or silently repair reviewed source. A new code revision requires coordinator-authorized re-review and a new immutable source binding; old approval never transfers automatically.

Approval requires no unresolved correctness/safety blocker and evidence for each claimed platform. Any missing native gate or untested lifecycle boundary remains explicit. Final report names files reviewed, severity/location/reproduction for actionable findings, exact tests/counts/skips, source/tree, CR commit, and unverified boundaries. Full H06/device lease, production readiness and real-game exactly-once remain outside this slice.

## Pre-source addendum: native evidence and runner reuse

Coordinator-supplied environment facts (not independently rerun by this reviewer): local default Python 3.14 lacks pydantic/MCP; bundled Python 3.12.14 has pydantic 2.13.5 but lacks MCP/AnyIO/YAML; the registered old D-drive Python 3.11 path is unavailable. Reusing WSL pure-Python dependencies reached a missing `pywintypes` import. No dependency installation, SDK shim or fake `pywintypes` is permitted to turn this into native integration evidence.

Verification therefore has three separately reported layers:

1. Independent POSIX/ext4 checkpoint, runner and CLI tests against the byte-verified immutable source, including real processes and crash injection.
2. Native Windows stdlib ownership-helper tests may load only that helper under bundled Python 3.12 and exercise real `msvcrt` process contention/release. These tests are explicitly primitive-only, not native harness or MCP integration coverage.
3. Full native Windows checkpoint/runner/CLI integration must run in the existing regression Windows job, which the coordinator reports already installs Python 3.12 and package dependencies. One narrowly scoped H06a test step is authorized; dependencies, permissions, publication and other jobs stay unchanged. Reviewer does not edit CI/source. Final acceptance requires the new H06a step to pass for the exact delivered source SHA, verified from its commands/results rather than a generic API/Electron-green badge. Before that result, report native integration as pending and do not grant unconditional cross-platform approval. CI-discovered source bugs require author repair and fresh immutable re-review.

Same-runner reuse is an independent oracle, not an accepted author claim. After release/reacquire, vary persisted budget and non-budget run state independently: unchanged ledger; increased spent/reserved amounts; changed absolute deadline or unknown-cost state; changed cursor/pending observation; foreign run/task; and terminal status. Compare the actual persisted counters/deadline before and after every path, and inspect decisions/calls to detect stale in-memory state. An equal-budget snapshot is insufficient if another safety-relevant field changed. If the contract rejects a changed nonterminal ledger with `fresh_runner`, rejection must occur before connection/dispatch/write and must not refund, finish-save or leak the owner. A terminal checkpoint must return with zero calls and cannot be overwritten by the old runner. Repeat delayed close/release from the old lifetime while a fresh owner is active. Preserve elapsed wall-time semantics as well as numeric equality; a reused deadline cannot restart the run clock.
