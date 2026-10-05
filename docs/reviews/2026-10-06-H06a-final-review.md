# H06a independent final source review

## Decision and exact scope

**APPROVE for the reviewed source and measured POSIX / native-lock-primitive scope.** No unresolved source correctness blocker remains in this review. **Full native Windows checkpoint/runner/CLI acceptance is still pending the new H06a step on exact-final-SHA CI**; this report is not unconditional cross-platform readiness or permission to skip that gate.

- Approved source: `96575c30dea99ab58265052987e79bb4e76c0972`.
- Source tree: `8c305fe09cda5cc9e10e306a05f970f644e735f5`.
- Base: `751df8ee867479b9ad272c9c64ab190f76cd0934`.
- Reviewed five production modules (`_checkpoint_lock`, `run_store`, `task_contracts`, `task_runner`, `game_agent`), associated ownership/native/lifecycle tests and contract documentation, and the narrowly added Windows CI step. No QA/common production, KB, MCP catalog, game-control, dependency or workflow-permission changes exist in the source diff.
- The plan was frozen before implementation inspection in `acfc30f3ce94e5bff5d3a89afe7b8c7ee328aabe`, then native/reuse gates were refined in `6b3164a7af1351912440ae989fd8209a8cc38811`.
- All review evidence/probes are separate from author source; no author implementation was written by the reviewer. No push or merge performed.

The implementation uses stable sidecar OS locking, owner-bound monotonic revisions, one runner per explicit ownership lifetime, serialized one-time release, fail-closed persistence errors and primary-aware teardown. This is cooperative coordination of one supported local checkpoint path. It does not complete H06 device leases or prove distributed/mixed-kernel/network-FS/alias coordination, real-action exactly-once, power-loss durability, production readiness or actual game operation.

## Findings closed by immutable source recheck

| Finding | Original evidence | Final closure evidence |
| --- | --- | --- |
| CR01 / P1: MCP cleanup masked cancellation/CAS; outer owner/direct-runner cleanup masked primary exceptions | `270d0a4`, `b4ad6c8`, `509c116`, `abe17cd`; original 44ad8aa and dea73e0 red logs remain unchanged | Original lifecycle, primary-conflict, owner-cleanup and six-test teardown matrix all pass. New identity tests assert the very same primary exception object, no persistence retry, unchanged last durable bytes, and successor reacquisition. Successful/failed terminal MCP cleanup faults remain visible and do not rewrite terminal JSON; cleanup-only errors still surface. |
| CR02 / P1: delayed concurrent old close invalidated successor; memory lock could be released twice | `b4ad6c8`, real-thread deterministic trace scheduling, two failing backend subcases | Original exact probe passes both backends without timeout. Code review verifies `_released` transition and release occur once under RLock before old public-active completion; old close cannot clear/release successor. |
| CR03 / P1: two runners sharing one owner dispatched eight calls but persisted only four reservations | `b4ad6c8`, public constructor arguments and asyncio.gather | Original probe now admits one runner, charges all four calls. New admission oracle proves rejection causes zero calls/writes, retains incumbent ownership, keeps a third store blocked, permits incumbent execution and preserves accounting; explicit outer exit allows successor. |

No remaining CRITICAL/HIGH findings. These closures apply only to the exact source above; further source changes require fresh review. Original failures are not replaced by green logs.

## Source and runtime provenance

A complete Git archive was created using explicit `git -c core.autocrlf=false -c core.eol=lf archive --format=tar ... 96575c30dea99ab58265052987e79bb4e76c0972`, extracted into `/tmp/h06a-cr-96575c3/source`. The independent verifier compared every extracted file against its immutable Git blob: **1557/1557 byte-identical before and after testing**, manifest SHA-256 `af0a750fdb5805b37d19277dcf1d489016866d47ea4c5a2009ab8ca3148aff69`. No expected hash or fixture was relaxed. The report worktree's old packages were never used as final tested source.

Linux: `/usr/bin/python3`, Python 3.12.3 (GCC 13.3.0), `Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.39`, disposable ext4 source/checkpoints. Existing dependency directory `/tmp/sanmou-cr-20261005-6155-deps` was reused read-only for full Pioneer tests; no installation. Versions: pydantic 2.12.5, MCP 1.29.1, AnyIO 4.13.0, FastAPI 0.116.1, Starlette 0.47.3, python-multipart 0.0.20, httpx 0.28.1.

Native primitive: `C:/Users/Lan/AppData/Local/Programs/Python/Python314/python.exe`, Python 3.14.3, Windows 11 build 26200. Stdlib-only independent helper import; actual lock targets are disposable local Windows files. Final helper hash `80603a20c15c049402acf248cc2848a8fef3f661351911d1294a86186b72d52c`. No SDK/pywintypes shim or falsely claimed native MCP coverage.

## Test results and commands

| Verification | Result | Time |
| --- | --- | --- |
| Independent original + additive probe scripts | 27 test methods pass, 0 skips; 24 independent methods plus 3 imported existing CLI methods; subcases include three crash cuts, two CLI contention phases, memory/JSON teardown and error-type/status variants | Per-script raw logs |
| Exact H06a focused suite | 63 pass, 0 skips | 12.198s |
| Full Pioneer with existing dependencies | 961 total: 959 pass, 2 skips | 37.259s |
| Full QA | 394 pass, 0 skips | 36.263s |
| Full common | 2 pass, 0 skips | 0.002s |
| Independent native Windows primitive | 1 pass, 0 skips | 0.360s |

Pioneer skips are exactly the existing Windows-native proxy launch integration and Windows retired-entrypoint/tombstone execution tests. They are not H06a test skips. Full-suite successes do not replace the explicit native H06a CI gate.

Independent probe launcher (each child bounded at 90 seconds):

```text
wsl -d Ubuntu -- python3 -B <review-artifact-dir>/run_independent.py /tmp/h06a-cr-96575c3/source /tmp/h06a-cr-96575c3/recheck test_independent_lifecycle test_primary_conflict test_concurrent_close test_shared_external_owner test_independent_store test_independent_crash test_independent_cli_race test_shared_owner_admission test_owner_cleanup_primary test_teardown_matrix
wsl -d Ubuntu -- python3 -B <review-artifact-dir>/run_independent.py /tmp/h06a-cr-96575c3/source /tmp/h06a-cr-96575c3/recheck test_final_error_identity
```

Here `<review-artifact-dir>` is `/mnt/c/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo/docs/test-reports/2026-10-06/H06a-CR-artifacts`. Launcher cwd is `<source>/packages/pioneer-agent/tests`; environment `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=../src:../../sanmou-common/src:.`; its outputs record concrete argv/runtime/platform/exit and log hashes. Process/crash probes use explicit pipe/event acknowledgments, not sleep-only races, and terminate only owned disposable children.

Full/focused exact commands:

```bash
# cwd /tmp/h06a-cr-96575c3/source/packages/pioneer-agent
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/h06a-cr-96575c3/source/packages/pioneer-agent/src:/tmp/h06a-cr-96575c3/source/packages/qa-agent/src:/tmp/h06a-cr-96575c3/source/packages/sanmou-common/src:/tmp/h06a-cr-96575c3/source/packages/pioneer-agent/tests:/tmp/h06a-cr-96575c3/source/packages/pioneer-agent/tests/unit:/tmp/sanmou-cr-20261005-6155-deps \
python3 -B -m unittest discover -s tests -p 'test_*.py' -v

# cwd /tmp/h06a-cr-96575c3/source/packages/pioneer-agent/tests
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../src:../../sanmou-common/src:. \
python3 -B -m unittest test_checkpoint_lock_native test_checkpoint_ownership test_task_runner test_task_cli test_task_cr_regressions -v

# cwd /tmp/h06a-cr-96575c3/source/packages/qa-agent
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:../sanmou-common/src \
python3 -B -m unittest discover -s tests -p 'test_*.py' -v

# cwd /tmp/h06a-cr-96575c3/source/packages/sanmou-common
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

Windows cwd: `C:/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo`; command `python -B docs/test-reports/2026-10-06/H06a-CR-artifacts/test_native_independent.py`, with `H06A_LOCK_SOURCE=//wsl$/Ubuntu/tmp/h06a-cr-96575c3/source/packages/pioneer-agent/src/pioneer_agent/agent_harness/_checkpoint_lock.py`. This source import location does not change the native local lock target semantics.

## Frozen matrix disposition

| Gate | Evidence and disposition |
| --- | --- |
| R01/R02: real competitors and stable lock lifetime | Independent CLI processes: contender zero connect/calls/writes while incumbent connection or cleanup is parked; replacement contention and native sidecar stability pass. |
| R03/R04: direct runner, reentry and reuse | Same-instance concurrent entry cannot release incumbent; independent runner exclusion, explicit-owner second admission, delayed/concurrent close, changed-budget fresh-runner refusal and same-budget nonbudget reload pass. |
| R05/R06: identity/revision/CAS failure | Stale/released owner, foreign task/run and strict expected revision reject without writes; primary conflict retains same object across harness conversion and teardown; no generic finish retry/refund. |
| R07/R08: pause/cancel/errors/terminal | Original lifecycle/focused tests plus independent cancellation/constructor/reload/pause/cancel/cleanup matrix and terminal cleanup-error/no-rewrite tests pass; terminal restart remains zero connection/calls. |
| R09/R10/R11: three crash cuts | Acknowledged persisted reservation, completed temp before replace and after replace; process death releases ownership; successor sees valid exact durable JSON, increasing revision, no lost reservations/deadline reset, and fresh observation before decisions. |
| R12: legacy migration | Independent state roundtrip and focused migration tests preserve task/run, budget/deadline/reservations, cursor/pending, observation/provenance and terminal fields under ownership; old terminal read does not require rewrite. |
| R13: unsupported/unknown | Bad envelope/revision/format nonrewrite probes plus focused unsupported backend and path checks pass; no old warn-and-continue lock fallback is used. |
| R14: regression/platform boundaries | Source scope remains bounded, full offline packages pass, native primitive passes; full Windows lifecycle remains pending exact-final-SHA CI. No broader lease/execution claim. |

## Raw logs, hashes and setup failures

Artifact root: `docs/test-reports/2026-10-06/H06a-CR-artifacts/`. `96575c3-artifact-manifest.json` hashes **53 artifacts**, including original red probes/logs and all final raw logs; manifest SHA-256 `798a8752e86807e90993bc411d5628dc02e64566c4f570176ef431e04bc18168`.

Key raw log SHA-256 values:

- Pioneer final: `f78a1ca7d3b56461e89a7dbeb77eb44f0fdd062895f561c00e4058f2da7e65a4`.
- QA full: `5d7d55c2b9e0bf2f41e97e6a25b7f446fd8464da941be7065acd83b5363d0431`.
- Common full: `e910e5a9ece82f432a805e5a34fc44d75dc873037b9450073e16cec2caa3cc6d`.
- Focused63: `1dd3e51afb86ad4d7268eb80c100319ee3a7f3407f39e50d6e30ef3d42c72441`.
- Native primitive: `29e0508c910dacfeb3a21c2ae1a079872972583f60950aaa8bab1b543fd3bce2`.

The first full Pioneer run intentionally used only default dependencies and failed import of FastAPI: 957 discovered test entries, one import ERROR and eight skips, preserved as `96575c3-pioneer-full.log`. This is environment/setup evidence, not a hidden source failure. The same immutable source then passed with existing dependency-path reuse, no installation or assertion/timeout changes. Earlier helper setup, PowerShell quoting and guessed-path read failures remain documented in interim reports; the shell-expansion error log is retained separately.

## Remaining handoff gate

Coordinator must integrate only the approved production bytes, audit the final payload, and verify the added `Windows H06a checkpoint ownership and lifecycle` step at the exact final delivered SHA. Its command runs the native/checkpoint/runner/CLI/CR regression modules in the existing Windows job; no dependency/permission changes were reviewed or required. CI failures require diagnosis and, for source changes, a new immutable review. Existing API/Electron success is not a substitute.

No game/CUA/capture/provider/paid model call, credential or private Downloads access, knowledge publish, deployment, account changes, automation creation or master publication occurred in this review. Reviewer reports/probes only; execution authority remains none.
