# D — QA integrity hardening self-test, 2026-09-08

## Identity and scope

- Task: `01a07f0b-53b8-74a3-9e61-71dd461bdff8`.
- Worktree: `C:\Users\Lan\.codex\worktrees\0788\sanmou_monorepo`.
- Branch: `feat/qa-review-d-20260908`.
- Start: `d377ef8bbaa69e6b25928255eac0cb62714e82f8`, clean detached HEAD before creating this branch.
- Frozen charter/report: coordinator commit `dd76d601f6f40d3e4fceaf10cdd360d78af88cb2`, read from the main checkout without merging it.
- Tested implementation/test tree before this report and TODO: `8acb0b599b20a25630993f35d07df0e78bd964cd` (Git tree object, not a commit). Final commit adds reporting only to this tree; obtain its immutable SHA from the delivery message.
- Owned findings: R04/R09/R10/R11/R12/R25/R26. No changes to Pioneer, shared common, MCP catalogs, GUI, execution, decoded research, or shared-memory.

## Changes and reproducible evidence

| Finding | Fix | Regression evidence |
| --- | --- | --- |
| R04 | `run_video_pipeline` writes `video-staging-pending.yaml` with original normalized metadata. It neither grants REVIEWED nor publishes a KB. Combat candidates remain in `video-knowledge.yaml`, not a loader-compatible formal KB. | `test_run_video_pipeline_cli`: real heuristic sample produces pending entries; calling the actual default `publish_staging` CLI on that output publishes 0 and skips all. `to_reviewed_entry()` rejects each item. A separately injected synthetic combat candidate remains in extraction output and produces no KB. |
| R09 | Empty initial retrieval returns exactly `知识库暂未收录此问题。`, with zero answer/query-rewrite calls and zero answer token/time counters. Generated answers require at least one bracketed citation, and every cited ID must belong to the current retrieval. Invalid output is not persisted in conversation history. | `ChatGroundingRegressionTests`: empty KB across two turns; unrelated populated KB plus previous grounded history; valid current ID; invented, missing and stale/partially-valid citations. |
| R10 | Publisher plans across all YAML buckets, resolves a canonical ID globally, removes its former positions, and writes the new bucket once. Topic fallback preserves an existing canonical ID within the same domain/kind; ambiguous multiple IDs abort before writes. Loader and direct SearchIndex reject duplicate IDs. | `KnowledgeIntegrityRegressionTests`: command-to-active migration with same and new incoming IDs; latest facts/source retained; old bucket empty; query returns new facts; duplicate loader/index refusal; conflicting IDs leave all files byte-identical. Existing reviewed-publish/query tests also pass. |
| R11 | Compute a maximum attribute only if both its base and growth are known. Explicit zero remains valid. | Mixed partial input yields military=190, command=0, intelligence=None, initiative=None. |
| R12 | After list whitespace normalization, explicitly reject an empty facts list. | Empty, ASCII whitespace, tabs/newlines and ideographic-space facts fail validation; mixed facts normalize and remain queryable. |
| R25 | Reject symlinks, Windows reparse points, non-regular and multi-link files; check every path component and resolved containment. Read head and hash through one opened descriptor, comparing its identity to pre/post path checks. Version metadata uses the same reader. Excluded directory names compare case-insensitively. | Synthetic private-file symlink, directory symlink, outside-root link, version-file link, hardlink, check/open replacement, and valid file hash/head/size. Executed on WSL Linux; no skips. |
| R26 | Payload filenames reuse the existing separator-neutral `_binary_name` helper. | Windows drive path, UNC, WSL/POSIX path and bare basename all yield only `hero.bytes` on Linux. |

The implementation files are `app/run_video_pipeline.py`, `chat/agent.py`,
`index/search_index.py`, `ingestion/{publish,normalize,client_package,client_lua_crypto}.py`,
`knowledge/{loader,models}.py` under `packages/qa-agent/src/qa_agent/`.
Tests are `test_review_d_regressions.py` and `test_run_video_pipeline_cli.py`.
The only KB edit removes the stale `hero-皇甫嵩` block from `profiles/heroes/minor.yaml`.

### 皇甫嵩 deduplication evidence

The retained `qun.yaml` record matches the already committed raw record in
`ingestion/raw/heroes/sgmdtx-all-heroes.yaml:2221` (source SGMDTX, captured
2026-04-09T19:17:08): orange rarity, 群雄→群 faction, cavalry, 平乱定叛,
base 72/81/93/23, growth 1.27/0.76/1.74/1.33, and the existing source notes.
The stale minor record has identical identity/tags and subset notes, but null
attribute fields and a stale missing-attributes constraint. Its orange rarity
also selects `qun.yaml` in the existing bucket resolver. No new fact, source
claim or external freshness verification was added; the retained record was
not rewritten or re-published. Conflicting canonical IDs in new input block.

## Environment and exact commands

Windows host with WSL2 Ubuntu, Linux `6.6.87.2-microsoft-standard-WSL2`.
Tests ran on CPython 3.12.3, GCC 13.3.0. Venv:
`/tmp/sanmou-qa-d-20260908-venv`; `PYTHONNOUSERSITE=1`.
Pydantic 2.12.5, PyYAML 6.0.1, MCP 1.29.1, google-genai 1.72.0,
requests 2.33.1, Pillow 12.2.0. No packages were installed into a shared runtime.

Initial Windows Python 3.14 lacked pydantic. `python3 -m venv` on WSL lacked
ensurepip. Pip installation targeting only the temporary venv timed out on
PyPI. The venv was completed by copying existing local/system site-packages
into its own directory (without overwriting newer copied versions), including
system PyYAML/idna absent from user site-packages. No `.env` or authentication
configuration was changed. No dependency import skip was counted as success.

Ordinary exec/apply_patch sandbox setup failed with `helper_unknown_error`.
Task-scoped `require_escalated` exec succeeded. Early source edits used a
literal Python edit script before the coordinator supplied the native-patch
fallback; subsequent edits used the original Codex apply-patch executable via
`--codex-run-as-apply-patch`. No system security setting was changed.

All final test commands use this package working directory:
`/mnt/c/Users/Lan/.codex/worktrees/0788/sanmou_monorepo/packages/qa-agent`.

```sh
PYTHONNOUSERSITE=1 PYTHONPATH=src /tmp/sanmou-qa-d-20260908-venv/bin/python -m unittest tests.test_review_d_regressions tests.test_run_video_pipeline_cli tests.test_ingestion tests.test_client_package_scan tests.test_client_lua_crypto tests.test_publish_staging_cli tests.test_video_publish tests.test_vision -v

PYTHONNOUSERSITE=1 PYTHONPATH=src /tmp/sanmou-qa-d-20260908-venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

The commands ran through `wsl --cd <package-path> --exec sh -c ...` with stdout
and stderr redirected to real files, preserving subprocess `fileno` behavior.
Focused log: `/tmp/sanmou-qa-d-focused.log`.
Final package log: `/tmp/sanmou-qa-d-package-final.log`.

## Results and failures retained

| Run | Result | Exit |
| --- | --- | --- |
| Initial new regression module after dependency setup | 13 passed, 0 failed, 0 skipped | 0 |
| First full suite, incorrectly run from repo root | 309 test methods, 4 failures, 1 import error, 0 skips | 1 |
| Focused after fixture corrections | 43 passed, 0 failed, 0 skipped | 0 |
| Full suite from correct package cwd, before effective LF rewrite | 321 methods, 319 passed, 2 failures, 0 skips | 1 |
| Shell workflow after verified LF rewrite | 2 passed, 0 failed, 0 skipped | 0 |
| Final focused, including zero query-rewrite on miss | 44 passed, 0 failed, 0 skipped (8.319s) | 0 |
| Final full package | 322 passed, 0 failed, 0 skipped (107.977s) | 0 |

First-run root causes, rather than weakened expectations:

1. Two existing shell tests returned 127 because the Windows checkout had a
   CRLF shebang (`bash\r`). Ordinary restore/checkout-index did not rewrite
   equivalent normalized content. A native apply-patch rewrite retaining every
   line produced LF. `git ls-files --eol` now reports `i/lf w/lf`, and
   `git hash-object --no-filters` exactly equals the HEAD script blob
   `44863bc50e518673e6cc0a8705ff6c51a5ca42e8`. No script diff enters this commit.
   An intermediate shebang-only rewrite also failed on `set -euo pipefail\r`;
   this was not counted as fixed until the entire file was byte-verified.
2. Running from repo root prevented `tests.test_advisor_terminal_source_preflight_cli`
   import; running from the documented package cwd restored the missing tests.
3. The heuristic bundle fixture does not actually emit a combat candidate.
   The new test's nonempty-combat assumption was removed and replaced by a
   separate injected `VideoCombatCandidate` with explicit synthetic facts.
4. The vision query `这个人？` has an existing n-gram KB match despite its
   unresolved image name. The attempted empty-evidence assertion was incorrect;
   the original vision test was restored unchanged. Zero-evidence behavior is
   covered using a controlled empty/unrelated retriever instead.

### Frozen baseline red check

Baseline QA source/config/KB were exported with `git archive d377ef8...` to
`/tmp/sanmou-qa-d-baseline` (no worktree switch, merge or production publish).
From the current package cwd:

```sh
PYTHONNOUSERSITE=1 PYTHONPATH=/tmp/sanmou-qa-d-baseline/packages/qa-agent/src /tmp/sanmou-qa-d-20260908-venv/bin/python -m unittest tests.test_review_d_regressions tests.test_run_video_pipeline_cli -v
```

At that stage the two modules contained 15 methods. Result: 15 failure records
(including subtests), 2 errors, exit 1, 3.825s, log
`/tmp/sanmou-qa-d-baseline-red.log`. Each of the seven findings has an actual
failing assertion on the old code. The two additional errors are explicitly
not counted as independent exploit proof: the old scanner lacks the new `os`
module hook, and the old pipeline lacks `pending_combat_entries`. Later added
history-miss coverage was run on the final implementation, not included in
that earlier 15-method baseline run.

## Compatibility and unverified boundaries

- QA six-tool catalog and response schemas remain unchanged. Full-suite MCP
  SDK tests exercise official in-memory and stdio success/error parity,
  strict extra-key/enum/type rejection and stable tool definitions.
- `sanmou-game/v1`, `execution_authority=none`, `executable=false`, disabled
  `--execute` and live replay were not modified. No game input/capture or
  privileged controller was used; no external holdout oracle was read.
- Tests use synthetic markers/facts/images and existing committed regression
  fixtures. No new real screenshot or private account image was collected,
  transmitted or committed. No actual answer/vision provider was called.
  Heuristic video extraction is offline; all publication tests use temporary KBs.
- Pipeline CLI intentionally stops at pending output; callers expecting an
  auto-published workspace KB must use a separate human review workflow.
- Query rewrites now require an initial current-query retrieval match. A
  context-only followup without such evidence may refuse until the user names
  the topic. Citation validation binds IDs, not semantic entailment of every
  generated clause; this is not a provider accuracy certification.
- POSIX symlink/hardlink and check/open replacement tests passed. Native Windows
  junction/reparse races and continuously hostile concurrent writes were not
  independently certified. Descriptor identity checks do not claim to be a
  signed privileged filesystem broker.
- Bucket writes are planned before mutation but remain multiple file writes;
  crash-atomic publication across buckets and concurrent writers are not
  implemented by this fix. Duplicate reads now fail closed instead of silently
  accepting partially migrated data.
- No production publication, game live closure, installation/release or
  master integration was performed. Unified adversarial review remains required.
