# Q03a CR repair — source-bound author verification

Date: 2026-10-05. Repairs CR01–CR03 from independent review
`a10472972de2e6a5fca675b363f086ab1372e003`. This is author verification,
not independent approval. No push, merge, live provider, credential read,
knowledge publication, or game control.

## Frozen code and explicit baseline history

- Prior report/code: `50b8ff032af9639da38228c84fedebf2dcd5d9cc` / `3f81519d34063d438af918a3750bcc38a535b6b7`.
- Production applicability repair: `2af538b4f9cf03a7757a158dc59b1af6143c4af7`, tree `41fbcad4eb5efed1fdfe3f07fa056cd0f0a8ccb9`.
- Final evaluator/tests/v2 rebind: `3b2b137679bd6b72a5681874bf9ab6ea0ac8f0c9`, tree `ec1d8f04ff42156c90a151b4d0e4c3fbddf765c6`.
- Branch: `codex/qa-evidence-q03-20261005`; commits remain local.

The production commit existed before rebinding unpublished v2. Only the
assessor file hash, production aggregate and baseline_commit changed in its
freeze; cases_sha256, original 12 queries/top-k/scorer labels and 6 synthetic
assessment cases are unchanged. Original v2 history remains in Git at
`b4a5a2d420b2c876293b4bcbe4d6d888fb94bb75`; no history was rewritten.
v1 remains byte-identical and default v1 rejects the new source tree.
Final production digest: `db41262f5574872c4304b752e74e6099056d310b12eb3e0dce71028e3261a804`.

## Repairs and explicit limits

CR01: before evaluating, load the lazy assessment dependency and verify every
loaded `qa_agent` module's resolved file/spec origin and package search path
against the selected package. Repeat after evaluation to cover further lazy
imports. An importlib-loaded B runner with A dependencies now raises
`ValueError: QA execution source mismatch` before retrieval/assessment; no
B-identity result is returned. This is a local module-origin restriction, not
protection against deliberate in-process code monkeypatching or remote signing.
The forty-hex baseline_commit check is still format validation, not Git
authentication; actual provenance is established by existing local commits
and the source manifests, not claimed to follow from regex validation.

CR02: validate corpus shape before execution: strict int version/top_k (bool
and float rejected), positive top_k, version-specific required nonempty suites,
nonempty unique IDs, valid query/evidence identity and assessment inputs/output
shape. v2 may not omit or empty assessment_cases. Hashing malformed data is no
longer sufficient to admit it. Scoring logic and source/KB drift guards remain.

CR03: empty constraints no longer certify comparable applicability. Arbitrary
profile notes are conservatively unassessed; explicit scope cues in facts and
all constraints also prevent hard scalar comparison. Diagnostics and the actual
prompt retain entry/source-bound qualifiers. Missing scalar reasons survive
this downgrade; no claim that notes lack an answer is made. Clean bounded
scalar controls still compare zero/equal/conflicting values.

This is intentionally not generic NLU/Q05: the fact-cue recognizer is finite,
and arbitrary facts are not semantically proven scope-free. All notes are
conservative, even apparently benign notes. `supported` still only denotes the
bounded scalar check, not source truth. Skill/faction fields, general semantic
entailment, provider quality, human gold and holdout remain unaccepted.

## Immutable CR replay

The three scripts were copied read-only from the reviewer worktree into
`Q03a-repair-artifacts/`. No root edits were necessary: their relative-root and
runner-derived discovery resolve this worktree. Source and copied SHA-256 are
identical:

| Script | Original = copied SHA-256 |
| --- | --- |
| mixed_import_probe.py | `565c67da5b63bac8209194372d79b2b898a885a4be3f7372bdf3288112c4f1e8` |
| test_independent_q03a.py | `9d4ab6c15bad527c665117c0de29f445582957bdafacfc687404631685c4dd3e` |
| test_q03a_extra.py | `85cdf0e1b9832602445600e0ec0b62284f71a4f03750a1153d6f95e97a5faa55` |

Pre-repair independent replay: **17 tests, 6 failing assertions, exit 1**.
These reproduce five schema failures plus the disjoint-notes scope failure.
Pre-repair mixed-import replay ran the original probe against the immutable
reviewer tree; it returned the B digest under A code with Recall 0/11, then
the probe deliberately exited 1. It never edited the reviewer tree.

Post-repair unchanged mixed probe exits 1 because the runner raises the expected
source-mismatch ValueError; this expected rejection is not a failed quality run.
Post-repair copied independent unit suite: **17 tests, OK, exit 0, 0 skips**.
Persistent red/green outputs accompany the copied scripts. No CR-owned file
was edited or merged. Independent re-review of the new SHA is still required.

## Reproducible verification

WSL root: `/mnt/c/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo`.
All commands use `PYTHONDONTWRITEBYTECODE=1`, Python `-B`, and no real model.

From `packages/qa-agent`:

```bash
PYTHONPATH=src:../sanmou-common/src:tests python3 -B -m unittest \
  test_evidence_assessment test_quality_eval \
  test_review_d_regressions.ChatGroundingRegressionTests -v

PYTHONPATH=src:../sanmou-common/src:../../docs/test-reports/2026-10-05/Q03a-repair-artifacts \
python3 -B -m unittest test_independent_q03a \
  test_q03a_extra.ApplicabilityBoundaryTests -v

PYTHONPATH=src:../sanmou-common/src:tests:/tmp/sanmou-cr-20261005-6155-deps \
python3 -B -m unittest discover -s tests -p 'test_*.py' -v

PYTHONPATH=src python3 -B -m qa_agent.quality_eval.runner \
  --baseline v2 --output /tmp/Q03a-repair-v2.json
PYTHONPATH=src python3 -B -m qa_agent.quality_eval.runner \
  --output /tmp/Q03a-repair-v1-should-not-exist.json
```

| Verification | Result |
| --- | --- |
| Focused final | 44 tests, OK, exit 0, 0 skips; 15.516 s |
| Copied independent negatives | 17 tests, OK, exit 0, 0 skips; 13.715 s |
| QA full final at 3b2b137 | 367 tests, OK, exit 0, 0 skips; 100.476 s |
| Explicit v2 CLI | exit 0; 12 retrieval rows, 6 fake-client gate rows; Recall/MRR 10/11 |
| Default v1 CLI | expected exit 1, source drift, no result file |

From `packages/pioneer-agent`, reused dependencies are read-only:

```bash
PYTHONPATH=src:../qa-agent/src:../sanmou-common/src:tests/unit:/tmp/sanmou-cr-20261005-6155-deps \
python3 -B -m unittest test_advisor_api -v
```

Cross-package **6 tests, OK, exit 0, 0 skips**, 2.400 s. Existing Windows checkout
shell CRLF was temporarily normalized only after verifying index and normalized
blob `44863bc50e518673e6cc0a8705ff6c51a5ca42e8`; raw LF hash matched the same
blob. Original CRLF formatting was restored after full tests; no script diff
or production change was included. This known environment correction is not
a test expectation/digest change.

## Raw log identity

Red/green independent logs are persisted in the sibling artifacts directory.
Full/focused/cross logs remain local temporary files; hashes are not signatures.

| `/tmp/` filename | SHA-256 |
| --- | --- |
| Q03a-repair-red.log | `42d9abf8a1b92c85c9c3fd7fa227d0acb0a223abbaa55f603a38230832ebbfce` |
| Q03a-repair-mixed-red.log | `d4c47cd91f1772679f790fa68a6093fa8f82c23577919bab3beb9d7afecd3429` |
| Q03a-repair-mixed-green.log | `ec4eafc9f8d4345c5282ee59fdd5dc97545ec64f01b2e885190ace852eb76a64` |
| Q03a-repair-independent-final.log | `a330a39e713e64ff4c398d8cff79a9d2479389640178c45bd108bd17e63340d0` |
| Q03a-repair-focused.log | `104c66b9717a327dc0fe7732966bd6ae79abe8d1d83a53c7242bab8e8ffa2fae` |
| Q03a-repair-full.log | `008a9bf3a9d7be359a941a1dfb90bcd34db308f83fb4d63b35bb7fb8724cf6de` |
| Q03a-repair-cross.log | `62780e8d5b35addfea1f3bcdd6789987d6de0358820846459c8d0ac0c986e5f4` |
| Q03a-repair-v1-rejected.log | `b3876301b37cfe585c98956040d75fa240e01ab392cc12995fa1484783063b97` |
| Q03a-repair-v2.json | `66b7b504951f69c0bcc19de7d699d8cc00a506cddc74c3ce4894ee14740ae425` |

Old Q03a report/red logs, v1, previous C/CR/integration reports and v2 cases
have empty diff. Formal KB, QueryService/common/MCP public contracts, providers,
Pioneer and publication permissions are unchanged. This report requests exact
SHA re-review; it does not declare the prior REQUEST_CHANGES resolved by fiat.
