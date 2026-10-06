# Q04b independent review — APPROVE (code/wiring; native pending)

Approved source `ebcd5d12546dc66044d0485089a10e2bdc43e4a8`, tree
`e6244518555af134d97c7b952be286b71500ac04`. No actionable finding in the frozen
CI-only scope. This is not final native acceptance or combined-tree approval.
Plan `64666ca0653a09a9e41e0861ce0ace292ea60044` was committed before author code
inspection; verification script `658caf58723f0aa0928246f84e63c8fb53e2134d` was
frozen before execution. The code-review skill guided exact scope/provenance and
regression checks; no implementation repair or external model consultation.

## Exact wiring and protected behavior

The sole code delta is the contract's three-line Windows Q04b step. It appears
exactly once, immediately after Windows H09b and before Desktop dependencies.
Removing it restores baseline `b37e7ed34e5c9df63d668349436b198bd8b0b27d` workflow
bytes and parsed YAML in full. Dependencies, actions, runner, jobs, permissions,
environment, timeouts, comments and all other steps are unchanged.

Packages remain `e849545fc31473d68835618c2c13ec44c35788c0`. The original test file
bytes/AST/25 qualified names and assertions are unchanged, including
`test_real_cli_create_only_and_explicit_version`. All 25 names in independent and
author raw test logs match the fixed AST exactly, each with an ok result; no skip
or weakened assertion. The new command selects the intended module, not zero tests.
899 ordinary package Python/JSON/YAML inputs in the fresh LF tree were verified
against their fixed Git blobs; no archive content was inspected.

## Independent execution and author crosscheck

Source checkout `/tmp/q04b-cr-ebcd5d1-20261006`; existing dependency directory
`/tmp/sanmou-cr-20261005-6155-deps`. Full argv/cwd/PYTHONPATH/exit/count/skip and log
hashes are recorded in `q04b-independent-results/summary.json`.

| Verification | Result |
| --- | --- |
| Exact new Windows command, run on Linux | 25 passed, zero skips, exit 0 |
| Original quality-eval module | 23 passed, zero skips, exit 0 |
| Full QA | 419 passed, zero skips, exit 0 |
| Real new CLI | 12/12 synthetic controls, exit 0 |
| Repeat CLI against same output | Expected FileExistsError / exit 1, original bytes unchanged |
| Original v1 / v2 CLI | Expected frozen-production-drift refusal / exit 1 |
| Original v3 CLI | Exit 0, current full hash unchanged |

Current v3 SHA256 remains
`db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`.
New CLI SHA256 remains
`c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120`.
Raw JSONs remain in `/tmp/q04b-cr-ebcd5d1-results/`; bounded plain logs and summary
are committed. Raw log whitespace is deliberately preserved. No unexpected red
occurred; three exit-1 controls are required refusals, not hidden failures.

Read fixed author report `a9abfee3290406c3d8e9fc54da200b3ecb1f4a02` and checked its
eight raw Gitblob logs against manifest bytes/SHA256/counts/exits. Source/tree,
unchanged packages/workflow, 25-name inventory and deterministic CLI/v3 hashes
match independent results. See `author-crosscheck.json`; author report commit has
no package or workflow difference from tested code. No old Q04a probe matrix was
rerun, copied or changed, and prior reviewer-tool corrections remain historical.

## Native and authority boundaries

Native remains pending: coordinator must verify final published exact SHA and
attempt, all 25 Hosted Windows qualified names each ok, Ran 25 / exit 0 / zero
skips, and all four jobs successful in that same run. This Linux run cannot
replace that gate. The prior local Windows missing-yaml / zero-tests record is
unchanged; no new local native dependency exploration, install or mock was used.

No product/test/fixture/CI implementation edits by reviewer; no main/WIP changes,
push, network/provider/game/bridge/.env/credentials, KB publishing, installation,
deployment, Q06 payload/ancestry or archive body/member reads. Q06 remains paused.
Approval grants no semantic quality, human-review, holdout or execution authority.
