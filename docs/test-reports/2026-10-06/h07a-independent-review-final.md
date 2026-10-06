# H07a independent final review

Verdict: **APPROVE, scoped to synthetic read-only approval handoff**.
No unresolved blocker remains in the frozen acceptance scope. This does not approve
real human authorization, grants, dispatch, device leases, game effects, broker or
production readiness, and does not authorize a push/merge/deployment by the reviewer.

## Exact source and independence

- Approved code SHA: `b3efd271c79908241b0c7e1acabafbd81c683051`.
- Approved source tree: `7b81ac676314fce3423e07979849b676758aa87c`.
- Packages tree: `46e832a6f4bbfb84e1f49bad517084841dd1b768`.
- Author final handoff: `f04646cc72cc92f8ea928942dd287b88667fe749`, report-only
  changes with the same packages tree. Its code report binds to b3efd271, not itself.
- Independent plan frozen before author implementation access:
  `eeda927c945e765c78ea0512c3b78cf91c210082`.
- Independent actual LF checkout: `/tmp/h07a-cr-b3-20261006`, detached at the
  approved SHA; byte-source preflight and final clean-tree assertion both passed.
- Published baseline remains `110bd7594e095c3ea0e1940ab2fc4bec5f4d7a77`. H07-only
  ancestry and diff were checked. Scope is four changed production modules plus
  one new approval helper, a new test module and one v1 compatibility fixture;
  budget/TaskSpec/catalog/QA/common/KB/old tests/old eval/CI/dependencies unchanged.

Reviewer used independent negative assertions, not a replacement implementation.
Reviewer made no author-source fix, push or merge. Source import into the isolated
review branch does not replace validation of the coordinator's final combined tree.

## Findings closed with original evidence retained

| Finding | Original failure | Verified closure |
| --- | --- | --- |
| F1 P1 | Slow post-observation save allowed stale/deadline-expired goal_verified. | Existing budget/cancel/freshness rules are rechecked after observation, revalidated and policy-pending saves; original deadline assertion and canonical stale/zero-policy assertion pass. |
| F2 P2 | Awaiting saw t+10 then accepted rollback to t+5, dispatching four tools and one policy. | v2 last_checked_at persists waiting high-water mark; same/fresh runner rejects regression, without replenishing ledger. Original frozen assertion passes. |
| F3 P2 | Clock rollback after consumption, or t+10 to t+8 above consumed t+3, allowed goal_verified. | Revalidation compares and advances watermark; at most one owned save per helper boundary followed by bounded recheck; both original frozen triggers pass. New watermark-write failure retains original error and fresh runner remains fail-closed. |

Original red logs and R1/R2 reports are retained, including a23 full-green evidence
which did not establish F3 correctness. No original test assertion or fixture was
weakened. The original reviewer's sole reason typo is separately documented in
`h07a-oracle-correction.md`: baseline requires `observation_stale`, not
`stale_observation`. Production has no alias. Original 339aa probe remains unchanged
and still reports exit 1 for exactly that historical spelling mismatch; this is not
counted as a test pass or as an unresolved production finding.

## Independent source-bound results

| Lane | Result | Exit |
| --- | --- | --- |
| Focused H07a + unchanged task/ownership/CR | 104 pass, zero skip | 0 |
| Pioneer full | 1048 total = 1046 pass + 2 Windows-only skip | 0 |
| QA full | 394 pass | 0 |
| Common full | 2 pass | 0 |
| Immutable original probes 339aa56 | 4 pass; one known oracle-only spelling failure | 1 |
| Canonical probes dcba322 | 5 pass; deadline/rollback unchanged; stale has zero policy assertion | 0 |
| Post-consumption clock probe d9ade7a | 1 pass | 0 |
| High-water progression probe f7e32f0 | 1 pass | 0 |
| Real offline H09 CLI | 8 controls, 2 verified goals, 6 expected safety stops; zero infra/safety/unexpected-goal errors | 0 |
| Old QA v3 | Byte-identical to independent a23 output; recall/MRR 10/11, multiturn 9/9, provider calls 0 | 0 |
| Actual published v1 reader experiment | Exact v1 roundtrip; v2 ValidationError; load does not rewrite bytes | 0 (verifier) |
| Windows native stdlib lock primitives | 3 pass, zero skip, actual Windows Python 3.14 | 0 |

H09 source_verified/complete/valid_suite/gate_pass are true; its stable projection
equals the earlier independently executed baseline lane. Cases are offline
Rule/Fake, not provider vision or live-action evidence. Focused/full/probe coverage
overlaps and must not be added into an inflated independent-sample count.

The two Pioneer skips are native Windows proxy launch integration and PowerShell/cmd
tombstone execution. Native lock tests do not replace them and are not full native
H07a/MCP coverage. Native tests read the exact b3 ext4 source bytes via UNC; their
runtime/command/file hashes are in `h07a-independent-b3-native.json` and raw log.

## Frozen acceptance matrix closure

The new tests and unchanged focused suites actually exercise runner-generated exact
request binding, explicit synthetic opt-in and none/false authority; awaiting
same/fresh resume and CLI zero-connect; denial/expiry/rollback/cancellation and
duplicate response rejection; new observation/session/window/provenance checks;
deadline/quota continuity; request/consumption/revalidation persistence failure;
original exception retention through cleanup; real two-process same-checkpoint
contention and durable-consumption crash; v1 flat/envelope/no-load-migration and
old-reader rejection; terminal/CAS/version non-regression; stop-condition priority
and ordinary pause behavior. The independent extra probes close the discovered
false-goal/time-boundary gaps, including zero-policy oracles.

Static review confirms no policy-owned grant/binding, alternate dispatch channel,
new scheduler/lock/DB, authority expansion or prohibited package changes. Existing
ownership/CAS remains same-host cooperative checkpoint ownership, not a device lease
or proof of exactly-once external effects.

## Evidence integrity and author cross-check

Independent raw commands/logs/checkpoints/source bindings are preserved in
`h07a-independent-b3-full/`. Manifest SHA256:
`d16f3f379333bafdf6d3fb5f426b531cf7cfd79226edaf214b30fe149e2e45e3`.
Every copied file was checked against its manifest. All four independent probe
hashes still match their original freeze commits.

Read-only `h07a-audit-final-handoff.py` verified the fixed f04646 author handoff:
53 Linux files and four native files, every raw SHA256/size, source/tree, actual
command exit (including original probe exit 1), source-input-byte binding and
protected Git metadata. Author and independent source records, frozen probe hashes,
actual-old-reader results, QA-v3 bytes and H09 stable projections match. Audit exited
0; result is `h07a-independent-final-handoff-audit.json`.

No new archive was created. Historical archives were protected only by Git
mode/type/blob metadata; no member was opened. Q06 candidate/content remained out of
scope and unapproved. No dependency installation, .env/credential read, paid model,
real game, bridge, external message, deployment, push or merge was performed.

Prior Windows-checkout CRLF preflight failure remains documented in R2; it was not
waived or repaired in place. Fresh exact-SHA ext4 validation supplied the acceptance
evidence. Final integration must still rerun or verify the exact combined source and
preserve `execution_authority=none`, `executable=false`.
