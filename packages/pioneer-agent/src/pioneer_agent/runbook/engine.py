"""Deterministic runbook phase machine.

The engine holds a cursor into an OpeningRunbook and, given a metrics
mapping, decides whether to stay, advance one phase, or escalate. It never
guesses: unknown metrics, blocked entries, abort triggers, and human gates
all surface as RunbookEscalation events routed to an LLM planner or a human.
The engine performs no I/O and calls no model — it is safe to run every tick.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

from pioneer_agent.runbook.models import (
    ConditionStatus,
    EscalationKind,
    EscalationRoute,
    OpeningRunbook,
    PhaseDefinition,
    RunbookDecision,
    RunbookEscalation,
    evaluate_all,
    evaluate_any,
)

logger = logging.getLogger(__name__)


class RunbookEngine:
    def __init__(
        self,
        runbook: OpeningRunbook,
        *,
        start_phase_id: str | None = None,
        confirmed_gates: Iterable[str] | None = None,
        completed: bool = False,
    ) -> None:
        self.runbook = runbook
        self._index = runbook.phase_index(start_phase_id) if start_phase_id else 0
        self._completed = bool(completed)
        self._confirmed_gates: set[str] = set()
        for phase_id in confirmed_gates or ():
            self.confirm_human_gate(phase_id)

    @property
    def current_phase(self) -> PhaseDefinition:
        return self.runbook.phases[self._index]

    @property
    def completed(self) -> bool:
        return self._completed

    @property
    def confirmed_gates(self) -> frozenset[str]:
        return frozenset(self._confirmed_gates)

    def confirm_human_gate(self, phase_id: str) -> None:
        """Record operator approval for a human_gate phase (e.g. 二拖一)."""
        self.runbook.phase(phase_id)
        self._confirmed_gates.add(phase_id)

    def override_phase(self, phase_id: str) -> None:
        """Planner/human override: jump the cursor, e.g. fall back a phase after abort."""
        self._index = self.runbook.phase_index(phase_id)
        self._completed = False

    def evaluate(self, metrics: Mapping[str, Any]) -> RunbookDecision:
        phase = self.current_phase
        if self._completed:
            return RunbookDecision(
                phase_id=phase.phase_id,
                previous_phase_id=phase.phase_id,
                completed=True,
                hold_reason="runbook_completed",
                selector_hints=dict(phase.selector_hints),
            )

        # The gate also guards start_phase_id / override_phase / restart resume:
        # an unconfirmed human_gate phase never hands out selector hints.
        if phase.human_gate and phase.phase_id not in self._confirmed_gates:
            return RunbookDecision(
                phase_id=phase.phase_id,
                previous_phase_id=phase.phase_id,
                hold_reason="human_gate_pending",
                human_gate_pending=phase.phase_id,
                selector_hints={},
                escalations=[
                    RunbookEscalation(
                        kind=EscalationKind.HUMAN_GATE,
                        route=EscalationRoute.HUMAN,
                        phase_id=phase.phase_id,
                        details={
                            "goal": phase.goal,
                            "title": phase.title,
                            "checked": "current_phase",
                        },
                    )
                ],
            )

        escalations: list[RunbookEscalation] = []

        abort_result = evaluate_any(phase.abort_when, metrics)
        if abort_result.status == ConditionStatus.SATISFIED:
            escalations.append(
                RunbookEscalation(
                    kind=EscalationKind.ABORT_TRIGGERED,
                    route=EscalationRoute.LLM_PLANNER,
                    phase_id=phase.phase_id,
                    details={
                        "triggered": [e.to_dict() for e in abort_result.satisfied],
                        "abort_result": abort_result.to_dict(),
                    },
                )
            )
            logger.warning("runbook: abort triggered in phase %s", phase.phase_id)
            return RunbookDecision(
                phase_id=phase.phase_id,
                previous_phase_id=phase.phase_id,
                hold_reason="abort_triggered",
                selector_hints=dict(phase.selector_hints),
                escalations=escalations,
                abort_result=abort_result.to_dict(),
            )

        if abort_result.status == ConditionStatus.UNKNOWN:
            escalations.append(
                RunbookEscalation(
                    kind=EscalationKind.UNKNOWN_METRICS,
                    route=EscalationRoute.LLM_PLANNER,
                    phase_id=phase.phase_id,
                    details={
                        "missing_metrics": abort_result.missing_metrics,
                        "checked": "abort_when",
                    },
                )
            )

        exit_result = evaluate_all(phase.exit_when, metrics)
        if exit_result.status == ConditionStatus.UNKNOWN:
            escalations.append(
                RunbookEscalation(
                    kind=EscalationKind.UNKNOWN_METRICS,
                    route=EscalationRoute.LLM_PLANNER,
                    phase_id=phase.phase_id,
                    details={"missing_metrics": exit_result.missing_metrics, "checked": "exit_when"},
                )
            )
            return RunbookDecision(
                phase_id=phase.phase_id,
                previous_phase_id=phase.phase_id,
                hold_reason="exit_metrics_unknown",
                selector_hints=dict(phase.selector_hints),
                escalations=escalations,
                exit_result=exit_result.to_dict(),
                abort_result=abort_result.to_dict(),
            )

        if exit_result.status == ConditionStatus.NOT_SATISFIED:
            return RunbookDecision(
                phase_id=phase.phase_id,
                previous_phase_id=phase.phase_id,
                selector_hints=dict(phase.selector_hints),
                escalations=escalations,
                exit_result=exit_result.to_dict(),
                abort_result=abort_result.to_dict(),
            )

        # Exit is satisfied, but never advance while safety (abort) metrics are
        # dark — hold and let the planner/human clear the blind spot first.
        if abort_result.status == ConditionStatus.UNKNOWN:
            return RunbookDecision(
                phase_id=phase.phase_id,
                previous_phase_id=phase.phase_id,
                hold_reason="abort_metrics_unknown",
                selector_hints=dict(phase.selector_hints),
                escalations=escalations,
                exit_result=exit_result.to_dict(),
                abort_result=abort_result.to_dict(),
            )

        return self._try_advance(phase, metrics, exit_result.to_dict(), abort_result.to_dict())

    def _try_advance(
        self,
        phase: PhaseDefinition,
        metrics: Mapping[str, Any],
        exit_result: dict[str, Any],
        abort_result: dict[str, Any],
    ) -> RunbookDecision:
        next_index = self._index + 1
        if next_index >= len(self.runbook.phases):
            self._completed = True
            logger.info("runbook: final phase %s complete", phase.phase_id)
            return RunbookDecision(
                phase_id=phase.phase_id,
                previous_phase_id=phase.phase_id,
                completed=True,
                selector_hints=dict(phase.selector_hints),
                exit_result=exit_result,
                abort_result=abort_result,
            )

        next_phase = self.runbook.phases[next_index]
        entry_result = evaluate_all(next_phase.entry_when, metrics)

        if entry_result.status == ConditionStatus.UNKNOWN:
            return RunbookDecision(
                phase_id=phase.phase_id,
                previous_phase_id=phase.phase_id,
                hold_reason="entry_metrics_unknown",
                selector_hints=dict(phase.selector_hints),
                escalations=[
                    RunbookEscalation(
                        kind=EscalationKind.UNKNOWN_METRICS,
                        route=EscalationRoute.LLM_PLANNER,
                        phase_id=next_phase.phase_id,
                        details={
                            "missing_metrics": entry_result.missing_metrics,
                            "checked": "entry_when",
                        },
                    )
                ],
                exit_result=exit_result,
                abort_result=abort_result,
            )

        if entry_result.status == ConditionStatus.NOT_SATISFIED:
            return RunbookDecision(
                phase_id=phase.phase_id,
                previous_phase_id=phase.phase_id,
                hold_reason="next_entry_not_satisfied",
                selector_hints=dict(phase.selector_hints),
                escalations=[
                    RunbookEscalation(
                        kind=EscalationKind.BLOCKED_TRANSITION,
                        route=EscalationRoute.LLM_PLANNER,
                        phase_id=next_phase.phase_id,
                        details={
                            "failed": [e.to_dict() for e in entry_result.failed],
                            "entry_result": entry_result.to_dict(),
                        },
                    )
                ],
                exit_result=exit_result,
                abort_result=abort_result,
            )

        if next_phase.human_gate and next_phase.phase_id not in self._confirmed_gates:
            return RunbookDecision(
                phase_id=phase.phase_id,
                previous_phase_id=phase.phase_id,
                hold_reason="human_gate_pending",
                human_gate_pending=next_phase.phase_id,
                selector_hints=dict(phase.selector_hints),
                escalations=[
                    RunbookEscalation(
                        kind=EscalationKind.HUMAN_GATE,
                        route=EscalationRoute.HUMAN,
                        phase_id=next_phase.phase_id,
                        details={"goal": next_phase.goal, "title": next_phase.title},
                    )
                ],
                exit_result=exit_result,
                abort_result=abort_result,
            )

        self._index = next_index
        logger.info("runbook: %s -> %s", phase.phase_id, next_phase.phase_id)
        return RunbookDecision(
            phase_id=next_phase.phase_id,
            previous_phase_id=phase.phase_id,
            transitioned=True,
            selector_hints=dict(next_phase.selector_hints),
            exit_result=exit_result,
            abort_result=abort_result,
        )
