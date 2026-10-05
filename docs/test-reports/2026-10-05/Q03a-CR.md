# Q03a independent CR verification

Date: 2026-10-05. Reviewer-owned evidence. **REQUEST_CHANGES**; see [findings](../../reviews/2026-10-05-Q03a-adversarial-review.md). No merge/push authorization or action was used.

## Exact source

- Reviewed code: `3f81519d34063d438af918a3750bcc38a535b6b7`.
- Reviewed tree: `d165dda6ff9ba8c2fd39a604406b5cfee84449c5`.
- Comparison baseline: `f879915ab43aa9148496a17f5277725c8c913403`.
- Reviewer worktree: `C:\Users\Lan\.codex\worktrees\qa-q03a-review-20261005\sanmou_monorepo`.
- WSL path: `/mnt/c/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo`.
- Local report branch: `codex/qa-q03a-cr-20261005`. Report-only commits are successors, not claims that a later report SHA was already tested.

## Reproducible commands and isolation

[verify.py](Q03a-CR-artifacts/verify.py) captures exact command arrays, working directories, child return codes, elapsed time, code/tree, and raw-log SHA256 in a same-name JSON for every run. It checks the frozen source before running and uses exclusive output creation. The ordinary steps are:

```text
python3 -B docs/test-reports/2026-10-05/Q03a-CR-artifacts/verify.py focused
python3 -B docs/test-reports/2026-10-05/Q03a-CR-artifacts/verify.py eval
python3 -B docs/test-reports/2026-10-05/Q03a-CR-artifacts/verify.py full
python3 -B docs/test-reports/2026-10-05/Q03a-CR-artifacts/verify.py cross
python3 -B docs/test-reports/2026-10-05/Q03a-CR-artifacts/verify.py extra
python3 -B docs/test-reports/2026-10-05/Q03a-CR-artifacts/verify.py full-final
python3 -B docs/test-reports/2026-10-05/Q03a-CR-artifacts/verify.py full-verified
python3 -B docs/test-reports/2026-10-05/Q03a-CR-artifacts/verify.py provenance
python3 -B docs/test-reports/2026-10-05/Q03a-CR-artifacts/verify.py integrity
python3 -B docs/test-reports/2026-10-05/Q03a-CR-artifacts/verify.py integrity-final
```

Run in this isolated checkout; the runner intentionally pins its source SHA and worktree. Existing artifacts must not be overwritten. The first two full runs preserve the earlier launcher shape and failures; the final launcher includes the QA package root for `tests.*` imports.

Environment is WSL Ubuntu, Python 3.12.3, with existing `/tmp/sanmou-cr-20261005-6155-deps` reused read-only for API dependencies. Child environments retain only PATH/HOME/locale/temp plus explicit PYTHONPATH and disabled bytecode writes, not user model credentials. [guarded_tests.py](Q03a-CR-artifacts/guarded_tests.py) blocks credential `.env` file opens and IPv4/IPv6 connection/DNS attempts in the unittest process; Unix-domain sockets remain allowed for local async/MCP mechanics. Spawned MCP stdio servers use their ordinary limited test environment. No model client configuration was constructed: actual ChatAgent checks used explicit fakes. No network request, provider, formal KB publication, game or private screenshot operation occurred. Standard offline ingestion/publish tests exercise only temporary fixture knowledge roots.

## Results

| Check | Result | Child exit | Evidence |
| --- | --- | --- | --- |
| Reviewer synthetic suite | 15 methods: 12 pass, 3 failing methods / 5 failed assertions | 1 | [record](Q03a-CR-artifacts/independent-initial.json), [raw](Q03a-CR-artifacts/independent-initial.log) |
| Author focused suite, independently rerun | 40 tests, OK | 0 | [record](Q03a-CR-artifacts/author-focused-recheck.json), [raw](Q03a-CR-artifacts/author-focused-recheck.log) |
| Extra applicability/source-label probes | 2 methods: 1 pass, 1 failure | 1 | [record](Q03a-CR-artifacts/extra-boundaries.json), [raw](Q03a-CR-artifacts/extra-boundaries.log) |
| Mixed-import execution identity | Reproduced A execution / B identity; reviewer fails deliberately after accepted eval | 1 | [record](Q03a-CR-artifacts/mixed-import-roots.json), [raw](Q03a-CR-artifacts/mixed-import-roots.log) |
| QA full, original checkout/initial launcher | 352 total; 2 CRLF failures + 1 reviewer import-path error | 1 | [record](Q03a-CR-artifacts/qa-full-original-format.json), [raw](Q03a-CR-artifacts/qa-full-original-format.log) |
| QA full, canonical LF/initial launcher | 352 total; only reviewer import-path error remains | 1 | [record](Q03a-CR-artifacts/qa-full-canonical-lf.json), [raw](Q03a-CR-artifacts/qa-full-canonical-lf.log) |
| QA full, canonical LF/import-path corrected launcher | 363 total; 9 failures / 11 errors caused by reviewer os.open wrapper changing capability identity | 1 | [record](Q03a-CR-artifacts/qa-full-final-canonical-lf.json), [raw](Q03a-CR-artifacts/qa-full-final-canonical-lf.log) |
| QA full, canonical LF/audit-hook launcher | 363 tests, OK, no skips; 87.317 s process time | 0 | [record](Q03a-CR-artifacts/qa-full-verified-canonical-lf.json), [raw](Q03a-CR-artifacts/qa-full-verified-canonical-lf.log) |
| Advisor API affected cross-package suite | 6 tests, OK | 0 | [record](Q03a-CR-artifacts/cross-advisor-api.json), [raw](Q03a-CR-artifacts/cross-advisor-api.log) |
| Frozen v2 eval | Twelve retrieval queries, six fake-client assessment rows | 0 | [record](Q03a-CR-artifacts/v2-eval.json), [result](Q03a-CR-artifacts/v2-result.json) |
| v1/default against new production | Expected source-drift refusal; no result created | 1 | [record](Q03a-CR-artifacts/v1-expected-drift.json), [raw](Q03a-CR-artifacts/v1-expected-drift.log) |

The negative evaluation-schema fixtures replace only synthetic read results and recompute the synthetic cases hash to isolate schema acceptance from hash drift. They do not edit the frozen files. The mixed-root probe changes only a disposable temporary A copy, imports the actual B runner normally via importlib, and patches no runner globals. It reports Recall 0/11 under the unchanged B manifest, establishing a real identity mismatch. Applicability probes use independent HeroStaticProfile records, not the author's helper functions.

## Source provenance and protected history

[source-provenance.json](Q03a-CR-artifacts/source-provenance.json) independently resolves the actual v2 production commit `23149c06a970da6876cd94403970934f164ed794`, reads its 185 KB/production blobs through local Git, and checks their specified UTF-8/BOM/LF-normalized SHA256. Zero mismatches. Original v1/v2 query objects, top-k and scorer cases compare equal. This is local reviewer evidence, not a runtime source-authentication feature or remote signature.

The runner still accepts a nonexistent forty-zero commit label, so `baseline_commit` alone is not proof of authenticity. The real frozen commit was verified separately; this review does not label the current real artifact fabricated.

Protected v1 and original C/CR/integration reports/artifacts remain empty-diff against `f879915`. Production package and script changes against the reviewed code are also empty after formatting restoration. Final [integrity-final.json](Q03a-CR-artifacts/integrity-final.json) records those checks and all artifact hashes. The earlier integrity snapshot is preserved; two reviewer Python files subsequently lost only an extra blank line at EOF for the non-log whitespace check. Raw logs and tested production bytes were not rewritten.

## Preserved environment failures and repair

The first full run encountered two existing Bilibili shell-test failures (`127` rather than `0`/`2`) plus a reviewer launcher error: the launcher prepended `QA/src` and `QA/tests` but omitted the QA package root, so `from tests.test_advisor_terminal_source_preflight_cli` failed. The subsequent LF-only run removed the two shell failures but retained this reviewer error. After adding the QA root, a second reviewer error became observable: the credential guard replaced `os.open`, making `os.open in os.supports_dir_fd` false and triggering the pre-existing fail-closed `unsupported_platform` gate. The resulting 363-test run had 9 failure assertions and 11 errors. These are not production findings. The reviewer replaced only its own open wrappers with a Python audit hook, preserving builtin capability identity, and performed another fresh complete run. All raw failures are retained; no production behavior or test expectation was changed.

Before every temporary formatting repair, the script's CRLF-normalized bytes were verified equal to `git show 3f81519:scripts/bilibili_video_knowledge_workflow.sh`; Git blob was `44863bc50e518673e6cc0a8705ff6c51a5ca42e8`. Original checkout SHA256 was `a34602895e39c1cf913c5005a22dfbd4f0d0266b253cbc3b7cc0b1a4f95cf9e5`; canonical LF SHA256 was `0ca3961747bf42c9fc7ad67315c97d93d22c25deb29bddca430982d64a3002fd`. Original bytes are restored in `finally` and rechecked. Expected digests, tests and business source were never relaxed or modified. See [format verification](Q03a-CR-artifacts/format-verification-verified.json).

## Limits

Independent red probes are retained and prevent approval despite ordinary suite passes. No provider semantic quality, authenticated human gold, independent holdout, generalized condition reasoning, skill/faction field checking, native Windows full-suite success, production readiness, or live-game capability is claimed. Root todo/autonomy state belongs to the coordinator; this reviewer did not edit it. All artifacts remain local; no push or merge was attempted.
