# Q03a independent adversarial review

Date: 2026-10-05. **Decision: REQUEST_CHANGES.** Three P2 findings remain on the exact reviewed code below. This is a local independent review, not implementation-owner approval, merge permission, or production certification.

## Frozen input and boundaries

- Code: `3f81519d34063d438af918a3750bcc38a535b6b7`.
- Tree: `d165dda6ff9ba8c2fd39a604406b5cfee84449c5`.
- Starting comparison: `f879915ab43aa9148496a17f5277725c8c913403`.
- Author report inspected read-only at `50b8ff032af9639da38228c84fedebf2dcd5d9cc`, not substituted for independent results.
- Isolated reviewer branch: `codex/qa-q03a-cr-20261005`; reviewer changed only these reports and independent artifacts. No implementation edit, merge, push, real provider, credential read, formal KB publication, or game operation.
- Frozen plan: bounded scalar scope; missing/zero; same-entity/path/applicability; actual ChatAgent/prompt; entity/rewrite drift; v1/v2 identity; original scorer behavior.

Commands, raw logs, return codes, hashes, provenance, and environment repairs are in [Q03a-CR.md](../test-reports/2026-10-05/Q03a-CR.md).

## Findings

### CR01 — P2: evaluator root check does not bind the code that actually executes

Location: [runner.py:15](../../packages/qa-agent/src/qa_agent/quality_eval/runner.py#L15), imports at lines 8-9 and result identity at lines 58-61.

`run(package)` checks only this runner's `__file__`. A normal `importlib` load of the frozen B-tree runner, with `PYTHONPATH` pointing at another A-tree QA package, imports Retriever/scoring/ChatAgent dependencies from A. The runner then hashes and reports B's production files. Independent reproduction used a disposable A copy whose `Retriever.retrieve` returns an empty list; it did not patch `__file__`, `snapshot`, `digest`, or runner globals. The call succeeded with B's production digest `82f30b27fd957235f4afc7ccc70250b85fea9e4ec899836956b02c0a85c9a03c` and B's source commit, while the real Retriever file was under `/tmp/q03a-cr-import-a-*`. Recall changed from 10/11 to 0/11; all six synthetic assessments still passed. This violates the explicit no-A-code/B-manifest requirement.

Fix: verify the actual imported QA execution dependencies belong to the selected package/source identity before evaluation, including lazy assessment imports, and reject mixed roots. Preserve the source manifest; do not merely broaden exclusions or rename the reported root. No remote signature requirement is implied.

Evidence: [reproducer](../test-reports/2026-10-05/Q03a-CR-artifacts/mixed_import_probe.py), [raw output](../test-reports/2026-10-05/Q03a-CR-artifacts/mixed-import-roots.log). Exit 1 is the reviewer's deliberate rejection after the evaluated runner incorrectly returned success.

### CR02 — P2: v2 accepts malformed metric parameters and an omitted gate suite

Location: [runner.py:22](../../packages/qa-agent/src/qa_agent/quality_eval/runner.py#L22), retrieval use at line 49, optional assessment suite at lines 55-56.

Independent read-boundary fixtures demonstrated accepted `top_k=0`, `top_k=-1`, `top_k=true`, and `version=2.0`; deleting `assessment_cases` also yielded a successful v2 report with zero assessment rows. The synthetic cases hash was intentionally recomputed in memory so these probes isolate schema validation from ordinary hash-drift rejection. Original disk fixtures/freezes were not changed. A digest binds malformed data too; it does not make invalid metric parameters or missing required v2 coverage valid. In particular, negative `top_k` acquires Python slice behavior instead of meaning a valid top-k retrieval experiment.

Fix: validate the version-specific corpus before execution: integer version (not bool/float), positive integer top-k, and a required nonempty v2 assessment suite. Keep rejection of unsupported versions, duplicate IDs, algorithms, source refs, and physical source drift. Preserve the existing v1 meaning.

Evidence: [independent cases](../test-reports/2026-10-05/Q03a-CR-artifacts/test_independent_q03a.py), [five failed assertions](../test-reports/2026-10-05/Q03a-CR-artifacts/independent-initial.log). Existing physical drift checks and the normal frozen v2 result passed separately.

### CR03 — P2: empty constraints are treated as proof of comparable applicability

Location: [evidence_assessment.py:68](../../packages/qa-agent/src/qa_agent/chat/evidence_assessment.py#L68), scalar comparison at lines 70-82.

The comparator treats `constraints=[]` as sufficient for comparison. Two otherwise valid same-hero/base-military records with values 20 and 30 and notes explicitly stating "本记录数值仅适用于 S1" versus "本记录数值仅适用于 S2" produce `conflicting + disclose_conflict`. The actual ChatAgent skips answer generation and returns the field values/source IDs without either condition. The literal statement that source values differ is true; the defect is classifying them under the same-applicability conflict gate and omitting the applicability distinction, contrary to this slice's stated non-comparable-scope boundary.

Fix: do not infer same/unconditional applicability solely from an empty `constraints` array. Make eligibility for this bounded comparison explicit and fail conservatively to `partial/unassessed` when applicability remains in unassessed prose; retain relevant qualifiers in diagnostics. This does not require generic semantic inference, full Q05 season reasoning, or selecting a true source.

Evidence: [independent applicability case](../test-reports/2026-10-05/Q03a-CR-artifacts/test_q03a_extra.py), [actual assessment/answer](../test-reports/2026-10-05/Q03a-CR-artifacts/extra-boundaries.log).

## Verified working boundaries

- All twelve supported base/max/growth x military/intelligence/command/initiative paths were checked through actual ChatAgent with a fake client; the exact field/value/ID/source reached the actual prompt.
- Zero/None, zero/equal-zero, genuine same-scope zero/one disagreement, three-source disclosure, different entities/stages, explicit nonempty constraints, ambiguous aliases, lineup membership, high-score wrong entity, and rewritten-subject drift behaved as scoped.
- Missing structured value with an answer in a later hero note remained partial and generated with that prose included. Empty evidence with or without history made zero rewrite/answer calls; invented citation IDs still failed the original gate.
- v1/default refused the new production tree. Original v1 and previous C/CR/integration evidence were unchanged. v2 inherited the original twelve queries, top-k, labels, and scorer cases exactly.
- Unsupported snapshot algorithm and mismatched evidence source_ref were rejected. Real v2 emitted twelve retrieval rows and six fake-client assessment rows, without provider quality or holdout claims.

## Identity and evidence limits

`baseline_commit` in the runner is currently only checked as forty lowercase hex characters. A nonexistent all-zero SHA is accepted as a label. This review independently resolved the actual `23149c06a970da6876cd94403970934f164ed794` commit and verified all 185 KB/production blobs against the freeze, with zero mismatches. Thus the current frozen source label is not shown false; source-commit authenticity is externally established by this local Git check, not by the runner's regex. This is recorded as a limitation, not a separate claim that the current artifact was forged.

General prose entailment, source truth, skills/faction fields, full season/version reasoning, human gold, independent holdout, real provider quality, and production/game execution remain outside this review. Appending profile notes expands prompt content without adding a context budget; no unrelated Q08 budget requirement is imposed here.

All first failures are retained. Repairs to the review launcher and temporary CRLF-to-LF presentation repair are identified separately from production defects. After remediation, provide a new exact code/tree and rerun the independent negatives and affected regressions; this approval decision must not be inherited by a changed tree.
