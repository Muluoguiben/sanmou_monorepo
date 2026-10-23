# Q02a: bounded hero-attribute referent resolution

Date: 2026-10-06. Base: `e17d937a39944b036e90701fecefb6611b1d88d6`; GitHub CI 37341606212 completed successfully in all four jobs. Q03a is closed as a bounded offline slice; the full Review route continues.

## Scope

Implement deterministic subject binding for a finite complete grammar: 他/该武将 + 初始/基础/满级/成长 + 武力/智力/统率/先攻 + 多少, allowing deliberately documented punctuation/particles. No general coreference, images, plural/comparison, season/condition NLU, skill references or recovery of raw retrieval misses.

Current real-KB read-only probes show a useful case: `他的满级智力是多少？` and `他的初始武力是多少？` retrieve background mechanics without the subject. `再详细说说他` has no raw evidence and remains refused with zero rewrite/answer calls.

## Required behavior

1. Perform original raw retrieval first. An empty result keeps the existing no-evidence refusal and zero rewrite/answer rule, even when a referent was previously accepted.
2. Create a private accepted referent only from the last completed explicit, unique hero-subject question and the answer's actual valid citations. All retrieved IDs are not accepted citations. Never infer entity from generated prose or treat history as factual evidence.
3. Bind canonical hero identity, cited current-source content/identity fingerprints and the last completed user/assistant turn. Reset, modified/replaced/cleared history, withdrawn/changed cited source, unrelated topic, refusal/conflict/invalid citation all invalidate the prior binding. Externally supplied history cannot establish a binding.
4. On a supported follow-up with a valid binding and nonempty raw evidence, skip LLM rewrite and deterministically re-retrieve from current KB using the resolved explicit question/entity. Feed that same resolved question to Q03a and the answer prompt; retain the original question for display/audit. A new source must not be ignored merely because it was not cited previously. Returned evidence remains top-k bounded, not a whole-KB conflict proof.
5. Supported follow-up without a unique valid binding returns a fixed clarification and makes no rewrite/answer call. Unsupported grammar stays on the legacy path and is explicitly outside this slice. Images do not establish or consume this text-only binding.
6. `Retriever.entries` and its index can diverge if mutated. Explicitly validate/rebuild the current retrieval view for this path or conservatively invalidate; do not call an old index a fresh snapshot. Avoid general snapshot governance redesign.
7. Preserve MCP/QueryService/common/Pioneer contracts, formal KB and existing citation gates. No real provider calls, credentials, model inventory, game/control operations, knowledge publication or new dependencies.

## Ownership and artifacts

- Implementation: existing `/root/q03a_implementation` agent, reused clean worktree `C:/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo`, new branch `codex/qa-referent-q02a-20261006`. The legacy directory name does not identify the source version; exact commit does.
- Independent CR: `/root/rag_eval_review`, separate worktree after code is frozen; coordinator owns master integration.
- Scope: QA private resolver, ChatAgent wiring, tests and explicit development baseline v3. Any extra source change needs a concrete necessity and review. Source-bound report required before CR; exact commands, environment, counts, negatives, hashes, limitations and first failures retained.

## Acceptance and evaluation

- Actual ChatAgent + fake clients: alias first question, single-cited entity among multiple candidates, multi-entity ambiguity, invalid citation, raw miss, fixed clarification, resolved prompt/assessment, re-query conflict, reset/history mutation, source change/withdrawal, topic switch and unsupported grammar.
- Explicit zero is known; new comparable same-entity 0/1 source evidence must trigger Q03a conflict without answer generation. Old answer numeric content is never copied as current evidence.
- Existing Q03a and grounding regressions remain. Full QA, focused new/old cases and affected Advisor API checks must pass; native skips must be explicit.
- New `--baseline v3` is opt-in. Default remains v1. Historical v1/v2 fixture bytes, source hashes and reports are immutable and correctly reject new production drift. Keep original query/top-k/labels/scorer definitions; add separately labeled developer-authored fake-client multi-turn cases with explicit count/denominator.
- Freeze v3 only against an already-existing production commit; verify real imported source roots and actual Git/blob binding independently. No auto-latest, expected-hash weakening, human-gold claim or provider-quality claim.

After independent APPROVE, coordinator reruns the exact combined source, scans publication scope, integrates/pushes under the verified same-route standing authorization and checks exact-final-SHA CI. Q02a success does not mark full Q02, general semantic correctness, independent holdout or production readiness complete.
