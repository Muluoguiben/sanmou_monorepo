# H09a independent CR: REQUEST CHANGES

Date: 2026-10-06. Reviewer: independent GPT-6 Astra agent.
Frozen plan: local commit `e617172a512c922aec8b4a461ebfd38e24debaa7`.

Current reviewed candidate: `134d73b0960d51b6361fb4085a58a3d598a74595`.
Exact tree: `caea2f5fd61a62bb361d28dbd77e5811544ceeb7`.
Previous candidate: `64adbfbb951754a36cfd9189f4294d70b323eb28` /
`eb7e0cf117fa39af4cb6d6ba0e3a3c5037371d58`.

Verdict applies to these exact candidates only. Three reproduced P2 contract
defects block H09a approval; no author WIP or implementation was changed.
H06 Windows hosted acceptance remains independently blocked; no publish allowed.

## Findings

### CR01 [P2] Bind the CLI actually executed, including __main__

`packages/pioneer-agent/src/pioneer_agent/agent_harness/_task_eval_source.py:87-90`
filters by the `sys.modules` key's top-level package. Python executes the CLI as
`__main__`, so the real entrypoint is excluded, while the on-disk original CLI
is included in the Git manifest and implicitly presented as executed source.

Reproduction uses an ordinary copied CLI outside the reviewed source root, adds
one comment (uncommitted bytes), then invokes it with the documented explicit
`--source-root` and `--suite-root` options. No hostile loader or monkeypatch is
involved. Both candidates return exit 0, `source_verified=true`, `gate_pass=true`
without binding the actual executed CLI. The raw process command and copied
entrypoint digest are in `unbound-cli-process.json` in each probe directory.

Fix: validate and record the actual entrypoint file/spec origin, including normal
`python -m` and direct-script `__main__` execution. If arbitrary library launchers
are intentionally supported, represent that boundary explicitly; never assert
that the committed CLI was used when an unbound CLI produced the report.

### CR02 [P2] Keep observed goal success separate from control-label agreement

`packages/pioneer-agent/src/pioneer_agent/agent_harness/task_eval.py:214`
computes goal success using `reached and passed`; `passed` includes expected tool
sequence and other labels. A goal run really reaches `succeeded/goal_verified`
with unchanged evidence and 12 calls. Changing only `expected.tool_calls` to `[]`
makes `goal_success` change from true to false. The control mismatch should fail
`control_pass`, but it must not erase the independently reported goal fact.

This was independently reproduced after the coordinator raised the static
candidate. The same single actual result is scored twice; no execution, fixture,
goal category or evidence changes. `label-probe.json` retains both scores and
the complete actual result for both code versions.

Fix: separate actual verified goal/evidence/safety checks from expected control
label matching. Preserve goal denominator 2 and keep the all-controls publication
gate strict. Do not count safety cases as goal successes or permit unsafe/infra
runs to masquerade as valid goals.

### CR03 [P2] Preserve actual execution when a phase artifact write fails

`packages/pioneer-agent/src/pioneer_agent/agent_harness/task_eval.py:132` lets a
phase JSON write exception escape after execution has completed, then
`:261-263` substitutes only an exception class and minimal scores. The accumulated
RunState, bottom-client calls, policy calls and trace are discarded from the
final report even though the final report itself is successfully writable.

Inject one `OSError` at the first `phase-1.json` write. The task has already made
12 tool and 3 policy calls and succeeded. The evaluator correctly exits 2 and
keeps denominator 8/infra_error 1, but the first case has no `actual` field; its
in-memory call/trace evidence is gone. This violates complete failure reporting
and makes the infra case unreviewable. Both versions reproduce identically.

Fix: retain accumulated actual state and call/trace records across artifact and
cleanup errors, record the error against the phase, and carry those facts into
the failed final report. Keep original failures and do not turn this into a
safety pass. A report write failure that prevents any report is a separate limit.

## Executed checks

| Source | Check | Outcome |
| --- | --- | --- |
| 64adbfbb | Fresh CLI twice | Each goal 2/2, safety 6/6, control 8/8, infra 0/8 |
| 64adbfbb | Stable projections/input manifests and all artifact digests | Match |
| 64adbfbb | New task-eval unittest module | 14 passed, 0 failed, 0 skipped |
| 64adbfbb | Related `test_task*.py` regression | 55 passed, 0 failed, 0 skipped |
| 64adbfbb | Independent original probes | 12 passed, CR01 failed |
| 64adbfbb | Supplemental probes | 1 passed, CR02/CR03 failed |
| 134d73b0 | Frozen probes replay | 13 passed, same 3 failed, 0 skipped |
| Both | Protected Git objects against supplied manifest | All 831 unchanged |

One of the 13 passing checks during replay validates the already-retained **64**
dual-CLI reports, not a new 134 formal CLI run. The other replay checks run actual
134 modules, including all eight normal cases and both full evaluator infra/CLI
probes. No full-suite or formal dual-CLI success is claimed for 134.

Covered independently: execution/expected and id isolation, exact three-window
counts, missing-evidence/Fake-success/replay/context/session cases, bottom-level
5-call cap including fresh-runner resume, resumed old-observation rejection,
equal capture-time rejection with a new id, terminal/paused no-op assertions,
sequence exhaustion infra denominator, checkpoint acquisition failure, malformed
suite/clock/tool rejection, fixture-byte caching/digest mismatch, path escape and
symlink rejection, lazy out-of-root module/package-path detection, and output
no-clobber. Formal report artifact hashes were independently recalculated.

The new source files, author test module and documented entrypoint were read;
existing TaskRunner, budget, policy, context and relevant contract paths were
inspected. Source-drift/untracked-source behavior has author-test evidence here;
a separate full provenance source-mutation run and exact module-name-to-file
mapping counterexample have not yet been independently completed. These are not
marked passed. Remaining checks resume after blocking fixes on a new SHA.

## Commands and environment

Ubuntu WSL ext4 detached worktrees:
`/tmp/h09a-cr-64adbfbb-20261006` and `/tmp/h09a-cr-134d73b0-20261006`.
Python 3.12 (full runtime/platform in `evidence-manifest.json` and CLI reports).
Dependencies reused from `/tmp/sanmou-cr-20261005-6155-deps`; none installed.

```sh
git -C /home/lan/projects/sanmou_monorepo worktree add --detach \
  /tmp/h09a-cr-64adbfbb-20261006 64adbfbb951754a36cfd9189f4294d70b323eb28
git -C /home/lan/projects/sanmou_monorepo worktree add --detach \
  /tmp/h09a-cr-134d73b0-20261006 134d73b0960d51b6361fb4085a58a3d598a74595
export PYTHONDONTWRITEBYTECODE=1
# ROOT is the matching immutable snapshot, never a relative parent directory.
export PYTHONPATH=$ROOT/packages/pioneer-agent/src:$ROOT/packages/sanmou-common/src:/tmp/sanmou-cr-20261005-6155-deps
python3 -B -m pioneer_agent.app.task_eval --output /tmp/h09a-cr-64adbfbb-eval1
python3 -B -m pioneer_agent.app.task_eval --output /tmp/h09a-cr-64adbfbb-eval2
# In 64 snapshot packages/pioneer-agent:
python3 -B -m unittest discover -s tests -p test_task_eval.py -v
python3 -B -m unittest discover -s tests -p 'test_task*.py' -v
# REVIEW is this report directory, absolute /mnt/c/... path:
python3 -B "$REVIEW/probes.py"
python3 -B "$REVIEW/supplemental_probes.py"
# With 134 snapshot absolute PYTHONPATH:
python3 -B "$REVIEW/replay_134.py"
```

## Preserved evidence

`original-evidence.tar.gz` stores the complete original outputs/fixtures/reports
from both versions, including initial red logs (no replacement or filtering).
SHA256: `4da3d2371a03bdcf64158e84f7ab0fc65c07fb8d01575a318f54722a9884ea46`.
`evidence-manifest.json` binds 405 original evidence files by path, bytes, SHA256.
Protected-manifest SHA256:
`651d4fd446e46c8dd2ae661ce27387016a0ff160ea94ec36f1de2c189531ae3e`.

Raw first-red logs:
- `/tmp/h09a-cr-64adbfbb-probes-first.log`
- `/tmp/h09a-cr-64adbfbb-supplement-first.log`
- `/tmp/h09a-cr-134d73b0-probes-first.log`

No provider, .env, network request, real MCP transport, game input, main-branch
mutation, dependency installation or CI retry was performed. Task CLI regression
uses an injected in-process ManagedSequence fake client. This review is not model,
holdout, live action, production or Windows H06 acceptance. Author's complete
source-bound self-test handoff was still pending when these blockers were issued.
