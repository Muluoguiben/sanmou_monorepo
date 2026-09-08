# E — Desktop / Advisor API / Windows packaging

Task: `01a07f0b-6d25-75c3-bcb1-acd4ca26cd1d`, 2026-09-08.

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
| Actual temporary install/start/mock upload/uninstall | pass | 0 |
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
