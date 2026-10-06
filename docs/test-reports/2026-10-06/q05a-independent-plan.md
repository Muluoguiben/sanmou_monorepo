# Q05a independent plan (before author memo / implementation)

Published baseline: `3711e92d38786418e8e955d19a56cd6c72611389`.
Contract: `bcdf07b65440921b1c2a015a432629263ed36205`.
Read complete contract, applicable AGENTS and code-review skill. Reviewer's clean
worktree is isolated on `codex/q05a-season-retrieval-cr-20261006`; old refs retained.
No author memo or implementation was read before freezing this plan.

## Interface and adversarial controls

1. Review fixed memo first: exact public signature/schema, query/tag/top_k types,
   classification/reasons, per-group diagnostic limits and total bound. Do not
   prescribe private APIs. Explicit opt-in facade must reuse original index,
   retriever/chunk/model ranking rather than duplicate it. No default integration.
2. Freeze counterexamples before execution: duplicated IDs across match/mismatch,
   unknown and query-irrelevant entries must reject the whole input before any
   filtering, deduplication or top-k. Do not let filtering conceal global conflicts.
3. Build high-scoring wrong-season candidates that would fill global top-k, plus
   a lower-ranked correct-season candidate. Match pool must filter before original
   ranking/top-k. Each mismatch/unknown diagnostic pool must use original query
   relevance/ranking with at most top_k results, never dump unrelated KB contents.
4. Exact, case-sensitive declared tags only: S1 versus S10/s1, multi-tag entries,
   no alias/NFC/wildcard/time inference. Reject absent/blank/edge-whitespace/non-str
   requests, blank query, bool/float/string/nonpositive top_k. Preserve existing
   model tag-stripping behavior without introducing new normalization or facts.
5. Missing tags and non-lineup entries are unknown with explicit reasons, not
   generic match. Exercise alias query, no match/empty pool and deterministic
   diagnostic caps/order. Preserve source/entry identity and input objects.
   Compare old default retrieval and service outputs against fixed baseline;
   opt-in season matching is not semantic support, human review or permission.

## Baseline migration and non-vacuity

6. Independently rerun published 3711 LF-tree v3 CLI and old quality tests. Freeze
   actual baseline JSON/hash before comparing new output: v3 full SHA must be
   `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`.
   On new production tree, preserve explicit v3 source-drift rejection and logs;
   old v1/v2 refusal semantics remain. No hiding new production files or rewriting
   any old cases/freeze/gold, including claim_spans_v1. CLI default remains v1.
7. v4 inherits all v3 top_k, queries/evidence labels, scoring/assessment fixtures,
   nine multi-turn controls and original metric definitions. Compare every
   inherited retrieval/mock/assessment/multiturn/provider/holdout report field
   deeply; allow only explicitly listed version/fixture/production/eval-source
   metadata and separate new season controls, never broad metric exclusions.
8. Test all v4 required assessment/multiturn groups and real multi-turn branch.
   Audit old test_quality_eval migrations: retain original assertions and coverage;
   fixture drift/file add-delete-edit/manifest/mixed-root/lazy foreign-module
   negative controls must reach their intended guard, not pass because v3 rejects
   the added production module first. Pin/rebind unaffected prerequisites for each
   independent negative control and inspect the actual reason/path.
9. Require production code fixed before mechanical v4 source/freeze generation;
   verify manifest against actual Git bytes and actual imported roots before/after
   lazy evaluation. New expected labels remain independently declared, not generated
   from implementation output. Source hashes are not signed identity authentication.
10. Rerun unchanged Q04 CLI: all old 12 controls and the entire non-eval_source
    report must match baseline. Audit only exact runner/new-module source entries
    and aggregate digest changes; record honest new full hash, no old-hash reuse.

## Narrow exceptions and final evidence

11. Only extra test repair: test_lineup_frame_extractor's three Image.open handles
    become context-managed; inputs/assertions otherwise identical. Capture warning
    behavior and rerun original assertions to prove handles close, retaining prior
    warning history. This is resource hygiene, not new retrieval capability.
12. Only CI addition: existing Windows step after Q04b with exact contract command
    for test_seasonal_retriever plus test_quality_eval. Inverse removal must restore
    full original workflow bytes/YAML; no dependency/permission/job/runner changes.
13. At fixed source run independent controls, new/v4/Q04 CLIs, targeted and full
    QA/Pioneer/common, H07/H10/H09; source-bind actual logs/counts/skips. Crosscheck
    immutable author report after own execution. Final native gate belongs to
    exact published SHA/attempt: original Windows25 plus new targeted names from
    final AST, each ok/zero skip, all four jobs. No local native dependency probing.

Reviewer never repairs production/CI code or changes old assertions/gold. Freeze
probes before runs, retain actual reds and unchanged repair oracles; bounded plain
evidence only. No main/WIP/push, Q06 payload/ancestry or old archive body/member,
provider/network/game/bridge/.env/credentials/install/KB publish/deployment access.
No new framework or repeated historical probe matrix. Next: send plan SHA, review
fixed author memo for contract blockers/necessary clarification, then await code.
