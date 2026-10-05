# Q02a-CR01/02 narrow repair — author verification

Date: 2026-10-06. Repairs the two P2 findings frozen in independent CR commit
`eb895ae4e149a38d65789c19c7e4aebdee0c3c1a`. Author self-test only; independent
re-review remains required. No push, merge, real provider or knowledge publication.

## Exact local source

- Reviewed prior code: `f3cd9b8814fc085d567063ab23e6576b9c24525f`.
- Repair started at coordinator successor `cd3f2e25896415cfb833cfdd836da37ba56c7b9a`.
- Coordinator-only state successor `826caea8e091b78a21a5c802ebf61001daa2e184` was preserved; its files were not staged by the implementation owner.
- Production repair: `90e51683343e7971ec43ca2afcf731fcd66faf4e`, tree `46c66dfb662ba766a87aa2925289b27d9341b28a`.
- Final code/tests/v3 binding: `40f46d3ea4525639877ad37a8da4ab6e334523e6`, tree `1351c2432adb0a638997ab9faff7bb22725fba4f`.
- Branch: `codex/qa-referent-q02a-20261006`.
- Windows root: `C:/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo`.
- WSL root: `/mnt/c/Users/Lan/.codex/worktrees/qa-evidence-q03-20261005/sanmou_monorepo`.

Production was committed first. Only then was unpublished v3 explicitly rebound
to the existing production commit (one file hash, aggregate digest and source
commit label). The original v3 cases and labels are unchanged. Earlier v3
binding remains in Git history; v1/v2 and all previous reports remain unchanged.
A separate Git/blob check resolved the new production commit and compared the
complete 186 KB/production blob set: **0 mismatches**. This is local provenance,
not a remote signature or a consequence of forty-hex label syntax.

## Narrow fixes

CR01: eligible preceding questions now use full-match anchored syntax:

- Bare canonical hero name or unique alias; or
- That name plus optional `的`, one stage (`初始/基础/满级/成长`), one attribute
  (`武力/智力/统率/先攻`), optional `是`, then `多少`.
- Both forms allow at most one trailing `？`, `?` or `。`, and outer whitespace.

Extra clauses, quoted/excluded mentions, introductory phrases or other unmatched
wording cannot establish a private binding. The old single-turn answer path is
unchanged: such questions may still retrieve and generate normally. This is a
finite acceptance grammar, not a negation blacklist or general NLU. Normal bare
canonical/alias and attribute positives, including notes/None cases, still work.

CR02: private hero eligibility now requires all three conditions:
`domain == Domain.HERO`, `entry_kind == EntryKind.HERO_PROFILE`, and
`isinstance(structured_data, HeroStaticProfile)`. The same helper controls anchor
discovery, cited identity and resolved evidence filtering. Fully model-validated
term/generic and hero/generic records with hero-shaped data cannot supply a hero
referent. No public KnowledgeEntry schema, formal KB or Q03a general assessment
scope was changed.

## Original red replay and exact probe provenance

Before production edits, the original reviewer launcher was invoked read-only
with the author source root explicitly supplied. It ran the original five-method
adversarial suite: **exit 1, two failing methods / three failed assertions**
(the unittest footer reports `failures=3`). Both excluded/quoted-name subcases
and the model-validated non-hero record reproduced. Raw output is `red.log`.

The four reviewer files were verified against CR Git blobs before copying.
An initial PowerShell text-display copy added one extra LF, detected by the
post-copy raw-blob check. For example, guarded_run.py initially hashed to
`b158b8fcf113e168207b1d3912fe76b3778c45c4`, not the frozen
`0fa46b738500da1ee9db10e891591f1a4ebbbc1d`; its tail was `29 0a 0a`
instead of `29 0a`. This initial copy was not byte-identical and is not reported
as such. See `copy-correction.json`. No assertion was changed.

Copied files were restored from raw originals and all four Git blob IDs matched
before the final replay. Reviewer originals were never edited. No path/root or
grammar changes were needed. `probe-provenance.json` records full raw identities:

| Probe | Final raw SHA-256 |
| --- | --- |
| guarded_run.py | `e261a9430250af377521aae52e3405ab1535958b42a5ce3ea2dbe1bc65423fee` |
| test_q02a_adversarial.py | `9591d87a1e46112f247e5e6c23ceb6ec42c06bb214f1e3a60c3e07a67bad9597` |
| test_q02a_contract.py | `b56e0b0bc3b6498ae4dc880c5965f9600366973e1e47d2baf66e91d1464c9f66` |
| grammar.json | `132c4a48e561098ef17915e1f5213c145ed674c40f6212ba1935a0dda3c0d700` |

Final exact-probe run: **26 methods (original 5 + original 21), OK, exit 0,
zero skips**, including the original positive matrix and notes/missing-value
controls. Earlier pre-byte-restoration green output is retained separately,
not substituted for this final exact replay.

## Commands and outcomes

Let `R` be the WSL root above and
`P=$R/docs/test-reports/2026-10-06/Q02a-repair-artifacts`.
All runs set `PYTHONDONTWRITEBYTECODE=1`. The copied launcher prohibits `.env`
reads, Internet-family connections and DNS; it preserves Unix sockets.

```bash
python3 -B "$P/guarded_run.py" "$R" test_q02a_adversarial test_q02a_contract -v
python3 -B "$P/guarded_run.py" "$R" test_referent_resolution test_quality_eval \
  test_evidence_assessment test_review_d_regressions.ChatGroundingRegressionTests -v

PYTHONPATH="$R/packages/qa-agent/src:$R/packages/sanmou-common/src:/tmp/sanmou-cr-20261005-6155-deps" \
python3 -B "$P/guarded_run.py" "$R" discover \
  -s "$R/packages/qa-agent/tests" -p 'test_*.py' -v

PYTHONPATH=/tmp/sanmou-cr-20261005-6155-deps \
python3 -B "$P/guarded_run.py" "$R" test_advisor_api -v
```

| Run | Exact result |
| --- | --- |
| Production controls + original contract + two fixed defect methods | 49 tests, OK, exit 0 |
| Final exact independent suites | 26 tests, OK, exit 0, 0 skips; 6.806 s |
| Focused author/evaluator/Q03a/grounding | 71 tests, OK, exit 0, 0 skips; 25.333 s |
| First full attempt | 394 tests, 1 error, exit 1; 111.484 s — launcher environment error below |
| Corrected full QA on final code | 394 tests, OK, exit 0, 0 skips; 122.489 s |
| Cross Advisor API | 6 tests, OK, exit 0, 0 skips; 3.063 s |

The first full command supplied only the dependency directory in PYTHONPATH.
The launcher updated parent sys.path, but the MCP stdio test explicitly passes
environment PYTHONPATH to its Python child. That child failed with
`ModuleNotFoundError: No module named 'qa_agent'`, then `Connection closed`.
`full-first.log` preserves this exit-1 run. The corrected command above supplies
absolute QA/common paths for the child; no source, assertion, timeout or expected
hash was relaxed. `full-final.log` is a separate successful run.

The pre-existing Windows shell checkout was temporarily normalized to its
verified Git LF bytes for testing; index, normalized content and raw LF blob
all matched `44863bc50e518673e6cc0a8705ff6c51a5ca42e8`. Original CRLF formatting
was restored afterwards and no shell-file diff remains.

From `$R/packages/qa-agent`, with `PYTHONPATH=src`:

```bash
python3 -B -m qa_agent.quality_eval.runner --baseline v3 --output /tmp/Q02a-repair-v3.json
python3 -B -m qa_agent.quality_eval.runner --baseline v1 --output /tmp/Q02a-repair-v1-should-not-exist.json
python3 -B -m qa_agent.quality_eval.runner --baseline v2 --output /tmp/Q02a-repair-v2-should-not-exist.json
```

v3 exits 0: unchanged 12 queries, Recall/MRR 10/11, six scalar controls and nine
developer-authored fake-client multi-turn scenarios. `provider.calls=0` and
quality remains `not_measured`. Multi-turn counters describe the final target
turn after resetting the fake, not total-conversation usage. v1/v2 each exit 1
with expected source drift and no result file. The existing read-only
`Q02a-artifacts/verify_git_binding.py` was rerun without changing it; its new
output is archived as `git-binding.log`.

## Preserved evidence and boundaries

Raw outputs are stored in `Q02a-repair-artifacts/` via byte-identical mechanical
copies with source/destination hash checks. First failures were not overwritten.

| File | SHA-256 |
| --- | --- |
| red.log | `7e8ffb86ad7974c5a0a0fdcbc57b616707210c5d151e74ee06d55c8fb6d8d223` |
| independent-final.log | `d5790618d3ce541b0cb7cabc98507bda6acec04de5da0eb5cafe8063dd3b6793` |
| focused.log | `cb5c7ce56f7a2ba11aae10df5893795db1519d6542b689cfe28b8ae78d6604c2` |
| full-first.log | `f3c94d45f5429d534777a5b64e18699baf87180b20f5941dd5b0d14810316d62` |
| full-final.log | `a0dd3a58555667f85386b1de72835279a8c01e6a40919190cc2e4c3050fd7ab7` |
| cross.log | `aea9ce1efe47f5be91c11d2f040b17a0efec6fb14e67dcb9e67ab908728cf94d` |
| git-binding.log | `c7020514f7f39b1315f1f7b22a941771b3cab9daece95a55a073b31d45e5c192` |
| v1-rejected.log / v2-rejected.log | `ed1f3cc628f8dc189b4d8ac10c87e853fef5c858629a96524f644c08d11b7409` |
| v3.json | `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8` |

Formal KB, general schema, public MCP/common/Pioneer, old v1/v2, original v3
cases and previous reports are unchanged. No dependency installation, real
model, secret read or game control occurred. Full Q02, general semantic subject
or refusal detection, human gold, independent holdout, provider quality and
production readiness remain unaccepted. Independent CR must evaluate the new
exact code/tree; author green results do not inherit or issue approval.
