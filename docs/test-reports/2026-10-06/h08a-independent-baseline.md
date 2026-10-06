# H08a preimplementation independent controls / baseline

Public registry/runtime probes frozen in `3ce5a9d9d8ad6cd1cf8f5710aa844516a12e4cca`
before reading author implementation. Five public controls cover exact builtin and
full canonical digests, nested isolation, strict identity/parameter/admission,
tri-state flat-precedence semantics, and zero runtime/model calls. Four integration
controls use existing SequenceClient, runner, Rule policy and budget/store ports.
Private internal duplicate validation will receive a separately frozen probe only
after fixed code identifies that internal surface; no public registration is added.

Baseline verifier c62f168 ran actual published
`60e3e002c7b38571e76d344dd100b47d053244e2` in fresh LF tree
`/tmp/h08a-cr-baseline-60e3-20261006`, existing dependencies only.

The four existing-runtime controls all passed using a manually constructed TaskSpec
from the frozen H08a contract, without importing the not-yet-reviewed registry:

- target3 requires obs-1/2/3, twelve actual offline tool calls, goal evidence and
  zero model reservations; terminal reentry adds no calls. The opaque @/: task ID
  persists through JsonRunStore at an explicit independent checkpoint path.
- Missing or wrong field observation evidence fails at the original step limit,
  even when the intended future precheck declares target already satisfied.
- Real RunBudgetLedger tool cap and original pause interrupt block further calls.
- A stale observation is rejected before FakeDecisionPolicy is invoked.

Real QA CLI baselines also match exactly:

- v4 SHA256 `c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`.
- Q04 SHA256 `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`.
- v1/v2/v3 each retain explicit source-drift refusal and expected exit 1.

Full argv/source/tree/exits and raw log hashes are in
`h08a-independent-baseline-results/summary.json`; the actual CLI JSONs remain at
`/tmp/h08a-cr-baseline-60e3-results/{v4,q04}.json`. No missing-registry ImportError
was manufactured or counted as a product red. No old full matrix was rerun.
No author implementation, runtime source, old assertion/fixture/gold, main/WIP or
CI was changed. No Q06/archive body/member, provider/network/game/bridge/.env,
install or push actions. Fake offline ports are not real MCP/game/provider proof.
