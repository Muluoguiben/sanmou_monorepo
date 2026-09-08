# C — Harness lifecycle, R17–R20

Status: implementation and self-tests complete; pending unified adversarial CR.
No live verification or production-readiness claim.

## Authorized capture-credential follow-up (latest delivery)

This follow-up supersedes delivery `edd3c3d57f92eb16b75f011c9a37d10005cf4256`.
After the user directly replied `允许` in task C, the reviewed patch was approved.
Earlier attempts based on coordinator-transmitted permission were rejected; no
patch was applied or alternative route used before the direct authorization.

Only `--windows-bridge` passes the process's existing `SANMOU_CAPTURE_TOKEN` to
the Game MCP child's environment. Screenshot/watch-folder and QA child environments
omit it. No default token, credential file lookup, CLI token option, logging,
account/API credential expansion or external transmission was added. Missing
credentials remain missing; protocol validation and refusal belong to A's adapter.

A's committed protocol was inspected at
`19808992e03423cf32540b901ddd360d8b5ae346`: `PROTOCOL_VERSION = 2`, environment
name `SANMOU_CAPTURE_TOKEN`, missing authentication rejects the proxy connection.
A confirms ASCII/no-whitespace length 32–256. No A code was merged into this tree.

Four new tests extend `test_agent_harness_timeouts.py`:

- Parameter/env checks cover bridge, screenshot, watch-folder and QA isolation,
  unrelated tokens, and absence of the sentinel token from argv.
- Missing-token test proves the CLI does not invent a credential.
- An exception containing a synthetic token produces a stopped result whose
  JSON, tool log and journal contain no token value.
- Official `StdioMcpClient` launches six real synthetic JSON-RPC children under
  Windows and WSL, using the generated game/QA environments. Each returns only
  presence/match booleans and is closed cleanly. Only the bridge-mode game child
  receives the sentinel. Neither argv, MCP output nor marker files carry it.

Latest tested blobs (all other source/test blobs below remain unchanged):

| Path under `packages/pioneer-agent/` | Git blob |
|---|---|
| `src/pioneer_agent/app/game_agent.py` | `c4059cd15105ee70e12ed2242a64bed841178d89` |
| `tests/unit/test_agent_harness_timeouts.py` | `6de43c9061f1b0c9db4100aafa78f1d7874769c4` |

The exact Windows/WSL focused and package commands in this report were rerun in
the same isolated environments. Final results: Windows focused **34/34** (9.151s),
WSL focused **40/40** (13.700s, including actual canonical Game/QA stdio), Pioneer
package **795/795** (39.990s); all exit **0**, **0 failures**, **0 skips**.
Logs: `C:/Users/Lan/AppData/Local/Temp/sanmou-c-capture-windows.log`,
`sanmou-c-capture-focused-wsl.log`, `sanmou-c-capture-package-wsl.log`.
The same canonical-LF fixture preparation described below was necessary; fixture
content/digests were not changed or committed. `git diff --check` passed.

Remaining integration blocker: A confirmed its later `4a2e4b8` only updates docs;
`CaptureBridgeClient.connect` still lacks automatic WSL-to-Windows proxy environment
propagation. This C change proves **parent -> Game MCP** environment forwarding,
not the next **WSL Game MCP -> Windows proxy** hop. A/CR/coordinator were notified.
That hop and complete A+C end-to-end capture require separate validation in the
combined tree. No actual token, real screenshot, model inference or game input was
used for this follow-up. Execution stays disabled. Unified CR remains pending.

## Scope and tested tree

- Task: `01a07f0b-3787-7f82-ab0c-400a65b4b1a2`.
- Worktree: `C:/Users/Lan/.codex/worktrees/c31a/sanmou_monorepo`.
- WSL view: `/mnt/c/Users/Lan/.codex/worktrees/c31a/sanmou_monorepo`.
- Branch: `feat/review-c-harness-r17-r20`.
- Start: clean detached `d377ef8bbaa69e6b25928255eac0cb62714e82f8`.
- Frozen charter: coordinator commit `dd76d601f6f40d3e4fceaf10cdd360d78af88cb2`, read only; not merged.
- Source/test blobs below identify the original R17–R20 implementation before adding this
  report and the C-only TODO section. The containing commit is supplied on handoff;
  this report does not invent a self-referential final SHA.

| Path under `packages/pioneer-agent/` | Tested Git blob |
|---|---|
| `src/pioneer_agent/agent_harness/loop.py` | `5473a9631922c5cf3fe978f11e50e95662544d95` |
| `src/pioneer_agent/agent_harness/policy.py` | `ad06b8d9c834b31537fa9411d8d6af087c08b754` |
| `src/pioneer_agent/agent_harness/stdio_client.py` | `e11d964c151db4e9c4469af7ccd13b329cc53ef0` |
| `src/pioneer_agent/app/game_agent.py` | `eae74e89aa77dc047fb90a467ff3159522f6418e` |
| `tests/unit/test_agent_harness_lifecycle.py` | `30897cfe0a671edf0596ed5b725ba11622ac674e` |
| `tests/unit/test_agent_harness_timeouts.py` | `5bea5794b88a7387bff92915bd002265fb6ce92f` |

## Findings and regression evidence

### R17 — Real timer domains

Removed the nonexistent `timing` perception checkpoint. Map and recruitment timer
checkpoints bind separately to `map_land` / `recruit_panel`, capture time,
observation ID and frame SHA. Each timer source becomes applicable after its first
successful observation. Refreshing the map cannot renew an old recruit checkpoint.
Legacy `timers` journal records remain historical and are no longer a stop input.
The existing `runtime_state.timing` pending-timer parsing stays compatible.

Tests: `test_r17_repeated_real_domains_refresh_timer_checkpoint` runs three rounds
121 seconds apart with no synthetic timing domain; all recommend. Negative tests
verify that a missing previously observed recruit source stops at 121 seconds and
an unknown map source cannot overwrite the previous checkpoint.

### R18 — Restart identity recovery

An empty initial session identity means unobserved. The first observation must
match both the current session and the persisted window before it becomes the new
baseline. A missing required identity stops as capture unhealthy; a known changed
identity still stops. Rejected/stale observations cannot overwrite the old baseline.

Tests use a real temporary JSON journal, recreate the harness, then exercise
same-window restart, changed/missing identity, preserved baseline and recovery
when the original window is observed again. Existing known-change-before-observe
and authority tests remain green.

### R19 — Recheck before advice

After QA/state/candidate latency, observation age and checkpoint validity are
checked again before journaling or returning a recommendation. Downstream
observations must preserve session/observation/SHA, captured time, window,
geometry, completed domains and unknown domains.

Tests advance a controllable clock by 300 seconds separately during QA, runtime
state and candidate calls: all stop stale without advice. Twelve subcases alter
downstream provenance and fail closed. Existing ready and human-confirmation
behavior remains compatible.

### R20 — Deadlines, cancellation and failure records

`StdioMcpClient` defaults to 30 seconds for connect/initialize/catalog and 60
seconds per request, with finite-positive constructor and CLI validation. The
installed official SDK `ClientSession` and `call_tool` both receive
`read_timeout_seconds`; an outer asyncio deadline covers transport/queue waits.
Each client owns SDK contexts in one task so nested game/QA clients can close
independently without crossing AnyIO cancel scopes. Failure invalidates the client;
there is no retry. SDK shutdown and a 10-second cleanup deadline bound cleanup.
CLI startup failures and cancelled calls write sanitized tool logs and stop journals.

Tests use a synthetic JSON-RPC child which independently ignores initialize,
tools/list or tools/call, and writes an EOF-close marker. Every bounded failure
closes the child. Tests cover transport creation cancellation, initialization and
call cancellation, nested clients, rejected reuse, actual harness failure logging,
CLI startup failure and nonfinite/nonpositive timeout settings. No test depends on
an indefinitely hanging run. SDK defaults/signatures were inspected at 1.29.1.

## Baseline reproduction

Exported the exact starting tree via native Windows Git:

```powershell
git archive --output=C:/Users/Lan/AppData/Local/Temp/sanmou-c-baseline.tar d377ef8bbaa69e6b25928255eac0cb62714e82f8 packages/pioneer-agent packages/sanmou-common packages/qa-agent
```

The archive was extracted to `/tmp/sanmou-c-baseline-lbjwtx6r` and exercised with
the existing ScriptedMcpClient/recommendation_ready fixture, in-memory journal and
controlled clock. Actual baseline output, in `sanmou-c-baseline-repro.log`:

```text
R17 stopped checkpoint_stale ['timers:121.000s'] ['session_status', 'observe_game']
R18 stopped window_identity_changed [...] ['session_status']
R19 recommended None [] ['session_status', 'observe_game', 'get_runtime_state', 'list_action_candidates']
```

R20 baseline evidence is the missing timeout configuration in the original source;
the new bounded silent-peer tests provide executable regression evidence. No
unbounded baseline hang was launched.

## Environments and exact verification commands

Windows: Python 3.14.3, task-only venv
`C:/Users/Lan/AppData/Local/Temp/sanmou-c-r17-r20-venv`; MCP 1.29.1,
Pydantic 2.13.5, AnyIO 4.15.1, PyYAML 6.0.3, Pillow 12.3.0,
FastAPI 0.141.1, HTTPX 0.28.1. Dependencies were installed only in the venv.

WSL Ubuntu: Python 3.12.3, kernel 6.6.87.2, glibc 2.39;
`/tmp/sanmou-c-r17-r20-venv` created with `--without-pip --system-site-packages`.
Read-only reuse of existing packages; FastAPI installed into this venv only.
MCP 1.29.1, Pydantic 2.12.5, AnyIO 4.13.0, PyYAML 6.0.1, Pillow 12.2.0,
FastAPI 0.141.1, google-genai 1.72.0, cryptography 46.0.7, requests 2.33.1,
HTTPX 0.28.1. No shared `.env`, credentials or global package changes.

From the Windows worktree root:

```powershell
$env:PYTHONPATH='packages/pioneer-agent/src;packages/sanmou-common/src;packages/qa-agent/src;packages/pioneer-agent/tests/unit'
& $env:TEMP/sanmou-c-r17-r20-venv/Scripts/python.exe -m unittest test_agent_harness test_agent_harness_lifecycle test_agent_harness_timeouts -v
```

Result: exit 0; 30 passed, 0 failed, 0 skipped; 5.177 seconds.

From the same worktree's `packages/pioneer-agent` under WSL:

```bash
PYTHONPATH=src:../sanmou-common/src:../qa-agent/src /tmp/sanmou-c-r17-r20-venv/bin/python -m unittest tests.unit.test_agent_harness tests.unit.test_agent_harness_lifecycle tests.unit.test_agent_harness_timeouts tests.unit.test_agent_harness_game_mcp_integration tests.unit.test_agent_harness_stdio_client tests.unit.test_game_agent_cli -v
PYTHONPATH=src:../sanmou-common/src:../qa-agent/src /tmp/sanmou-c-r17-r20-venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Results: focused exit 0, 36 passed / 0 failed / 0 skipped (11.379 seconds);
package exit 0, 791 passed / 0 failed / 0 skipped (38.098 seconds).
`git diff --check` also passed. Actual stdout/stderr was redirected by the shell
to files, never replaced by an in-process stderr object.

Logs under `C:/Users/Lan/AppData/Local/Temp/`:
`sanmou-c-focused-windows.log`, `sanmou-c-final-focused-wsl.log`,
`sanmou-c-package-final-wsl.log`, `sanmou-c-baseline-repro.log`.

## Initial failures and compatibility limits

- Native Windows broad focused discovery: 30 run, 28 passed, 2 errors because
  existing canonical fixture reads require POSIX dir_fd/O_DIRECTORY/O_NOFOLLOW.
  These tests passed under WSL; no security gate or expected result was relaxed.
- Initial WSL venv creation failed because ensurepip was unavailable. Recreated
  using `--without-pip --system-site-packages`. Direct PyPI download timed out;
  pure-Python wheels were downloaded via Windows and installed offline into venv.
- An initial repo-root package discovery had 22 import errors (556 discovered);
  corrected to the AGENTS package cwd. No tests were deleted or skipped.
- Windows autocrlf changed frozen eval input bytes. Package runs found 7 digest
  errors among 791 tests. Both clean static-tool-calls files were restored from
  the Git index with LF, without changing content or expected digests. Generation
  SHA became `329c8441c264afef8b38d78e6ba956bdebd0b8fc980acb239bde533d0341229f`.
  Final package run above passed. F owns the permanent `.gitattributes` fix;
  Windows reruns need canonical fixture bytes until that change is integrated.
- Sandbox exec/apply_patch helper initialization failed. Task-scoped reviewed
  elevated exec was usable. After coordinator guidance, source edits used the
  native `codex.exe --codex-run-as-apply-patch` entry point.

## Boundaries and handoff

Canonical server handlers/catalog/models and QA six-tool surface unchanged.
`execution_authority=none`, `executable=false`, disabled normal execution and live
replay remain unchanged. No control dispatch, new mutating catalog, knowledge
publication, privacy approval or decoded research. No external holdout oracle.

All new evidence is synthetic; official SDK integration exercised the existing
Game and QA servers with committed fixtures/knowledge. No real screenshots,
model inference, real game input, resource consumption or account operations.
Package tests include existing local replay/fixture checks; this is not live closure.
Broker, real image/model accuracy, real action verification and production
deployment remain unverified. Shared memory untouched. Await unified CR before
coordinator integration; this developer does not merge or push master.
