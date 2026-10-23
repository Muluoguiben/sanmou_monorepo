# Q05a UTF-8 test-I/O follow-up: native gate blocker

This narrowly supplements the Q05a contract; it does not change seasonal
production logic, fixtures/gold, freeze bindings, the scorer or workflow.
Original source `3d8257bf03d47bb86fb80994c924987033b1858a` and combination
`2e0d7b9fb61563f82fbcea6239993fef28970c9a` passed their documented Linux checks.
They were not published. The coordinator stopped candidate generation after
finding locale-dependent text I/O in the tests newly selected for Windows.

## Direct native observation and fixed input

Existing bundled Windows Python, standard-library only: no QA import, dependency
search/install, environment mutation outside the child, or native QA test run.

```text
filesystem_encoding=utf-8; filesystem_errors=surrogatepass
text_locale=cp936; utf8_mode=0; default_open_encoding=cp936
v4/cases.json: 31024 bytes, 1116 non-ASCII bytes
SHA256=16b0218cee40dbe9d4796568474697324a51a71ced9f12901b2d60126794cc7a
Gitblob=fdb7f31ce56144fedbe538aa9324984c75971d7c
default Path.read_text(): UnicodeDecodeError, codec=gbk, start=183
```

The working-file Git hash equals the fixture blob at fixed 3d8257b. This is an
explicitly labelled transcription of tool output, not a byte-sealed raw native
test log and not a successful 44-test native run.

## Narrow repair and unchanged assertions

Only `test_seasonal_retriever.py` and the already-migrated
`test_quality_eval.py` may add explicit `encoding="utf-8"` to text
`Path.read_text`/`write_text` calls. Preserve all positional arguments, assertions,
test names/counts, production files, old/new fixture bytes and CI settings.
AST compatibility may additionally remove exactly that keyword on those two
TextIO methods when comparing against pre-fix tests; no generic keyword removal
or broad AST exclusions. Fixed test-only repair e0d9d6e must retain 27b production
freeze and v4/Q04 whole report hashes c30d4129...858c / b9658bf8...f0b6.

Preserve every original failure: strict POSIX C startup on 3d gives 44 tests,
one failure and 27 errors; after explicit TextIO correction, that profile still
exposes an independent ASCII-filesystem/surrogate boundary in the old snapshot
code. Do not modify the scorer, rename Chinese files or call that boundary fixed.

The isolating control starts with UTF-8 filesystem encoding and utf8_mode=0,
then genuinely sets LC_CTYPE=C before running the same test group. Assert the
test process's actual filesystem UTF-8, default file-text ASCII and UTF8-mode 0.
Do not mock open/read or enable UTF8 mode to hide the failure. UTF-8 stdout is
only log transport. Explicitly disclose that spawned CLI interpreters inherit
C.UTF-8 from the environment, not the parent's in-memory locale change.
Both old and new source must run under the same frozen control; retain old red
and new green. Final real Hosted Windows original25/new44/all4jobs remains the
acceptance gate, independently of this Linux control.

## Preserved pre-fix combination evidence

The completed 2e0d Linux evidence was moved, not deleted or rewritten, to
`docs/test-reports/2026-10-06/Q05a-pre-utf8-integration-artifacts/`.
Its 28 plain files retain exact bytes/SHA256 and original source paths;
manifest SHA256 is
`8a027f937c46333943ac55c214ab7f955bf860d4f03b920124463b15f9ce7d5c`.
All hashes were checked before and after the within-worktree move. No final
candidate, main-WIP migration or publication had occurred. These Linux passes
remain valid evidence of that source and environment, not native acceptance.

Keep the original source-specific review and append the new REQUEST_CHANGES /
repair review. No archive is created/read, Q06 remains paused, and no provider,
game, credentials, new dependency, deployment or execution authority is added.
