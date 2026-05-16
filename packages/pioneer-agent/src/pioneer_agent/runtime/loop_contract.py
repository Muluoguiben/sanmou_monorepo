from __future__ import annotations

from pioneer_agent.storage.trace_store import TickTrace, TracePhase


LOOP_PHASE_ORDER: tuple[TracePhase, ...] = (
    TracePhase.OBSERVE,
    TracePhase.DECIDE,
    TracePhase.ACT,
    TracePhase.VERIFY,
    TracePhase.TRACE,
    TracePhase.RECOVER,
)


def validate_loop_contract(trace: TickTrace) -> list[str]:
    problems: list[str] = []
    if trace.current_phase != TracePhase.TRACE:
        problems.append(f"current_phase must end at trace, got {trace.current_phase.value}")

    for phase in LOOP_PHASE_ORDER:
        step = getattr(trace, phase.value)
        if step is None:
            problems.append(f"missing {phase.value} step")
            continue
        if step.phase != phase:
            problems.append(
                f"{phase.value} step phase mismatch: got {step.phase.value}"
            )

    if not trace.next_recovery_strategy:
        problems.append("next_recovery_strategy is required")
    return problems


def ensure_loop_contract(trace: TickTrace) -> TickTrace:
    problems = validate_loop_contract(trace)
    if problems:
        raise ValueError("loop contract violation: " + "; ".join(problems))
    return trace
