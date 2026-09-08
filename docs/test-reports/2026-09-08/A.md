# A — capture/bridge hardening self-test

Task: `01a07f09-c64c-7852-a533-7db7730a048c` (R01/R02/R06/R07).
Date: 2026-09-08. Initial delivery `4a2e4b8` was pushed by the coordinator after
direct user destination approval. The original push-refusal history is retained
below. Current CR path-conversion follow-up and its new tested identity/results
are in the final section. Native Windows package portability and live
authentication integration remain blocked.

## Worktree and tested tree

- Worktree: `C:/Users/Lan/.codex/worktrees/ecc7/sanmou_monorepo`.
- WSL view: `/mnt/c/Users/Lan/.codex/worktrees/ecc7/sanmou_monorepo`.
- Branch: `feat/a-capture-bridge-hardening-20260908`.
- Start: `d377ef8bbaa69e6b25928255eac0cb62714e82f8`, clean detached HEAD;
  baseline ancestry check returned 0 before this branch was created.
- Frozen charter/report read from coordinator documents at `dd76d601`;
  that documentation commit was not merged into this feature.
- Initial delivery's tested implementation Git tree: `998cac7a0e5eed674900f62f5f60ef0c19eaebfa`.
  Obtained with `git write-tree` after staging the 14 implementation, test and
  operating-document files. This report and the task-local TODO were added
  afterwards; no implementation or test changes followed those final tests.
  The final commit SHA is supplied in the delivery message, not invented here.
- No other worktree, master branch, shared `.env`, credential file or installed
  controller was modified. Only the feature branch is to be pushed.

## Changes and regression evidence

| Finding | Fix | Reproducible negative/positive evidence |
|---|---|---|
| R01 | Replace legacy PS/BAT controller and installer with non-executable tombstones; remove installation/control recommendations from repo skill | `RetiredControllerTests`: scan for absence of task registration, elevation, native input and process launch; on Windows execute eight old entry actions and BAT, each exits 1 with disabled marker and never writes requested status path. Existing external installed copies are untouched. |
| R02 | Server binds 127.0.0.1, requires explicit environment authentication, and has only read-only network dispatch. Proxy also rejects input. No control opt-in exists | Real ephemeral loopback socket/framing tests submit click/move/drag/key/restore/foreground/start-game and confirm rejection before any window lookup/input. Wrong/missing auth and old protocol fail before observation. Even a fully guarded click after valid capture is rejected. Missing server auth does not create a listening socket. |
| R06 | `CaptureBridgeClient` separates capture from legacy control client; adapters expose control lazily. Capture/discovery never restore or focus; adapter uses same-frame geometry | Fresh subprocess imports production game MCP and constructs default capture adapter without any control/legacy bridge/executor module in the import graph. Fake minimized WGC/DXGI and discovery fail with zero SendMessage/ShowWindow/SetForegroundWindow/input calls. Windows import reaches the existing POSIX fixture safety refusal; WSL fully imports MCP successfully. |
| R07 | Protocol v2 binds request/response IDs and aware server acquisition-start time. Client accepts time only within request-send/response-receive interval. Framing/deadlines are bounded; any failure closes socket/proxy and clears cached frame | Fake socket timeout, partial header, partial body, oversized frame, old ID and malformed response close stream; attempted next request cannot receive old bytes. Client rejects absent/naive/old/future capture times, wrong hash/length/geometry and obsolete protocol and invalidates state. Adapter preserves server time. Real Windows client + proxy subprocess + loopback fake server returns a synthetic PNG, pings and tears down successfully. |

New tests live in `packages/pioneer-agent/tests/unit/test_capture_bridge_security.py`.
Existing bridge/client/capture boundary tests retain pixel, geometry, semantic
ROI and offline atomic guard assertions. Positive protocol stubs were extended
with request/time metadata. The old network-input success assertion was replaced
with explicit refusal while preserving its screenshot/backend binding check;
offline low-risk guard tests remain. No test, schema or safety gate was deleted
or relaxed to obtain green results.

Owned implementation: adapters `__init__.py`, `capture.py`,
`capture_bridge_client.py` (new), `bridge_client.py`, `bridge_proxy.py`,
`win_bridge_server.py`; retired repo-local controller PS/BAT and skill;
`docs/bridge-architecture.md`; four affected/new unit-test files.

## Environments and setup

Windows: Windows 11 build 26200, CPython 3.14.3, task-local `.venv-a`.
WSL: Ubuntu, Linux 6.6.87.2-microsoft-standard-WSL2, glibc 2.39, Python 3.12.3,
task-local `/tmp/sanmou-a-01a07f09-venv`.
Final environments have `include-system-site-packages=false`.

Both final environments: pydantic 2.13.5, Pillow 12.3.0, PyYAML 6.0.3,
mcp 1.29.1, FastAPI 0.141.1, Starlette 1.6.0, python-multipart 0.0.32,
google-genai 1.75.0, cryptography 46.0.7, httpx 0.28.1.
Both dependency checks returned 0, `No broken requirements found`.

Setup from worktree root (Windows PowerShell):

```powershell
python -m venv .venv-a
./.venv-a/Scripts/python.exe -m pip install -e packages/sanmou-common -e packages/pioneer-agent -e packages/qa-agent httpx
./.venv-a/Scripts/python.exe -m pip check
wsl -d Ubuntu -- python3 -m venv --without-pip /tmp/sanmou-a-01a07f09-venv
wsl -d Ubuntu -- python3 -m pip --python /tmp/sanmou-a-01a07f09-venv/bin/python install --proxy http://127.0.0.1:7897 --retries 0 --timeout 20 -e /mnt/c/Users/Lan/.codex/worktrees/ecc7/sanmou_monorepo/packages/sanmou-common -e /mnt/c/Users/Lan/.codex/worktrees/ecc7/sanmou_monorepo/packages/pioneer-agent -e /mnt/c/Users/Lan/.codex/worktrees/ecc7/sanmou_monorepo/packages/qa-agent httpx
wsl -d Ubuntu -- python3 -m pip --python /tmp/sanmou-a-01a07f09-venv/bin/python check
```

WSL ensurepip was absent; direct PyPI access timed out. No global package changes
were made. A temporary system-site read-only fallback was used for diagnosis,
then disabled and replaced with the fully isolated pyproject installations above.
Normal exec/apply_patch failed during Windows sandbox helper setup. Scoped
reviewed exec and the native Codex apply-patch entry performed local work; no
security setting was disabled. A failed WSL quoting attempt created one empty
file, `=2.6,`, which was inspected and removed before staging.

## Final commands and results

Run focused tests with these module names:

```text
tests.unit.test_bridge_client tests.unit.test_win_bridge_server_guard tests.unit.test_capture_adapters tests.unit.test_win_capture_boundary tests.unit.test_capture_bridge_security
```

Windows commands, cwd `packages/pioneer-agent`:

```powershell
$env:PYTHONPATH='src;../sanmou-common/src'
../../.venv-a/Scripts/python.exe -X utf8 -m unittest tests.unit.test_bridge_client tests.unit.test_win_bridge_server_guard tests.unit.test_capture_adapters tests.unit.test_win_capture_boundary tests.unit.test_capture_bridge_security -v
../../.venv-a/Scripts/python.exe -X utf8 -m unittest discover -s tests -p 'test_*.py' -v
```

WSL commands, same worktree's `packages/pioneer-agent` directory:

```bash
PYTHONPATH=src:../sanmou-common/src /tmp/sanmou-a-01a07f09-venv/bin/python -B -m unittest tests.unit.test_bridge_client tests.unit.test_win_bridge_server_guard tests.unit.test_capture_adapters tests.unit.test_win_capture_boundary tests.unit.test_capture_bridge_security -v
PYTHONPATH=src:../sanmou-common/src /tmp/sanmou-a-01a07f09-venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
```

| Final run | Exit | Total | Pass | Failure | Error | Skip |
|---|---:|---:|---:|---:|---:|---:|
| Windows focused | 0 | 47 | 47 | 0 | 0 | 0 |
| WSL focused | 0 | 47 | 45 | 0 | 0 | 2 |
| WSL Pioneer package | 0 | 788 | 786 | 0 | 0 | 2 |
| Windows Pioneer package | 1 | 777 | 740 | 6 | 22 | 9 |

WSL's two skips are explicitly Windows-only: real native proxy launch and
PowerShell/BAT tombstone execution, both passed in the Windows focused run.
FastAPI tests were exercised; none skipped for missing dependencies. The WSL
package run includes actual official SDK game/QA stdio subprocess tests against
synthetic fixtures, not a live game or model.

Native full-suite failures remain outside this slice: deliberate POSIX
dir_fd/O_DIRECTORY/O_NOFOLLOW fixture guards, Windows file/link/inode assumptions
in corpus/holdout tests, a Windows path separator assertion in game-agent CLI,
and runbook lock-file cleanup. They were not suppressed. Missing test-module
imports reduce Windows collection to 777 versus WSL's 788; this is not a full
Windows MCP runtime certificate. Initial native diagnosis had 6 failures,
29 errors and 9 skips before UTF-8/canonical fixture setup; the final result
above supersedes that attempt.

Initial WSL package run had 7 eval errors from checkout CRLF conversion. The two
unchanged static-tool-call fixtures were re-extracted with
`git -c core.autocrlf=false checkout-index --temp -- <exact two paths>` and their
SHA256 checked before replacement: generation
`329c8441c264afef8b38d78e6ba956bdebd0b8fc980acb239bde533d0341229f`, prediction-only
holdout `8cf263c1ae98d73dcbec4ea4428cbb4228bc4b31c7416181e24a7042c970c2b1`.
No fixture content, manifest hash or expectation changed. F owns the durable
LF `.gitattributes` fix; A does not stage those fixtures or F's files.

Native output was redirected to real files, never substituted with StringIO.
Final logs under `C:/Users/Lan/AppData/Local/Temp/`:
`sanmou-a-native-focused-final.log`, `sanmou-a-native-package-final.log`,
`sanmou-a-wsl-focused-final.log`, `sanmou-a-wsl-package-final.log`.

## Compatibility, remaining blockers and evidence limits

- `git push -u origin feat/a-capture-bridge-hardening-20260908` was rejected
  before execution by automatic approval review. Stated reason: sending feature
  source to GitHub was sensitive external transfer and the destination was not
  considered explicitly trusted/authorized. Configured destination is
  `git@github.com:Muluoguiben/sanmou_monorepo.git`. No alternate upload, connector
  or indirect push was attempted. Coordinator/CR received the local commit and
  report location; explicit destination approval is pending. Remote delivery
  must not be claimed until a successful push and ref verification.
- Canonical Game MCP seven tools and QA six tools unchanged; no second catalog.
  `execution_authority=none`, `executable=false`, normal `--execute` and live
  replay restrictions remain intact. Knowledge/privacy approval was untouched.
- Wire protocol v1 and unbound raw PNG peers intentionally fail closed. Server
  and proxy/client must be upgraded together. All network input is disabled,
  including formerly guarded requests. Offline control primitives remain for
  regression compatibility, with no network route.
- The new direct Windows capture chain requires a separately provisioned
  `SANMOU_CAPTURE_TOKEN` in server/client environments. The existing
  `game_agent --windows-bridge` environment allowlist does not forward it.
  C's proposed narrowly scoped forwarding was initially rejected by automatic
  approval review. The coordinator later relayed explicit user approval for
  Game MCP only, under `--windows-bridge`, never QA/CLI/logs/files/network.
  C owns that follow-up; A confirmed protocol/variable compatibility without
  editing C's code. This A-only tree still fails authentication through the
  old game-agent allowlist until C's separately reviewed change is integrated.
  C then reported a second automatic-review refusal: coordinator-relayed
  approval was not accepted as direct user authorization. C remained at
  `edd3c3d57f92eb16b75f011c9a37d10005cf4256` with no forwarding patch;
  the combined authentication integration remains blocked, not implemented.
- General same-user loopback bearer authentication is not a protected broker
  or defense against a compromised same-user process. Existing elevated external
  controller copies/tasks were not examined, stopped, replaced or uninstalled.
- A single ordinary-permission WGC observation window was requested from the
  coordinator after offline safety tests, initially deferred, then permitted
  after the scoped authorization above. Preflight in `.venv-a` returned
  `dxcam=False`, `windows_capture=False`, `win32gui=True`, `win32process=True`,
  `PIL=True` using `importlib.util.find_spec`; command exit 0. The coordinator's
  instruction was to stop immediately on missing permissions/dependencies.
  Accordingly no install, helper, listener, real token, screenshot, elevation,
  retry or game input was attempted. A read-only `Get-Process -Name
  com.bilibili.nslg` check reported `game_running=true`, `process_count=1`.
  Actual WGC access/high-integrity capture remain unverified. This is a concrete
  dependency blocker, not a live test pass. The follow-up changed this report
  and Task A's TODO only; the tested implementation tree remains unchanged.
- All images in new tests are generated synthetic PNGs. No private/real image,
  external oracle, model call, login, account mutation, game input or resource
  consumption occurred. Repository synthetic holdout tests are not independent
  external holdout evidence. Actual WGC/DXGI accuracy, occlusion handling and
  production signing/installation remain separate gates.

## CR follow-up — WSL proxy path conversion (R07/P2)

CR independently found that `_to_windows_path` prefixed every Linux path with
the hardcoded Ubuntu UNC, so a Windows-backed `/mnt/c/...` worktree pointed at
an inaccessible `\\wsl$\Ubuntu\mnt\c\...` path. The original native proxy test
did not cover this WSL path. CR's synthetic blackbox recorded no fake-server
connections even when its synthetic environment was explicitly propagated;
this was a path blocker separate from authentication.

Starting follow-up HEAD: `4a2e4b8d1d58cac2a6a564a4e9a1cf8540eb26c3`, same A
feature/worktree. No other developer branch was merged. New tested implementation
tree: `03b2013d1820819e7be2539763429e426a85a6ed`, recorded with `git write-tree`
after staging only the path implementation, new path tests and architecture
paragraph, before this report/TODO update. Implementation/tests were unchanged
after final verification. Final immutable commit SHA is in the delivery message.

The regression was written before the fix. This command exited 1 and showed
the incorrect Ubuntu UNC versus the expected `C:\Users\Synthetic User\...`:

```powershell
# Worktree root; current focused import paths.
$env:PYTHONPATH='packages/pioneer-agent/src;packages/sanmou-common/src;packages/pioneer-agent'
./.venv-a/Scripts/python.exe -X utf8 -m unittest tests.unit.test_capture_bridge_paths.CaptureBridgePathTests.test_windows_backed_worktree_uses_drive_path -v
```

Fix: use `subprocess.run(["wslpath", "-w", "-a", str(path)], check=True,
capture_output=True, text=True, encoding="utf-8", timeout=5)`. Reject empty,
relative, drive-relative, multiline or NUL-containing results. Converter errors
raise a clear path-conversion failure before proxy creation, invalidating any
cached frame. Native Windows paths pass through unchanged. Remove the caller's
hardcoded `/mnt/c` working directory as well. No shell execution, credential
forwarding, control capability or protocol change was added.

Eight new tests cover Windows-backed paths with spaces, a non-Ubuntu distro UNC,
custom mount layout, native Windows passthrough, bounded argv-only invocation
with metacharacters, invalid outputs, missing/failing/timed-out converter, and
no proxy launch/cached frame after conversion failure.

Final follow-up commands (same isolated dependencies as above):

```powershell
# Worktree root: eight path tests, exit 0, 8/8 pass.
./.venv-a/Scripts/python.exe -X utf8 -m unittest tests.unit.test_capture_bridge_paths -v
# packages/pioneer-agent: Windows focused, exit 0, 55/55 pass, no skips.
$env:PYTHONPATH='src;../sanmou-common/src'
../../.venv-a/Scripts/python.exe -X utf8 -m unittest tests.unit.test_bridge_client tests.unit.test_win_bridge_server_guard tests.unit.test_capture_adapters tests.unit.test_win_capture_boundary tests.unit.test_capture_bridge_security tests.unit.test_capture_bridge_paths -v
# Worktree root: WSL package, exit 0, 796 total = 794 pass, 2 Windows-only skips.
wsl -d Ubuntu --cd /mnt/c/Users/Lan/.codex/worktrees/ecc7/sanmou_monorepo/packages/pioneer-agent -- env PYTHONPATH=src:../sanmou-common/src /tmp/sanmou-a-01a07f09-venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
```

Logs: `C:/Users/Lan/AppData/Local/Temp/sanmou-a-pathfix-native-focused.log`
and `C:/Users/Lan/AppData/Local/Temp/sanmou-a-pathfix-wsl-package.log`.
The two WSL skips remain the Windows-native proxy/tombstone tests, both passed
in the 55-test Windows focused run. The native Windows full-suite result earlier
in this report is historical; it was not rerun for this path-only follow-up.

Actual path-only interoperability probe, exit 0:

```powershell
wsl -d Ubuntu --cd /mnt/c/Users/Lan/.codex/worktrees/ecc7/sanmou_monorepo/packages/pioneer-agent -- env PYTHONPATH=src:../sanmou-common/src /tmp/sanmou-a-01a07f09-venv/bin/python -B -c 'import json,subprocess,tempfile; from pathlib import Path; from pioneer_agent.adapters.capture_bridge_client import _to_windows_path,_PROXY_SCRIPT; directory=tempfile.TemporaryDirectory(prefix="sanmou-a-pathfix-"); linux_file=Path(directory.name)/"synthetic proxy.py"; linux_file.write_text("synthetic path evidence",encoding="utf-8"); converted=[_to_windows_path(_PROXY_SCRIPT),_to_windows_path(linux_file)]; result=subprocess.run(["python.exe","-c","import json,os,sys; print(json.dumps([os.path.isfile(p) for p in sys.argv[1:]]))",*converted],capture_output=True,text=True,timeout=15,check=True); exists=json.loads(result.stdout); print(json.dumps({"windows_worktree_path":converted[0],"linux_fixture_path":converted[1],"windows_is_file":exists,"proxy_started":False,"credential_forwarding":False})); directory.cleanup(); assert exists==[True,True], exists'
```

Windows `isfile` returned `[true, true]`: the checked-in proxy mapped to its
actual `C:\Users\Lan\.codex\worktrees\ecc7\...` path; the synthetic Linux file
mapped to `\\wsl.localhost\Ubuntu\tmp\sanmou-a-pathfix-...\synthetic proxy.py`.
The temporary directory was cleaned. The non-Ubuntu/custom-mount cases are
synthetic unit tests, not additional installed-distro execution.

This probe started only a Windows Python file-existence check. It did not start
the proxy or capture server, send/forward any token, capture images or touch the
game. The automatic WSL Game MCP-to-Windows-proxy token propagation gap remains
open for separately authorized integration; neither these tests nor C's upstream
environment tests establish an end-to-end authenticated WSL capture. No reviewed
KB, schema, fixture hash, external oracle or execution gate changed.
