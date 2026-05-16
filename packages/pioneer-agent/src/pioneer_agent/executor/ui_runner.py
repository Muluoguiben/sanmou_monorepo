"""Drop-in replacement for `ActionRunner` that dispatches via UIActions.

Keeps the existing ActionRunner (non-implemented stub) untouched so
existing unit tests continue to pass. Consumers opt in by injecting
`UIActionRunner` into `AgentRuntime` instead.
"""
from __future__ import annotations

from pioneer_agent.core.device import CapabilityFlags
from pioneer_agent.core.models import CandidateAction, ExecutionResult
from pioneer_agent.executor.action_handlers import dispatch
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.safety.guard import GuardDecision, SafetyGuard, SessionMode


class UIActionRunner:
    def __init__(
        self,
        ui: UIActions,
        *,
        capabilities: CapabilityFlags | None = None,
        safety_guard: SafetyGuard | None = None,
        session_mode: SessionMode | str | None = None,
    ) -> None:
        self.ui = ui
        self.capabilities = capabilities
        self.safety_guard = safety_guard or SafetyGuard()
        self.session_mode = session_mode

    def run(self, action: CandidateAction) -> ExecutionResult:
        verdict = self.safety_guard.evaluate(
            action.action_type,
            risk=action.risk,
            capabilities=self.capabilities,
            session_mode=self.session_mode,
            confirmation_token=_confirmation_token(action),
        )
        if verdict.decision != GuardDecision.ALLOW:
            status = "requires_confirmation" if verdict.decision == GuardDecision.REQUIRE_CONFIRMATION else "blocked"
            return ExecutionResult(
                action_id=action.action_id,
                status=status,
                verification_status="not_applicable",
                failure_reason=verdict.reason,
                recovery_required=False,
                summary={
                    "action_type": action.action_type.value,
                    "blocked_by": "safety_guard",
                    "guard_decision": verdict.decision.value,
                    "risk_level": verdict.risk_level.value,
                    "observe_only": self.capabilities.observe_only if self.capabilities else None,
                },
            )
        return dispatch(action, self.ui)


def _confirmation_token(action: CandidateAction) -> str | None:
    value = action.params.get("confirmation_token")
    return value if isinstance(value, str) else None
