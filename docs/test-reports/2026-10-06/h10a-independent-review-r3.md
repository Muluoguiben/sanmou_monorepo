# H10a independent review R3

Verdict: **REQUEST CHANGES** for wrong actual-policy binding introduced by lazy
dispatch. Source `38ad046d619b5635c27f43914e7a9321656689e3`, tree
`60b36930b9aaabd8004ec44907a361a83a1a5991`; execution root
`/tmp/h10a-cr-38ad046-20261006`.

## F4 [P2]: lazy entry may call Q under P's provenance and budget choice

`task_runner.py:505-509` chooses model reservation/pending identity from current
policy P; line 526 prepares its provenance. The lazy wrapper at line 539 then
looks up `self.policy.decide` again rather than retaining the selected target.
The timeout sample at line 540 is another public port call between those points.

Independent deterministic probe freezes a valid P (`uses_model=False`), then has
the budget port's remaining_seconds sample hand off to a synthetic Q declaring
`uses_model=True`. The ledger explicitly permits zero model attempts. This is a
controlled local scheduling/port boundary, not a paid provider call or new runtime.

Same frozen probe, two immutable sources:

- 9e6a8bd: actual call P / trace P / model reservations 0; pass, exit 0.
- 38ad046: actual call Q / trace P / model reservations 0; fail, exit 1.

The new wrapper therefore changes the actual callee after its budget/source
decision. Both provenance correctness and the declared-model quota binding are
broken; final policy_stop does not undo the already-entered Q invocation.

Probe `h10a-independent-policy-binding-budget-cut.py` was frozen before execution at
`f56dcc51f34b612107cf2ede5ef484bb13ae2aca`, SHA256
`ab8b059c2906b17fe087dd0832721678543eeb7d3045f9aeccde069e860d6650`.
Raw output: `h10a-9e6a8bd-budget-binding.log` and
`h10a-38ad046-budget-binding-red.log`.

Minimum fix: bind the same selected policy object and callable to model-reservation
selection, declared provenance and lazy invocation, or fail closed if the intended
binding changes. Do not temporarily grant budget to Q, refund existing reservations,
weaken old probes or build a policy hot-reload framework. Keep default v1 unchanged
and preserve the lazy F3 guards/no-inner-awaitable behavior.

## Non-reproduction explicitly retained

The earlier call_soon-on-pending-save variant was frozen at `2772656` and ran on
both 9e and 38ad. Both sources passed two tests, actual P and model count zero.
It is not a failure reproduction. This host's Python 3.12 wait_for implementation
directly awaits the positive-timeout coroutine, so a queued callback did not get
ahead of this synchronous synthetic policy entry. That stdlib implementation was
read locally; no runtime installation or network lookup was used. Its raw logs
`h10a-{9e6a8bd,38ad046}-callsoon-binding.log` are preserved separately.

The budget-port variant above supplies the missing deterministic handoff and proves
the exact late-lookup regression without assuming a different Python scheduler.

## Existing fixes and regression checks on 38ad

All previously frozen acceptance assertions were rerun unchanged:

- Public/default-v1 complete snapshot: 5 pass, exit 0.
- Targeted identity/privacy/task/context digest/H07-version checks: 5 pass, exit 0.
- Short-marker invocation privacy: 1 pass, exit 0.
- Ambient caller primary isolation plus genuine-primary controls: 2 pass, exit 0.
- F3 provenance/deadline actual-call check: 1 test/two subcases pass, exit 0.
- New causal module: 30 pass with RuntimeWarning promoted, exit 0; no coroutine
  warning reported. This includes checks that an expired wrapper does not construct
  an inner awaitable and that old charged reservations are retained.

Thus F1/F2/ambient/F3 repairs remain effective in these exercised cuts. F4 is a new
failure on the same frozen actual-identity/budget boundary, not a reopened old
assertion or expanded permission scope. Full independent matrix is not claimed on
38ad while this fixed-source counterexample is red; prior 9e results remain exact-
source historical evidence. Rerun the complete matrix on the next fixed source.

All commands use Python 3.12.3, existing dependencies and fresh LF source trees.
Every example is synthetic and provider-free. Native new H10 remains not executed.
No archive/Q06/.env/provider/game/bridge/install/main-WIP/push/merge operations.
