# F — Eval/R&R correctness and CI regression gates

## Identity and scope

- Task: `01a07f0b-85e8-7880-bb8f-3845dc01fef2`.
- Worktree: `C:/Users/Lan/.codex/worktrees/0f15/sanmou_monorepo`.
- Branch: `feat/review-f-eval-ci-20260908`.
- Initial HEAD: `d377ef8bbaa69e6b25928255eac0cb62714e82f8`, detached and clean.
  The requested baseline is present. No other developer branch was merged.
- Frozen charter/report: read from the coordinator's checkout at `dd76d601f6f40d3e4fceaf10cdd360d78af88cb2`.
- Tested implementation/index tree: `cce0c039d5f37fec9c20cec3a4e705791ef2490d`.
  This tree includes implementation, tests, workflow and directory attributes,
  before adding this report and the F-only TODO section. It is a **tree object**,
  not an invented final commit. Final delivery supplies the commit SHA separately.
- Owned changes: `mcp_eval/{models,runner,scoring,source_bindings}.py`,
  `app/mcp_eval.py`, `record_replay/annotations.py`, associated regression tests,
  `evaluation/scenarios/v1/.gitattributes`, `.github/workflows/regression.yml`.
  QA production modules, other developers' modules and master are untouched.

## Findings and negative evidence

| Finding | Fix | Regression evidence |
|---|---|---|
| R13 | Build frame-pair groups from all recording inputs; check every pair in each segment. Any ambiguous/shared-frame group must be complete and alone, with ambiguous outcome and trace-only/excluded use. | A normal click followed by two ambiguous inputs can no longer be merged into an approved, countable no-change negative. Mixed trace-only segments and partial groups are rejected; separate complete trace-only/excluded groups remain valid. |
| R14 | Inject a digest-collecting wrapper at the canonical `OfflineFixtureEvaluator` byte seam. Include every evaluated fixture name/SHA256 in source bindings and the aggregate catalog digest. | Mutate chapter wood by one **inside the reader**, leaving disk/expectations unchanged: both runs still match 19 actions, but catalog digests differ. Read count remains exactly one per fixture; recorded hashes equal the actual consumed bytes. Missing byte bindings are rejected. |
| R15 | Failed calls supply no folded state, candidates, unknown-domain updates, journal, terminal result, successful tool coverage or successful domain coverage/refresh. All-failed generation scenarios receive zero scores. Attempts/costs/failures remain visible in observability. | All calls failed in home/no-change/interrupted scenarios: success rate and all nine scores are zero, no normal observations or refreshes remain. A failed later response cannot overwrite earlier successful evidence; failed-only tool calls do not satisfy required coverage. |
| R16 | Compute latest valid refresh separately at failure and end; require the successful response to have completed by the cutoff. Reject observations after their call completion and failure timestamps outside the transcript. End means maximum call completion. | Recovery at .060 does not erase valid .020 evidence at .030 failure. A late response carrying an old observation cannot retroactively satisfy failure checks. Future timestamps are rejected by schema and scorer; overlapping calls use the true final completion. |

Baseline proof: the five targeted new tests were run against a temporary archive
of the original `d377ef8` source, while retaining the current test code. Exit 1,
5 test methods, 7 failing assertions/subtests, 0 errors/skips. R13 accepted the
mixed negative; R14 retained the same digest; R15 credited failed queries;
R16 erased earlier refreshes and accepted future time. These are expected
baseline failures, not failed final validation. Log: `/tmp/sanmou-f-baseline-repro.log`.

Run provenance now explicitly states `evaluation_mode=static_transcript`,
`runtime_fixture_executed`, `provider_vision_executed=false`, and
`live_action_executed=false` in manifest, metrics and CLI output. Static runner
API/CLI and run schema reject a provider/model name masquerading as execution.
Existing static model identifiers remain accepted. Old golden-bound manifests
without consumed-byte hashes must be regenerated; seven/six MCP tool contracts
and input schemas have not changed.

## Environment and preparation

Linux: WSL2 Ubuntu, kernel `6.6.87.2-microsoft-standard-WSL2`, glibc 2.39,
Python 3.12.3. Task-only venv: `/tmp/sanmou-f-20260908-venv`.

Final dependency versions: pydantic 2.13.5, PyYAML 6.0.3, Pillow 12.3.0,
cryptography 46.0.7, FastAPI 0.141.1, uvicorn 0.52.4, python-multipart 0.0.32,
httpx 0.28.1, MCP 1.29.1, google-genai 1.75.0. The final environment was installed
from all three pyprojects, including API/SDK and uvicorn extras. No global Python
packages, shared `.env`, authentication or model credentials were changed.

```sh
ROOT=/mnt/c/Users/Lan/.codex/worktrees/0f15/sanmou_monorepo
PY=/tmp/sanmou-f-20260908-venv/bin/python
python3 -m venv --without-pip /tmp/sanmou-f-20260908-venv
python3 -m pip --python "$PY" install --proxy http://127.0.0.1:7897 \
  -e "$ROOT/packages/sanmou-common" -e "$ROOT/packages/pioneer-agent" \
  -e "$ROOT/packages/qa-agent" httpx
```

Default Windows sandbox tools failed before process startup with
`helper_unknown_error: setup refresh had errors`; task-scoped reviewed elevated
exec and the native Codex apply-patch entry point worked. WSL ensurepip was absent;
`--without-pip` plus system pip's `--python` option installed into the independent
venv. Direct PyPI timed out; the local proxy succeeded. Initial exploratory
dependency installation lacked cryptography/google-genai upper bounds; all final
results below were rerun after applying the declared bounds.

Windows: Windows 11 build 26200, Python 3.14.3 in
`C:/Users/Lan/AppData/Local/Temp/sanmou-f-win-20260908-venv` (the registered 3.11
path was missing). Same final core dependency versions as above. Desktop:
Node 24.14.0, npm 11.9.0, TypeScript 5.9.3 and Vite 5.4.21 from the lockfile.

Windows checkout converted transcript JSON and a QA shell script to CRLF.
`git ls-files --eol` and SHA256 comparison proved the cause; restored only the
three confirmed-unmodified files from the index with `core.autocrlf=false`.
No expected digest, oracle, fixture content or script logic was changed.
Directory-level `.gitattributes` fixes line endings for the hash-bound eval JSON;
the CI Windows checkout also sets `core.autocrlf=false`. The shell script is not
part of this change. Before correction, focused tests reported 18 digest errors
and QA reported 2 shebang failures; after restoration both passed.

## Final verification

| Check | Exit | Pass | Fail/error | Skip | Log |
|---|---:|---:|---:|---:|---|
| Focused eval, annotations, contract/service/official stdio | 0 | 75 | 0 | 0 | `/tmp/sanmou-f-focused-final.log` |
| Pioneer full package | 0 | 788 | 0 | 0 | `/tmp/sanmou-f-pioneer-full-final.log` |
| QA full package, including six-tool stdio | 0 | 307 | 0 | 0 | `/tmp/sanmou-f-qa-supported-final.log` |
| Common full package | 0 | 2 | 0 | 0 | `/tmp/sanmou-f-common-supported-final.log` |
| Native Windows API, baseline six tests | 0 | 6 | 0 | 0 | Windows temp `sanmou-f-windows-api-final.log` |
| Desktop `npm ci`, typecheck, build | 0 each | All three commands | 0 | N/A | Windows temp `sanmou-f-desktop-{install,typecheck,build}.log` |
| Eval CLI / artifact readback | 0 | 14 scenarios, 19 runtime fixtures | 0 | Holdout unscored by design | `/tmp/sanmou-f-eval-supported.log` |
| Workflow YAML structure / `git diff --check` | 0 | Passed | 0 | N/A | Local structural checks only |

Exact Linux test commands, with variables defined above:

```sh
cd "$ROOT/packages/pioneer-agent"
PYTHONNOUSERSITE=1 PYTHONPATH=src:../sanmou-common/src "$PY" -m unittest \
  tests.unit.test_mcp_eval tests.unit.test_mcp_eval_regressions \
  tests.unit.test_record_replay_annotations tests.unit.test_game_mcp_contract \
  tests.unit.test_game_mcp_service tests.unit.test_game_mcp_server -v
PYTHONNOUSERSITE=1 PYTHONPATH=src:../sanmou-common/src "$PY" -m unittest discover -s tests -p 'test_*.py' -v
cd "$ROOT/packages/qa-agent"
PYTHONNOUSERSITE=1 PYTHONPATH=src:../sanmou-common/src "$PY" -m unittest discover -s tests -p 'test_*.py' -v
cd "$ROOT/packages/sanmou-common"
PYTHONNOUSERSITE=1 "$PY" -m unittest discover -s tests -p 'test_*.py' -v
```

The baseline reproduction used the same five new test methods under `PYTHONPATH=/tmp/sanmou-f-baseline-20260908/packages/pioneer-agent/src:../sanmou-common/src`:
`test_failed_payloads_never_supply_observations_or_scores`,
`test_recovery_refresh_preserves_pre_failure_history`,
`test_future_observation_is_rejected_by_schema_and_scorer`,
`test_golden_binds_exact_evaluator_bytes_without_second_read`, and annotation
`test_later_burst_cannot_hide_inside_a_countable_negative_segment`.

Windows commands (cwd `packages/pioneer-agent`):

```powershell
$env:PYTHONPATH='C:/Users/Lan/.codex/worktrees/0f15/sanmou_monorepo/packages/pioneer-agent/src;C:/Users/Lan/.codex/worktrees/0f15/sanmou_monorepo/packages/sanmou-common/src;C:/Users/Lan/.codex/worktrees/0f15/sanmou_monorepo/packages/qa-agent/src'
& 'C:/Users/Lan/AppData/Local/Temp/sanmou-f-win-20260908-venv/Scripts/python.exe' -m unittest discover -s tests/unit -p 'test_advisor_api*.py' -v
```

Desktop commands (cwd `apps/sanmou-advisor-desktop`): `npm.cmd ci --no-audit --no-fund`,
`npm.cmd run typecheck`, `npm.cmd run build`. HTTP/HTTPS proxy was process-local.
These checks prove compilation/build only; they do not prove browser or Electron
visual correctness.

Eval command (cwd repository root):

```sh
PYTHONNOUSERSITE=1 PYTHONPATH=packages/pioneer-agent/src:packages/sanmou-common/src "$PY" -m pioneer_agent.app.mcp_eval \
  --battery packages/pioneer-agent/evaluation/scenarios/v1/battery.json \
  --output-dir /tmp/sanmou-f-eval-supported-20260908 \
  --repo-sha d377ef8bbaa69e6b25928255eac0cb62714e82f8 \
  --golden-expectations packages/pioneer-agent/tests/golden/advisor_fixture_expectations.json \
  --golden-fixture-root packages/pioneer-agent/tests/fixtures
```

This precommit CLI identifies the **base commit plus the tested implementation
tree above**, not unmodified d377ef8. Artifacts: `run-manifest.json` and
`metrics-report.json` under that output directory; run ID
`run-82ca0a0bc3334bacaf4aa1072c25a7f1`, catalog digest
`0d9b9b4b0b24e08e29b7da280e5f09643766185b5b3578728e7b27be83f73bb5`.
13 generation transcripts score 1.0 against authored expectations; 1 holdout has
null scores and no labels. Golden 19/19 checks selected action **type only**;
the added hashes improve reproducibility, not visual accuracy or evidence quality.

## CI and remaining boundaries

The workflow installs all three packages plus HTTPX, explicitly imports FastAPI
and the official MCP client, runs the three package suites on Ubuntu, and runs
Windows API tests plus desktop typecheck/build, `npm test` and `npm run dist:win`.
Task E confirmed `npm test` means Node probe tests plus Playwright-driven actual
Electron, with no external Chrome install; `dist:win` includes `--publish never`.
Workflow permissions are read-only; no credentials, live game, publishing or
knowledge review promotion is configured.

**Integration prerequisite:** E owns the new desktop test/packaging scripts and
additional Windows API regressions. They are absent from this baseline feature
and intentionally have not been copied/cherry-picked. The Windows workflow will
fail at those missing scripts until the combined tree includes E. F has not run
E's Electron tests, unsigned installer build, or the hosted GitHub workflow.
Unified CR must run those commands on the combined SHA. CI uses Python 3.12 /
Node 20; local Windows checks used Python 3.14 / Node 24, so exact hosted-version
coverage is also pending. No tests were skipped/removed to hide this prerequisite.

New regressions use synthetic JSON and generated solid-color PNGs only. Existing
package fixture tests ran unchanged; no new game screenshot, private raw image,
model call or live game input was used. Existing JSON runtime fixtures are not
provider-vision evidence. SDK subprocess transport is real; game action execution
is not. External holdout oracle/private keys were not accessed. All authority
flags, disabled `--execute`/live replay, and six/seven-tool compatibility remain.
Representative approved provider-vision accuracy, independent holdout operation,
privacy-reviewed human R&R provenance, trusted broker, live action closure and
signed clean-machine installation remain outside this offline result.
