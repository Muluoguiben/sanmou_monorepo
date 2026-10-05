# Q02a repair — independent source-bound verification

Date: 2026-10-06. **APPROVE for the exact bounded repair; Q02a-CR01/02 closed.** [Review disposition](../../reviews/2026-10-06-Q02a-adversarial-recheck.md).

## Source identities, not checkout labels

- Code/eval/tests: `40f46d3ea4525639877ad37a8da4ab6e334523e6`; tree `1351c2432adb0a638997ab9faff7bb22725fba4f`.
- Production commit: `90e51683343e7971ec43ca2afcf731fcd66faf4e`.
- Original fixed probes: `eb895ae4e149a38d65789c19c7e4aebdee0c3c1a`, preserved alongside its original REQUEST_CHANGES and raw red output.
- Actual execution root: `/tmp/q02a-independent-6jt1kbqg`, complete Git archive of the code commit, excluding `.env.example`. All 1,455 original files match Git blob bytes. [Snapshot](Q02a-CR-recheck-artifacts/snapshot.json).
- Report-only root: `C:/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo`, branch `codex/qa-q02a-cr-20261006`. Its packages were not labeled as the repair implementation. No author working-tree file was executed or normalized.
- Author report commit `005fce84f1eaff4e60a0e04f838c908a9e8da6ae` / tree `ef78592f3a4b06326ed33f8372738e070c405d73` changes only nineteen docs/report/artifact paths relative to the reviewed code. Later coordinator-only state commits do not change this review input.

## Original byte identity and independent results

[probe-identity.json](Q02a-CR-recheck-artifacts/probe-identity.json) compares the original four files and prior orchestration helper directly to `eb895ae` Git blobs before every phase. The author copy was not used:

| Original probe | SHA256 |
| --- | --- |
| guarded_run.py | `e261a9430250af377521aae52e3405ab1535958b42a5ce3ea2dbe1bc65423fee` |
| test_q02a_contract.py | `b56e0b0bc3b6498ae4dc880c5965f9600366973e1e47d2baf66e91d1464c9f66` |
| test_q02a_adversarial.py | `9591d87a1e46112f247e5e6c23ceb6ec42c06bb214f1e3a60c3e07a67bad9597` |
| grammar.json | `132c4a48e561098ef17915e1f5213c145ed674c40f6212ba1935a0dda3c0d700` |

| Check | Independent result | Child exit | Record / raw output |
| --- | --- | --- | --- |
| Original independent suites | 26 methods, OK, zero skips | 0 | [record](Q02a-CR-recheck-artifacts/original-independent-26.json), [log](Q02a-CR-recheck-artifacts/original-independent-26.log) |
| Additional finite-scope controls | 8 methods, OK, zero skips | 0 | [record](Q02a-CR-recheck-artifacts/new-repair-scope.json), [cases](Q02a-CR-recheck-artifacts/test_repair_scope.py) |
| Focused resolver/eval/Q03a/grounding | 71 tests, OK, zero skips | 0 | [record](Q02a-CR-recheck-artifacts/repair-focused.json), [log](Q02a-CR-recheck-artifacts/repair-focused.log) |
| Full QA | 394 tests, OK, zero skips; 56.864 s process time | 0 | [record](Q02a-CR-recheck-artifacts/qa-full.json), [log](Q02a-CR-recheck-artifacts/qa-full.log) |
| Advisor API affected cross-package | 6 tests, OK, zero skips | 0 | [record](Q02a-CR-recheck-artifacts/cross-advisor-api.json), [log](Q02a-CR-recheck-artifacts/cross-advisor-api.log) |
| v3 development eval | 12 queries, Recall/MRR 10/11; 6 scalar + 9 final-turn fake-client controls | 0 | [record](Q02a-CR-recheck-artifacts/v3-eval.json), [result](Q02a-CR-recheck-artifacts/v3-result.json) |
| Default v1 / explicit v2 | Expected source-drift rejection, no result created | 1 each | [v1](Q02a-CR-recheck-artifacts/v1-eval.json), [v2](Q02a-CR-recheck-artifacts/v2-eval.json) |

The eight new methods cover bare/alias/punctuation/outer-space and literal metacharacters, canonical-prefix overlap, unsupported seed clauses/extra syntax spaces, validated hero-domain/generic-kind rejection, valid hero plus generic/lineup background citations, later old-alias sharing without redirection, and current canonical ambiguity. These supplement rather than replace the unchanged original red probes. Root/lazy-origin and strict v3 metadata negatives remain in those original probes.

## Commands and guards

[recheck.py](Q02a-CR-recheck-artifacts/recheck.py) reuses the immutable previous reviewer orchestration and launcher, with explicit new code/tree/output/source root. It does not patch the QA implementation. Deliberate isolated fault injections inside the unchanged negative tests remain part of those tests. Every JSON record includes actual command, cwd, execution root, code/tree, child exit, elapsed time and log SHA256. Phases from the report checkout:

```text
python3 -B docs/test-reports/2026-10-06/Q02a-CR-recheck-artifacts/recheck.py snapshot
python3 -B docs/test-reports/2026-10-06/Q02a-CR-recheck-artifacts/recheck.py focused
python3 -B docs/test-reports/2026-10-06/Q02a-CR-recheck-artifacts/recheck.py full
python3 -B docs/test-reports/2026-10-06/Q02a-CR-recheck-artifacts/recheck.py cross
python3 -B docs/test-reports/2026-10-06/Q02a-CR-recheck-artifacts/recheck.py eval
python3 -B docs/test-reports/2026-10-06/Q02a-CR-recheck-artifacts/recheck.py provenance
python3 -B docs/test-reports/2026-10-06/Q02a-CR-recheck-artifacts/recheck.py author-history
python3 -B docs/test-reports/2026-10-06/Q02a-CR-recheck-artifacts/recheck.py integrity
```

Absolute snapshot QA/common/Pioneer/test paths are passed in PYTHONPATH, including to MCP stdio children. The audit-hook launcher denies `.env` file opens and Internet-family connection/DNS attempts while retaining Unix sockets and native `os.open` identity. Explicit fake clients prevent real provider construction. The child environment is allowlisted and contains no forwarded user model credentials. No dependency installation, network/game operation, formal KB publication, source edit, merge or push occurred. Standard publish tests use temporary fixture roots only.

## Source/version verification

[source-provenance.json](Q02a-CR-recheck-artifacts/source-provenance.json) resolves the real production commit and checks all 186 KB/production manifest entries at both production and final code: 372 normalized blob comparisons, zero mismatch. The production digest is `3e1a234cf0a425171a40076bf1f2d83fc35c0fce4cb7af887f9913763000b9a6`. Original queries, top-k, scorer definitions and scalar cases are unchanged; v3 cases are also byte-identical to the original Q02a version. v3 rebind changed only resolver hash, production aggregate, source commit and its explanatory README. Old v1/v2 and historical reports remain immutable.

[integrity.json](Q02a-CR-recheck-artifacts/integrity.json) repeats exact snapshot comparisons after testing, verifies unchanged original reviewer assets/red evidence, and indexes artifact SHA256. Commit syntax alone is not authentication; this review's local Git/blob evidence establishes the particular binding, without a remote-signature claim.

## Preserved red/setup evidence — separate categories

1. **Original product defects:** the two excluded/quoted-name failures and validated non-hero failure remain in original review commit `eb895ae`; those files and assertions were not modified.
2. **Author setup failures:** report commit `005fce84` preserves `copy-correction.json` (text copying added one LF before byte restoration), pre-byte-restoration results, `full-first.log` (394 tests, MCP child missing qa_agent because only the dependency directory reached PYTHONPATH), and separate final successful results. [Immutable references/hashes](Q02a-CR-recheck-artifacts/author-evidence-reference.json) records these files. None were erased or counted as independent passes.
3. **Reviewer setup failure:** the first snapshot attempt stopped before tests because the imported verification helper's definition-time default commit remained `f3cd9b`, despite retargeting the orchestration variable to `40f46d3`. The mismatch was correctly detected at WORKLOG.md. [Raw tool stderr](Q02a-CR-recheck-artifacts/snapshot-first-error.log) and [diagnosis](Q02a-CR-recheck-artifacts/snapshot-first-error.json) are retained. The reviewer passed the requested immutable commit explicitly and repeated the complete blob check; no production byte, expected digest or test expectation was changed. All subsequent independent test runs above passed on their first execution.

## Limits

Approval is only for this bounded offline source repair. Eligible seed syntax is finite, aliases are literal, accepted identity is canonical/source-bound rather than a promise of timeless alias uniqueness, and mixed background citations do not become hero identity authority. Provider call counts in v3 are fake final-target-turn counters, not full conversation cost or provider semantic quality. General coreference, arbitrary-language refusal detection, full Q02, semantic truth, human gold, holdout, disk KB refresh, whole-corpus conflict completeness, native Windows full-suite validation, production readiness and live-game execution remain unaccepted.
