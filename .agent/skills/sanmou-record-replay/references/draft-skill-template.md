# Draft Skill Review Template

Use this checklist when turning compiler output into a human-reviewed skill proposal. Do not edit the raw trace.

## Identity

- Proposed workflow name:
- Source session IDs:
- Holdout session IDs:
- Reviewer and review date:
- Intended page/domain:
- Risk class:

## Preconditions

- Observable starting page:
- Required semantic targets:
- Target uniqueness rule:
- Required runtime fields:
- Known popups or interruptions:
- Unresolved assumptions:

## Reviewed Steps

For each step, document the reviewed action API, semantic target, current-frame evidence, expected new observation, timeout, and stop condition. Do not copy demonstration coordinates into executable instructions.

## Verifier

- Action-specific expected delta:
- Positive examples:
- No-change examples:
- Negative and ambiguous examples:
- False-positive and false-negative measurements:
- New-frame/freshness requirement:

## Recovery and Safety

- Safe no-op behavior:
- Known-state recovery:
- Kill-switch behavior:
- Operator confirmation scope:
- Actions explicitly excluded:

## Independent Eval

- Generation/eval session overlap check:
- Cross-size and cross-state coverage:
- Unknown-target result:
- Popup-interrupt result:
- Timeout/no-change result:
- Zero-dispatch safety result:
- Fresh-agent forward-test result:

## Promotion Decision

Leave the decision as `pending_review` until every required gate is evidenced. Record rejected assumptions and failure cases; do not silently weaken the gate to make the skill pass.
