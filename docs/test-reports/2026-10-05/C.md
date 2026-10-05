# C — QA Q07/Q-E0 development baseline

Date: 2026-10-05 (Asia/Shanghai). Owner: C. Branch: `codex/harness-c-qa-eval-20261005`.

## Source identity and scope

- Dispatch baseline: `965ef6713b58048c0765654e8061c5cffda6c59d`; business baseline: `12e7ddc73c86665ccad0764c8aa8aec51de39e3a`.
- Code commit: [`621cf8baf324902b9e77d056b3b03f288f07baf6`](https://github.com/Muluoguiben/sanmou_monorepo/commit/621cf8baf324902b9e77d056b3b03f288f07baf6).
- Actual Windows worktree: `C:\Users\Lan\.codex\worktrees\a8b3\sanmou_monorepo`.
- WSL test path: `/mnt/c/Users/Lan/.codex/worktrees/a8b3/sanmou_monorepo` (same checkout, not another project's cwd).
- Only new QA eval code/tests/versioned fixtures, this report and its logs changed. No production retrieval/generation, KB, publishing policy, Pioneer, MCP contract, root todo or manifest changes.
- `execution_authority=none`, `executable=false`; no provider, vision, game, live replay or knowledge publication calls.

Implementation and protocol: [versioned fixture README](../../../packages/qa-agent/tests/fixtures/quality_eval/v1/README.md).

## Frozen corpus and source digests

Algorithm: SHA-256 over UTF-8/LF-normalized text, BOM removed, then sorted relative-path-to-hash JSON. The cases hash is directly over its normalized text. These are portable content hashes, not raw CRLF checkout hashes. Individual file hashes are in [freeze.json](../../../packages/qa-agent/tests/fixtures/quality_eval/v1/freeze.json) and [retrieval result](C-artifacts/retrieval-621cf8b.json).

| Identity | SHA-256 | Count |
| --- | --- | --- |
| Formal KB YAML | `3b4d9ec9183bf7ac22761a659abdae7da16ddc2ef21fe5078f3f48c240287959` | 34 files |
| QA production Python, excluding new eval | `e093738d8fe76f4de40cafce02fab4a6c575a82684ba05470730785152b0ac11` | 150 files |
| Eval Python | `6ee6d07a2f92e7f0ad71ca280c49bdd3755891711c8de9db71ee23f899ff6361` | 3 files |
| Queries and scorer labels | `e3200852adc8a23c4aab550893ad3ff26f751cbf885ad6d478584627db9cb1e4` | 12 queries / 8 synthetic answers |

All labels are developer-authored, with source/review metadata. Each query's expected evidence binds ID, source_ref and answer-lines digest. Synthetic judgments bind answer, evidence and question/history context digests. None are human-approved gold; independent holdout is not established; quality thresholds remain unset.

## Results and denominators

| Layer | Actual result | Meaning / limits |
| --- | --- | --- |
| Lexical retrieval Recall@5 | macro sum 10 / 11 answerable queries = 0.9091 | Development labels only; each query has one expected evidence ID |
| Lexical retrieval MRR | reciprocal-rank sum 10 / 11 = 0.9091 | Ten expected entries rank first; one miss |
| Canonical / alias / natural / season | 4/4, 2/2, 2/2, 1/1 | Per-category answerable query recall |
| Raw follow-up coreference | 0/1 | `再详细说说它` retrieves nothing despite prior 君王殿 label; no history rewrite invoked |
| Raw topic switch | 1/1 | Explicit 补兵 follow-up finds team-recruit; not full conversation quality |
| No-answer retrieval | 1 query, empty evidence | Deliberately unrecorded token; excluded from answerable recall/MRR |
| Citation ID and claim support | 8 synthetic annotated examples | Scorer validation only; not provider answers or measured production semantic quality |
| Provider refusal / full multiturn | unmeasured, no provider observations | Refusal precision/recall scorer tested separately with explicit booleans; no keyword inference |
| Human review / independent holdout | 0 / not established | No quality acceptance threshold claimed |

Correct ID with wrong numeric value/entity yields citation validity 1/1 but support 0/1. Missing citation has citation denominator zero (null validity), and completeness 0/1 even when candidate evidence is correct. Empty evidence invalidates a cited ID. Unknown claims remain unjudged. True-but-off-topic answers now have fact support 1/1 and separate context correctness 0/1. Claim segmentation covers the complete answer; unsupported/unreviewed/unknown claims cannot inflate supported citation completeness.

External adjudication remains a trust boundary: these functions do not infer semantics or authenticate a human reviewer. Incorrect supplied labels still require independent review. The runner never marks the development labels as approved gold.

## Source-bound verification

Environment: WSL2 Ubuntu, Linux `6.6.87.2-microsoft-standard-WSL2`, Python 3.12.3, pydantic 2.12.5, PyYAML 6.0.1, mcp 1.29.1. Native Windows Python 3.14 lacks pydantic and was not used for package tests. Windows Git resolves the app-managed UNC gitdir; WSL Git does not. [code-sha.txt](C-artifacts/code-sha.txt) was captured with native `git rev-parse HEAD` before tests.

From `packages/qa-agent`, with `PYTHONDONTWRITEBYTECODE=1` and `PYTHONPATH=src:../sanmou-common/src`:

```text
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
python3 -B -m unittest tests.test_quality_eval tests.test_review_d_regressions.ChatGroundingRegressionTests -v
python3 -B -m qa_agent.quality_eval.runner --output <new-result-file.json>
```

- Full QA: **343 tests, 343 pass, 0 fail, 0 skip**. [Final source-bound log](C-artifacts/qa-full-bound.log).
- Focused: **20 tests, 20 pass, 0 fail, 0 skip**, including 16 eval tests and four existing grounding/empty-evidence tests. [Log](C-artifacts/focused-bound.log).
- [verification.json](C-artifacts/verification.json) records actual subprocess return codes, exact commands, cwd, dependencies and code SHA. [verify.py](C-artifacts/verify.py) reproduces these tests and refuses to overwrite logs.
- Frozen lexical eval completed without provider/network and emitted [result](C-artifacts/retrieval-621cf8b.json); unit regression also patches socket creation to fail during this runner.
- Source/fixture `git diff --check` passed. Preserved raw test logs contain Rich logger padding/trailing spaces, so the all-artifact whitespace check reports those lines; raw evidence was not rewritten to suppress them. No other package implementation was touched; full Pioneer/common tests are left to combined-tree CR, not claimed here.
- Internal read-only reviewer found one P2 (true-but-off-topic incorrectly labeled unsupported). Fixed before code commit; reviewer independently reran 16 tests on the exact code SHA and closed the finding. This is not the batch's independent combined-tree CR approval.

## Preserved failures and environment repairs

- First focused run: 14 pass ([log](C-artifacts/focused-initial.log)). A context-binding extension then exposed a fixture digest mismatch: 15 tests, 1 error ([failure](C-artifacts/focused-context.log)). Windows CRLF bytes had been hashed instead of the specified normalized text. Fixed the freeze construction, kept the LF-equivalence/path-binding test; 15 tests then passed ([log](C-artifacts/focused-context-fixed.log)). No expected retrieval labels were adjusted after measuring results.
- First full QA run: 341 tests, 339 pass, 2 failures ([log](C-artifacts/qa-full-initial.log)). Both were existing Bilibili workflow shell tests: Windows `core.autocrlf=true` produced a `bash\r` shebang, return 127. [Direct stderr](C-artifacts/shell-crlf-error.log) preserves the diagnosis. For WSL validation only, script bytes were verified equivalent to the original Git blob after CRLF normalization, then restored to that exact LF blob. No source content change was committed; original checkout CRLF restored after tests.
- The initial full run occurred before the final two scorer tests and is not final source-bound evidence. `retrieval-initial.json` is likewise pre-final exploratory output, not the final score.
- Code-bound full run also passed 343 tests ([first code-bound log](C-artifacts/qa-full-621cf8b.log)); its shell wrapper failed to preserve a machine-readable exit variable. The final Python subprocess runner reran to record reliable return codes rather than treating wrapper exit 0 as test success.
- First attempt at the Python runner failed before tests because WSL Git could not resolve the Windows UNC `.git` pointer. Native Git source capture fixed this environment mismatch. Default exec helper also failed before process creation, so narrowly scoped explicit execution was used.

## Remaining boundaries

No provider/live regression, semantic judge calibration, independent holdout, human label review, full multi-turn generation, version-conflict/contradiction quality, CUA eval or native Windows package test pass is claimed. Frozen development retrieval is a reproducible baseline, not a production quality gate. Root todo/manifest and master integration belong to the coordinator. The requested destination is only C's feature branch. Remote push was blocked by automatic approval review: it judged trusted-user authorization for the remote destination and log/environment payload insufficient. No push occurred; coordinator may inspect/cherry-pick the local immutable commits, or obtain explicit approval before remote publication.
