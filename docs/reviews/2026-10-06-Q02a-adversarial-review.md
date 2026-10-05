# Q02a independent adversarial review

Date: 2026-10-06. **REQUEST_CHANGES: Q02a-CR01 and Q02a-CR02 are demonstrated P2 blockers.** Ordinary suite success does not close these identity/subject-boundary gaps.

## Frozen source and review boundary

- Plan committed before implementation inspection: `0b9d514c1ffe76d85de209dc9f8802dcf2c2aba7`, [plan](2026-10-06-Q02a-review-plan.md).
- Reviewed code/eval/tests: `f3cd9b8814fc085d567063ab23e6576b9c24525f`; tree `b73cf4b49fc311d55b50b7caf56a7a7b2fb0b01e`.
- Production source commit: `a2726c24eba982245fb83e46fdfd6ce0f41880d8`.
- Baseline: `e17d937a39944b036e90701fecefb6611b1d88d6`.
- All behavioral execution used `/tmp/q02a-independent-953xps1e`, made from that immutable code commit, not the author's moving branch or the review checkout's older packages. All 1,445 source files matched exact Git blobs before testing.
- No implementation, formal KB, common/MCP/Pioneer contract, old v1/v2 fixture, or prior Q03a evidence was edited. No real provider, credential/config, network, game, merge or push operation was used.

## Q02a-CR01 — P2: a unique name occurrence is promoted to an explicit subject

Frozen location: `packages/qa-agent/src/qa_agent/chat/referent_resolution.py:52-66`, especially line 62; acceptance uses this result at lines 95-108.

`_explicit_hero` searches `alias in question` anywhere in the previous user question. That identifies mentions, not the explicitly requested subject. Two independent actual-ChatAgent cases use previous questions `不要介绍沈将，请只说明城建。` and `沈将只是引文中的名字，本题只问城建。`. The fake answer contains the current valid `[q02-review-hero-a]` citation and passes the existing citation gate; then `他的初始武力是多少？` is reported as `resolved`, rewritten deterministically to `沈将初始武力是多少`, and makes one answer-model call instead of zero-model clarification.

This does not require the model to understand every refusal or produce a semantically correct answer. It demonstrates why valid citation IDs cannot convert a merely excluded/quoted name into the previous question's explicit subject. The accepted-state contract must be narrower than an unrestricted substring match.

Fix: define an anchored finite grammar for eligible explicit seed questions, including any deliberately supported bare canonical/alias form and bounded attribute question. Reject extra/nonmatching clauses for binding rather than adding a negation-keyword blacklist or claiming general NLU. Preserve ordinary legacy answering for unsupported seed questions without granting referent state.

Evidence: `test_excluded_name_is_not_an_explicit_hero_subject` in [supplemental probes](../test-reports/2026-10-06/Q02a-CR-artifacts/test_q02a_adversarial.py), with [raw actual resolution/call traces](../test-reports/2026-10-06/Q02a-CR-artifacts/independent-supplemental.log). Both subcases fail the zero-answer expectation.

## Q02a-CR02 — P2: non-hero domain/kind records can establish a hero referent

Frozen location: `packages/qa-agent/src/qa_agent/chat/referent_resolution.py:48-49`; the same helper controls candidate eligibility and actual-citation identity at lines 55 and 107.

`hero_identity` checks only `isinstance(structured_data, HeroStaticProfile)`. The current KnowledgeEntry validator does not guarantee the reverse metadata invariant: a `domain='term', entry_kind='generic_rule'` record with HeroStaticProfile data is accepted by `KnowledgeEntry.model_validate`. The independent case uses full model validation, not `model_copy` or validation bypass. With only that non-hero record plus background mechanics, the real ChatAgent accepts its valid ID as a hero anchor and later resolves the pronoun to 沈将 with one answer call.

Fix the private resolver eligibility check to require `Domain.HERO`, `EntryKind.HERO_PROFILE` and `HeroStaticProfile` together. Apply the same eligibility to anchor discovery, cited identity and final resolved evidence. No public schema or wholesale KB rewrite is needed; the legacy knowledge surface can remain unchanged.

Evidence: `test_nonhero_metadata_cannot_supply_a_hero_referent` in [supplemental probes](../test-reports/2026-10-06/Q02a-CR-artifacts/test_q02a_adversarial.py), [raw validated domain/kind and resulting binding](../test-reports/2026-10-06/Q02a-CR-artifacts/independent-supplemental.log).

## Independent verification completed

- Frozen preimplementation probes: **21 methods pass**, including 32 positive grammar combinations and their nested controls.
- Additional source-informed probes: **5 methods, 3 passed / 2 failing methods, 3 failed assertions**. Two CR01 subcases and one CR02 case reproduce the blockers. These are not baseline feature-gap failures: they run against the new frozen implementation.
- Author focused cases independently rerun: **68/68 pass**, zero skips.
- Full QA independently rerun: **391/391 pass**, zero skips.
- Affected Advisor API: **6/6 pass**, zero skips.
- v3 evaluation completed: twelve lexical queries retain Recall/MRR 10/11; six Q03a controls and nine fake-client multi-turn scenarios pass. Multi-turn call counts describe the final target turn after mock reset, not total conversation usage or provider quality.
- New lazy `referent_cases` foreign-origin rejection and strict v3 boolean/missing-suite negatives pass. v1/v2 correctly reject new production drift; no output file is created for those expected failures.

Commands, exact roots, return codes, raw-log SHA256, source/manifest binding and preservation checks are in [Q02a-CR.md](../test-reports/2026-10-06/Q02a-CR.md). Every original red output is retained; no assertion or frozen plan was weakened to obtain green results.

## Limits and next step

No approval is issued for this code/tree. Repair the two bounded gates, freeze a new production/code tree and explicitly rebind unpublished v3 while retaining original history. Do not mutate v1/v2 or previous reports. The new tree needs independent replay of these exact red probes and proportionate regression, not an inherited approval.

General coreference, arbitrary-language refusal understanding, full-Q02 completion, semantic model truth, human gold, independent holdout and production/game execution are not asserted. Source commit identity is established through local Git/blob evidence, not forty-hex syntax or remote signing. Report-only local commits do not authorize integration or publication.
