# H06a final re-review after CR04

## Decision

**APPROVE for source `6b7b5caad1cbffc59692d3fe9df6a3b3d88dfa9c`, tree `bb2636242bad0e796ded0b43d6fc1a5142a839f9`, limited to reviewed code / measured POSIX behavior / native Windows lock primitive.** CR01, CR02, CR03 and CR04 are closed on this exact source. No unresolved source blocker was found. **Full native Windows checkpoint/runner/CLI remains pending the new H06a step on exact-final-SHA CI.** This is not unconditional cross-platform readiness.

This is the current source disposition, superseding the CR04 REQUEST CHANGES supplement. The original scoped 96575c3 approval, CR04 supplement, all earlier red logs and their manifests remain unchanged. Author uncommitted coordination state was not used as source. No reviewer implementation, push or merge occurred.

Relative production changes from 96575c3 are confined to `task_runner.py`; the corresponding ownership tests and internal checkpoint contract also change. No dependency, permission, QA/KB, MCP catalog or game authority change is part of this repair. The borrowed client-slot binding is identity-checked and restored only by its owning wrapper; the short RLock protects local check/install/restore/active transitions, not network awaits or a new device lease.

## CR04 closure and additional lifetime checks

The **unchanged** `test_sequential_harness_reuse.py` now passes both cases. Same-harness fresh-runner recovery actually proceeds to success, rather than merely taking the probe's allowed fail-fast branch. Observation history is `obs-1`, `obs-2`, `obs-3`; original client/journal/checkpoint are reusable after the retired wrapper is detached. Fresh-harness control remains green.

Five additional independent lifecycle scenarios pass:

1. Repeated/delayed old close leaves a successor's exact wrapper untouched; successor succeeds and restores the original client. Terminal same-runner reuse has no new physical calls.
2. Paused same-runner resume reinstalls its wrapper only for the new owned lifetime, succeeds and returns the slot to the original client.
3. A third-party replacement survives close; reuse refuses before calls/writes, preserves checkpoint bytes and permits later lock acquisition.
4. A second constructor over an occupied harness is rejected without creating its checkpoint/sidecar, and the incumbent binding/lock survive.
5. A cleanup fault after actual lock release still detaches the wrapper, preserves the exact cancellation object and leaves a recoverable cancelled checkpoint.

Existing explicit-owner admission tests also pass: a rejected second runner does not write or release incumbent ownership; after the first run returns the external owner remains held until its caller exits. No support for concurrent shared-harness execution is claimed.

CR01–CR03 unchanged original probes, error identity/no-retry-write checks, admission checks and the six-test owned-teardown matrix were rerun, all green. No failure is closed solely by author self-tests.

## Source and evidence binding

The reviewer created a full archive using `git -c core.autocrlf=false -c core.eol=lf archive --format=tar ... 6b7b5caad1cbffc59692d3fe9df6a3b3d88dfa9c`, then extracted it at `/tmp/h06a-cr-6b7b5ca/source`. **1639/1639 files match immutable Git blobs before and after testing**, aggregate manifest SHA-256 `ebd4eaf431835766394b2754ae9f1b1f1b99f01619d9fb3edf02398b7b118a61`. The extra report files in this archive are included in verification; the report worktree's old package source was not executed.

Runtime is the same independently recorded environment as the prior final review: Linux/WSL ext4, `/usr/bin/python3` 3.12.3, kernel `6.6.87.2-microsoft-standard-WSL2`; existing `/tmp/sanmou-cr-20261005-6155-deps` supplies FastAPI and related dependencies for the full Pioneer run. No packages were installed. Native primitive uses actual Windows Python 3.14.3, Windows 11 build 26200, real local temp-file locks and helper hash `80603a20c15c049402acf248cc2848a8fef3f661351911d1294a86186b72d52c`; no MCP/native dependency shim.

## Exact-source results

| Check | Result | Time |
| --- | --- | --- |
| Original/additive independent gate methods | 34 final methods pass, 0 skips: 31 independent plus 3 imported existing CLI methods; includes multi-case concurrency/crash/identity tests | Per-script logs |
| Full Pioneer | 970 total: 968 pass, 2 existing Windows-only skips | 44.325s |
| Full QA | 394 pass, 0 skips | 40.680s |
| Full common | 2 pass, 0 skips | 0.003s |
| Focused H06a suite / exact Windows-step module list | 72 pass, 0 skips | 16.047s |
| Native Windows independent lock primitive | 1 pass, 0 skips | 0.356s |

Pioneer skips remain the native Windows proxy launch integration and Windows retired-entrypoint/tombstone tests; no H06a test is skipped. The 34 passing-method total uses the corrected five-method wrapper fixture run, not both versions cumulatively.

Probe launcher argv:

```text
wsl -d Ubuntu -- python3 -B /mnt/c/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo/docs/test-reports/2026-10-06/H06a-CR-artifacts/run_independent.py /tmp/h06a-cr-6b7b5ca/source /tmp/h06a-cr-6b7b5ca/recheck test_independent_lifecycle test_primary_conflict test_concurrent_close test_shared_external_owner test_independent_store test_independent_crash test_independent_cli_race test_shared_owner_admission test_owner_cleanup_primary test_teardown_matrix test_final_error_identity test_sequential_harness_reuse test_wrapper_lifetimes
wsl -d Ubuntu -- python3 -B /mnt/c/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo/docs/test-reports/2026-10-06/H06a-CR-artifacts/run_independent.py /tmp/h06a-cr-6b7b5ca/source /tmp/h06a-cr-6b7b5ca/recheck test_wrapper_lifetimes_v2
```

Each child uses cwd `/tmp/h06a-cr-6b7b5ca/source/packages/pioneer-agent/tests`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=../src:../../sanmou-common/src:.` and a 90-second bound. Raw logs and concrete argv/runtime/exit/hash output are separate. Explicit process barriers/events are preserved; only disposable owned children are terminated.

Package commands are `python3 -B -m unittest discover -s tests -p 'test_*.py' -v`, cwd respectively `<source>/packages/pioneer-agent`, `qa-agent`, `sanmou-common`. Pioneer child-inherited PYTHONPATH is exactly:

```text
/tmp/h06a-cr-6b7b5ca/source/packages/pioneer-agent/src:/tmp/h06a-cr-6b7b5ca/source/packages/qa-agent/src:/tmp/h06a-cr-6b7b5ca/source/packages/sanmou-common/src:/tmp/h06a-cr-6b7b5ca/source/packages/pioneer-agent/tests:/tmp/h06a-cr-6b7b5ca/source/packages/pioneer-agent/tests/unit:/tmp/sanmou-cr-20261005-6155-deps
```

QA uses `src:../sanmou-common/src`, common uses `src`. All use `PYTHONDONTWRITEBYTECODE=1`. Focused argv is `python3 -B -m unittest test_checkpoint_lock_native test_checkpoint_ownership test_task_runner test_task_cli test_task_cr_regressions -v`, cwd `<source>/packages/pioneer-agent/tests`, PYTHONPATH `../src:../../sanmou-common/src:.`.

Native argv is `C:/Users/Lan/AppData/Local/Programs/Python/Python314/python.exe -B docs/test-reports/2026-10-06/H06a-CR-artifacts/test_native_independent.py`, cwd the Windows review worktree, `H06A_LOCK_SOURCE=//wsl$/Ubuntu/tmp/h06a-cr-6b7b5ca/source/packages/pioneer-agent/src/pioneer_agent/agent_harness/_checkpoint_lock.py`. Only source is loaded through that path; lock targets are native local Windows temp paths.

## Preserved test-fixture error, not a source regression

The first new wrapper probe used a one-decision FakeDecisionPolicy containing only `pause`, then incorrectly expected the same policy instance to continue on resume. Source `FakeDecisionPolicy` explicitly returns `stop/fake_script_exhausted` after its script is exhausted. This produced four passes and one expected-fixture-mismatch failure (5 methods, 1.218s). The original probe and log remain intact; `test_wrapper_lifetimes_v2.py` changes only the synthetic input sequence to `pause, continue, continue`, preserving every assertion and production code, then all five pass (1.216s). It is reported separately, not erased or mislabeled as an application defect. No deadlines/assertions were relaxed.

Original setup/source failures from earlier review rounds also remain intact. The 96575c3 53-artifact manifest has not been regenerated.

## Artifact integrity and final gate

`docs/test-reports/2026-10-06/H06a-CR-artifacts/6b7b5ca-artifact-manifest.json` hashes **79 artifacts**, including previous immutable manifests/red evidence and all new logs/probes. Manifest SHA-256: `c52a0428db218f286dd7e0c7673d58df31480551c63a1f7197ea4863896bc72f`.

Key new raw log hashes:

- Pioneer full: `c50d5ff329f8c99e3fb8960d92e53d4b22f003b9399876d030545cad1f7eae43`.
- QA full: `5bfc7bca10aed839371b092db0d983fec90ca125ad38a94e25e30e68cc67bbe5`.
- Focused72: `10b2e555a5f9b8462b3f5a5c5ae8ea13fe0d77467af763ec038bb45aca062176`.
- Native primitive: `9cb40f015d1ed9344f9f7431882d730a64010d9035c53d4ca38908a64ecbda92`.
- Corrected wrapper fixture: `a721dc1ad4c0395b2a74786989d4a7a4af4bbb64a5ca9ebd88de0c2e28f4a8cb`.

The original 14-gate matrix remains covered by rerun probes, focused tests and source inspection. The only remaining platform gate is actual Windows full H06a lifecycle execution at the exact delivered SHA; coordinator must verify that added CI step, not infer it from API/Electron green. New source changes require new immutable review. No cross-checkpoint device lease, arbitrary alias/fork inheritance/network/mixed-kernel guarantee, real-game exactly-once or production readiness claim is added.

Review work changed only reports/probes. No game/provider/CUA/capture, secrets/private Downloads, deployment, knowledge publication, new dependencies/automations, push or merge. Execution authority remains none.
