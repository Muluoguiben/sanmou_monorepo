# Q02a independent review plan — frozen before implementation review

Date: 2026-10-06. **PLAN ONLY: no implementation review, executed result, finding, or approval.** The author is implementing; its moving source tree is deliberately not inspected.

## Immutable inputs and ownership

- Baseline: `e17d937a39944b036e90701fecefb6611b1d88d6`, tree `e22764f11b64722a4a84c883bcfa8e6bd0de5983`.
- Task contract read via `git show e5bfdb2147c17435d24a1d5646dc3cb63895a0e5:docs/qa-referent-resolution-q02a-2026-10-06.md`, not from uncommitted files; task blob `383ea1ff4f7b13349400f43ea08a298b39970dea`.
- Coordinator reports CI run 37341606212 passed all four jobs. This plan does not independently certify hosted CI.
- Report worktree: `C:/Users/Lan/.codex/worktrees/qa-q03a-review-20261005/sanmou_monorepo`; branch `codex/qa-q02a-cr-20261006`. The legacy directory name is not a tested-source identity.
- Current writes are limited to this plan and `docs/test-reports/2026-10-06/Q02a-CR-artifacts/`. No package edits, author-tree reads beyond immutable task input, new branch, push, merge, dependency installation, provider/network/game operation, `.env` read, or formal KB publication.
- Existing Q03a source-bound reviews and every original red log remain unchanged.

## Frozen interpretation

1. Q02a is text-only, complete finite grammar, single-use, immediate-follow-up resolution. Only an explicit unique hero question followed by an answer with actual valid same-hero citations can establish the private referent. A resolved pronoun turn cannot silently renew it.
2. Actual citations, not all candidate evidence IDs, establish identity. A question about A with only a valid B citation, mixed A/B hero citations, lineup-member evidence, generated prose, ambiguous alias, or externally supplied history cannot establish A.
3. Raw retrieval is the first evidence gate. Empty raw evidence preserves the existing fixed no-evidence response and zero rewrite/answer calls, even when substitution could have found an answer. A recognized but unbound/invalid follow-up with nonempty raw evidence gets deterministic clarification, never legacy model fallback.
4. Current state must be bound: original question, actual accepted citations, canonical identity, relevant source contents, full ordered history and container identity. Reset, clear/replace/edit, an intervening turn, invalid citation, conflict, or an exception invalidate the old state. Fully reverted changes between calls are outside the observable mutation contract; a general mutable-container audit framework is not required.
5. Images do not use or establish text binding; as an intervening turn they still invalidate the old binding. Unsupported grammar takes the existing path but must not revive a consumed or invalidated referent.
6. `entries` and `SearchIndex` may diverge. A deterministic fresh view is preferred; explicit conservative invalidation is allowed on a detected mismatch. This is an in-memory consistency promise, not disk hot reload or general snapshot governance. Normal consistent-snapshot follow-up must actually work; universal clarification is not a pass.
7. Evidence in the resolved top-k must not be restricted to old cited IDs. A same-entity source present in the valid catalog but uncited previously must participate when retrieved now; genuine same-scope 0/1 disagreement must enter Q03a conflict and make zero answer calls. This is not a whole-catalog conflict-completeness claim.
8. Both Q03a and the actual answer prompt receive the resolved explicit question and freshly retrieved evidence. Original user text remains in history/display/audit. Prior answer prose/numbers are not copied into the new evidence block. Notes/None retain Q03a's partial behavior instead of blanket refusal.

Items 5-7 incorporate the coordinator's explicit alignment: images invalidate old binding; index mismatch may clarify conservatively; a valid current snapshot cannot avoid successful follow-up or hide an uncited retrieved conflict source.

Refusal invalidation is evaluated for controlled no-evidence/invalid-citation/conflict/clarification paths and any explicitly documented finite recognizer, not as a promise to understand every natural-language model refusal. Valid citation IDs do not establish semantic answer success. This slice must not grow into a keyword-based claim of general refusal understanding.

## Independent cases prepared now, executed only after code freeze

Assets: [grammar fixtures](../test-reports/2026-10-06/Q02a-CR-artifacts/grammar.json), [black-box ChatAgent probes](../test-reports/2026-10-06/Q02a-CR-artifacts/test_q02a_contract.py), [execution notes](../test-reports/2026-10-06/Q02a-CR-artifacts/README.md).

- P01 normal resolution: canonical and alias explicit anchors, both pronouns, all four stages and four attributes; zero rewrite, exactly one answer for clean evidence, current scalar and resolved subject in actual prompt/assessment.
- P02 actual-citation provenance: multiple retrieved candidates with only A cited is valid; B-only/mixed-hero/lineup-only citations and externally supplied history are not.
- P03 raw-miss precedence and fixed clarification: raw miss stays zero-model not-found; nonempty raw plus no valid binding clarifies; no substring whitelist matches or extra second questions enter the deterministic branch.
- P04 lifetime and context: one successful use only; reset, container replacement with equal contents, earlier history edit while the last pair stays intact, clear, metadata edit, incomplete external turn, unrelated turn, provider exception, invalid citation, and images invalidate.
- P05 current-source identity: mutation of canonical name, aliases, structure, facts, notes, constraints, source_ref, and withdrawal invalidate. No requirement to treat score/confidence as truth.
- P06 current retrieval: a previously uncited current same-hero conflicting source must not be filtered out; in-place additions/removals with stale index must either rebuild and detect the conflict or explicitly clarify with zero model calls, never generate the old answer.
- P07 fresh evidence, not answer copying: a previously generated unsupported number with a valid ID does not become the follow-up's evidence; the new prompt must use the current KB scalar. Q03a clean conflicts, notes/None and existing citation rejection stay intact.
- P08 version/provenance gate (to inspect and extend after freeze): v3 opt-in, v1 default, immutable v1/v2 fixtures/cases/hashes/reports, existing production commit and local blob binding, strict metadata, mixed/lazy import rejection, separately denominated synthetic multi-turn results. No human-gold, holdout, provider-quality or full-Q02 claim.

The script intentionally tests observable ChatAgent behavior instead of choosing a private resolver class/attribute name before implementation. Fixed clarification is compared with an independently checked unbound control, not merely any nonempty answer. Old-number exclusion is limited to the new evidence block, not legitimate history text elsewhere. It does not infer an approval decision or edit package data. Fixture entities are synthetic, not game knowledge.

## Baseline expectation is not a bug report

At `e17d937`, Q02a does not exist. Successful deterministic follow-up, accepted-state lifecycle and no-binding clarification probes are expected to fail their future contract; those outcomes would be **planned feature gaps**, not regressions introduced by the implementation. Existing raw-empty zero-generation and original citation/Q03a guards are expected to remain valid. No baseline tests have been executed in this preparation commit. Tests are not marked expected-failure in code, so a frozen implementation cannot hide a remaining failure behind an xfail.

Only Python syntax parsing, JSON parsing and document/path checks are permitted now. They do not establish runtime correctness, fixture retrieval preconditions or passing tests.

## Execution after the coordinator supplies immutable code

1. Pin code/tree and report-only successor; record actual execution root and imported QA module origins. Do not call this report checkout the implementation tree.
2. Keep probe semantics and these expectations unchanged. Validate synthetic retrieval preconditions explicitly; if a reviewer fixture/setup defect appears, retain its first output and distinguish it from a product defect.
3. Execute independent probes with explicit fake clients and network/credential guards. Record actual rewrite/answer counts, resulting assessment, current prompt, evidence and history state. Never substitute author self-tests.
4. Rerun Q03a/grounding, new focused cases, full QA and affected Advisor API checks. Use a complete immutable Git snapshot including Desktop/docs resources when avoiding Windows CRLF; compare bytes against blobs before/after. Preserve every failure and do not weaken expected digests.
5. Independently verify v3's existing source commit/manifests and metrics. Recheck unchanged v1/v2 and all historical Q03a evidence. Source-commit regex alone is not authentication; no remote signature is required.
6. Assign severity only to demonstrated defects within this bounded task. Produce a new source-bound CR decision and local report commit. Publication/integration remains coordinator/user-owned; no approval is inherited from Q03a.
