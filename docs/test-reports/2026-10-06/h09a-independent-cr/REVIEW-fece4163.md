# H09a independent review: REQUEST CHANGES (normal installation metadata)

Date: 2026-10-06. Reviewer: independent GPT-6 Astra agent.

Reviewed source commit: **`fece4163d04af5057493549da2db74a8fa65ed06`**.
Reviewed source tree: **`4c25f8fa14ea99d8aca09d49cf6c3c911c5c2f8e`**.

This review applies only to the exact source above and its eight-case offline
TaskRunner control evaluation. It is not approval of this or a later combined tree,
the report commit as newly executed source, H06 Windows, production, provider,
vision, human gold, independent holdout or live game execution. H06 Windows
hosted acceptance remains incomplete and blocks publication. No push/merge or
third CI retry was performed.

## Review disposition

All five reproduced contract defects are closed by original unchanged assertions:

| Finding | Final verification |
| --- | --- |
| CR01 actual CLI provenance | Copied CLI is non-gating diagnostic; exact committed module/direct file bind real launcher |
| CR02 goal/control metric coupling | Same verified actual retains goal success under expected tool-label mismatch; control fails |
| CR03 phase artifact failure | Full actual state, tool/policy calls and trace retained with infra failure |
| CR03b final artifact hash-read failure | Failed report preserves all 8 case results and available hashes; missing digest explicit, gate false |
| CR04 projection exception false green | Real committed-entry fault yields exit2, incomplete/false gate and retained facts |

Additional finalization probes confirm artifact enumeration failure preserves
cases with explicit unavailable hashes, and genuinely unwritable report.json
produces CLI `report_available=false`, `complete=false`, `gate_pass=false`, exit2.
That unavoidable output failure is distinct from recoverable artifact failures.

The original five defects are closed, but the additional verified CR05 below
blocks approval. A positive-verdict draft was not committed or handed off after
this candidate was identified. Source and reviewer assertions were not weakened
to obtain green. Prior red logs, reports, probes, archives and typed inventories
remain unchanged in preceding review commits.

### CR05 [P2] Do not classify ordinary editable-install metadata as source drift

`packages/pioneer-agent/src/pioneer_agent/agent_harness/_task_eval_source.py:73-81`
rejects every untracked file anywhere under src except __pycache__, including
standard `src/pioneer_agent.egg-info/SOURCES.txt`, PKG-INFO and other generated
setuptools metadata. The existing pyproject uses setuptools.build_meta with src
layout; regression.yml lines 30/59 install these packages with `pip install -e`.
The repository explicitly ignores `*.egg-info/` in .gitignore.

Independent reproduction: create a separate detached fece worktree and invoke
existing local setuptools 68.1.2 with `setup(script_args=['egg_info'])`. No pip,
dependency installation, network or source editing is involved. It creates five
standard metadata files and git status remains clean. Running the original
committed CLI then exits 2, source_verified/gate false, with diagnostic
`untracked_source:packages/pioneer-agent/src/pioneer_agent.egg-info/SOURCES.txt`.
The README's documented command requires committed code in a Git worktree but
does not restrict use to special metadata-free pre-install snapshots. The task
contract requires rejection of untracked source, not ordinary nonsource install
metadata. This breaks normal repository setup despite passing pristine-snapshot
tests, so it is an actual scoped usability defect rather than a claimed limitation.

Fix narrowly: distinguish conventional generated packaging metadata from actual
source/config under the checked roots, without hiding arbitrary source, native
modules, .pth hooks, links/reparse points or other unexpected files. Add a formal
CLI regression after ordinary local metadata generation while retaining all
source-drift/untracked-source protections. Do not simply ignore an unrestricted
egg-info subtree or weaken source/import byte binding.

Raw first red: `/tmp/h09a-cr-fece4163-editable-metadata-first.log`.
Full evidence: `/tmp/h09a-cr-fece-editable-metadata-evidence`.
Frozen reproducer: `editable_metadata_fece.py`.
Archive: `evidence-fece-metadata-red.tar.gz`, SHA256
`eaec08dd2272a4365e08b005d14b33b94fd009bb4e7ec599df54d4039b29d58c`;
typed inventory records 11 regular files, no symlinks, 3 directories.

## Independent exact-source verification

Clean detached ext4 source: `/tmp/h09a-cr-fece4163-20261006`.
Python 3.12.3, Linux 6.6.87.2-microsoft-standard-WSL2, existing dependency root
`/tmp/sanmou-cr-20261005-6155-deps`; no dependency installation or changes.

| Verification | Result |
| --- | --- |
| Pioneer complete unittest suite | 990 total: 988 pass, 0 fail/error, 2 Windows-only skips |
| QA complete unittest suite | 394 pass, 0 fail/error/skip |
| common complete unittest suite | 2 pass, 0 fail/error/skip |
| Frozen reviewer assertions | 19 pass, 0 fail/error/skip; 18 current-source assertions plus 1 historical-64 report comparison |
| Additional finalization boundaries | 2 pass, 0 fail/error/skip |
| Fresh `-m` formal evaluations | Two runs: each 2/2 goals, 6/6 safety stops, 8/8 controls, 0/8 infra |
| Direct committed-file formal evaluation | Same totals; correct direct-script launcher binding |
| Stable projections/input manifests | All three equal, also equal to author's final runs |
| Artifact hashes | Independently recalculated against exact stored bytes |
| Actual module identities | 87 modules each `-m`, 86 direct: exact file/spec.origin/package paths checked |
| Source/input binding | 179 original source/config blobs and 7 input buffers bound |
| Protected paths | All 831 mode/type/blob records unchanged |
| Source drift and untracked source | Exact final-SHA negative worktrees rejected by real CLI, exit2, no cases or positive gate |

Windows-only skipped tests are
`test_native_client_proxy_server_end_to_end_with_synthetic_capture` and
`test_retired_entry_points_exit_without_writing_requested_paths`. They are not
counted as passes or a replacement for hosted Windows acceptance.

Full regression includes three pre-existing official SDK stdio integration tests
whose source specifies four child-server starts: Game+QA together, Game server
smoke, and QA parity. Parameters were inspected: fixture/contract-skeleton Game
server and static-KB QA server only, no Windows bridge, live capture/control or
provider. Other tests use mocks, in-memory transports or local fixtures. These
stdio checks are regression evidence, **not** a claim that H09 evaluated real
transport: H09 itself still uses its explicit synthetic ScriptClient and no
provider/network/real game. All evaluator runs remain authority=none and
executable=false; measured provider tokens/cost/latency remain not applicable.

## Task-control coverage

The eight actual outcomes are: three-observation goal (12 tools/3 policy),
missing field evidence (12/3, step_limit), false success proposal (4/1), replayed
observation (6/1), five-tool budget (5/1, no sixth dispatch), pause/fresh resume
(4+8 tools, Fake then Rule, no budget/deadline refill), context overflow (4/0),
non-read-only session (1/0). Normal completed reservations settle, model attempts
are zero, and terminal/paused-without-resume calls add no tool/policy calls.

Independent faults also cover expected/id isolation, same id replay, new id with
nonincreasing capture time, resumed old observations, sequence exhaustion as
infra retained in fixed denominators, checkpoint failure, schema and unknown
tools, fixture raw-byte digest mismatch and one-buffer semantics, path escape,
symlinks, lazy out-of-root module/package-path shadowing, source byte drift,
untracked sources, output no-clobber and failure report integrity.

The source-negative copies `/tmp/h09a-cr-fece-byte-drift` and
`/tmp/h09a-cr-fece-untracked` alone received deliberate test mutations through
apply_patch. Their HEAD is the reviewed code commit; rejection reasons were
independently confirmed as `source_byte_drift` and `untracked_source`. The clean
review source stayed unmodified. Same-root malicious module replacement is not
claimed to be defended; no ordinary trusted-loader counterexample was found.

## Author handoff independently audited

Author report commit: `08c97024b4c0566c26f5c2b0461c1efb3e5d3c23`.
Report tree: `7ba048c425de6813ab5bf4a899421f9c0b0159f9`.
Compared with the reviewed code, exactly 299 report-directory additions and no
existing/source edits; the complete packages tree is identical.

`audit_author_handoff.py` read immutable Git blobs, not author WIP, and did not
execute author audit scripts. It checked all 297 final-manifest file entries,
the 179 source blob identities/bytes in each formal report, all artifact hashes,
7 committed input buffers, three formal report states and stable projections,
and every typed member of the author's final probe archive (252 regular files,
1 symlink, 88 directories). No archive extraction or symlink following occurred.

- Author final manifest SHA256:
  `a193b156f42a1d36dd9560d924db7f1f5572161c3717e767e86d39073c83b85f`.
- Author REPORT.md SHA256:
  `557e92eacc32097f6a3883a540966b14fda50bf74b4809cf3c098c782c319f92`.
- Machine-readable independent result: `author-handoff-audit.json`.

Author logs agree with independently obtained counts but do not substitute for
the independent runs. Author development failures and earlier source versions
are separately retained and not represented as final-source passes.

## Commands

The actual complete-suite commands used package cwd, `python3 -B`,
`PYTHONDONTWRITEBYTECODE=1`, absolute source/dependency PYTHONPATH, and
`set -o pipefail` with `2>&1 | tee` to preserve stdout/stderr and command status.
For Pioneer, PYTHONPATH includes absolute Pioneer, QA and common src plus the
existing dependency root; QA includes absolute QA/common src plus that root.

```sh
git -C /home/lan/projects/sanmou_monorepo worktree add --detach \
  /tmp/h09a-cr-fece4163-20261006 fece4163d04af5057493549da2db74a8fa65ed06
# From each package cwd:
python3 -B -m unittest discover -s tests -p 'test_*.py' -v
# From clean snapshot root, using its absolute PYTHONPATH:
python3 -B -m pioneer_agent.app.task_eval --output /tmp/h09a-cr-fece4163-eval1
python3 -B -m pioneer_agent.app.task_eval --output /tmp/h09a-cr-fece4163-eval2
python3 -B packages/pioneer-agent/src/pioneer_agent/app/task_eval.py --output /tmp/h09a-cr-fece4163-direct
# REVIEW is this report directory as an absolute /mnt/c path:
python3 -B "$REVIEW/replay_fece.py"
python3 -B "$REVIEW/final_boundaries_fece.py"
python3 -B "$REVIEW/source_report_checks_fece.py"
python3 -B "$REVIEW/source_negative_checks_fece.py"
python3 -B "$REVIEW/audit_author_handoff.py"
```

Wrappers only rebind explicit ROOT/DATA/source identifiers; original assertions
are unchanged. Historical probe file/output labels containing `2cc` do not mean
that old source was loaded: final wrappers and report source manifests bind fece.

## Preserved independent evidence and safe inspection

Final evidence: `evidence-fece4163.tar.gz`.
SHA256: `47c903baa7b32b394bcb227d44d25b5e615b521efaa30de32f8e08eb4f6085aa`.
Typed inventory: `evidence-fece4163-typed-inventory.json` records **395 regular
files, 1 symlink, 136 directories** and each regular member's raw-byte hash.

Prior archives remain immutable:
- `original-evidence.tar.gz`: 403 regular files, 2 symlinks, 136 directories.
- `evidence-2cc7b2f8.tar.gz`: 344 regular files, 1 symlink, 119 directories.

All symlinks are intentional negative path-test artifacts with absolute original
temporary link targets. Inspect tar member bytes and typed metadata only; do not
extract wholesale or follow archived links. The old 405-path manifest is not a
claim of 405 regular files; its typed supplement records the two link identities.

CR05 prevents approval of this exact SHA despite the preceding passing checks.
After repair, the coordinator must still review/retest any combined publication
tree and preserve the unsatisfied H06 Windows release gate.
