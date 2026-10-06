# H10a independent review R2

Verdict: **REQUEST CHANGES** for a remaining actual-invocation accounting defect.
Source `9e6a8bd7ec1b72318c0bd00637be4b92f3483aa8`, tree
`83fae646d1d89ae16b65de99eff2e41a86df8a28`.
R1 F1/F2 and the ambient-primary repair passed unchanged independent controls.
All listed full regression lanes passed, but that does not override the new red.

## F3 [P2]: deadline before coroutine entry is recorded as an invocation

`task_runner.py` creates the v2 invocation identity/provenance immediately before
`asyncio.wait_for` in both policy and tool paths (policy around lines 516-525;
tool around 684-690). `task_trace.py:invocation` may spend time computing the
provenance after the prior budget guard. If that work exhausts remaining_seconds,
wait_for(timeout=0) cancels the coroutine before its body enters. The trace still
has a non-null invocation_id and transport=error, and the policy trace additionally
claims an invoked-input context_digest although policy never received execution.

Independent frozen probe `fe73b8aa56797abec06769e410116cb7727b26f9`, file
`h10a-independent-dispatch-deadline.py`, SHA256
`7b177b2da24dc3734eae3d6834ea47527e796c2b3cec57fec192bb2568be7191`, advances
controlled wall/monotonic time while a valid custom policy_version declaration is
read at the pending tool or pending policy cut. This models provenance work
consuming deadline, not an invalid schema, model request or new execution authority.

Both cases first assert failed/run_deadline and actual call ledgers (tool case:
zero tools/zero policy; policy case: four earlier tools/zero policy). Both then fail
because the selected record claims transport=error and an invocation UUID. Actual
process exit 1, one test/two failed subcases. Raw:
`h10a-9e6a8bd-dispatch-deadline-red.log`.

Minimum fix: v2 must distinguish a reserved/planned call from the awaitable actually
entering dispatch; account for provenance work in pre-dispatch deadline/cancel
guards. A coroutine not entered must not claim invocation_id/context_digest or an
attempted transport. Keep existing charged reservations (no refunds), default v1,
budget implementation and scope unchanged; no new scheduler is needed. Re-run
the unchanged probe on the fixed source and retain this original output.

## Closed controls and source-bound full results

Independent current-source results, all exit 0 unless noted above:

- Frozen public/default-v1 oracle: 5 pass; targeted provenance/privacy: 5 pass;
  short-marker invocation privacy: 1 pass. Long-marker control also passes but is
  not a substitute for the short-marker privacy oracle.
- Ambient caller probe `4593df8`: old dfa had four failed boundary subcases; new 9e
  has 2 passing tests, preserving genuine policy/cancel primaries. Old/new raw logs
  remain committed. Actual call counts at the failure cuts are 1/4/4/12, with no
  emit retries, and a saved terminal is not rolled back.
- New causal module 26; H07a module 35; focused 171; Pioneer 1079 total = 1077 pass
  + two existing Windows-only skips; QA 394; common 2.
- Actual H09 CLI: source_verified/complete/gate_pass true, eight controls, two goals,
  six expected safety stops, zero infra/safety/unexpected-goal errors.
- Frozen QA v3 SHA256 remains
  `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`.
- AST checks prove every preexisting task_contracts definition and default
  _safe_event remain unchanged; old tests/fixtures/checkpoint/budget/QA/common/CI
  paths have no changes. The default oracle still preserves all 16 events, order,
  fields and terminal no-op, with no random v2 contamination of H09.

Compact evidence `h10a-independent-9e6a8bd/` contains 27 copied logs/command/source
files (472063 bytes) plus summary. Complete generated H09/v3 artifacts remain at
explicit fresh /tmp paths and are hash-bound in summary, not duplicated matrices.
These lanes' empty failures list does not include the separate frozen F3 probe.

## Author report cross-check / limits

Fixed report handoff `b8ef01a7f777c1232f0f62639794fe256d478746` has the same packages
tree `b985fc15756f37e328ba24e5b28e897c382cdd3d` as 9e. Eleven raw logs, their counts/
skips/exits/bytes/SHA256, verifier hash and frozen-input hashes were independently
checked from new plain Git blobs. H09 source/stable projection and QA-v3 bytes agree
with independent output. The raw 27-event sample has one lifetime, three windows,
12 tools, three observations/policies/outcomes, 15 unique actual invocation IDs and
valid parents; Rule/Fake model reservations remain zero. This healthy sample does
not prove the exhausted-deadline cut.

Audit result is `h10a-final-handoff-audit.json`, exit 0. The audit parser's initial
failure on unittest's singular `Ran 1 test` was corrected to accept singular/plural
grammar; original parser output is retained. No test/implementation oracle changed.

New H10 native coverage is not executed; old H07 Windows35 is not that evidence.
No Q06/archive body/member access, provider/game/bridge/.env/install/push/merge or
main-WIP changes. Recommendation-only none/false remains unchanged.
