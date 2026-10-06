# Q04a independent review — APPROVE (source / Linux scope)

Reviewed source `676ac1ed012458ccc00a01df159476747921c181`, tree
`16b74ba49c8bf44288c7e23d9935e56631fea471`. No actionable product finding
remains in the frozen Q04a contract. This approval does not validate a future
combined tree, native Windows Q04 execution, real semantic quality, or publication.

Plan `95865435ae2ff2a6ee8d6905f1f72eaf18591052` preceded memo and implementation
inspection. Public probes were frozen in `39bdb13ae1676e75b974abebdcf4b2cad0d21c25`
before reading implementation; 10 hand-authored semantic oracles were first
validated against the unchanged scorer at published `5791ca397507007b9397c78763b3523b8ec16421`.
The code-review skill guided independent source inspection, adversarial controls,
severity assessment and source-bound verification; no external paid model call.

## Scope and inspection

Read the complete contract, interface memo, new module/test/12-case synthetic
fixture/freeze, original scorer and runner, and author report. Package diff is
exactly four new files; all old production, scoring/runner, fixtures, Pioneer,
common, KB, dependencies and CI remain unchanged. Author handoff
`0530fbbc32804de2e1d2f9176f524fa70227c902` has the same packages tree
`e849545fc31473d68835618c2c13ec44c35788c0` as reviewed code.

Strict schema and normalized codepoint bounds reject wrong types, bool offsets,
drift, unknown IDs, duplicates, gaps/overlaps and invalid links. Distinct spans of
one ID preserve positions while projecting unique IDs to the unchanged scorer.
Wrong facts/citations remain scored data; mechanical links do not invent semantic
support. Unknown/unreviewed and true zero denominators preserve original metrics.
Generic human-review declarations remain unauthenticated; synthetic suite upgrades
are rejected even after rebinding annotation and fixture hashes. No automatic
entailment, KB-review authority, provider-quality or holdout claim was introduced.

Public probes passed unchanged. Additional independent real-process CLI probes
exercise nine hand-authored controls in temporary coherent source trees, create-only
output, fixture drift, deliberately wrong expected result returning exit 1 with
gate_pass=false, rebound human-upgrade rejection, actual foreign scoring-module
origin and wrong package root. Temporary copies contained ordinary Python source
and new synthetic JSON only, not KB, archives, model configuration or credentials.

## Independent results

Fresh LF source `/tmp/q04a-cr-676ac1e-20261006`; fresh baseline
`/tmp/q04a-cr-baseline-5791-20261006`; existing dependencies only. Full commands,
actual exit/count/skip and raw-log hashes are in `q04a-independent-results/summary.json`.

| Gate | Actual result |
| --- | --- |
| Independent public / isolated CLI probes | 5 / 4 passed, zero skips |
| New claim module / old quality eval module | 25 / 23 passed |
| H10 causal / H07 approval | 32 / 35 passed, RuntimeWarning-as-error, zero skips |
| Full QA | 419 passed |
| Full Pioneer | 1085 total: 1083 passed, original 2 Windows-only skips |
| Full common | 2 passed |
| New real CLI | 12/12 synthetic controls; none/false; provider calls 0 |
| H09 real CLI | 8/8 controls: 2 goal successes, 6 expected safety stops; no infra/safety violation |
| Old v1/v2, both trees | Expected exit 1, same frozen-production-drift refusal |
| Old v3, both trees | Exit 0; exact allowed metadata delta only |

No skip is counted as pass. Source inventory first checked 898 ordinary package
files; a follow-up NUL-delimited inventory included the Git-quoted non-ASCII
filename and verified all 899 `.py/.json/.yaml/.yml` inputs against fixed Git blobs.
The complete audit is `author-crosscheck-complete.json`. No source was rewritten.

## Exact legacy delta / author crosscheck

Fresh baseline v3 SHA256 remains
`480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`.
New v3 is `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`.
Every non-eval_source field is deeply identical. The only added source entry is
`src/qa_agent/quality_eval/claim_spans.py`, SHA256
`062ae64d50609e2b3542b2c2fd35d66614a40df100a02dd253acf42a57df8155`;
all prior source entries and algorithm are unchanged. Independently recalculated
new aggregate digest is `caadfdc8ed6dfdc50a82b8b376bda1bc1089a1cc6b1af907de6ba33772a714e2`.
Historical whole-report hash was not changed or applied to the new report.

Author's ten raw logs were read from immutable report Git blobs and checked for
exact byte counts/SHA256, unittest totals, skips and OK summaries. Manifest source,
tree, package tree and results agree with independent execution. New CLI report
matches SHA256 `c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120`.
Independent H09 report remains at
`/tmp/q04a-cr-676ac1e-rerun-results/h09-cli/report.json`, SHA256
`509712ac824ce1def968b25830cd74cee6500ec9c3c64badf2f16ccc6dd51f61`;
full old/new v3 JSONs remain beside it. Compact comparison and raw log evidence
are committed without duplicating those large report/checkpoint trees.

## Reviewer-only corrections and preserved first red

There was no reproduced product defect. The first integration probe in
`12c7e4d315bf1a252b51d1fbcc5d4343b4eea725` passed `Path('.').parent`, which is still
`.` and therefore did not construct a wrong root. Its actual 4-test/1-failure log
and original command/exit/hash remain `integration-probes-original-red.log` and
`original-run-progress.json`. Commit `41cca94156fd55b3e0ba38c00853c7a800a583f8`
changed only that input to `Path('.').resolve().parent`; all assertions and all
other probes stayed unchanged. Corrected probe passed against the same 676ac1e
product source. This is a reviewer construction correction, not a product fix.

The initial author-log audit (`eab24b4`) also wrongly required unittest OK to be
the final bytes of the entire log. Pioneer emits buffered test stdout after its
valid `Ran 1085 ... / OK (skipped=2)` summary. That audit-only assertion failed;
`42f938e` anchored OK to the unittest Ran summary instead. All original raw bytes,
hashes/counts and source are unchanged; original audit source remains in Git.
`1531128` then added the NUL-delimited input inventory described above. These
review-tool corrections do not weaken product tests or alter old gold/fixtures.

## Remaining boundaries

Reviewer native Q04 execution: not_executed. Root separately attempted bundled
Windows Python and recorded environment-blocked missing `yaml`, zero new tests
executed, in `a49f9ede0252f98910355b5eac759dc8b0242e4d`; this is not a Q04 pass or
product failure and is not our native execution evidence. No dependency probing,
installation or mocking was performed to manufacture native coverage.

Approval is only for the fixed offline implementation and tested Linux scope.
Source/module paths and hashes are not signed authenticity or adversarial
filesystem protection. External labels are not human gold or entailment proof.
No archive body/member or Q06 payload/ancestry was read; Q06 remains paused.
No provider/network/game/bridge/.env/credential/KB publish/install/deploy/push or
main change. Coordinator owns exact combined-tree checks and any publication.
