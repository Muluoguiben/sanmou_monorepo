# Q05a independent review — APPROVE (fixed source / Linux)

Reviewed source `3d8257bf03d47bb86fb80994c924987033b1858a`, tree
`0aa22ba210af5fb112b9ad073939428961511b4d`. No actionable product finding remains
within the frozen Q05a slice. Final combined-tree and Hosted Windows acceptance
remain coordinator gates; this is not semantic-quality or production-readiness approval.

Plan `f6b42207200d25628d70db83119599f18e115238` preceded author memo/code inspection.
Public controls `356f09f02ba5fb8923e2bf4f706293edfe21b0dd`, v4 controls
`b9f2fc5d8ef0c208cd73f83f513187c76bf3ce2f`, and resource/baseline controls
`c5dcdeacc1c54b53c7ac57a9867e9cf706fcc217` were frozen before implementation review.
The code-review skill guided adversarial controls, exact-source regression and
source-specific severity assessment; no external paid consultation or code repair.

## Scope and substantive checks

Read the fixed facade, season evaluator, runner changes, dedicated tests, all new
season controls, freeze binding, old-test migration, image-handle change and CI step.
The full package/workflow diff matches the allowed ten paths. Existing default
retriever/index/model/ChatAgent/QueryService/MCP/KB/Pioneer/common and old scoring/
v1-v3/claim_spans_v1 fixture bytes are unchanged. No default seasonal integration.

The facade passes the whole input to original SearchIndex before grouping, then
uses original Retriever independently for each pool. Frozen independent controls
prove that baseline global top-2 is filled by wrong-season entries while a correct
lower-ranked entry is recovered by prefiltering. Cross-pool and query-irrelevant
duplicate IDs still reject. Exact S1/S10/s1 and Unicode tags, multi-tags, model tag
stripping, alias query, empty/unrelated pools, strict parameter types, per-pool
limits, source/object identity and unchanged default results passed. Unknown
reasons distinguish non-lineup from missing tags. No season inference or authority
upgrade is introduced; three groups total at most 3*top_k.

The v4 tests exercise valid baseline prerequisites before each altered fixture.
Malformed season schemas, missing assessment/multiturn/season groups and a real
foreign lazy season module fail at their intended guards, not an earlier source
or fixture drift. A valid but wrong expected result produces a saved failed-season
report and exit 1; repeating against the same output raises FileExistsError and
preserves bytes. Old metrics and quality_threshold=None remain unchanged.

## Source/freeze and compatibility proof

Fresh LF tree `/tmp/q05a-cr-3d8257b-20261006`; 904 ordinary Python/JSON/YAML package
inputs were checked against exact Git blobs. v4 freeze references pre-existing
`27b73de689cc5863ed02a0dd30526fde8533d080`; its entire production manifest matches
that commit and tested source, with no src diff from 27b to 3d. KB and manifest
aggregate digests were independently recomputed. New expected labels were not
generated from implementation output.

Published 3711 was independently rerun before implementation review: quality23,
v3 CLI and Q04 CLI all passed. The actual baseline JSONs and raw command evidence
are recorded in `q05a-independent-baseline.md` and its results directory.

- Old v3 full SHA256:
  `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`.
- New v4 full SHA256:
  `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`.
- Old Q04 full SHA256:
  `c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120`.
- New Q04 full SHA256:
  `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`.

v4 cases inherit every v3 field except version and additional season_cases. The
whole old/new report projection matches outside exactly protocol, baseline_commit,
cases_sha256, production, eval_source and season. This includes retrieval,
mock_scoring_only, assessment, all nine multi-turn controls, provider/holdout,
refusal, quality_threshold and permissions. Current v1/v2/v3 retain actual exit-1
source-drift refusals; old successful v3 hash is never presented as a new-tree pass.

Q04's entire non-eval_source report is identical, including all twelve controls
and fixture metadata. Only runner.py hash and added season_cases.py entry change
the source inventory; all other entries are unchanged. The new aggregate digest
is `362d033dc66962b43aa3c09a9add9fbaff321f3c64ccb9416b656b9818d91b99`, verified
against actual Git-checked files. Detailed projections are in comparisons.json.

Old quality-test ASTs are unchanged except exact v3-to-v4 call/fixture-path
literals; the original v3 schema tests remain. Only one new v3-rejection method
is added. The image test differs only by the approved context-managed open;
original assertions pass and independently captured ResourceWarnings fall from
exactly three at old line 172 to zero. This is resource hygiene, not retrieval
capability. Removing the unique new Windows step restores whole workflow bytes
and parsed YAML; its position is immediately after Q04b and all other settings remain.

## Independent execution and author audit

| Gate | Result |
| --- | --- |
| Public seasonal controls / v4 integration controls | 5 / 4 passed, zero skips |
| Original crop assertion plus warning capture | 1 passed, zero ResourceWarnings |
| Q05 targeted | 44 passed: 20 season + 24 quality, names exactly match Git AST |
| Original Q04 / H07 / H10 | 25 / 35 / 32 passed, zero skips |
| Full QA | 440 passed |
| Full Pioneer | 1085 total: 1083 passed, original 2 Windows-only skips |
| Full common | 2 passed |
| Real v4 / Q04 CLI | 8 season controls / 12 claim controls passed |
| Real H09 CLI | 8 controls: 2 goal successes, 6 expected safety stops; no infra/safety violation |
| Current v1/v2/v3 CLI | Required exit 1; source-drift refusal logged, not a pass |

H10 ran RuntimeWarning-as-error; its raw log has no RuntimeWarning/never-awaited
lines. No skips are counted as passes. Exact argv/cwd/PYTHONPATH/count/exit/skip/
log hashes are in `q05a-independent-results/summary.json`; the raw logs retain
original whitespace. Full JSONs remain at `/tmp/q05a-cr-3d8257b-rerun-results/`.

Author handoff `17e82effff23e8701629c0cbdd5e3f611ada3853` changes only docs relative
to tested packages/workflow. Independently checked fourteen final raw log hashes,
byte counts, unittest summaries, actual exits, targeted names, four baseline logs,
deterministic v4/Q04 hashes and H09 totals against our runs. Author report does
not substitute for the runs above. Audit evidence: author-crosscheck.json.

## Preserved failures and reviewer-oracle corrections

The original b9f2fc5 v4 probe appended a nonexistent expected ID, which the accepted
memo explicitly treats as malformed. Unchanged execution on fixed 3d produced
four tests / one failure because no report was correctly created after
`expected ID not in input entries`. Actual stdout/stderr is retained verbatim in
`q05a-original-v4-oracle-red.log`. Commit `51497c3341e5ad2062ac4922c9b6e216c5f52d79`
only changes that input to remove an existing declared match ID, with an added
nonempty precondition; all original failure-report/exit/no-clobber assertions
remain. All four corrected probes pass on the same unchanged product source.
This is reviewer oracle construction correction, not product repair or relaxed gold.

Initial final verifier cf4722d stopped before tests because its AST migration
normalizer handled standalone v3 but omitted the exact fixture-path literal.
The narrow approved path mapping was added in cad3ec7; original source and explicit
diagnostic remain in `q05a-verifier-construction-notes.md`. No old assertion changed.

Author's earlier mixed-EOL/diff-check failure at 9b7eb40, separate LF-restoration
commit 27b, and 43-tests/one-error pydantic.root_model lazy-cache test contamination
are retained. Their three named original logs were byte/hash checked. The latter
fix only restored the targeted sys.modules entry in a new test; source-mismatch
and zero-call assertions remain, and a real CLI negative test was added. These
pre-freeze results are not final-source validation. Known early shell exit-code
ambiguity is disclosed by author; our direct subprocess refusals have exact exits.

## Remaining gates and boundaries

Native Q05 is not executed by reviewer. Final exact published SHA/attempt must
show original Windows25 and the new 44-name targeted group all ok/zero skips,
plus all four jobs successful. Prior Q04b native25 is not Q05 native evidence.
No local native dependency probing/install, real provider, game/bridge, .env or
credential access, KB publish, deployment, push or main/WIP change was performed.
No Q06 payload/ancestry or archive body/member reads; Q06 remains paused.
All evidence is bounded plain text/JSON. Label applicability does not certify
semantic support, human review, holdout quality, source signatures or execution rights.
