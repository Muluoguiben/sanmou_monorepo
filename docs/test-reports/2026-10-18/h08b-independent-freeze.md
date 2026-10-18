# H08b public probe and baseline freeze

Source inspected/executed: `a3985a9217ad815778bf743ec3f840be5ebaa5d3`.
Its `packages/` and `.github/` match published baseline
`155817a444718366c3dbd56ac91fff8d52500fa5` by Git diff exit 0.
Read frozen plan, interface memo `06fd180`, and clarified contract `41be91e4`.
No author WIP or implementing source inspected before freezing these probes.

`h08b-independent-public-probes.py` implements the existing plan's public cuts:
strict mutated/constructed/nested-extra models; complete exact preflight;
ambient direct exception-chain privacy; validation before harness reads and
external-owner/checkpoint side effects; acquire-hook caller mutation; late
budget mutation after prepared provenance and before lazy tool/policy dispatch;
runtime drift latch; exact 101-character skill-only dual-sink format exception.
The syntax-only noncatalog digest sink control does not authenticate a recipe.
These are frozen candidate assertions, not evidence of an implementation defect.

The baseline modes intentionally omit `skill_compilation` entirely. Captured
full default-v1 and unbound-v2 event sequences, terminal reentry, calls and budget
requests/settlements. Only v2 event/lifetime/parent/window/invocation random IDs
and emitted-at timestamps are normalized, declared in the probe before capture.
No other field or event is projected away. Freeze and immediate verification both
exit 0. Oracle SHA256:
`1f67511746be903d11f4d8d5cef24ac8f3b78d3285ad75218003613b1fa1223c`.

WSL Ubuntu Python 3.12.3 was the existing coordinator-verified environment.
Windows default Python 3.14 lacks pydantic; no dependencies installed or searched.
TMPDIR is inside this review tree's ignored `data/agent_runs/` directory.
Old `test_skill_registry` + `test_causal_trace`: 55 tests, 54 pass, 1 error,
0 skips, exit 1. The original error is preserved in
`h08b-baseline-initial-red.log`: JsonRunStore correctly refuses WSL `/mnt/c`
checkpoint locking. This blocks local real-disk checkpoint probes in this tree;
it is not a product regression or a passing native result. No old assertions or
filesystem guards were changed; no missing-interface red was manufactured.

No product/CI/root WIP changes, archives, provider/game/bridge, credentials,
dependency installation, publication, push or merge. Further fixed-SHA review,
original H10 F1-F4/probes, exact composition and final native CI remain pending.
