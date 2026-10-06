# Q04a independent plan (before interface/implementation review)

Published baseline: `5791ca397507007b9397c78763b3523b8ec16421`.
Frozen contract: `9e35b34e2540923bd7b253f71b3d1f49da1093fb`, tree
`7c287132a868c8b720c1d0dc49563d983f820a2b`.
Review branch `codex/q04a-claim-spans-cr-20261006`, initially clean; old refs retained.
Read AGENTS.md, code-review skill, full contract and existing scoring/runner source.
No author interface memo or implementation was read before freezing this plan.

## Scope / baseline oracles

Expected additions are quality_eval/claim_spans.py, one dedicated test module and
new synthetic-development fixtures. Any small helper needs an explicit reason.
Old scoring.py/runner.py, production QA/ChatAgent/retrieval/KB/MCP/common/Pioneer,
dependencies/CI, old v1-v3 cases/freeze/labels/expectations remain byte-identical.
Reuse digest/ratio/score_answer/snapshot and existing module-origin checks; no new
entailment judge or eval framework. Old v1/v2 rejections must not be forced green.

## Frozen acceptance gates

1. **Interface first.** Review the fixed one-page memo before implementation: exact
   schema/version, normalization, support-span projection, label status and every
   denominator. CRLF becomes LF; remaining bare CR and unencodable surrogate text
   are rejected per coordinator clarification. No NFC or implicit text rewriting.
2. **Strict bindings.** Independently compute context/answer/evidence-content and
   annotation-version hashes. Change each independently without rebinding and
   require rejection. Test unknown/wrong entry id, wrong hash/type/version, extra
   or missing field, duplicate IDs and identical support links. Offsets are true
   integer Unicode-code-point positions in normalized text, never bool/float/string,
   UTF-8 bytes or UTF-16 units. Empty/out-of-range/reversed spans fail, never search
   for a guessed replacement. Preserve exact answer coverage without gap/overlap.
3. **Unicode controls.** Chinese, emoji, decomposed combining characters, LF/CRLF
   equivalence and non-NFC equivalence each get positive/negative controls. Verify
   the exact selected substring against independently normalized text and its hash.
   Reject malformed UTF-8/unpaired surrogates and bare CR, without silently dropping
   characters or changing offsets. Do not require grapheme boundaries.
4. **Projection, not semantic invention.** Project valid links to unique entry ids
   and compare every inherited result to unchanged score_answer. Multiple distinct
   spans for one id retain locations but do not inflate support/claim denominators.
   Supported requires a valid link; nonclaim has no links; other verdicts may have
   none as fixed by memo. Invalid annotation links are rejected, while wrong/missing
   citations in answer text remain scored data rather than excluded cases.
5. **Mechanical != semantic.** Freeze independent synthetic controls for correct
   id/span with wrong number/entity, partial citation and conflicting evidence.
   Mechanically valid spans can still carry unsupported/unknown external labels;
   do not pick the first source to resolve conflict or promote valid hashes to
   semantic support. Preserve all original score numerators/denominators/values;
   a zero denominator stays None/unknown, not zero or a 100-percent pass.
6. **No label-authority upgrade.** Developer-authored, unreviewed and externally
   declared human-reviewed are distinguishable. Synthetic suites allow the first
   two controls but cannot become human gold through a case's self-declaration.
   A generic scorer may accept human-reviewed labels only as unauthenticated
   declarations. Reviewer/source text and content hashes grant no KB review,
   publication, trusted revision, independent holdout or provider-quality status.
7. **Actual source/fixture provenance.** New report binds its own explicit fixture
   version/content and actual eval-source file list/digests. Reject fixture drift,
   wrong package roots and mixed QA imports, including lazily loaded dependencies,
   using reusable origin checks. Do not claim signed/authenticated source from a
   self-reported revision. Input text is data, never executable instructions.
8. **CLI and old-report compatibility.** Run the new CLI for its explicit synthetic
   fixture plus independent controls; output is create-only and existing files
   remain unchanged on a second attempt. No provider/network/config/publication.
   Rerun old v3: retain historical full hash
   `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`, record the new
   hash, and allow only exact eval_source added-file/digest differences. All other
   fields must match deeply; old eval_source entries must be unchanged and every
   added/current entry checked against actual Git source. No broad exclusion list
   or rewritten old gold/hash. Compare v1/v2 baseline success/rejection behavior too.
9. **Fixed-source verification.** Freeze probes before runs; keep first reds and
   identical assertions for repair verification. Run dedicated tests, full QA/
   Pioneer/common, existing H07/H10/H09 and old v3. Record actual argv/exit/count/
   skip, source SHA/tree, provider_calls=0 and none/false in compact plain evidence.
   New Q04 native coverage is separate from H10 native; do not reopen dependency
   installation/exploration or infer coverage from unrelated previous passes.

No implementation repair by reviewer, no main WIP/push/deployment, credentials/.env,
provider/game/bridge, Q06 payload/ancestry or archive body/member reads. No new
archives or repeated old matrices. Coordinator owns final combined-tree/CI and
authorized publication. Next: review fixed memo, then wait for fixed author code.
