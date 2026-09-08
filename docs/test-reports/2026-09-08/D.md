# D — QA integrity hardening self-test, 2026-09-08

## Identity and scope

- Task: `01a07f0b-53b8-74a3-9e61-71dd461bdff8`.
- Worktree: `C:\Users\Lan\.codex\worktrees\0788\sanmou_monorepo`.
- Branch: `feat/qa-review-d-20260908`.
- Start: `d377ef8bbaa69e6b25928255eac0cb62714e82f8`, clean detached HEAD before creating this branch.
- Frozen charter/report: coordinator commit `dd76d601f6f40d3e4fceaf10cdd360d78af88cb2`, read from the main checkout without merging it.
- Original tested implementation/test tree: `8acb0b599b20a25630993f35d07df0e78bd964cd` (Git tree object, not a commit), delivered as `2cfda735887e2a7cf237adeafea8d6c7feb2c837`. CR04 subsequently found an uncovered YAML deletion-boundary defect; the original passing tests were not sufficient evidence of record preservation.
- CR04-only tested tree: `5b141cc036cab2effda974b38152e01f049c43c5` (not delivered separately).
- Combined CR04/CR05 tested tree before report/TODO updates: `67293499bb9b5d94406721fc86a18fd8d3b23459`. The replacement commit adds reporting only to this tree; obtain its immutable SHA from the replacement delivery message.
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
The intended KB edit removes the complete stale `hero-皇甫嵩` record from
`profiles/heroes/minor.yaml`. The first delivery left its last note attached to
韩当; CR04 below records the correction and full retained-record verification.

### 皇甫嵩 deduplication evidence

The retained `qun.yaml` record matches the already committed raw record in
`ingestion/raw/heroes/sgmdtx-all-heroes.yaml:2221` (source SGMDTX, captured
2026-04-09T19:17:08): orange rarity, 群雄→群 faction, cavalry, 平乱定叛,
base 72/81/93/23, growth 1.27/0.76/1.74/1.33, and the existing source notes.
The stale minor record shares identity/tags but has null attribute fields, a
stale missing-attributes constraint, and an additional legacy maximum-attribute
note (136/119/180/90). The first report's claim that its notes were a subset was
incorrect. Its orange rarity selects `qun.yaml` in the existing bucket resolver;
the legacy note is removed with its stale entry, never adopted as a new fact.
The retained qun record matches the committed raw source described above and
was not rewritten or re-published. Conflicting canonical IDs in new input block.

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
| Original delivery focused, including zero query-rewrite on miss | 44 passed, 0 failed, 0 skipped (8.319s) | 0 |
| Original delivery full package, before CR04 coverage | 322 passed, 0 failed, 0 skipped (107.977s) | 0 |

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

## CR04 revision — complete deletion and retained-record preservation

Reviewer: unified CR task `01a07f0d-b543-70f2-9055-cca7d4323f7d`.
Defect in original D commit `2cfda735`: deletion ended before the final note at
`minor.yaml:451`. YAML attached that line to the preceding `hero-韩当` record,
contradicting its own recorded values. Schema-valid arbitrary note strings and
the original 322 tests did not catch the semantic ownership error.

The replacement deletes only that one stray line. No other hero fact is edited.
The new fixture `tests/fixtures/qa_minor_dedup_baseline.json` was generated from
the frozen d377ef8 source, not from the broken or repaired D output. It records
the original order and canonical-JSON SHA256 of each of nine surviving minor
records, plus the entire retained qun bucket. The new test
`tests/test_kb_dedup_preservation.py` checks every record, including the adjacent
韩当, and the sole retained 皇甫嵩. Legitimate future KB changes require a separate
reviewed baseline update; these hashes must not be regenerated merely to pass.

Canonical serialization is `json.dumps(value, ensure_ascii=False, sort_keys=True,
separators=(',', ':')).encode('utf-8')`, after `yaml.safe_load`.
An additional one-off direct parsed-list comparison (without using the new hash
fixture) confirms current minor equals baseline minor with only `hero-皇甫嵩`
removed: nine retained records, `unrelated_changed_ids=[]`; qun parsed lists equal.

Blob evidence:

- Repaired minor: `7df7ff6cdd506f36e761e65f7a645badf5e96026`.
- Retained qun: `a62ee36b1a17b70cab1ee71d21ac257d058ea08d`, exactly the d377ef8 Git blob;
  `git diff d377ef8 --exit-code -- packages/qa-agent/knowledge_sources/profiles/heroes/qun.yaml` exits 0.
- `git diff 2cfda735 -- minor.yaml` contains exactly one removed line.

Commands below ran from the same package cwd and isolated runtime above:

```sh
# Run before the one-line data fix: fails only on hero-韩当; qun passes.
PYTHONNOUSERSITE=1 PYTHONPATH=src /tmp/sanmou-qa-d-20260908-venv/bin/python -m unittest tests.test_kb_dedup_preservation -v

# After the one-line fix:
PYTHONNOUSERSITE=1 PYTHONPATH=src /tmp/sanmou-qa-d-20260908-venv/bin/python -m unittest tests.test_kb_dedup_preservation tests.test_review_d_regressions tests.test_run_video_pipeline_cli tests.test_ingestion tests.test_client_package_scan tests.test_client_lua_crypto tests.test_publish_staging_cli tests.test_video_publish tests.test_vision -v

PYTHONNOUSERSITE=1 PYTHONPATH=src /tmp/sanmou-qa-d-20260908-venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

| CR04 run | Result | Exit |
| --- | --- | --- |
| New regression on unchanged original D data | 2 methods: 1 passed, 1 failed (`hero-韩当` subtest); 0 skips, 0.095s | 1 |
| Replacement focused | 46 passed, 0 failed, 0 skips, 8.180s | 0 |
| CR04-only full package | 324 passed, 0 failed, 0 skips, 101.405s | 0 |

Logs are real files `/tmp/sanmou-qa-d-cr04-red.log`,
`/tmp/sanmou-qa-d-cr04-focused.log`, `/tmp/sanmou-qa-d-cr04-package.log`.
No new images, providers, game input, production KB publication or source
claims were used for this revision. The reviewer probe was not edited.

## CR05 revision — retain and check the lexical scan root

The original scanner normalized `root` with `resolve()` before checking links.
A synthetic `public-root -> LocalPersistentData` alias therefore became an
ordinary resolved root; the default exclusion only saw descendants and missed
the runtime directory name itself. This gap was present in D `2cfda735` despite
the original file-link and parent-link tests passing.

The revised scanner keeps an absolute lexical root instead of resolving it
first. It rejects parent-traversal root components and checks the root and
every ancestor with `lstat`, refusing symlinks or Windows reparse attributes.
Per-file checks repeat this complete ancestor check before/after descriptor
reads; failures propagate closed. Default runtime-directory exclusions also
apply case-insensitively to root components. A real runtime directory requires
`include_runtime_files=True`, but that explicit data-policy opt-in never grants
permission to traverse a root/ancestor alias.

New tests in `ClientScanRegressionTests` cover root symlink, ancestor alias,
both runtime flag values, direct runtime root default refusal/explicit opt-in,
and simulated Windows `FILE_ATTRIBUTE_REPARSE_POINT` on root and parent.
Existing ordinary-root, file/directory link, hardlink and check/open replacement
tests remain enabled. Everything uses temporary synthetic trees; no client
installation or real account cache was scanned. Windows attribute simulation
on WSL is not native Windows reparse/race execution evidence.

Before the fix, the scanner class ran 7 methods and produced 5 failure records
(including subtests), exit 1, 0 skips, in 0.033s; its prior 4 methods passed.
The later both-flag root-alias subcases were added to verify that explicit
runtime opt-in cannot bypass link safety. Log: `/tmp/sanmou-qa-d-cr05-red.log`.

Combined focused command, from the same package cwd:

```sh
PYTHONNOUSERSITE=1 PYTHONPATH=src /tmp/sanmou-qa-d-20260908-venv/bin/python -m unittest tests.test_kb_dedup_preservation tests.test_review_d_regressions tests.test_run_video_pipeline_cli tests.test_ingestion tests.test_client_package_scan tests.test_client_lua_crypto tests.test_publish_staging_cli tests.test_video_publish tests.test_vision -v

PYTHONNOUSERSITE=1 PYTHONPATH=src /tmp/sanmou-qa-d-20260908-venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

| Combined replacement run | Result | Exit |
| --- | --- | --- |
| Focused | 49 passed, 0 failed, 0 skips, 6.704s | 0 |
| Full package | 327 passed, 0 failed, 0 skips, 101.251s | 0 |

Logs: `/tmp/sanmou-qa-d-cr04-cr05-focused.log` and
`/tmp/sanmou-qa-d-cr04-cr05-package.log`. Scanner Git blob:
`3a5553253ddc2c4448ae46f56931d368fc1d1bb5`.

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
