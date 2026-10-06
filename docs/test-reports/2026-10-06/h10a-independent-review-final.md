# H10a independent final review

Verdict: **APPROVE for the scoped opt-in causal-trace implementation and exercised
offline/Linux gates**. No unresolved finding remains within the frozen contract.
New H10 native coverage is **not_executed**; old H07 Windows35 is not that evidence.

## Exact approved source

- Code: `2128fb88329b1a38b410ad63e09c37034d08e8c7`.
- Tree: `3fe1e07f9d2e30b856d95177298fb80692bf396c`.
- Packages tree: `3d1c4a78faf912f522be764454762601aa1f7409`.
- Author report-only handoff: `762855b6488bf1f0650bba6f6263597638b87fd8`, with the
  same packages tree. The approval is not for an unexamined later combined tree.
- Published baseline: `ae03faf0862f9930c58f7811d625de4b632f05ba`; frozen contract
  `358df146ba184a771d3673428915a70fe8aa4c9c`; independent plan frozen before author
  implementation at `fda28a5aeb370b8f032dfe04e0acb094d00811dd`.
- Independent clean LF source: `/tmp/h10a-cr-2128fb8-20261006`. Review branch retains
  all previous plans, probes, original reds and source-specific R1/R2/R3 reports.

## Findings closed without weakening oracles

| Finding | Verified closure |
| --- | --- |
| F1: completion name/metadata differed from pre-call identity | The actual invocation's captured policy identity supplies both display fields and provenance. Original identity-mutation assertion passes. |
| F2: new trace wrapper disclosed secondary sink/validation text | No raw secondary cause is retained; wrapper context is suppressed and invocation validation leaves its handler before raising. Original long/short-marker and formatted-traceback controls pass; genuine primary objects/classification are not scrubbed or replaced. |
| Ambient caller exception polluted primary precedence | Window/tool/policy capture their current operation's exception explicitly. The identical frozen test had four red boundaries on dfa and passes on approved source; handled outer exceptions do not hide logging failure, while genuine policy/cancel failures still win. |
| F3: exhausted provenance deadline invented invocation | Local lazy wrappers recheck guards and publish identity only at entered dispatch. Unentered tool/policy records retain not_attempted, no invocation/context digest; charged reservations are not refunded. Frozen fe73 passes. |
| F4: lazy call could use Q under P's source/budget choice | Before reserving budget, v2 captures the same policy object, bound callable, id and uses_model. That binding supplies reservation selection, provenance and invocation. Frozen f56 reports actual P = trace P, model reservations 0; Q is not called. Added tests cover callable replacement and reservation-time object replacement. |

The call_soon scheduling variant remains a non-reproduction on this Python 3.12
runtime; it is not used to claim F4 was reproduced or fixed. Its old/new passing
logs remain separate from the deterministic budget-port red. The original long
privacy marker alone was insufficient due possible validation repr truncation;
the short-marker original assertion remains required. No old assertion/fixture was
relaxed, no failure was converted into a skip, and no production fix was authored
by the reviewer.

## Independent source-bound validation

All commands in the final independent matrix exited 0. Coverage overlaps and must
not be summed as independent samples.

- Original public/default-v1 probes: 5 pass; targeted provenance/privacy: 5 pass;
  short-marker invocation privacy: 1 pass; ambient-primary: 2 pass; F3 deadline:
  1 test/two subcases pass; F4 budget binding: 1 pass.
- Long-marker control (1) and non-reproducing call_soon/default control (2) were
  also rerun unchanged, but are not substitutes for the stronger privacy/F4 oracles.
- New causal module: 32 pass; existing H07a module: 35 pass; focused: 177 pass.
- Pioneer full: 1085 total = 1083 pass + two existing Windows-only skips.
- QA full: 394 pass; common full: 2 pass.
- Actual H09 CLI: source_verified/complete/gate_pass true; eight controls, two
  verified goals, six expected safety stops; zero infra/safety/unexpected-goal errors.
- Frozen QA-v3 SHA256 unchanged:
  `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`.

Every existing task_contracts class/function definition and default _safe_event
passed AST equality against the published baseline. Old tests/fixtures, checkpoint,
budget implementation, CLI/CI, MCP, QA/common/KB have no changes. The complete v1
oracle still matches all 16 events/fields/order, 12 tools, first tool/session_status
and terminal reentry with zero added events. Old H09 score/error/index consumers
therefore receive no new v2 IDs through the default path.

The new public-schema controls independently compute actual validated TaskSpec and
pre-call PolicyContext digests, verify mutation resistance, event-time H07 v1/v2
state provenance, same/fresh lifetime separation, exact call ledger/parent graph,
emit-only sink compatibility, two-sink identity/minimization parity and unknown
usage. Source labels remain declared/unknown/absent rather than source authentication.
Model reservation IDs and actual invocation IDs remain separate; Rule/Fake has no
invented provider usage or model reservation.

## Evidence integrity and final handoff cross-check

`h10a-independent-2128fb8/` contains only this source's 33 raw log/command/source
files (478310 bytes) plus compact summary. Summary SHA256:
`2ee574390c5a2593347198a896db5019b15da48afd3e3485b41f7315a91ba525`.
Copied files match the full runtime manifest. Full generated H09/v3 JSON artifacts
remain at the explicit fresh /tmp paths and hashes in summary, avoiding duplicated
case/checkpoint matrices. Earlier original evidence remains unmodified.

Read-only `h10a-final-handoff-audit-r4.py` checked the fixed author's report and all
14 final log blobs: bytes/SHA256, actual counts/skips/exits, verifier hash and every
frozen probe/oracle hash. Author H09 source/stable projection and QA-v3 bytes match
the independent run. Author summary SHA256:
`66b41ab5e26dcac93a6fb9f8567baf1c1af4b3b1284a75a1ed925b2621d82abe`.

The 27-event sample (SHA256
`e7012df93a50a0d30be6a594bdd6fe94ce02fe11c3a6d79d1d90211e66b1791a`) has valid
same-lifetime parents, three windows, 12 tools, three observations/policies/outcomes
and 15 unique actual invocation IDs; policy attempt_id/usage remain None and the
reported ledger is step=3/tool=12/model=0. Audit exited 0; result is retained in
`h10a-final-handoff-audit-r4.json`. The sample is synthetic runtime evidence, not
an audit of provider internals, trusted time or real-world effects.

## Limits / integration handoff

New H10 native execution was not performed; no dependency installation/exploration
was resumed. The two full-suite skips are the old Windows proxy/tombstone cases,
not new H10 passes. Existing H07 Windows evidence is not reused as native causal-
trace proof. Full H10, distributed tracing, exactly-once, real human authorization,
source authenticity and production readiness remain outside this approval.

No archive body/member, Q06 payload/ancestry, credentials/.env, provider/game/bridge,
installation, deployment, main WIP, push or merge was accessed/performed by this
review. All behavior remains recommendation-only, execution_authority=none and
executable=false. The coordinator still owns exact combined-tree verification and
any later authorized integration/publication; this review does not itself authorize
new execution capability or substitute for that final source check.
