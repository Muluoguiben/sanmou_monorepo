# H07a durable recovery / Windows step: independent review

Scope verdict: **APPROVE for reviewed code and independently executed Linux gates**.
**Native complete-module acceptance remains PENDING the final Hosted Windows CI
step**. This report does not claim a local native 35-test pass, live MCP transport,
real approval/game operation, power-loss durability or production readiness.

Reviewed code `b785458e9b322707e38f0b424ab78a9512abd8d1`, tree
`726d99e49ab3fe0822b0bc306870f7d98d319cb0`, based on published
`ca04ae1ef396576c5983f887502bf20b7d6f0015` and frozen contract `ecf50e0012c336c131f75b9bc6c102530a0d1876`.
Independent plan was committed before author WIP at `f5c7206`, then bound to the
contract at `04a919b2609265db6e721eab1b39cd5a368953cc`. No author code was fixed by
reviewer. Independent probes/verifier were frozen at `b93d6492fa8987918c8d86ca6647762beb1aa2f2`
before execution. Actual source ran from a clean fixed detached ext4 checkout,
`/tmp/h07a-native-cr-b785458-20261006`.

## Scope and test effectiveness

The code diff is exactly two files, 213 additions and zero deletions: five new
approval tests plus their local helpers, and one Windows job step. The two intended
recovery boundaries are split into five explicit positive/negative test methods;
the actual complete module has 35 tests, not a forced count of 32.

Independent AST comparison confirms every preexisting function/helper and all 30
old test method bodies are unchanged. YAML structural comparison confirms removal
of the sole added H07a step makes the entire workflow identical to baseline,
including permissions/dependencies/runner/timeouts and H06/H09/API/Desktop steps.
Production code is unchanged. The new step runs the complete module from the tests
directory without skip-on-import-failure or error suppression.

Actual JsonRunStore tests check durable waiting watermark updates through new store
and runner/ledger instances, unchanged request/expiry/deadline and reservations,
remaining-time reduction, and independent approval-clock/deadline negatives with
zero new tools/policy. This is real-file/new-reader coverage, not falsely labeled
as a separate process restart.

The two new process cases really use spawn children and stop them after the actual
approval_revalidated write, before policy. Raw proof includes checkpoint bytes/hash,
running status, obs-2 and zero policy calls; parent validates the bytes after child
termination. Fresh recovery rejects reusing the response, observes obs-3 before its
policy context, preserves old charges and adds only newly attempted work. The replay
negative stops with reused_observation before policy. The interrupted pending step
stays charged; the tests correctly do not invent a requirement that it be cleared.
The older consumed-but-not-revalidated crash test remains unchanged and fail-closed.

Additional independent controls used these unchanged new tests without editing
production files: in-process temporary mutation that refunded reservations was
caught by the reservation-equality assertion; mutation that skipped the fresh
observation was caught by the expected tool sequence assertion. Each produced
exactly one expected assertion failure and zero test errors, and the controls'
outer verifier passed. Their raw FAIL sections are intentional detection evidence,
not production-suite failures. Independent boundary reruns also recorded actual
spawn PIDs 2674244/2674253 and joined exit -15, with no surviving test child.

## Independently executed results

- Five new boundary cases: 5 pass, zero skip; two negative controls detected.
- Complete approval module: 35 pass, zero skip, exit 0.
- Focused task/ownership/CLI/CR regression: 109 pass, exit 0.
- Pioneer full: 1053 total, 1051 pass and two existing Windows-only skips, exit 0.
- QA full: 394 pass; common full: 2 pass; exit 0 each.
- Actual H09 CLI: source_verified/complete/gate_pass true; eight controls, two goals,
  six expected safety stops, zero infra/safety/unexpected-goal errors, exit 0.
- Frozen QA v3: exit 0; exact SHA256
  `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8` retained.

These overlapping lanes must not be summed into independent sample counts. The
Linux skips remain the old Windows proxy integration and tombstone checks; they
are not passes. No native whole-module test was run or skipped by this reviewer:
coordinator reported existing native MCP/runtime dependencies unavailable, and the
explicit instruction was to stop local environment exploration without installing
or bypassing dependencies. The coordinator's small native fixed-disk helper check
is auxiliary only, not 35-test or MCP evidence. Final exact-SHA Hosted Windows CI
must still execute the new step successfully with zero skipped approval tests.

## Evidence and remaining gate

Fresh evidence only is preserved in `h07a-native-recovery-independent-b785458/`:
commands/exit codes, raw output, actual H09 artifacts, frozen QA-v3 result, source
file hashes and old-AST/workflow checks. Total evidence is bounded (45 files,
976395 bytes). Every copied file matches its manifest; manifest SHA256 is
`528e0d9075ec97eaada7219e7c25e6fc084e5db2c3622560b14fbde09a2459b0`.
The verifier exited 0 and records `native_status=pending_hosted_windows_ci`.

Author fixed-handoff cross-check: `61132b6962f45c95d5adb916bc90ff1c4319950b` is
report-only above the reviewed code. Both commits have packages tree
`8df6ebbd7eec3323f8f3e2054013157de2861c8e` and .github tree
`7235130b9af9859cec2193f3268b47eb8a4d72ca`. The report was read in full; the new
seven raw logs were verified from fixed Git blobs against their byte counts and
SHA256, and the actual unittest counts/skips/outcomes were checked against summary.
Author verifier SHA256 matched its committed blob. The explicit new H09 JSON
matched its recorded hash, code/tree and independent stable projection; QA-v3 was
byte-identical to the independent run. Read-only audit exited 0 and is preserved in
`h07a-native-recovery-handoff-audit.json`; author summary SHA256 is
`a609e92f543c8a4d02b26fd4a174d43b2b8628061b954e52d1d3ce6955eeacc2`.

No unresolved code/Linux finding remains. The coordinator must still verify the
exact combined tree and final Windows job; this scoped review is not a substitute
for pending native acceptance. Do not mark complete native coverage until the new
Hosted step actually reports all 35 approval tests passing with zero skips for the
final source. No push/merge was performed by reviewer.

No archive body/member or Q06 payload/ancestry was read. Main WIP was not touched.
No dependencies, credentials, .env, provider, game, bridge, deployment, push or
authority were added. Synthetic none/false behavior and old assertions remain intact.
