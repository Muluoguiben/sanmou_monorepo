# A — read-only task runtime and A/B integration

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
