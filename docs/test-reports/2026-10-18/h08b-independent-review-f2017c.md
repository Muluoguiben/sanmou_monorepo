# H08b independent review

Decision: **APPROVE the fixed product/CI diff**. No blocking correctness, privacy,
authority, or compatibility finding. This is not final native-CI acceptance.

## Source and scope

- Author source: `f2017c826a9bd798c66be404e99b8e3f8b0ffa50`.
- Independently executed review merge: `695ec15a8570097c30b9d74380485001b9e53939`.
- Both packages trees: `970efcd960fcb694502938d7cefb22785b05e1cf`.
- Contract read from `41be91e4`; interface memo from `06fd180`; original negative
  plan retained. Public probe freeze was committed before author-code access.
- Exact allowed diff from published `155817a`: four product files, new test file,
  and three Windows workflow lines. No old tests, fixtures, budgets, TaskSpec,
  RunState, checkpoints, QA/common implementation or authorization change.
- Independent read/hash audit verifies 956 tracked files in its explicitly
  enumerated text suffix/name scope against Git blob bytes. Workflow inverse
  deletion restores original whole bytes and parsed YAML; new AST inventory is
  exactly 31 test names and matches the executed dedicated log.
- A second reviewer independently checked the fixed trace producer and sinks;
  no concrete issue found. Main reviewer inspected all four product changes and
  all 31 new tests, then used separately frozen/supplemental probes.

## Observations

Strict detached validation retains nested extra data before checking it, rejects
type/coercion/model_construct/model_copy bypasses, verifies the complete exact
preflight declaration and independently rebuilds the task through one builder.
Invalid binding returns before harness reads, owner acquisition/binding/checks,
checkpoint bytes, trace, tool or policy side effects. An acquire-hook mutation
does not change the single runner-owned task snapshot.

Actual task drift and cached provenance/declaration drift latch at existing trace
and dispatch boundaries. Independent late-budget tests cover first tool, ordinary
policy and model-declaring policy; completion settlement and durable-terminal
cuts do not emit false bound events or redispatch. Genuine primary failures retain
their original classification/object; new binding/trace errors have clean direct
cause/context even inside an ambient caller exception.

Both sinks preserve only skill/declared and the complete 101-character fixed
recipe syntax. Near matches, other slots, newline, Unicode, and hex-length/case
controls keep the original hash path. A syntax-only noncatalog digest remains a
sink-format control, not source authentication. Binding neither grants execution
nor proves fresh observations, human review, signing or an actual compile call.

## Executed evidence

All final local rows below use WSL Python 3.12.3, explicit repository-local ext4
scratch, canonical LF source bytes, no added dependencies and no real providers.
Raw logs and command/source/environment/hash records are retained in
`h08b-independent-results/`; the final index is `h08b-independent-summary-v2.json`
(the first index is retained as `h08b-independent-summary.json`).

| Check | Actual result |
| --- | --- |
| Dedicated H08b31 + H08a23 + H10a32 | 86 passed, 0 skips |
| Independent public/supplemental adversarial probes | 11 passed, 0 skips |
| Original unchanged H10 eight probe scripts | 18 passed, 0 skips |
| Full default-v1 / unbound-v2 frozen event oracle | Exact match except predeclared random v2 IDs/timestamp |
| H07 + original Q04/Q05 groups | 104 passed, 0 skips |
| Real ASCII default text / UTF-8 filesystem, utf8_mode=0 | New 31 passed, 0 skips |
| QA full, correct package cwd, canonical root shell | 440 passed, 0 skips |
| Common full | 2 passed, 0 skips |
| Pioneer full, correct package cwd | 1135 total: 1126 passed, 1 import error, 8 skips |
| H09 actual CLI, r4 | Exit 0; complete/source_verified/gate_pass; 8 controls, 2 goals, 6 expected safety stops, 0 infra errors/violations |
| QA v1-v3 | Original expected frozen-source refusals, exit 1 |
| QA v4 / Q04 actual CLIs | Exit 0; full output hashes unchanged |

Pioneer residual is environmental, not green: missing `fastapi` causes one module
import error and six API skips; the other two skips are existing Windows-only
tests. No assertion failure. No dependency installation, skip change or API test
rewrite was used to hide this gap. Final native CI must cover it.

Whole output hashes:

- QA v4: `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`.
- Q04: `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`.

## Original failures and environment corrections remain retained

1. Windows Python 3.14 lacked pydantic; no product probe ran there.
2. Initial WSL-on-drvfs baseline: 55 tests, one checkpoint-backend error. Authorized
   ext4 TMPDIR rerun gives 55 pass. Original error transcription stays retained.
3. First evidence collector finished 55 pass but could not resolve the Windows
   worktree UNC gitdir. Mapping was limited to read-only Git metadata commands.
4. Initial candidate runs used inherited CRLF checkout bytes. Coordinator restored
   only Git-blob-equivalent CRLF-to-LF text (including later extensionless files,
   SQL schema and the root Bilibili shell). Git stat-cache M/empty snapshots were
   not accepted as byte proof; direct raw blob verification replaced that gate.
5. First public dual-sink probe incorrectly assigned an existing frozen
   TraceProvenance field: 55 setup subcase errors, not product failures. Input
   construction changed to model_copy; all original assertions remained unchanged.
   Original 105601-byte red log and its metadata remain; nine probes then passed.
   Two additional completion/terminal probes were added after fixed-code review.
6. Initial full-suite commands ran from repo root instead of package cwd, producing
   tests-package/stdin-server import errors. Correct package-cwd reruns retain the
   original assertions. QA r2 retained two pre-restoration root-shell CRLF failures;
   QA r3, started after restoration, is the complete 440-pass run.
7. H09 initial CLI failed Git discovery (CalledProcessError); explicitly mapping
   only that CLI's existing GIT_DIR/GIT_WORK_TREE exposed the separate schema.sql
   byte drift (InputError). Both original reports/logs remain. No identity guard,
   fixture, output predicate, or product code was changed for these repairs.
8. H09 r3 reached all eight case directories but the evidence collector's 300s
   outer timeout interrupted finalization before report.json existed. The empty
   original stdout log and explicit timeout transcription remain. One final r4
   uses a 600s outer collection limit and completed successfully; product case/run
   budgets are unchanged. Its final source commit/tree exactly match review
   `695ec15a8570097c30b9d74380485001b9e53939` /
   `d1044d4fe0a20713798bc89d1d16b5fe42a86198`. All eight controls passed; two goals,
   six expected safety stops, zero infra errors, unexpected goals or safety
   violations. Source verification is the actual CLI gate, not a wrapper claim.
   Independent post-run verification rehashes all 25 listed artifacts, checks
   every case assertion, all phase model counters/reservations, and each phase/
   checkpoint state plus task authority/executable flags; results are in the
   final v2 index, not inferred from exit 0 alone.

No protected Q06 archive-body/member access, provider fees, live game/bridge action, credentials,
knowledge publication, deployment, push, master merge or destructive cleanup.
The old logs and failed assertions were not deleted or rewritten. Only bounded
new plain review evidence/probes were authored here.

## Remaining release gate

Coordinator must run the exact composed final SHA on hosted native CI: new 31-name
inventory, zero skips and exit 0; original H08a23/H10a32/H07a35/Q0425/Q0544; all four
jobs from the same run. Earlier H08a green and this local component review are not
substitutes. Recommendation-only / execution_authority=none / executable=false
and all Q06 archive/publication restrictions remain unchanged.
