# Q03a repair — independent source-bound verification

Date: 2026-10-05. **APPROVE for the exact bounded repair; CR01-CR03 closed.** This record is reviewer-owned, not a restatement of author results. See [disposition](../../reviews/2026-10-05-Q03a-adversarial-recheck.md).

## Sources and execution roots

- Reviewed code: `3b2b137679bd6b72a5681874bf9ab6ea0ac8f0c9`; tree `ec1d8f04ff42156c90a151b4d0e4c3fbddf765c6`.
- Actual author checkout HEAD verified before/after every subprocess: `3986047adafa6a5334bc7a27a055d0800ddf259d`; tree `0629b700e2e76009a6edf07e304e77f2a4e35b4a`. Only nine documentation/report paths differ from reviewed code.
- Direct focused/probe/eval/cross execution root: `C:\Users\Lan\.codex\worktrees\qa-evidence-q03-20261005\sanmou_monorepo`, WSL `/mnt/c/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo`.
- Final full QA execution root: `/tmp/q03a-cr-recheck-wxyqqyk_`, an ext4 archive of the exact reviewed repository tree, excluding `.env.example`. All **1,336 files** were verified byte-for-byte against their actual Git blobs before tests, with zero mismatches; no source edit or author-checkout normalization was performed. [Final archive identity](Q03a-CR-recheck-artifacts/archive-full-identity.json). The earlier partial packages/scripts snapshot at `/tmp/q03a-cr-recheck-jfc2q_9i` also matched its 1,106 blobs but lacked Desktop/docs resources; its failure is preserved separately.
- Reviewer report checkout remains at the old CR package tree. Explicit source-root arguments and PYTHONPATH select the repaired code; the report checkout is only the output destination.

Author source has two existing untracked documentation/autonomy paths, recorded in provenance; they were not read as inputs, altered, staged, or mistaken for production drift. The tracked author source remained unchanged throughout review.

## Original probe identity and local source binding

[provenance.json](Q03a-CR-recheck-artifacts/provenance.json) verifies the author's copied scripts against original `a104729` blobs, using raw bytes rather than normalized equality:

| Probe | Original blob = copied file SHA256 |
| --- | --- |
| mixed_import_probe.py | `565c67da5b63bac8209194372d79b2b898a885a4be3f7372bdf3288112c4f1e8` |
| test_independent_q03a.py | `9d4ab6c15bad527c665117c0de29f445582957bdafacfc687404631685c4dd3e` |
| test_q03a_extra.py | `85cdf0e1b9832602445600e0ec0b62284f71a4f03750a1153d6f95e97a5faa55` |

The real production commit `2af538b4f9cf03a7757a158dc59b1af6143c4af7` was independently resolved locally. Its 185 KB/production blobs match the v2 freeze. New production digest is `db41262f5574872c4304b752e74e6099056d310b12eb3e0dce71028e3261a804`; only `src/qa_agent/chat/evidence_assessment.py` differs from the prior production manifest. KB and cases digests are unchanged. The runner's forty-hex check still does not authenticate a commit; this independent Git evidence establishes this particular binding, not a signature guarantee.

## Independent results

| Check | Observed result | Child exit | Evidence |
| --- | --- | --- | --- |
| Original copied independent suite | 17 tests, OK, no skips | 0 | [record](Q03a-CR-recheck-artifacts/original-independent-replay.json), [raw](Q03a-CR-recheck-artifacts/original-independent-replay.log) |
| Repair focused regression | 44 tests, OK, no skips | 0 | [record](Q03a-CR-recheck-artifacts/repair-focused.json), [raw](Q03a-CR-recheck-artifacts/repair-focused.log) |
| New reviewer lazy/spec/path/notes controls | 8 tests, OK, no skips | 0 | [record](Q03a-CR-recheck-artifacts/new-lazy-and-scope-negatives.json), [cases](Q03a-CR-recheck-artifacts/test_repair_boundaries.py) |
| Original mixed-import probe | Explicit `QA execution source mismatch` rejection, no result returned | 1, expected | [raw](Q03a-CR-recheck-artifacts/mixed-import-original-probe.log), [interpretation](Q03a-CR-recheck-artifacts/mixed-import-interpretation.json) |
| Full QA, initial packages/scripts-only snapshot | 367 tests; 2 Desktop-resource expectation failures due to reviewer snapshot omission | 1 | [record](Q03a-CR-recheck-artifacts/qa-full-ext4-snapshot.json), [raw](Q03a-CR-recheck-artifacts/qa-full-ext4-snapshot.log) |
| Full QA, complete frozen repository snapshot | 367 tests, OK, no skips; 40.518 s process time | 0 | [record](Q03a-CR-recheck-artifacts/qa-full-complete-snapshot.json), [raw](Q03a-CR-recheck-artifacts/qa-full-complete-snapshot.log) |
| Affected Advisor API cross-package | 6 tests, OK, no skips | 0 | [record](Q03a-CR-recheck-artifacts/cross-advisor-api.json), [raw](Q03a-CR-recheck-artifacts/cross-advisor-api.log) |
| v2 lexical/gate development eval | 12 queries, top-k 5, Recall/MRR 10/11; 6 fake-client gate cases | 0 | [record](Q03a-CR-recheck-artifacts/v2-eval.json), [result](Q03a-CR-recheck-artifacts/v2-result.json) |
| Default v1 on repaired production | Source-drift rejection; no result file | 1, expected | [record](Q03a-CR-recheck-artifacts/v1-expected-drift.json), [raw](Q03a-CR-recheck-artifacts/v1-expected-drift.log) |

Mixed-import exit code alone is not acceptance evidence: the old defective probe also exited 1 deliberately after observing the wrong digest. The new raw log is a ValueError from the source-origin guard, and the separate interpretation record confirms no claimed-production-digest payload was produced.

## Commands, guards and artifact hashes

[recheck.py](Q03a-CR-recheck-artifacts/recheck.py) pins both the source code and actual report-only author HEAD, uses exclusive artifact output, and records exact commands/cwd/execution roots/return codes/elapsed time/log SHA256. Reviewer commands, from the CR checkout:

```text
python3 -B docs/test-reports/2026-10-05/Q03a-CR-recheck-artifacts/recheck.py provenance
python3 -B docs/test-reports/2026-10-05/Q03a-CR-recheck-artifacts/recheck.py targeted
python3 -B docs/test-reports/2026-10-05/Q03a-CR-recheck-artifacts/recheck.py eval
python3 -B docs/test-reports/2026-10-05/Q03a-CR-recheck-artifacts/recheck.py cross
python3 -B docs/test-reports/2026-10-05/Q03a-CR-recheck-artifacts/recheck.py full
python3 -B docs/test-reports/2026-10-05/Q03a-CR-recheck-artifacts/recheck.py full-complete
python3 -B docs/test-reports/2026-10-05/Q03a-CR-recheck-artifacts/recheck.py integrity
```

Each command's subprocess argv and cwd is in its record, not inferred from the CR checkout. The final full run executes `guarded_recheck.py /tmp/q03a-cr-recheck-wxyqqyk_ discover -s tests -p test_*.py -v` from that snapshot's QA package. The full snapshot deliberately does not contain later repair-report probes; it contains the reviewed commit's files only.

Child environments carry a small allowlist plus explicit PYTHONPATH and disabled bytecode writes, not user provider credentials. [guarded_recheck.py](Q03a-CR-recheck-artifacts/guarded_recheck.py) uses an audit hook to deny `.env` opens while preserving builtin `os.open` capability identity, and blocks Internet-family connects/DNS in the unittest process; Unix sockets remain available for local async machinery. ChatAgent exercises use fake clients. Existing API dependencies are reused read-only, not installed or changed. Standard ingestion tests write only disposable fixture KBs; formal KB, publishing authority and game state were untouched.

Final [integrity.json](Q03a-CR-recheck-artifacts/integrity.json) records all artifact SHA256 plus unchanged author protected paths and unchanged original local CR evidence. Old reports/red logs and the original reviewer launcher failures remain untouched under `a104729`.

## Reviewer setup failures retained

Before the full suite, exact-byte archive validation stopped twice at `packages/pioneer-agent/CLAUDE.md`; **neither attempt ran unittest**. The first hypothesis of a symlink was wrong: independent Git inspection showed a regular `100644` blob of 3,755 bytes, whereas native Windows archive emitted 3,838 bytes with 83 CRLF pairs. The real cause was inherited line-ending conversion. Tool-returned stderr was transcribed unchanged into [first](Q03a-CR-recheck-artifacts/archive-first-error.log) and [second](Q03a-CR-recheck-artifacts/archive-second-error.log) records; [diagnosis](Q03a-CR-recheck-artifacts/archive-format-diagnosis.json) identifies the reviewer-only correction.

The corrected archive command uses only per-command `-c core.autocrlf=false -c core.eol=lf`, with global Git configuration unchanged. The first byte-verified snapshot contained only packages/scripts and produced two full-suite failures because QA MCP readiness tests also inspect Desktop static source. Its archive SHA256 is `92ec61916768b4a90500a33908b545536c6bc3ff3f8c487185f93d6935ca3276`; this is not accepted as a complete integration run. The reviewer then archived the complete same commit, again excluding `.env.example`, and reverified every file. Final archive SHA256 is `f8a7debecf6e6243de3ce74932170a9e1233af251003dead8b882ea293545074`. No expected test, digest, or production file was relaxed. The author checkout's CRLF formatting was never modified in this round.

## Remaining limits

No real model/vision/network/game operation, source truth certification, general semantic entailment, full condition/season NLU, human gold, independent holdout, native Windows full-suite pass, release approval, merge or push is claimed. Runtime module-origin validation is not protection against deliberate same-process monkeypatching. Facts use finite applicability cues; any profile notes conservatively lower scope without suppressing normal evidence-backed generation. Approval, if granted, is only for this bounded repaired slice on the exact source above.
