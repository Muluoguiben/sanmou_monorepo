# QA development evaluation v1

Scope: Q07/Q-E0 offline lexical retrieval measurement and scorer validation.
Run from `packages/qa-agent` with `PYTHONPATH=src python3 -m
qa_agent.quality_eval.runner --output /tmp/qa-eval-new.json`. Output creation is
exclusive: preserve prior results rather than overwrite them.

## Frozen identity and split

`freeze.json` pins baseline 965ef6713b58048c0765654e8061c5cffda6c59d,
all production Python files and all KB YAML files by relative path and SHA-256,
plus the exact cases file. Text uses UTF-8 (BOM removed) and LF-normalized bytes;
this is a portable content digest, not a raw checkout-byte hash. Results also
hash the evaluator source. The report binds these manifests to a real code commit.
Changes to KB, production source, queries or labels fail closed; a future baseline
needs a new reviewed version, not silent re-freezing in this runner.

All 12 queries and eight synthetic answers are **developer-authored development
fixtures**, not human-approved gold or an independent holdout. Evidence labels
bind entry ID, source_ref and answer-lines digest to the frozen KB. KB presence
is not independent verification of game truth. Query relevance labels have not
been independently reviewed. The two history-bearing queries measure raw lexical
follow-up retrieval only; they do not execute or evaluate model history rewriting.
The no-answer case is a deliberately unrecorded token, not broad OOD coverage.

## Scoring definitions

- Recall@5 per answerable query: relevant IDs retrieved / labeled relevant IDs.
  Macro recall averages answerable queries; no-answer rows have null recall.
  MRR averages reciprocal first relevant rank, zero for answerable misses.
  Reports split retrieval by canonical/alias/natural/season/coreference/topic-switch.
  nDCG is absent because graded relevance labels are absent.
- Citation-ID validity: valid citation occurrences in actual answer text / all
  citation occurrences. Zero citations is null, never a perfect pass. Evidence
  candidates alone cannot satisfy this metric. Syntax matches the current ChatAgent.
- Claim support: externally adjudicated supported claims / adjudicated claims.
  Unknown or unreviewed claims are excluded and reported separately. This function
  does not perform semantic inference or keyword matching. Developer-authored
  synthetic verdicts test arithmetic and failure behavior only.
- Supported citation completeness: supported and reviewed claims citing every
  labeled supporting ID inside their own span / all factual claim spans.
  Unknown, unsupported, unreviewed and uncited claims cannot increase the numerator.
  Spans must cover the entire exact answer without gaps; annotations bind the full
  answer, query/history context and all supplied evidence text hashes. Nonclaim segmentation and semantic
  verdict correctness still need an independent human audit; metadata is not proof
  of an authenticated reviewer. No arbitrary answer is auto-promoted to gold.
- Refusal precision: correctly refused / all refused; recall: correctly refused /
  all expected refusals. The scorer requires explicit boolean judgments, never a
  refusal-keyword heuristic. No provider refusal score is measured in this batch.
- Context correctness: externally labeled correct turns / judged turns, distinct
  from fact support. A true fact answering the old topic remains supported but
  contextually incorrect. Unknown or unreviewed context labels are unscored.
- Multiturn: wrong antecedent and stale-topic synthetic labels exercise scorer
  behavior; raw retrieval rows expose follow-up limitations. Full conversation
  success is unmeasured. Existing ChatAgent empty-evidence zero-generation tests
  remain part of full QA regression.

Quality thresholds are **unset**, to be agreed before a future independent holdout
is observed. Provider generation/semantic quality, contradiction disclosure,
independent holdout, calibrated judges, and live cost/latency are unmeasured.
Mock scorer passes do not demonstrate model quality. No models, .env credentials,
network, game controls, publishing, retrieval changes or vector database are used.
