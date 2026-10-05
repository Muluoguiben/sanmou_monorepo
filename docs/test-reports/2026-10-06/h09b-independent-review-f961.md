# H09b independent review: f961

Verdict: **REQUEST_CHANGES** for one P2 evidence-retention defect. No native hosted Windows evaluator acceptance is claimed.

- Frozen review plan commit: `a026cd9f9abb72cb65c1992371e0ae0825548622` (unchanged).
- Reviewed source: `f961c1594018651d584bbe622547a79e5648c5a7`.
- Source tree: `bef7699f43bcb9659b35f02f53834f744fe51d10`.
- Reviewed three changed implementation/test/workflow files and existing evaluator/source contracts; did not inspect author WIP or change author code/assertions.

## P2: retain empty report bytes before rejecting semantics

`scripts/check_windows_task_eval.py:226` requires report length greater than zero before emitting evidence. Decoder line 256 likewise rejects zero length. If a child returns zero but creates an empty `report.json`, the gate fails correctly, but emits only `report_size`, without the required original byte count/SHA/frame. Contract section 8 explicitly requires available report bytes to be retained on success and failure. Empty output is a realistic truncated-write failure, not permission to erase evidence.

Independent reproduction: `mock_exit_zero_empty_report_retention` uses the existing synthetic subprocess fixture, changes only the produced report file to zero bytes, and requires failure plus reconstructable zero-byte evidence. Actual gate exit is 1; decoding the log raises `missing_end`. `empty_report_evidence_roundtrip` separately raises `report_size`. See raw `h09b-cr-f961/empty-report-original.log`. Its synthetic native/commit fields are mock data, not native CLI evidence.

Requested correction: represent zero bytes as a bounded begin/end frame with byte count 0, SHA256 of empty bytes and chunk count 0. Semantic report validation must still fail. Preserve the original failing probes and add failure-retention coverage; reassess a new immutable SHA.

## Verification and evidence classes

1. Native Windows Python 3.14 stdlib checker unittest: **18 pass** on a separate LF checkout at exact source SHA. Raw log: `h09b-cr-f961/windows-stdlib-lf.log`. These tests use synthetic reports/mock orchestration, not the actual evaluator CLI.
2. Independent Windows probes: **18/20 pass**, with the two failures above exposing the same defect. Source/tree/checker digest/interpreter and individual results: `h09b-cr-f961/probe-results.json`. Probe source: `h09b-independent-probes.py`. Positive native physical checkout path and full 512 KiB timestamp-prefixed log roundtrip passed; corrupted/truncated/mixed/duplicate/reordered frames and selected report-type/authority/source/aggregate mutations rejected.
3. The first separate snapshot inherited local `core.autocrlf=true`: **18 run, 3 failures/2 errors**, all orchestration stops at fixture SHA mismatch. The complete red log remains `h09b-cr-f961/windows-stdlib-crlf-original.log`. A new worktree was then created with `git -c core.autocrlf=false worktree add --detach ... f961...`; no original fixtures, expected hashes or assertions were modified. The production workflow already sets `core.autocrlf=false`, so this is retained environment-negative evidence, not an implementation defect.
4. No Linux CLI rerun, actual local Windows evaluator CLI, provider, game, dependency installation, network, push, master merge or CI retry performed by this reviewer. Hosted native acceptance remains blocked until publication and exact final-SHA new-step evidence reconstruction.

## Reproduction

Use existing Windows Python `C:/Users/Lan/AppData/Local/Programs/Python/Python314/python.exe`:

```text
python -m unittest discover -s <fixed-LF-source>/packages/pioneer-agent/tests -p test_windows_task_eval_ci.py -v
python docs/test-reports/2026-10-06/h09b-independent-probes.py <fixed-LF-source> <new-output-directory>
```

The probe refuses a source HEAD other than the reviewed SHA. It imports only the stdlib checker test fixture, uses bounded synthetic data and never executes reconstructed log bytes. Review artifacts are local-only and source-bound; no H09a historical scope enlargement.
