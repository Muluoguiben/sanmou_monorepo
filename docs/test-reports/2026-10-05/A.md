# A — read-only task runtime and A/B integration

## CR01–CR03 repair delivery (current)

Date: 2026-10-05. Author repair complete; independent re-review pending. The earlier
code `c902d196...` received REQUEST_CHANGES and is not approved by its green unit suite.
No master operation or CR/C branch import occurred during repairs.

- Fixed code: [58df02b22a26802c1bee6293e7afa8583e654468](https://github.com/Muluoguiben/sanmou_monorepo/commit/58df02b22a26802c1bee6293e7afa8583e654468).
- Fixed A+B tree: `e8bca4ffd066fdf724e64539c95bc944f239f9ab`.
- A0 remains `5269a1a5d09bddcf268d180a3f016f323c27cb95`; B remains
  `9430107ab24a740e751321ca41a98c0e282e2954` and is already included in A.
- Independent red report/reproducer read with `git show` from
  `2f9b61402f7baf959e380b3b32a524e1c8856946`. Only its inspected four-test script
  was extracted to `/tmp/sanmou-A-original-cr.py` for execution. No merge/cherry-pick
  of the CR combination or C payload was performed.
- Repair report commit follows the fixed code and is identified in the final handoff.

Changes are confined to A's task_runner.py and new test_task_cr_regressions.py:

1. CR01/CR02: after checkpoint persistence, recheck cancellation/pause before invoking
   either the underlying tool or policy. The check stays inside the reservation's
   try/finally, so undispatched reservations are still settled and counted. Policy
   checkpoint persistence itself is now inside that finally-protected region.
2. Timeout classification gives explicit cancel/pause priority over deadline failure
   for both tool and policy boundaries. A cancellation that makes remaining time zero
   persists cancelled/cancel_requested rather than failed/run_deadline.
3. CR03: policy transport and validation stages are tracked independently. Invalid
   returned payload is ok/error; ConnectionError or timeout before response is
   error/not_checked; async cancellation is cancelled/not_checked; valid business
   stop is ok/ok with business=stop. Pre-dispatch interruption is
   not_attempted/not_checked. Unknown Usage remains null and reserved usage charged.

Eight new tests include tool/policy checkpoint cut points, cancelled checkpoint
restart with zero calls, pause/resume with reobservation and retained consumed quota,
zero pending reservations after settlement, in-flight timeout/cancel precedence,
invalid return, ConnectionError, actual asyncio timeout, cancellation and business stop.
All use the real B context/budget/trace implementations and synthetic MCP/policy calls.

| Verification | Result | Exit |
| --- | --- | --- |
| New regressions on original runtime, before fix | 8 tests, 10 failures including subcases | 1 |
| New regressions after fix | 8 pass, 0 skip, 0.114s | 0 |
| Original independent CR script on fixed SHA | 4 pass, 0 skip, 0.027s | 0 |
| Fixed-SHA focused A/B/legacy suite | 101 pass, 0 skip, 2.044s | 0 |
| Fixed-SHA Pioneer full suite | 934 total, 932 pass, 2 Windows-only skips, 39.751s | 0 |
| Fixed-SHA common suite | 2 pass, 0 skip, 0.023s | 0 |

Fixed-SHA focused command, from `packages/pioneer-agent`:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:../sanmou-common/src:tests:tests/unit \
python3 -B -m unittest test_task_cr_regressions test_task_cli test_task_runner \
  test_harness_b test_task_contracts test_agent_harness test_agent_harness_lifecycle \
  test_game_agent_cli -v
```

Original CR script: same cwd, `PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=src:../sanmou-common/src:tests python3 -B /tmp/sanmou-A-original-cr.py`.
Full Pioneer/common commands and environment are unchanged from the historical
record below, including the temporary API dependency directory. The final two skips
remain native Windows proxy/tombstone checks; they are not passes. Logs and SHA-256
bindings: [cr-evidence.json](A-logs/cr-evidence.json), `A-logs/cr-*.log.gz`.
The local red run used the old committed runtime plus new uncommitted regression
inputs; the fixed-SHA focused/full logs bind the final committed test source.

Provider, vision, game input, live replay and native Windows coverage remain unrun.
Game/QA catalogs and none/false execution authority are unchanged. CR01–CR03 are
submitted for independent closure; this report is not a replacement CR approval.

## Historical initial delivery (retained; superseded for approval)

Date: 2026-10-05 (Asia/Shanghai). Scope: H01/H02/H03 and offline H09.
Status: author implementation and combined A/B self-test complete; independent CR pending.
No master merge/push. No live provider, vision, game input, publishing or control broker.

## Immutable source identity

| Role | Commit |
| --- | --- |
| Dispatch baseline | `965ef6713b58048c0765654e8061c5cffda6c59d` |
| Business baseline | `12e7ddc73c86665ccad0764c8aa8aec51de39e3a` |
| A0 contract | [5269a1a5d09bddcf268d180a3f016f323c27cb95](https://github.com/Muluoguiben/sanmou_monorepo/commit/5269a1a5d09bddcf268d180a3f016f323c27cb95) |
| A1 core | [0a54c54be7115d2652dbd86e946cb59edeefc1c7](https://github.com/Muluoguiben/sanmou_monorepo/commit/0a54c54be7115d2652dbd86e946cb59edeefc1c7) |
| B dependency | [9430107ab24a740e751321ca41a98c0e282e2954](https://github.com/Muluoguiben/sanmou_monorepo/commit/9430107ab24a740e751321ca41a98c0e282e2954) |
| B integration merge | [93c5498302270f269c988f963a7952e8b32f8bc3](https://github.com/Muluoguiben/sanmou_monorepo/commit/93c5498302270f269c988f963a7952e8b32f8bc3) |
| Final A code / tested A+B combination | [c902d19601e2b16a4529fa874445fdef3814f5a8](https://github.com/Muluoguiben/sanmou_monorepo/commit/c902d19601e2b16a4529fa874445fdef3814f5a8) |
| Tested code tree | `0818587711158ef2c4dd3e5bfecf9ca3fa28f245` |

Report commit is created after this code-bound report and supplied in the final handoff;
it is not a self-referential code SHA. Subsequent report-only commits do not change the
tested source. `git merge-base --is-ancestor 9430107... HEAD` returned 0: CR must not
cherry-pick B again onto A. C is not included in this tree.

Worktree: `C:/Users/Lan/.codex/worktrees/9027/sanmou_monorepo`.
WSL view of the same worktree: `/mnt/c/Users/Lan/.codex/worktrees/9027/sanmou_monorepo`.
Branch: `codex/harness-a-runtime-20261005`. No other worktree was modified.

## Delivered behavior

- Versioned TaskSpec/RunState and DecisionPolicy port; Runbook Condition/evaluate_all/
  evaluate_any and canonical Game MCP catalog are reused. Policy controls task continuation,
  waiting, pause/stop and success proposals; existing candidate ranking is unchanged.
- TaskRunner composes existing single-window freshness/binding/stop gates, adds three-or-more
  fresh observation steps, goal-evidence validation, absorbing terminal states, bounded
  waiting, pause/cancel and resume. Success is verified from authoritative state; a policy's
  success proposal is not proof. Missing metrics/evidence cannot succeed.
- Atomic version-checked checkpoint stores cursor, pending call, accepted observation IDs,
  session/window, capture timestamp, evidence refs and budget snapshot. Resuming a nonterminal
  run reobserves and rejects repeated IDs, nonincreasing capture timestamps and changed identity.
  Terminal restart performs no tool calls. Interrupted reservations remain charged.
- A integrates B's actual BoundedContextBuilder, RunBudgetLedger and JsonlRunTrace.
  Calls reserve before dispatch, checkpoint pending work, and settle in finally. Unknown
  model usage/cost stays unknown and reserved tokens stay charged. Rule policy has no model
  attempts. No automatic retry is enabled; B's optional retry helper is separately tested.
- Policy/validated-tool/lifecycle events carry run/step and observation/evidence references.
  Transport/contract/business outcomes remain separate. Game schema validation now occurs
  inside legacy ToolLog's failure boundary, fixing schema errors logged as success.
- CLI opt-in flags: `--task-spec`, `--run-state-path`, `--run-trace-path`, `--resume-task`,
  `--task-timeout`, `--task-tool-limit`. Task mode uses RuleDecisionPolicy and Game-only
  windows; `--qa-question` is rejected in task mode instead of silently ignored. Existing
  single-window CLI/QA behavior remains. Task CLI tests inject a fake MCP context manager.

Task contracts and integration timing: [harness-task-context-v1](../../contracts/harness-task-context-v1.md).
Game seven tools, QA six tools, `execution_authority=none`, `executable=false`, disabled
`--execute` and live replay are unchanged.

## Verification and environment

Python 3.12.3 (WSL Ubuntu), Pydantic 2.12.5, MCP 1.29.1, PyYAML 6.0.1.
Final API tests use read-only dependencies installed by B at
`/tmp/sanmou-harness-b-api-deps-20261005`: FastAPI 0.116.1, Starlette 0.47.3,
python-multipart 0.0.20. No global Python installation/configuration changed by A.
All tested source is from A's actual worktree; this dependency directory contains packages,
not B's source. `PYTHONDONTWRITEBYTECODE=1` and `python3 -B` used throughout.

| Check | Result | Exit | Source binding |
| --- | --- | --- | --- |
| A0 focused | 5 passed, no skip | 0 | committed as A0 |
| A1 focused + legacy regressions | 49 passed, no skip | 0 | precommit source later A1 |
| A/B actual services + CLI + legacy | 93 passed, no skip, 1.620s | 0 | precommit source later final A code |
| Pioneer first full run | 922 total, 913 pass, 1 import error, 8 skips, 39.766s | 1 | final A code |
| Pioneer final full run | 926 total, 924 pass, 2 skips, 37.764s | 0 | final A code |
| Common full run | 2 passed, 0 skip, 0.028s | 0 | final A code |
| `git diff --check`, clean tracked source, B ancestor | passed | 0 | final A code |

Focused invocation from repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src:packages/pioneer-agent/tests:packages/pioneer-agent/tests/unit \
python3 -B -m unittest test_task_cli test_task_runner test_harness_b test_task_contracts \
  test_agent_harness test_agent_harness_lifecycle test_game_agent_cli -v
```

Source-bound final full invocation from `packages/pioneer-agent`:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/tmp/sanmou-harness-b-api-deps-20261005:src:../sanmou-common/src \
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
```

First full invocation is identical without the temporary dependency directory. Common:
from `packages/sanmou-common`, `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -B -m unittest discover -s tests -p 'test_*.py' -v`.

Raw output is preserved losslessly as `A-logs/*.log.gz`; original/gzip SHA-256, original
temporary paths, code identities and summaries are in [evidence.json](A-logs/evidence.json).
The final full run includes every new A/B test on committed source.

## Preserved failures and skips

1. Initial default exec helper failed before process creation (`helper_unknown_error`).
   Scoped escalated commands were used for authorized repository work only.
2. Native `python` 3.14 A0 attempt: 1 loader error, `ModuleNotFoundError: No module named
   'pydantic'`. `py -3.11` then exited 101: its registered D: interpreter could not start.
   Neither attempt counts as native coverage; WSL A0 then passed 5/5.
3. First source-bound full Pioneer run failed importing `unit.test_advisor_api_upload_cleanup`
   because FastAPI was absent. Six API tests skipped for that same dependency reason.
   The final run loaded the temporary API dependencies and passed those tests.
4. Final remaining skips, not counted as native passes:
   - `CaptureSecurityTests.test_native_client_proxy_server_end_to_end_with_synthetic_capture`:
     native Windows proxy launch integration.
   - `RetiredControllerTests.test_retired_entry_points_exit_without_writing_requested_paths`:
     Windows tombstone execution requires PowerShell/cmd.
5. An unquoted PowerShell `HEAD^{tree}` query was misparsed and failed; quoted
   `git rev-parse 'HEAD^{tree}'` returned the recorded tree. No source change resulted.
6. Internal read-only subagent could not read code: two scoped reads were rejected because
   automatic approval review's model was at capacity. The main session also had one
   combined read/test command rejected for the same capacity reason; it did not execute.
   Later scoped main-session commands succeeded. No independent internal approval is claimed.

## Offline H09 evidence and limits

Frozen cases: `packages/pioneer-agent/tests/fixtures/agent_harness/task_cases_v1.json`.
Digest is recorded in evidence.json. This is a developer-authored development split,
not an independent holdout/gold set. Synthetic sequence derives from the committed
`recommendation_ready.json` fixture; current chapter increases 1/2/3 under a fresh
observation ID and timestamp. No real gameplay progression is simulated as an action.

Four expected paths match (4/4): rule reaches goal after three observations; rule refuses
missing field provenance; fake success proposal is rejected; step cap terminates early.
The one supported-goal scenario succeeds (1/1); all three intended non-success scenarios
remain non-success (3/3). Assertions check none/false authority; zero game input exists.
These are conformance case counts, not a provider task-success or safety benchmark.
Tool/model budgets, JSONL trace, context overflow, cancellation during wait/call, crash
pending-call restore, old evidence, policy context mutation, session permissions and
post-policy staleness have additional offline negatives in test_task_runner.py.

| Evidence class | What ran / not claimed |
| --- | --- |
| Mock / fixture policy-in-loop | Rule/Fake policy, fake MCP sequence, real A/B services; passed |
| Existing fixture/static replay | Included in Pioneer full unittest; not provider vision |
| Model-attempt accounting | FakeModelPolicy only; estimates/reservations, measured token/cost unknown |
| Provider / vision | Not run; no model API calls or private images |
| Live action / live replay | Not run; authority remains none/false |
| Independent CR | Pending; internal reviewer was blocked by tooling |

Exact field provenance is required for goal success. Aggregate-only metadata cannot
prove an arbitrary leaf metric; unsupported conditions fail closed rather than guess.
No claim of complete live TaskSpec coverage, optimal policy, semantic model grounding,
cross-process checkpoint lease/CAS, exactly-once game side effects, native Windows
checkpoint semantics, complete QA quality, or production readiness is made.
Goal success remains absorbing if CLI transport cleanup later fails; that separate
deadline/cleanup failure is returned as `transport_lifecycle_error` and traced, never
silently reported as clean lifecycle success.

Next owner: unified CR freezes final A code plus C, observes B already in A's DAG, and
runs independent adversarial combined-tree checks. Coordinator owns root todo/manifest.
