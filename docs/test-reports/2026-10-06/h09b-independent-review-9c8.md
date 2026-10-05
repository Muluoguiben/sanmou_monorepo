# H09b independent re-review: 9c8

## Verdict

**APPROVE_CODE_SCOPED**, with zero remaining blocking findings in the bounded H09b implementation. This is **not** native hosted Windows CLI acceptance or H09b completion. Approval is conditional on combined-tree checks and the exact published final SHA's existing Windows job actually running the new H09b step, reconstructing its original report bytes from that step's raw logs, checking source/native/8-case/read-only/zero-model invariants, and all existing CI jobs passing. Old Windows H06 results, synthetic platform metadata and Linux CLI results are not substitutes.

Reviewed source `9c8db2605d64c08736830585b20c542138d66678`, tree `a7d1114304936416cb86d6d8428ccef68a1be0d8`. Immutable author handoff `1abcaac29697420de6de0663f2bc8e244f456336`, tree `783e74cc753125e07133510641ac6f2794956b2b`, was read as data. No author audit script was executed and no author WIP inspected.

## Re-review and regression evidence

- Original plan commit `a026cd9f9abb72cb65c1992371e0ae0825548622` and first REQUEST_CHANGES commit `5b0b972f6ce86dc02f88fd3328893b82e6687561` remain unchanged.
- The sole P2 is fixed by two zero-length lower-bound changes and two additional unit tests; no runtime, SourceBinding, metadata policy, TaskRunner, suite/fixture or dependency change.
- Independent native Windows Python 3.14 **stdlib checker tests: 20/20 pass**, on a fresh detached LF checkout of the exact source. These are synthetic report/mock orchestration tests, not an actual native evaluator CLI. Raw log: `h09b-cr-9c8/windows-stdlib-20.log`.
- Original frozen independent probes: **20/20 pass**, with only the expected source SHA replaced in memory by `h09b-recheck-9c8.py`. Original file and all assertions are unchanged. Identity/digests: `h09b-cr-9c8/identity-only-replay.json`; results: `h09b-cr-9c8/probe-results.json`. Original f961 red evidence remains in its original directory/commit.
- The empty-report reproduction now emits a 0-byte/0-chunk begin/end frame with the SHA256 of empty bytes, reconstructs exact empty bytes, and still fails semantic validation with `JSONDecodeError`. Raw mock evidence: `h09b-cr-9c8/empty-report-original.log`. Synthetic native/source fields in that file are not actual platform/source evidence.
- Five additional independent empty-frame negatives rejected: negative length, unexpected chunk, wrong digest, missing end and duplicate end. Full 512 KiB timestamp-prefixed roundtrip and earlier corrupted/missing/repeated/reordered/oversize paths remain covered by the original unchanged probes.

## Author handoff audit

Reviewer-owned `h09b-handoff-audit.py` read immutable Git blobs, verified all **8/8** raw evidence byte counts and SHA256 values against the handoff table, checked result lines, exact Linux report source commit/tree, eight cases and totals, and the author's 20/20 replay. Evidence: `h09b-cr-9c8/handoff-audit.json`.

Author's fixed-source Linux results are corroborated by raw logs: Pioneer **1018 = 1016 pass + 2 Windows-only skips**, QA **394 pass**, common **2 pass**, CLI **8 cases / 2 goals / 6 expected safety stops / 8 controls**, no infra/unexpected/safety violations. These runs were executed by the author, not independently rerun by this reviewer; the report's environment is explicitly Linux. Original d610 handoff was also fully read and its seven raw artifact hashes matched, with old red history preserved.

The reviewer audit's initial result-line regex failed on CRLF native log lines. This was an audit-parser error, not a source/product failure. `h09b-cr-9c8/audit-parser-first-failure.log` preserves it; the narrow correction accepts an optional CR before newline without changing raw bytes, digest checks, test counts or pass criteria. The corrected audit passes.

## Scope and remaining boundary

The final implementation scope is still exactly three files: checker, checker unittest and **three added workflow lines**. The existing Windows job inserts H09b after H06 and before Desktop; existing jobs/actions/runner/permissions/dependencies and old gates are unchanged. Additional changed documents/todo are evidence/accounting, not new runtime scope.

The checker actually calls current Python's module CLI subprocess with bounded time and no shell, enforces local physical Windows paths and source/input/artifact checks, checks strict case-level safety and report semantics, and retains bounded original report bytes on valid-size success/failure. Log decode is data-only; an end marker never means gate success. No hostile-loader/TOCTOU sandbox guarantee is added to the existing trusted-local-process threat model.

No push, master merge, CI retry, provider/game/.env access, network or dependency installation by reviewer. No H09a retroactive scope enlargement. This closes the independent code review slice only; the overall existing roadmap is unchanged and no new implementation project is started here.
