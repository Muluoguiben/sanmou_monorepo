# Q02a independent CR — source-bound verification

Date: 2026-10-06. **REQUEST_CHANGES.** [Q02a-CR01/02 findings](../../reviews/2026-10-06-Q02a-adversarial-review.md) are independent of ordinary suite passes.

## Identity

- Frozen plan: `0b9d514c1ffe76d85de209dc9f8802dcf2c2aba7`; the prepared script/grammar bytes are unchanged.
- Reviewed code: `f3cd9b8814fc085d567063ab23e6576b9c24525f`; tree `b73cf4b49fc311d55b50b7caf56a7a7b2fb0b01e`.
- Existing production commit: `a2726c24eba982245fb83e46fdfd6ce0f41880d8`.
- Actual execution root: `/tmp/q02a-independent-953xps1e`, complete immutable Git archive excluding `.env.example`; 1,445 exact file/blob comparisons, zero mismatch. [Snapshot](Q02a-CR-artifacts/snapshot.json).
- Archive SHA256: `34e26c7976b1d5ed1c8f9d96b0d816925bc97c3b4422dbe3a4060c47cd304052`. Per-command `core.autocrlf=false/core.eol=lf` avoids Windows archive conversion; global configuration and author checkout were not changed.
- Report checkout remains `C:/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo`, branch `codex/qa-q02a-cr-20261006`. Its old packages were not called the new implementation. Author report/state successors were not executed or substituted for frozen code.

## Results and raw evidence

| Check | Actual result | Child exit | Record / raw log |
| --- | --- | --- | --- |
| Frozen independent plan | 21 methods, OK, zero skips | 0 | [record](Q02a-CR-artifacts/independent-frozen-plan.json), [log](Q02a-CR-artifacts/independent-frozen-plan.log) |
| Supplemental adversarial | 5 methods; 2 failing methods / 3 failed assertions | 1 | [record](Q02a-CR-artifacts/independent-supplemental.json), [log](Q02a-CR-artifacts/independent-supplemental.log) |
| Focused existing/new | 68 tests, OK, zero skips | 0 | [record](Q02a-CR-artifacts/author-focused-recheck.json), [log](Q02a-CR-artifacts/author-focused-recheck.log) |
| QA full | 391 tests, OK, zero skips; 40.253 s process time | 0 | [record](Q02a-CR-artifacts/qa-full.json), [log](Q02a-CR-artifacts/qa-full.log) |
| Advisor API cross-package | 6 tests, OK, zero skips | 0 | [record](Q02a-CR-artifacts/cross-advisor-api.json), [log](Q02a-CR-artifacts/cross-advisor-api.log) |
| v3 development eval | 12 query rows; Recall/MRR 10/11; 6 assessment and 9 final-target-turn fake-client controls | 0 | [record](Q02a-CR-artifacts/v3-eval.json), [result](Q02a-CR-artifacts/v3-result.json) |
| v1/v2 against new production | Expected source-drift failures, neither result file created | 1 each | [v1](Q02a-CR-artifacts/v1-eval.json), [v2](Q02a-CR-artifacts/v2-eval.json) |

The supplemental probes run real ChatAgent with explicit fake clients. Previous answers in CR01 contain currently retrieved valid IDs and actually pass the citation gate. CR02 constructs its term/generic record using `KnowledgeEntry.model_validate` and confirms HeroStaticProfile was accepted; no validation bypass is used. Their raw failures include original question, resolved question, resolution, and model-call count. No claim is made that a real provider was observed producing these answers.

## Commands and protection

[verify_frozen.py](Q02a-CR-artifacts/verify_frozen.py) pins the immutable source, constructs the full snapshot from Git objects, and creates outputs exclusively. Every test record contains exact argv/cwd/root/code/tree/return code/time/log hash. Phases from the report checkout:

```text
python3 -B docs/test-reports/2026-10-06/Q02a-CR-artifacts/verify_frozen.py snapshot
python3 -B docs/test-reports/2026-10-06/Q02a-CR-artifacts/verify_frozen.py focused
python3 -B docs/test-reports/2026-10-06/Q02a-CR-artifacts/verify_frozen.py full
python3 -B docs/test-reports/2026-10-06/Q02a-CR-artifacts/verify_frozen.py cross
python3 -B docs/test-reports/2026-10-06/Q02a-CR-artifacts/verify_frozen.py eval
python3 -B docs/test-reports/2026-10-06/Q02a-CR-artifacts/verify_frozen.py provenance
python3 -B docs/test-reports/2026-10-06/Q02a-CR-artifacts/verify_frozen.py integrity
```

[guarded_run.py](Q02a-CR-artifacts/guarded_run.py) takes an explicit source root, denies `.env` file opens using an audit hook, and blocks Internet-family connection/DNS attempts while preserving Unix sockets and builtin dir_fd capability identity. Child environments use a small allowlist and explicit PYTHONPATH; no user provider secrets are propagated. No dependencies were installed; the existing read-only API dependency directory was reused. Ordinary ingestion tests write only temporary fixture roots; formal KB, publishing permissions and game state remain unchanged.

This round needed no CRLF repair, reviewer launcher repair or failed setup retry. Initial preparation had only static AST/JSON validation and executed zero tests; the runtime results above occurred later, on the authorized frozen implementation.

## Version/provenance and remaining limitations

[source-provenance.json](Q02a-CR-artifacts/source-provenance.json) independently resolves the production commit and compares all 186 KB/production manifest entries at both that commit and reviewed code: 372 normalized content comparisons, zero mismatch. Original queries/top-k/scorer/six-assessment sections are unchanged. A separate read-only reviewer independently reached the same result from Git objects; that was not substituted for behavioral execution.

[integrity.json](Q02a-CR-artifacts/integrity.json) records post-test source comparison, unchanged original plan assets, unchanged v1/v2 and prior Q03a history, and SHA256 for all local artifacts. New v3 multi-turn count is nine synthetic scenarios; mock counts are reset before the final target question, so they do not measure full-conversation usage, provider quality, human gold or an independent holdout.

The runner's commit-label syntax is not Git authentication. Local object/blob checks establish this particular source binding; no remote signature or production certification is claimed. Native Windows full-suite behavior, arbitrary-language reference/refusal semantics and real-provider quality remain outside scope. No author source was edited; no merge or push was attempted. New source must be independently re-reviewed after repair.
