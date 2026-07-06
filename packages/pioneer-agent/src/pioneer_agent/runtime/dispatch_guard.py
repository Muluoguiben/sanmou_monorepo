"""Single seam for every input-dispatch decision in the autonomous loop.

Every path that injects input into the client — action dispatch in the tick,
the terminal click of a multi-step flow, and ESC recovery — must ask this
guard first. A new dispatch path added to the loop is guarded by construction
instead of hand-assembling its own subset of checks (the failure mode that
produced the continuation and ESC bypasses).
"""
from __future__ import annotations

from dataclasses import dataclass

from pioneer_agent.core.models import CandidateAction
from pioneer_agent.runbook.action_filter import (
    RUNBOOK_FILTER_REJECT_REASON,
    action_type_allowed,
    normalized_allowed_action_types,
)
from pioneer_agent.runbook.models import RunbookDecision
from pioneer_agent.safety.kill_switch import KillSwitch

# Runbook hold reasons that must block input dispatch (safety semantics);
# other holds only pause phase transitions while in-phase work continues.
RUNBOOK_BLOCKING_HOLDS = frozenset(
    {"abort_triggered", "human_gate_pending", "runbook_completed"}
)

KILL_SWITCH_REASON = "kill_switch"


@dataclass(frozen=True)
class DispatchVerdict:
    allowed: bool
    reason: str | None = None
    failure_reason: str | None = None


_ALLOW = DispatchVerdict(allowed=True)


class DispatchGuard:
    def __init__(self, *, kill_switch: KillSwitch | None = None) -> None:
        self.kill_switch = kill_switch
        self._decision: RunbookDecision | None = None

    def update_decision(self, decision: RunbookDecision | None) -> None:
        self._decision = decision

    @property
    def decision(self) -> RunbookDecision | None:
        return self._decision

    @property
    def kill_switch_active(self) -> bool:
        return self.kill_switch is not None and self.kill_switch.is_triggered()

    @property
    def runbook_hold_active(self) -> bool:
        return (
            self._decision is not None
            and self._decision.hold_reason in RUNBOOK_BLOCKING_HOLDS
        )

    def action_verdict(self, action: CandidateAction) -> DispatchVerdict:
        """May this selected action be dispatched right now?"""
        base = self._input_verdict()
        if not base.allowed:
            return base
        if self._decision is not None:
            allowed = normalized_allowed_action_types(self._decision.selector_hints)
            if not action_type_allowed(action.action_type, allowed):
                return DispatchVerdict(
                    allowed=False,
                    reason=RUNBOOK_FILTER_REJECT_REASON,
                    failure_reason=RUNBOOK_FILTER_REJECT_REASON,
                )
        return _ALLOW

    def recovery_verdict(self) -> DispatchVerdict:
        """May non-action input (ESC recovery / close_popup) be dispatched?"""
        return self._input_verdict()

    def _input_verdict(self) -> DispatchVerdict:
        if self.kill_switch_active:
            return DispatchVerdict(
                allowed=False,
                reason=KILL_SWITCH_REASON,
                failure_reason="manual kill switch is active",
            )
        if self.runbook_hold_active:
            reason = f"runbook_hold:{self._decision.hold_reason}"
            return DispatchVerdict(allowed=False, reason=reason, failure_reason=reason)
        return _ALLOW
