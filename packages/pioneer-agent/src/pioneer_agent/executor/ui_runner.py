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
from pioneer_agent.runtime.architecture_gates import (
    ArchitectureGateDecision,
    AutomationMode,
    AutomationReadinessGate,
)
from pioneer_agent.safety.guard import GuardDecision, SafetyGuard, SessionMode
from pioneer_agent.verifier.registry import VerifierGateDecision, VerifierRegistry


class UIActionRunner:
    def __init__(
        self,
        ui: UIActions,
        *,
        capabilities: CapabilityFlags | None = None,
        safety_guard: SafetyGuard | None = None,
        session_mode: SessionMode | str | None = None,
        verifier_registry: VerifierRegistry | None = None,
        automation_mode: AutomationMode | str = AutomationMode.SEMI_AUTO,
        automation_gate: AutomationReadinessGate | None = None,
    ) -> None:
        self.ui = ui
        self.capabilities = capabilities
        self.safety_guard = safety_guard or SafetyGuard()
        self.session_mode = session_mode
        self.verifier_registry = verifier_registry or VerifierRegistry()
        self.automation_mode = automation_mode
        self.automation_gate = automation_gate or AutomationReadinessGate()

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
        verifier_verdict = self.verifier_registry.evaluate(action.action_type)
        if verifier_verdict.decision != VerifierGateDecision.ALLOW:
            return ExecutionResult(
                action_id=action.action_id,
                status="blocked",
                verification_status="not_applicable",
                failure_reason=verifier_verdict.reason,
                recovery_required=False,
                summary={
                    "action_type": action.action_type.value,
                    "blocked_by": "verifier_registry",
                    "verifier_decision": verifier_verdict.decision.value,
                },
            )
        automation_verdict = self.automation_gate.evaluate(
            action.action_type,
            mode=self.automation_mode,
            human_confirmed=_confirmation_token(action) is not None,
        )
        if automation_verdict.decision == ArchitectureGateDecision.BLOCK:
            return ExecutionResult(
                action_id=action.action_id,
                status="blocked",
                verification_status="not_applicable",
                failure_reason=automation_verdict.reason,
                recovery_required=False,
                summary={
                    "action_type": action.action_type.value,
                    "blocked_by": "architecture_gate",
                    "architecture_gate": automation_verdict.to_dict(),
                },
            )
        return dispatch(action, self.ui)


def _confirmation_token(action: CandidateAction) -> str | None:
    value = action.params.get("confirmation_token")
    return value if isinstance(value, str) else None
