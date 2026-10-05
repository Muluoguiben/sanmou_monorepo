# Q03a independent repair recheck

Date: 2026-10-05. **Decision: APPROVE, only for the bounded repair on the exact source below.** CR01-CR03 are closed by new independent evidence. This does not rewrite the previous REQUEST_CHANGES or its red evidence, and is not production or execution approval.

## Source identity

- Reviewed code/eval/tests: `3b2b137679bd6b72a5681874bf9ab6ea0ac8f0c9`.
- Reviewed tree: `ec1d8f04ff42156c90a151b4d0e4c3fbddf765c6`.
- Production applicability repair: `2af538b4f9cf03a7757a158dc59b1af6143c4af7`.
- Actual frozen author checkout HEAD: `3986047adafa6a5334bc7a27a055d0800ddf259d`, tree `0629b700e2e76009a6edf07e304e77f2a4e35b4a`; differences from reviewed code are nine report/artifact paths under `docs/` only.
- Reviewer remains on `codex/qa-q03a-cr-20261005` over original local CR `a10472972de2e6a5fca675b363f086ab1372e003`. Its old package tree was never labeled as the repaired test source. No merge, push, production edit, model call, credential read, formal KB publication, or game operation occurred.

The three original probes copied into the author report directory match their `a104729` Git blobs byte-for-byte. Independent [provenance](../test-reports/2026-10-05/Q03a-CR-recheck-artifacts/provenance.json) records their SHA256, real author root/head/tree, and 185 verified source/KB blobs. Runtime baseline_commit remains format-only; this reviewer independently verified the actual local commit and manifests, without claiming a remote signature.

## Finding disposition

| Original finding | Independent new evidence | Disposition |
| --- | --- | --- |
| CR01, mixed execution roots | Unchanged original mixed-import probe raises `ValueError: QA execution source mismatch: qa_agent.knowledge` before a result. Its exit is 1, but there is no `claimed_production_digest` output and no accepted-identity marker. New cases also reject a foreign lazy assessment module before invocation, a foreign module inserted during evaluation before report return, mismatched module spec origin, and an extra package search root. | Closed for the local module-origin contract; deliberate in-process executable monkeypatching remains excluded. |
| CR02, malformed v2 schema | All original integer/version/top-k/missing-suite negatives pass unchanged. Independently rerun author strict-schema coverage passes; original v1 meaning and physical/source/label drift checks remain. | Closed for the identified schema requirements. |
| CR03, incomparable prose scopes | Original S1/S2 notes probe passes unchanged. New actual-ChatAgent probes preserve S1/S2 facts/qualifiers in the prompt, downgrade benign notes without refusing, retain missing-value/prose reasons, and still stop generation for a genuine clean same-scope zero/one conflict. | Closed for conservative notes and explicitly recognized fact-cue scope, not general NLU/Q05. |

No new actionable finding was identified in the scoped repair review. The unchanged original independent suite passed 17 tests; new lazy/scope probes passed 8; focused repair regression passed 44; affected Advisor API tests passed 6; full QA passed 367 tests on the byte-verified complete Git snapshot. All have zero skips. Commands, exact roots, return codes/hashes and preserved reviewer-only setup failures are documented in [Q03a-CR-recheck.md](../test-reports/2026-10-05/Q03a-CR-recheck.md).

## Frozen baseline and retained boundaries

- v1 files and previous C/CR/integration evidence remain unchanged. Original local CR reports, probes, failures, and reviewer-tool repair history are untouched.
- v2 cases remain byte-identical. The unpublished v2 freeze was explicitly rebound to the already-existing repair commit; only the assessor production file hash, aggregate production digest and source commit changed. Earlier v2 state and evidence remain in immutable Git history.
- v2 still evaluates twelve queries at top-k five and six synthetic gate cases; development macro Recall and MRR remain 10/11. Default v1 still rejects the repaired production with source drift and emits no output artifact.
- Notes are deliberately conservative: any note can yield partial/unassessed, but does not turn the existing evidence-backed generation path into blanket refusal. Recognized fact-scope cues are finite; arbitrary free-form facts are not proven scope-free. Supported remains a bounded scalar check, not source truth or answer entailment.
- No provider semantic quality, human-reviewed gold, independent holdout, calibrated judgment, full Q05 validity resolution, native Windows full-suite pass, production readiness, or game execution authorization is established.

This is a new exact-source decision after remediation, not approval inherited from an older tree. Any further source change requires a new binding and proportionate revalidation. Reports remain local; integration/publication decisions belong to the coordinator and user.
