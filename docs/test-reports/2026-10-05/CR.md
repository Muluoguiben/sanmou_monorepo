# CR verification record — 2026-10-05

Status: **PENDING_DELIVERIES**, not APPROVE and not a completed integration test.

- Cwd: `C:\Users\Lan\.codex\worktrees\6155\sanmou_monorepo`.
- Entry HEAD: `965ef6713b58048c0765654e8061c5cffda6c59d`, clean detached HEAD.
- Created only `codex/harness-cr-20261005`; master was not checked out or changed.
- Read root AGENTS, batch task sheet, harness review, QA review and current todo.
- `git fetch origin master`: exit 0; SSH printed a remote-forward port 1278 warning.
- Fetched manifest: A/B/C IDs and all delivery SHAs null; no valid targets for
  read_thread/wait_threads yet. No historical branch substituted for this batch.
- `python --version`: Python 3.14.3. Dependencies/full test environment not yet verified.
- Default exec helper failed before process creation with helper_unknown_error.
  Explicit scoped elevated read commands succeeded; no tests ran in that failed call.
- An unquoted PowerShell `HEAD^{tree}` command was malformed and failed. This
  is command-shell evidence only, not a source or test failure; use quoted refs.

## Test evidence boundary

| Class | Executed | Claim |
| --- | --- | --- |
| Baseline source inspection | Yes | Review plan only |
| Combined focused / adversarial tests | No | Await immutable deliveries |
| Pioneer / QA / common full suites | No | Await combination |
| Provider / vision / live action | No | Out of scope |

See the review document for the freeze protocol and fault-injection matrix.
The next action is to obtain populated current-batch IDs and immutable deliveries,
verify author source-bound reports, compose the DAG, then execute the matrix.

## Coordination and environment refresh

- Manifest `5e6f575398e5a940b983b2ab30b62eb93f2a5d70` resolves the null-ID blocker.
  A `01a10c00-3644-74b2-814b-b063f3444d42`,
  B `01a10c00-c914-73f0-ac5d-28d952d54ff9`,
  C `01a10c00-ef29-78a0-8894-ac2585839654` (local).
- Fixed A0 `5269a1a5d09bddcf268d180a3f016f323c27cb95` source/docs/tests read;
  author 5/5 is author evidence only, not a reviewer rerun or final delivery.
- Native Python 3.14 dependency probe: exit 1, pydantic missing. The launcher lists
  a Python 3.11 on D: but that executable does not exist (probe exit 1).
- WSL Python 3.12.3: pydantic 2.12.5, PyYAML 6.0.1, mcp 1.29.1,
  anyio 4.13.0 (dependency probe exit 0). No global dependencies installed.
- Verified WSL path: `/mnt/c/Users/Lan/.codex/worktrees/6155/sanmou_monorepo`.
  The first backslash-form wslpath argument failed; forward-slash form succeeded.
- These are environment probes, not test-suite results. Native Windows coverage
  remains unestablished. Final combination and full regressions remain pending.

## C immutable delivery and first independent rerun

C code: `621cf8baf324902b9e77d056b3b03f288f07baf6`.
C report: `bd062f3548026b74798dd8f7178cbb615fe7e9cf`.
Local CR+C merge: `c0af471aaf9230b5c9c0374fe395aff84e3a9212`,
tree `5dcafc922138b29edbf2bd274834a8d209df2837`.
This is not the final A/B/C combination. No source conflict occurred.

Independent focused run: 20/20 pass, no skips, exit 0 on WSL Python 3.12.3.
Command and timing: [c-focused.json](CR-artifacts/c-focused.json).
Raw evidence: [c-focused.log](CR-artifacts/c-focused.log).
The helper [run_checks.py](CR-artifacts/run_checks.py) captures subprocess exit codes
and creates logs exclusively. Author results were not substituted for this rerun.

C's immutable report explicitly documents an automatic-review rejection of its
remote push. CR therefore only merged C locally and has not pushed the inherited
C source/log payload. Local review can proceed; publication remains separate.
