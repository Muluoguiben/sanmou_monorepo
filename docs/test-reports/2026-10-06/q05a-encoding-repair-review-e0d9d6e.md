# Q05a-P1 repair — APPROVE for fixed test I/O; native pending

Reviewed source `e0d9d6ef6083f5dc8f3c71daae6e46ed0793c750`, tree
`94abdeb7aa1e391c02eefaf415893b23eb7d741a`. The narrow explicit-UTF-8 test-I/O repair
resolves Q05a-P1 under the tested non-UTF text locale with UTF-8 filesystem paths.
It does not fix or approve the separate strict-C ASCII-filesystem boundary, and
does not establish Windows native success. Coordinator's final exact Hosted gate
remains required. Prior 52b2642 approval and 0ef24f2 REQUEST_CHANGES stay unchanged.

## Exact repair scope

Relative to original `3d8257bf03d47bb86fb80994c924987033b1858a`, non-doc changes
are exactly test_quality_eval.py and test_seasonal_retriever.py. Independent
paired-AST comparison permits only 15 added encoding="utf-8" keywords on existing
read_text/write_text calls (14 changed source lines, one has two calls). Removing
only newly added keywords restores both entire original ASTs; existing UTF-8
arguments are not stripped. All 44 method names, assertions and inputs remain.
No broad AST exclusion, mock file reader, errors-ignore path or test skip.

Git trees for QA src, every fixture/freeze, .github, Pioneer and common are exactly
unchanged. The production27b freeze and all evaluator code therefore retain the
previous source bytes; actual v4 and Q04 CLIs were also rerun and retain their
complete hashes. This is not a production/fixture/CI workaround.

## Original probes and actual locale outcomes

Original strict-C probe faefc08 and supplemental real text-locale probe 8bb4a1d
were each frozen before their executions. Each was run unchanged on old and new
sources. No PYTHONUTF8=1 or patched open/read was used.

| Source / actual runtime | Original 44-test outcome |
| --- | --- |
| 3d, strict C startup, ASCII filesystem | exit 1: 1 failure + 27 errors |
| e0, same strict C startup | exit 1: 8 failures + 2 errors; zero UnicodeDecodeError occurrences |
| 3d, UTF-8 filesystem / runtime C text locale | exit 1: 27 errors |
| e0, same UTF-8 filesystem / runtime C text locale | exit 0: 44 passed, zero skips/errors/failures |

The supplemental process starts LC_ALL=C.UTF-8 with utf8_mode=0, then actually sets
LC_CTYPE=C before running tests. Captured locale.getencoding and a real default-open
handle both report ANSI_X3.4-1968, while sys.getfilesystemencoding stays UTF-8.
stdout UTF-8 is output encoding only. A separately spawned interpreter is recorded
as C.UTF-8/default UTF-8: in-memory setlocale does NOT propagate to the tests' CLI
subprocesses. Their inherited environment is explicit in metadata; no claim that
those children also ran with ASCII text locale is made. This control is not CP936
or Windows execution, but isolates the actual locale-dependent text I/O defect.

Strict-C startup still fails because the existing snapshot traverses non-ASCII
KB filenames represented as surrogate escapes under ASCII filesystem encoding.
That separate boundary was neither fixed nor hidden. Original strict-C red remains
in q05a-nonutf-original-results; new strict-C red and both supplemental results
are in q05a-encoding-repair-results. Neither strict-C result is counted as pass.

## Independent normal-locale verification

Fresh LF checkout `/tmp/q05a-cr-e0d9d6e-20261006`, existing dependencies only.
Public probes 5, v4 integration probes 4, targeted tests 44 and full QA 440 all
passed with zero skips. Real v4/Q04 CLI outputs match the preceding implementation:

- v4 SHA256 `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`.
- Q04 SHA256 `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`.

Normal commands and exact source/tree/AST additions/log hashes are in
q05a-encoding-repair-results/normal/summary.json. Unchanged Pioneer/common/H07/H10
were not independently rerun again for this two-test-file repair; their prior 3d
source-specific evidence remains as recorded, and author's fresh e0 full matrix
was independently checked, not presented as our own execution.

Author report `dacf8a0aea62eef7bd9415779cdcf03e6faffe70` was read in full. It has
no package/workflow changes from e0. Fourteen normal raw log hashes, byte counts,
test/skip/exit summaries, 44-name inventory and report hashes were verified,
together with all four source-bound strict-C/supplemental raw logs and metadata.
See normal/author-crosscheck.json. All author/independent old and remaining red
facts agree; neither report claims native completion.

The initial narrow audit 95deff4 stopped before tests because it omitted known
docs-only report ancestry from its permitted diff. cd8ab87 corrected only that
scope check; the full non-doc diff and exact AST gate remain strict. This reviewer
tool correction is retained in q05a-encoding-audit-notes.md, not called a product
repair or used to discard locale failures.

## Final limitations

Final published exact SHA/attempt must still demonstrate original Windows25 plus
Q05 targeted44 qualified names each ok, zero skips, exit 0, and all four jobs
successful. No local native dependency exploration/install was performed. Root's
separate Windows stdlib cp936/UTF-8-filesystem observation is not reviewer native
test evidence. The code-review skill informed this narrow, evidence-bound review.
No implementation/main/WIP/push, Q06/archive body/member reads, provider/game/bridge,
.env/credentials, installation or deployment actions were taken. No new authority,
semantic quality, holdout or general ASCII-filesystem compatibility is claimed.
