# E — Desktop / Advisor API / Windows packaging

Task: `01a07f0b-6d25-75c3-bcb1-acd4ca26cd1d`, 2026-09-08.

CR02 follow-up: the original installation readiness check at `8729d18f` was
unsound and is superseded by the awaited HTTP verification documented below.
Historical passes/failures remain recorded; see **CR02 revision** for current
source identity, deterministic regressions and two actual installation reruns.

CR03 follow-up supersedes OS-assigned test ports. See **CR03 revision** for the
Node 20.20.2 / Python 3.12.14 reruns and bounded high-port allocation evidence.

The same follow-up also addresses **CR06**: Pillow pixel-limit rejection now
returns 413 after cleanup. Its final API, package baseline and newly rebuilt
installer evidence are documented separately below.

**CR07** aligns current validation with supported Node 24.14.0. This final
documentation-only revision reruns the unchanged `b865808d` source/lock on that
exact runtime and preserves all older unsupported Node 20 observations.

## Identity and scope

- Worktree: `C:/Users/Lan/.codex/worktrees/3fd9/sanmou_monorepo`.
- Branch: `feat/desktop-api-r03-r21-r24-20260908`.
- Start and review baseline: `d377ef8bbaa69e6b25928255eac0cb62714e82f8`.
- Initial checkout was clean and detached; a task-specific branch was created.
- Frozen charter read from coordinator commit `dd76d601f6f40d3e4fceaf10cdd360d78af88cb2`.
- Owned changes: `apps/sanmou-advisor-desktop`, the upload-save path in
  `packages/pioneer-agent/src/pioneer_agent/app/advisor_api.py`, its new upload
  regression tests, this report/evidence JSON, and the E-only TODO section.
- No other developer branch was imported; master and the main worktree were not modified.
- [E-test-evidence.json](E-test-evidence.json) records SHA-256 of the exact tested
  source bytes, complete failure/skip lists, log hashes and installer hash. The
  report does not invent its own commit SHA; use the commit containing this file.

## Findings and negative evidence

| Finding | Change | Regression evidence |
|---|---|---|
| R03 | Extracted Python probing; handle spawn errors/null output and continue candidates. Unexpected startup errors are caught before creating the window. | Node test reproduces ENOENT and falls back from a deleted `PYTHON` to the working environment. The original function from the exact baseline throws `TypeError: Cannot read properties of undefined (reading 'trim')`. Real Electron with missing repo/Python/PATH still opens and shows failure. |
| R21 | `preload.cts` emits `preload.cjs`; context isolation and sandbox enabled. Missing desktop bridge errors visibly instead of falling back to port 8765. Runtime status is fetched afresh. | Actual Electron verifies `window.sanmou`, a randomized custom API URL, sandbox=true and no renderer `require`. Installed app verifies packaged paths and a custom embedded port. |
| R22 | Monotonic selection version invalidates old analysis/history success, error and finally handlers. Chat has selection/request identity; changing selections clears conversation. History image/report are applied together after both lookups. Preview cleanup is tied to its lifetime. | Real Electron covers picker/drop/paste A→B while A is in flight; A cannot set B's report or clear B's busy flag. Also covers old error/chat, analysis→history, reversed history responses, and history→paste. Tests wait for response completion before asserting the old result stayed discarded. |
| R23 | Evidence quality is independent of the execution restriction. Unknown, explicitly untrusted, low/zero confidence, non-finite confidence and legacy-only evidence degrade the presentation. | Actual rendered panel: good evidence plus `advisor_mode` is sufficient; unknown with no recommendation, zero-confidence evidence, untrusted evidence and legacy-only reports are insufficient. Execution text always remains advisory. The 0.8 threshold is conservative display guidance, not a new game selector. |
| R24 | Unwind the writer before unlinking partial uploads, including interrupted reads. Invalid-image validation also handles Pillow `SyntaxError`. | Native Windows HTTP upload >10 MiB returns 413 and leaves no file/report; interrupted read leaves no file; exactly 10 MiB invalid input reaches image validation (400); corrupt PNG checksum returns 400 with no residue. Against baseline these four tests report 1 pass, 1 failure, 2 errors (WinError32, leftover partial file, uncaught PNG SyntaxError). |

The corrupt-PNG case was found during the installation check: the original test
PNG had an invalid IDAT checksum. Both the test input and the missing error
handling were fixed; the final installation uses a valid synthetic 1×1 PNG.

## Environment

- Windows 11 `10.0.26200`, PowerShell; Python `3.14.3`, Node `24.14.0`, npm `11.9.0`.
- The registered Python 3.11 launcher path was absent. No global Python or auth
  configuration was repaired; `.venv` belongs to this worktree.
- WSL Ubuntu Python `3.12.3`, temporary environment `/tmp/sanmou-e-01a07f0b-venv`.
- Shared Python versions: FastAPI `0.141.1`, Starlette `1.6.0`, Pydantic `2.13.5`,
  Pillow `12.3.0`, MCP `1.29.1`, httpx `0.28.1`, uvicorn `0.52.4`,
  python-multipart `0.0.32`, google-genai `2.22.0`, PyYAML `6.0.3`.
- Desktop: Electron `29.4.6`, Playwright `1.58.2`, Vite `5.4.21`, React `18.3.1`.
  New electron-builder was updated from `26.8.1` to `26.15.3`; package manifest
  requires `^26.15.3` and the lockfile resolves that version.
- The standard sandbox exec/Node/apply_patch helpers failed during setup with
  `helper_unknown_error`. Scoped reviewed elevated exec worked. Subsequent
  patches used the installed Codex native `--codex-run-as-apply-patch` entry.
- WSL ensurepip was unavailable; venv used `--without-pip`, with existing pip's
  `--python` option. Initial direct PyPI access timed out; the coordinator's
  verified process-local proxy worked. No global pip configuration was changed.

## Reproducible commands

From the Windows worktree root:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e packages/sanmou-common -e packages/pioneer-agent httpx
$env:PYTHONPATH='packages/pioneer-agent/src;packages/sanmou-common/src;packages/qa-agent/src'
.venv/Scripts/python.exe -m unittest discover -s packages/pioneer-agent/tests/unit -p 'test_advisor_api*.py' -v
```

From `apps/sanmou-advisor-desktop`:

```powershell
npm ci
npm run typecheck
npm run build
npm test
npm run dist:win
npm run test:install:win
Get-AuthenticodeSignature release/Sanmou-Advisor-0.1.0-unsigned-x64.exe
```

`dist:win` also runs the complete build. `npm test` runs Node probing tests and
Playwright against the real installed Electron executable, not an external Chrome.
`test:install:win` explicitly installs this package into a fresh temporary path,
uses a separate profile/random port/task-local Python, runs synthetic upload,
closes the app, uninstalls and removes its temporary directory. A subsequent
Windows process inspection found no remaining `sanmou-e-install-*` API process.
Packaged mode writes to its user-data directory; development mode preserves the
existing repository `data/advisor` history location.

Full Windows package command, cwd `packages/pioneer-agent`:

```powershell
$env:PYTHONPATH='src;../sanmou-common/src;../qa-agent/src'
../../.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v > $env:TEMP/sanmou-e-pioneer-final.log 2>&1
```

Comparable Windows baseline, created within this task's ignored `build/`:

```powershell
git clone --no-hardlinks --no-checkout . build/e-baseline
git -C build/e-baseline checkout --detach d377ef8bbaa69e6b25928255eac0cb62714e82f8
cd build/e-baseline/packages/pioneer-agent
$env:PYTHONPATH='src;../sanmou-common/src;../qa-agent/src'
& C:/Users/Lan/.codex/worktrees/3fd9/sanmou_monorepo/.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py' -v > $env:TEMP/sanmou-e-pioneer-baseline.log 2>&1
# Same baseline import paths, but load the four new negative regressions:
& C:/Users/Lan/.codex/worktrees/3fd9/sanmou_monorepo/.venv/Scripts/python.exe -m unittest discover -s C:/Users/Lan/.codex/worktrees/3fd9/sanmou_monorepo/packages/pioneer-agent/tests/unit -p test_advisor_api_upload_cleanup.py -v
```

WSL setup from this same worktree's `/mnt/c/...` path:

```bash
python3 -m venv --without-pip /tmp/sanmou-e-01a07f0b-venv
python3 -m pip --python /tmp/sanmou-e-01a07f0b-venv/bin/python install --proxy http://127.0.0.1:7897 -e packages/sanmou-common -e packages/pioneer-agent httpx
# Run this command once in packages/pioneer-agent and once in
# build/e-baseline/packages/pioneer-agent, with separate actual log files:
PYTHONPATH=src:../sanmou-common/src:../qa-agent/src /tmp/sanmou-e-01a07f0b-venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
# Golden status regression, cwd packages/qa-agent:
PYTHONPATH=src /tmp/sanmou-e-01a07f0b-venv/bin/python -m unittest tests.test_mcp_tools.McpToolTests.test_advisor_golden_replay_status_reports_expectation_failures -v
```

Native unittest stdout/stderr went to real log files. No custom replacement
stderr stream or modified test expectations were used.

## Results and limits

| Check | Result | Exit |
|---|---|---|
| Windows full Advisor API | 10 pass, 0 fail/error/skip | 0 |
| Node Python probe | 2 pass, 0 fail/skip | 0 |
| Actual Electron regressions | 14 pass, 0 fail/skip | 0 |
| Frozen lockfile `npm ci` | pass | 0 |
| Typecheck / build | pass | 0 |
| Unsigned NSIS packaging | pass | 0 |
| Original temporary install/start/mock upload/uninstall | observed pass; readiness acceptance superseded by CR02 | 0 |
| Authenticode | `NotSigned`, as intended | 0 |
| Golden status regression in WSL | 1 pass, 0 skip | 0 |
| Windows exact baseline package | 764 reported, 6 failures, 29 errors, 9 skips | 1 |
| Windows intermediate E package | 767 reported, 6 failures, 29 errors, 9 skips | 1 |
| Windows final E package | 768 reported, 6 failures, 29 errors, 9 skips | 1 |
| WSL exact baseline package on same Windows checkout | 775 reported, 7 errors, 0 skips | 1 |
| WSL final E package on same Windows checkout | 779 reported, 7 errors, 0 skips | 1 |
| Four new upload regressions against original baseline | 1 pass, 1 failure, 2 errors | 1 |
| npm audit | 12 affected package entries (1 low, 2 moderate, 8 high, 1 critical) | 1 |

The complete **35 Windows FAIL/ERROR names**, all **9 skip names and reasons**, and
both original/fixed lists are in `E-test-evidence.json.windows`. Their sets and
skip lists match exactly. This establishes no added package failures under the
tested environment; it is **not** a passing Windows package result. Categories:
POSIX secure fixture-read requirements (`dir_fd`, `O_DIRECTORY`, `O_NOFOLLOW`),
Windows symlink permissions, closed-root file metadata checks, transcript digest
checks, a subprocess-environment assertion, GBK decoding and the pre-existing
runbook file-lock behavior. None of those gates were weakened here.

All seven WSL errors also match baseline and originate from `fixture digest
mismatch for scenario home-observation`. `git ls-files --eol` confirms the scenario
JSON files are `i/lf w/crlf`. F owns the `.gitattributes` fix in
`42f0f5013e820de066ac53776512686588c3af7a`; E did not normalize/rewrite fixtures,
hashes or expectations. Combined-tree verification remains with CR.

## Dependency audit / release blockers

The full npm advisory ranges, links and fix recommendations are preserved in the
evidence JSON. The table classifies reachability; no exploit attempt was made.

| Package (resolved) | Severity / affected range | Surface and remediation |
|---|---|---|
| Electron 29.4.6 | high; up through affected 40/41/42/43 releases, exact ranges in JSON | Shipped runtime; renderer/IPC/permission and other Electron advisories. Existing sandbox limits do not prove these safe. Audit suggests 44.2.0 major migration; require dedicated compatibility/security review before production. |
| extract-zip 2.0.1 | high; `*` | Electron development/install ZIP extraction, not bundled renderer code. Symlink traversal from a malicious archive. Audit routes remediation through the Electron upgrade. |
| Vite 5.4.21 | high; `<=6.4.2` | Development server, source/path exposure and Windows launch-editor path handling. Not present in the packaged runtime. Audit suggests Vite 8.2.2 major migration. |
| esbuild 0.21.5 | moderate; `<=0.24.2` | Development server exposure if invoked; used for builds here. Audit routes remediation through Vite upgrade. |
| @babel/core 7.29.0 | low; `<=7.29.0` | Build-time source map file reads from malicious build input. Compatible transitive update available. |
| browserslist 4.28.2 | high; `<=4.28.6` | Build-time untrusted queries/stats can crash or exhaust memory. Compatible transitive update available. |
| axios 1.16.0 | high; `1.0.0–1.17.0` | `wait-on` development dependency; request construction/form/DoS advisories, not the renderer's native fetch. Compatible update available. |
| form-data 4.0.5 | high; `4.0.0–4.0.5` | `wait-on` and builder publish dependency; multipart field/filename injection. Build uses `--publish never`. Compatible update available. |
| joi 17.13.3 | moderate; `<17.13.4` | `wait-on` option validation; deeply nested link schemas can exhaust stack. Compatible update available. |
| nanoid 3.3.12 | high; `<=3.3.17` | PostCSS build dependency; invalid custom generator sizes can loop. Compatible update available. |
| postcss 8.5.14 | high; `<=8.5.22` | Build-time malicious source maps may disclose local map files. Compatible update available. |
| shell-quote 1.8.3 | critical; `<=1.8.4` | `concurrently` development command handling; malicious op/newline or parser inputs. Scripts use fixed commands; not a proof of general safety. Compatible update available. |

The newly introduced builder's affected dependency chain was removed by updating
to 26.15.3. Remaining packages already existed via desktop development/runtime
dependencies; form-data is additionally referenced by builder publishing. The
audit is not a production approval. CR must classify the remaining blockers;
this task does not perform unrelated Electron/Vite major migrations.

## Evidence boundaries and handoff

- Desktop/installation/API inputs are synthetic, with a controlled fake API for
  race tests and the real installed Python API for install/upload validation.
- The full package suite additionally reads existing committed game fixtures;
  no new real screenshot was captured or privacy-approved in this task.
- No vision/LLM provider, game input, game restart, privileged controller,
  external holdout oracle, knowledge publication or automatic approval was used.
- Seven Game MCP / six QA tools and their canonical catalogs are unchanged.
  Advisor execution remains disabled; normal `--execute` and live replay were
  not altered. No game logic was moved into TypeScript.
- No clean-machine signed production installation, update/rollback, model
  accuracy, or live game closure is claimed. The installer requires preinstalled
  Python dependencies (or an external API). Visual layout was checked via real
  Electron DOM/loaded-image assertions, not a manual pixel-layout certification.
- One intermediate package rebuild overlapped a dependency update and failed
  with `app-builder.exe ENOENT`; the final validation pipeline is sequential.
- One installation repeat saw embedded Python `exited` while health responded;
  a retry passed, so that isolated collision cause was not established. The
  test now reserves its random port through installation until launch. A new
  deterministic occupied-port Electron regression proves an exited embedded
  Python is shown as offline/error even when another service answers health.
  The renderer polls the actual process status instead of trusting health alone.
- CI commands were sent directly to F. Final immutable SHA/branch/report are
  delivered to the coordinator and unified CR; no merge/push to master occurs.

## CR02 revision — awaited installation readiness

Revision parent: `8729d18f5cab45b3616c15b9fc5eef36746b690e`, same worktree and
feature branch. This follow-up changes test support, the npm test entry and
documentation only; production Python, Electron main/preload and renderer
source are byte-for-byte unchanged from that commit. The evidence JSON preserves
the prior artifact/source manifest and adds current tested file SHA-256 and Git
blob IDs. The containing final commit supplies the full tree identity without a
self-referential SHA in this report.

### Retained review failures

CR tested E `8729d18f` in combined `a8babdb` and supplied:

- `sanmou-cr-async-readiness-proof.log`: actual Electron
  `page.waitForFunction(async () => false, undefined, {timeout: 800})` returned
  `JSHandle(false)` after 188 ms instead of polling until timeout. The
  Playwright 1.58.2 poller treated the Promise itself as truthy.
- `sanmou-cr-install-smoke.log`: the subsequent host fetch failed with
  `ECONNREFUSED 127.0.0.1:10483`.
- `sanmou-cr-install-smoke-diagnostic.log`: another install failed with
  `ECONNREFUSED 127.0.0.1:9184` while runtime config still said `running`.

These original logs are under `C:/Users/Lan/AppData/Local/Temp/`; hashes and
non-sensitive failure summaries are retained in `E-test-evidence.json.cr02`.
The old check discarded the returned false handle, so prior successful installs
did not prove readiness waiting was correct. This is separate from the earlier
Python-`exited`/other-listener observation, whose cause remains unestablished.

### Fix and deterministic regression

`tests/advisor-readiness.mjs` polls the host HTTP endpoint, awaiting both fetch
and JSON body completion. Default limits are 30,000 ms overall, 1,000 ms per
request (including the body), and 100 ms between failed probes. Acceptance
requires all of `status=ok`, the exact expected per-test data directory, and
`runtime_admin_enabled=false`. Aborts, non-200 responses, malformed/incorrect
health and transport errors retry only within the deadline. Distinct failure
reasons are retained rather than hidden by the final request timeout. This is
condition-based polling, not a fixed startup sleep.

`install-smoke.mjs` no longer uses `page.waitForFunction` or an unguarded follow-on
host fetch. It consumes the verified health result, then verifies current
embedded-process status, exact configured URL, packaged backend root and mock
upload. Before each install it checks user/machine uninstall registries, fails
on inspection errors or an existing Advisor installation, and constrains the
temporary install/profile to absolute children of its allocated temporary root.
Cleanup closes only the Electron instance it launched and uninstalls only its
temporary installation; it never searches for or kills all Python/Electron.

Seven new HTTP tests are part of `npm test`:

1. Two 503 responses, then 200 headers with a manually held JSON body: the wait
   stays pending until the body is released and succeeds on the third attempt.
2. An always-503 API rejects within its overall deadline.
3. HTTP 200 for another data directory is rejected.
4. HTTP 200 with runtime administration enabled is rejected.
5. HTTP 200 with non-ready status is rejected.
6. A permanently stalled response body is aborted, retried and bounded.
7. An actual socket/network failure is retried before healthy success.

The first local run was 5/7: a last-millisecond timeout masked the earlier
identity failure; the stalled-body fixture's 30/150 ms request/overall budget
did not yield two server requests on Windows. Failure reasons are now preserved.
The stalled fixture uses 100/1,000 ms budgets while retaining both original
assertions (at least two requests and completion under 1,500 ms); no acceptance
assertion was removed. The other short negative fixtures retain 150 ms deadlines.
The initial failure log and final passing logs are retained by name/hash.

### Current commands and results

From the repository root:

```powershell
node --test apps/sanmou-advisor-desktop/tests/advisor-readiness.test.mjs
$env:PYTHONPATH='packages/pioneer-agent/src;packages/sanmou-common/src;packages/qa-agent/src'
.venv/Scripts/python.exe -m unittest discover -s packages/pioneer-agent/tests/unit -p 'test_advisor_api*.py' -v
```

From `apps/sanmou-advisor-desktop`, run serially:

```powershell
npm run typecheck
npm test
npm run dist:win
npm run test:install:win  # run 1, log sanmou-e-cr02-install-1.log
npm run test:install:win  # run 2, log sanmou-e-cr02-install-2.log
Get-AuthenticodeSignature release/Sanmou-Advisor-0.1.0-unsigned-x64.exe
```

| CR02 check | Result | Exit |
|---|---|---|
| Focused readiness tests | 7 pass, 0 fail/skip | 0 |
| Full desktop test command | 9 Node + 14 real Electron pass, 0 fail/skip | 0 |
| Complete Advisor API tests | 10 pass, 0 fail/skip | 0 |
| Typecheck and build/unsigned packaging | pass | 0 |
| Actual install 1: startup / mock PNG / uninstall | pass; 16 awaited readiness attempts | 0 |
| Actual install 2: startup / mock PNG / uninstall | pass; 18 awaited readiness attempts | 0 |
| Installer signature | `NotSigned` | 0 |

Runtime and dependencies are the same versions listed earlier; no dependency or
lockfile changed. Current commands/log hashes, actual installer SHA-256 and
tested Git blobs are in `E-test-evidence.json.cr02`. The previous full Windows
and WSL baseline comparison is retained, not rerun or reclassified as passing in
this test-only revision. The 12 dependency advisories, unsigned/non-clean-machine
status, missing update/rollback and provider/live evidence boundaries remain.

## CR03 revision — browser-safe test ports on the CI runtime

Revision parent: `5afaec4bb46c91c4c1fd153e0c79670276c1d197`, same feature branch
and worktree. CR03 itself changes only E test infrastructure, its npm test entry
and documentation. The final follow-up also contains the CR06 API fix below;
other production source, F's CI policy and the dependency lockfile are unchanged.
Tested source SHA-256 / Git blob IDs and the new installer hash are
in `E-test-evidence.json.cr03`; the containing commit supplies full tree identity.

### Retained independent failure

On E `5afaec4` / combined `682f994`, CR's Node 20.20.2 + Python 3.12.14 run had
9 Node passes and 13 Electron passes / 1 failure. `listen(0)` selected port 5061
in the R23-good test's setup: history never appeared and the API stayed checking.
The R23 assertion itself was never reached. CR's native `http.get` received 200
on 5061, but real Electron fetch failed with `net::ERR_UNSAFE_PORT`.

The [Fetch port-blocking table](https://fetch.spec.whatwg.org/#port-blocking)
includes 5061; the table inspected on 2026-09-08 has no ports in 49152–65535.
An OS-allocated ephemeral port therefore did not establish browser usability.
This is separate from R23 evidence semantics and CR02's async readiness defect.

Original evidence is retained by filename/hash and summarized in the JSON:

- `C:/Users/Lan/AppData/Local/Temp/sanmou-cr-node20-test.log`.
- `C:/Users/Lan/AppData/Local/Temp/sanmou-cr-browser-port-proof.log`.
- CR worktree `.codex-autonomy/adversarial-review-20260908/evidence/CR03-port-5061-context.md`.

### Allocation, reservation and regressions

`tests/safe-ports.mjs` is shared by Electron mocks, readiness HTTP fixtures and
the installer. Each candidate must be an integer in 49152–65535 before `listen`
is called. It binds only `127.0.0.1`, tries at most 32 candidates by default
(configuration hard-capped at 128), retries only `EADDRINUSE`/`EACCES`, and
immediately propagates unrelated bind errors. Injected candidate prefixes are
subject to the same range check. Exhaustion fails without an OS-port-zero fallback.

HTTP tests retain their bound server. Installation uses a private TCP reservation
held through the installer; its idempotent release runs immediately before
Electron launches Python, and again during final cleanup. The existing awaited
HTTP/profile-identity gate remains unchanged. Readiness timeouts were not
lengthened, and Chromium port security was not disabled.
Allocation itself is inside the installation cleanup scope, so exhausted
candidates also trigger cleanup of the already-created temporary directory.

Six new pure Node tests cover:

1. Forced 5061 / 0 / 10080 / 65536 never reach the actual bind call.
2. An occupied reservation forces retry while its owner stays bound.
3. Three forced collisions exhaust exactly three attempts, leaving no extra
   error/listening handlers and no listener.
4. Unsafe-only exhaustion makes zero bind calls and never falls back to port 0.
5. Reservation remains exclusive until explicit release; release is idempotent
   and the same port can then be rebound.
6. Permission collisions retry; an unrelated interface error fails immediately.

A new real Electron case injects 5061 and a held safe port, fetches successfully
from the resulting high-port listener, and separately confirms a browser fetch
to 5061 still emits `net::ERR_UNSAFE_PORT`. All original R23 assertions stay intact.

The initial system-Node 24 pure allocation test run was 5/6: a new test incorrectly
expected zero HTTP `listening` handlers, but Node already installs
`setupConnectionsTracking`. The assertion now compares exact pre/post listener
counts, preserving the framework handler while proving no leak. That initial
failure log is retained. The first full Node 20 pipeline after the fix passed;
the suite was not retried unchanged to obtain green.

### Exact runtime, commands and results

CR explicitly confirmed its Electron/install processes and uninstall entry count
were zero and released the window before E's actual runs. Each E installation
still independently checked for an existing Advisor installation and constrained
cleanup to its own absolute temporary directory and launched processes.

- Node executable (read-only reuse):
  `C:/Users/Lan/AppData/Local/npm-cache/_npx/ebaba8b9e55fd0a9/node_modules/node/bin/node.exe`,
  verified `v20.20.2`.
- Base Python (read-only reuse):
  `C:/Users/Lan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`,
  verified `3.12.14`. E created its own `.venv`; CR's editable environment was not used.
- E's earlier Python 3.14 venv was safely moved inside this worktree to
  `build/cr03/venv-py314` after checking ownership, absolute paths and no running
  users of it. No global Python/auth settings changed.
- The Python dependency versions remain FastAPI 0.141.1, Starlette 1.6.0,
  Pydantic 2.13.5, Pillow 12.3.0, MCP 1.29.1, httpx 0.28.1, uvicorn 0.52.4 and
  python-multipart 0.0.32. Electron remains 29.4.6 and Playwright 1.58.2.

Environment preparation from the repository root, after archiving the old venv:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& C:/Users/Lan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -B -m venv --without-pip .venv
& C:/Users/Lan/AppData/Local/Programs/Python/Python314/python.exe -m pip --python .venv/Scripts/python.exe install -e packages/sanmou-common -e packages/pioneer-agent httpx
$env:PYTHONPATH='packages/pioneer-agent/src;packages/sanmou-common/src;packages/qa-agent/src'
.venv/Scripts/python.exe -B -m unittest discover -s packages/pioneer-agent/tests/unit -p 'test_advisor_api*.py' -v
```

Exact Node 20 invocation (do not substitute `npm.cmd`, which can pick Node 24):

```powershell
$node20='C:/Users/Lan/AppData/Local/npm-cache/_npx/ebaba8b9e55fd0a9/node_modules/node/bin/node.exe'
$npmCli='D:/nodejs/node_modules/npm/bin/npm-cli.js'
$env:PATH=(Split-Path -Parent $node20)+';'+$env:PATH
$env:PYTHONDONTWRITEBYTECODE='1'
# From repository root:
& $node20 --test apps/sanmou-advisor-desktop/tests/safe-ports.test.mjs apps/sanmou-advisor-desktop/tests/advisor-readiness.test.mjs
# Then from apps/sanmou-advisor-desktop, serially:
& $node20 $npmCli ci
& $node20 $npmCli run typecheck
& $node20 $npmCli run build
& $node20 $npmCli test
& $node20 $npmCli run dist:win
& $node20 $npmCli run test:install:win # planned run 1
& $node20 $npmCli run test:install:win # planned run 2
```

| CR03 check | Result | Exit |
|---|---|---|
| Node 20 focused port + readiness tests | 13 pass, 0 fail/skip | 0 |
| Node 20 npm ci / typecheck / build | pass, with engine warnings below | 0 |
| Node 20 full desktop command | 15 Node + 15 real Electron pass, 0 fail/skip | 0 |
| Independent Python 3.12 complete API tests | 10 pass, 0 fail/skip | 0 |
| Node 20 unsigned NSIS build | pass | 0 |
| Node 20 / Python 3.12 final install 1: startup / mock PNG / uninstall | pass; port 50678, 12 readiness attempts | 0 |
| Node 20 / Python 3.12 final install 2: startup / mock PNG / uninstall | pass; port 56767, 12 readiness attempts | 0 |

The earlier two planned installs also passed (57134/52587). Their logs are
retained with `-pre-cleanup` suffixes; the table above uses two reruns of the
exact final script after placing allocation within the cleanup scope. No
production/build input changed in that final test-script adjustment.

The npm install reported `EBADENGINE` for existing `@electron/rebuild@4.2.0` and
`node-abi@4.35.0` (both declare Node >=22.12.0). No engine override or CI policy
change was made. The concrete current build with no native Node addon to rebuild
passed on Node 20; this does not certify those packages' general Node 20 support.
The warning is retained for CR alongside the existing 12 dependency advisories.

Only synthetic input and local test services were used. No game input, model
call, private screenshot, external oracle or publication occurred. Historical
Windows 3.14/WSL results and the unresolved earlier Python-exited case remain;
CR06 adds a new Windows 3.12 full-package comparison below. Unsigned,
clean-machine, update/rollback and production gates remain.

## CR06 revision — preserve Pillow pixel rejection and clean the upload

CR independently supplied a 69-byte synthetic PNG advertising 20000×20000 in
IHDR, with tiny IDAT data. The default Pillow guard raises
`Image.DecompressionBombError` while opening the header, before pixel decoding.
The old validation handler did not catch it: Windows HTTP returned 500 and left
one 69-byte upload, with no report. Review proof is
`sanmou-cr-pixel-guard-cleanup-red.log` and
`probes/upload_pixel_guard_cleanup.py` in the review evidence directory.

The new regression was first run against the still-unmodified API here and
reproduced `(HTTP 500, one upload, 69 remaining bytes, no report)` with exit 1.
The same test, without changed expectations, passes after the fix. Both red logs
and the actual test/API Git blob identities are retained in the evidence JSON.

The API now owns an explicit binary reader around `Image.open`, so it closes
even when Pillow rejects the header before an image context is entered. After
that closure, `DecompressionBombError` removes the upload and returns 413 with
an image-pixel-limit explanation. Pillow's `MAX_IMAGE_PIXELS=89478485` remains
unchanged; no warning/limit override was introduced. The original >10 MiB 413,
invalid-checksum 400 and interrupted-upload cleanup regressions still pass.

The new test checks the real header guard before HTTP, asserts the limit remains
enabled/unchanged, and installs a fail-fast sentinel on PNG pixel loading to
assert it is never called. It creates only 69 bytes, never a giant bitmap. The
native Windows TestClient uses `raise_server_exceptions=False`, verifies HTTP
413, zero remaining upload files/bytes and no report.

The installer was rebuilt after the API changed. The final installation script
compares the installed `advisor_api.py` SHA-256 with the current source, so an
older artifact cannot satisfy the check. It then sends the same tiny header to
the actual installed API, verifies 413/zero files/no report, and performs the
normal valid 1×1 PNG upload before closing/uninstalling. The installed API hash
was `20a2d22aa36e73fd1668d94b242f8aa12cbf3cd417174b59985ea0c27c31ccc5`
in both final runs.

### Current validation

The Node 20/Python 3.12 environment and invocation rules above were retained.
Exact commands (root unless a working directory is specified):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH='packages/pioneer-agent/src;packages/sanmou-common/src;packages/qa-agent/src'
.venv/Scripts/python.exe -B -m unittest discover -s packages/pioneer-agent/tests/unit -p 'test_advisor_api*.py' -v
# Cwd packages/pioneer-agent; also run from build/e-baseline/packages/pioneer-agent
# using the absolute same .venv/Scripts/python.exe and the same PYTHONPATH:
$env:PYTHONPATH='src;../sanmou-common/src;../qa-agent/src'
../../.venv/Scripts/python.exe -B -m unittest discover -s tests -p 'test_*.py' -v
# Desktop cwd, using $node20 / $npmCli / PATH defined in CR03:
& $node20 $npmCli run dist:win
& $node20 $npmCli run test:install:win # final source-bound run 1
& $node20 $npmCli run test:install:win # final source-bound run 2
& $node20 $npmCli test
```

| CR06/final check | Result | Exit |
|---|---|---|
| Local new header test before API edit | 500 + 1 file / 69 bytes, expected red | 1 |
| Complete Windows Python 3.12 API tests | 11 pass, 0 fail/skip | 0 |
| Final Node 20 desktop command | 15 Node + 15 Electron pass, 0 fail/skip | 0 |
| Rebuilt Node 20 unsigned installer | pass; contains current API bytes | 0 |
| Final installed header rejection / normal upload / uninstall, run 1 | pass; port 63715, 13 readiness probes | 0 |
| Final installed header rejection / normal upload / uninstall, run 2 | pass; port 59920, 12 readiness probes | 0 |
| Windows Python 3.12 full package, d377 baseline | 764 tests, 10 failures, 29 errors, 9 skips | 1 |
| Windows Python 3.12 full package, final E | 769 tests, 10 failures, 29 errors, 9 skips | 1 |

The whole-package result is **not a pass** and equality of counts is not treated
as equality of failures. The primary runs share 38 failure/error names and differ
on two unchanged autonomous-loop tests: the current-only failure was
`test_authorized_low_risk_custom_runner_cannot_forge_post_verification`; the
baseline-only failure was
`test_tick_continues_upgrade_flow_from_entry_to_confirm_then_verifies`.

Those two tests were rerun with their original assertions and fixed ordering
on both trees. An additional temporary diagnostic wrapper only printed each
original `tick` result after it returned; it did not replace stderr, clocks,
assertions, dispatch or verification. Both trees produced
`post-action observation was not captured after dispatch`, and the first test's
pass/fail switched between the trees across these runs. This records existing
timestamp-gate instability, not an API-cleanup failure or a reason to weaken
the gate. All primary/focused/diagnostic failures and names are preserved.
No blanket "no new failures" claim is made from the primary comparison alone.

The exact focused cases were:

```powershell
$cases=@(
 'tests.unit.test_autonomous_loop.AutonomousLoopTests.test_authorized_low_risk_custom_runner_cannot_forge_post_verification',
 'tests.unit.test_autonomous_loop.AutonomousLoopTests.test_tick_continues_upgrade_flow_from_entry_to_confirm_then_verifies'
)
# Run in each tree's packages/pioneer-agent with the same Python/PYTHONPATH:
& C:/Users/Lan/.codex/worktrees/3fd9/sanmou_monorepo/.venv/Scripts/python.exe -B -m unittest @cases -v
```

The explicit interpreter was this worktree's absolute `.venv/Scripts/python.exe`,
not a system `python` chosen by PATH. The diagnostic script and log hashes are
recorded in JSON. No autonomous-loop source, tests or freshness gates were edited.
The prior Windows 3.14 counts remain historical evidence, not comparable by
count alone to this 3.12 run. Existing dependency/engine warnings, unsigned status,
clean-machine/update/rollback limits and live/provider blockers are unchanged.

## CR07 revision — supported CI host runtime

Validation source: `b865808d021ca4fd81c1bb087735187f485b51a2`. E made no changes
to production code, test scripts, desktop dependencies, engines declarations or
the lockfile in this revision. This commit updates only E's report/evidence and
task-local TODO. F owns the workflow change; its inspected commit
`6bff970d8ed6d6eff6153e783b715273847847b7` pins `node-version: '24.14.0'`.
E read that workflow through `git show`; it did not merge or edit F's tree.

The retained lock resolves `@electron/rebuild@4.2.0` and `node-abi@4.35.0`, both
declaring Node `>=22.12.0`. A direct semver check returns false for 20.20.2 and
true for 24.14.0 for both packages. Prior Node 20 runs with EBADENGINE remain
unsupported observations even though this project's no-native-addon build
happened to pass. They are not retroactively promoted to supported execution.
The [official release table](https://nodejs.org/en/about/previous-releases)
lists Node 24 as LTS and Node 20 as EOL when checked on 2026-09-08. The exact
local/CI patch frozen for this check is 24.14.0, not a claim to test the latest
upstream patch.

### Exact environment and commands

- Host Node: `D:/nodejs/node.exe`, verified `v24.14.0`; not the bundled 24.19 runtime.
- npm CLI: `D:/nodejs/node_modules/npm/bin/npm-cli.js`, npm 11.9.0.
- Python: E's existing isolated `.venv`, Python 3.12.14; dependency versions unchanged.
- Production/test/lock source bytes and Git blobs are identical to the preceding
  `b865808d` evidence manifest. The final report commit supplies a new immutable
  report identity, not a new implementation claim.
- CR explicitly confirmed zero owned processes/uninstall entries and released
  the window before E began Electron/install runs. E did not infer release from
  elapsed time. PATH was modified only in each command process.

From `apps/sanmou-advisor-desktop`, with real logs under `%TEMP%`:

```powershell
$node24='D:/nodejs/node.exe'
$npmCli='D:/nodejs/node_modules/npm/bin/npm-cli.js'
$env:PATH='D:\nodejs;'+$env:PATH
$env:PYTHONDONTWRITEBYTECODE='1'
& $node24 $npmCli ci
& $node24 $npmCli run typecheck
& $node24 $npmCli run build
# Additional explicit engine enforcement, followed by the full sequence:
& $node24 $npmCli ci --engine-strict
& $node24 $npmCli run typecheck
& $node24 $npmCli run build
& $node24 $npmCli test
& $node24 $npmCli run dist:win
& $node24 $npmCli run test:install:win # planned run 1
& $node24 $npmCli run test:install:win # planned run 2
```

The extra strict check enforces rather than ignores the declared engines. No
ignore-engines, force, engine declaration override, dependency major migration,
Chromium safety override or readiness-timeout increase was used.

### Results for this runtime

| Check | Result | Exit |
|---|---|---|
| Exact dependency-engine semver checks | 24.14.0 satisfies both; 20.20.2 satisfies neither | 0 |
| Pure Node port/readiness tests | 13 pass, 0 fail/skip | 0 |
| Default npm ci | pass; EBADENGINE count 0 | 0 |
| npm ci --engine-strict | pass; EBADENGINE count 0 | 0 |
| Typecheck / build on 24.14.0 | pass | 0 |
| Full desktop command | 15 Node + 15 real Electron pass, 0 fail/skip | 0 |
| Newly rebuilt unsigned NSIS package | pass | 0 |
| New package install 1 / pixel 413 / valid upload / uninstall | pass; port 58638, 12 readiness probes | 0 |
| New package install 2 / pixel 413 / valid upload / uninstall | pass; port 62917, 12 readiness probes | 0 |
| Final owned Electron / install API / uninstall entries | 0 / 0 / 0 | 0 |

This is a new build made by Node 24.14.0, not reuse of a Node 20 installer.
Installer SHA-256 is
`a4aabfd1b813803948bde9bff4bde4f71b333f736496e14b8977f1dbd3255cc0`;
Authenticode still reports `NotSigned`. Both installed API source hashes match
the frozen source (`20a2d22aa36e73fd1668d94b242f8aa12cbf3cd417174b59985ea0c27c31ccc5`).
Each run preserved the existing-installation check and private temporary path
constraints, verified 69-byte pixel-limit rejection with no residual file/report,
then a normal mock PNG upload, app closure and uninstall.

The 12 npm advisory entries remain. The prior full Python package failures,
timestamp-test instability, Node 20 EBADENGINE logs and earlier unexplained
Python-exited observation are retained unchanged; they are not resolved by
selecting Node 24. Python full-package tests were not rerun for this host-only
validation. These are local matching-runtime results, not a hosted GitHub Actions
or combined-tree approval. Signed clean-machine, update/rollback, live/model and
other production evidence gates remain with unified CR and their owners.
