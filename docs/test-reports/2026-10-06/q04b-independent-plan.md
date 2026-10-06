# Q04b independent plan (before author code review)

Published baseline: `b37e7ed34e5c9df63d668349436b198bd8b0b27d`.
Contract: `b41aae48bd0b14fdb2ea343183d4cecce253d94d`, tree
`3a1e079d400fb988301ee4a3509e4234b97d2754`.
Clean reviewer worktree reused on `codex/q04b-native-claim-spans-cr-20261006`;
old refs preserved. Read AGENTS, code-review skill and full Q04b contract.
No author implementation or new self-report inspected before this plan.

1. Review immutable source SHA/tree only. The sole code delta must be the exact
   three-line Windows Q04b step specified by the contract, immediately after H09
   and before Desktop dependencies. Removing it must restore the entire baseline
   workflow bytes and parsed YAML, including all steps, dependencies, jobs,
   permissions, environment, actions, runners and timeouts.
2. Packages tree must remain `e849545fc31473d68835618c2c13ec44c35788c0`.
   Compare original test module bytes/AST: exactly the same 25 qualified test
   methods and assertions, including real CLI/create-only coverage, no skip changes.
3. On fresh fixed-source LF checkout with existing dependencies, independently run
   new module 25, old quality module 23, full QA 419, real new CLI/create-only
   coverage and old v3. Record actual commands, exits, skips and source binding.
   Current v3 full SHA must stay
   `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`;
   retain old v1/v2 frozen rejection semantics. Do not repeat Q04a public probes,
   old large harness matrices, or create a new framework for this CI-only change.
4. Crosscheck author's immutable report, manifests and raw log hashes/counts with
   independent execution before scoped code/wiring approval. Preserve any real
   red evidence; do not alter old tests, labels, expected metrics or fixtures.
5. Native status remains pending until coordinator verifies final published exact
   SHA/attempt: Hosted Windows Q04b step has all 25 original qualified names each
   ok, Ran 25, exit 0, zero skips/failures/errors, and the same run's four jobs
   succeed. Linux or old H10 native evidence does not satisfy this gate.

Reviewer writes only plans/probes/bounded plain evidence, not product or CI code.
No main/WIP/push, dependency installation or further local native exploration.
Keep prior zero-tests native environment-blocked record and Q04a reviewer-tool
correction history unchanged. No provider/network/game/bridge/.env/credentials,
KB publication, Q06 payload/ancestry, archive body/member reads or new archives.
Next: send plan SHA, then wait for fixed author code and source-bound self-report.
