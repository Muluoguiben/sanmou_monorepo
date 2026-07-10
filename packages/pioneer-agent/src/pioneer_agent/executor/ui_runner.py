"""Drop-in replacement for `ActionRunner` that dispatches via UIActions.

Keeps the existing ActionRunner (non-implemented stub) untouched so
existing unit tests continue to pass. Consumers opt in by injecting
`UIActionRunner` into `AgentRuntime` instead.
"""
from __future__ import annotations

from pioneer_agent.core.device import CapabilityFlags, DeviceSession
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ExecutionResult
from pioneer_agent.executor.action_handlers import dispatch
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.runtime.architecture_gates import (
    ArchitectureGateDecision,
    AutomationMode,
    AutomationReadinessGate,
    validate_low_risk_semantic_target,
)
from pioneer_agent.safety.guard import GuardDecision, SafetyGuard, SessionMode
from pioneer_agent.verifier.registry import VerifierGateDecision, VerifierRegistry


class UIActionRunner:
    def __init__(
        self,
        ui: UIActions,
        *,
        device_session: DeviceSession | None = None,
        capabilities: CapabilityFlags | None = None,
        safety_guard: SafetyGuard | None = None,
        session_mode: SessionMode | str | None = None,
        verifier_registry: VerifierRegistry | None = None,
        automation_mode: AutomationMode | str = AutomationMode.SEMI_AUTO,
        automation_gate: AutomationReadinessGate | None = None,
    ) -> None:
        self.ui = ui
        self.device_session = device_session
        self.capabilities = capabilities
        self.safety_guard = safety_guard or SafetyGuard()
        self.session_mode = session_mode
        self.verifier_registry = verifier_registry or VerifierRegistry()
        self.automation_mode = automation_mode
        self.automation_gate = automation_gate or AutomationReadinessGate()

    def run(self, action: CandidateAction) -> ExecutionResult:
        session_block = self._validate_device_session(action)
        if session_block is not None:
            return session_block
        assert self.device_session is not None
        effective_capabilities = self.device_session.capabilities
        verdict = self.safety_guard.evaluate(
            action.action_type,
            risk=action.risk,
            capabilities=effective_capabilities,
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
                    "capabilities_known": True,
                    "observe_only": effective_capabilities.observe_only,
                    "device_session_id": self.device_session.session_id,
                    "session_mode": (
                        self.session_mode.value
                        if isinstance(self.session_mode, SessionMode)
                        else self.session_mode
                    ),
                },
            )
        verifier_verdict = self.verifier_registry.evaluate_action(action)
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
        semantic_target_verdict = validate_low_risk_semantic_target(action)
        if semantic_target_verdict.decision == ArchitectureGateDecision.BLOCK:
            return ExecutionResult(
                action_id=action.action_id,
                status="blocked",
                verification_status="not_applicable",
                failure_reason=semantic_target_verdict.reason,
                recovery_required=False,
                summary={
                    "action_type": action.action_type.value,
                    "blocked_by": "semantic_target_gate",
                    "semantic_target_gate": semantic_target_verdict.to_dict(),
                },
            )
        result = dispatch(action, self.ui)
        if semantic_target_verdict.decision != ArchitectureGateDecision.SKIP:
            summary = dict(result.summary)
            summary["semantic_target_gate"] = semantic_target_verdict.to_dict()
            result = result.model_copy(update={"summary": summary})
        return result

    def _validate_device_session(
        self,
        action: CandidateAction,
    ) -> ExecutionResult | None:
        reason = self._device_session_failure_reason()
        session = self.device_session
        if reason is None:
            return None
        return ExecutionResult(
            action_id=action.action_id,
            status="blocked",
            verification_status="not_applicable",
            failure_reason=reason,
            recovery_required=False,
            summary={
                "action_type": action.action_type.value,
                "blocked_by": "device_session",
                "device_session_present": session is not None,
                "device_session_active": session.active if session is not None else None,
            },
        )

    def input_authority_failure_reason(self) -> str | None:
        reason = self._device_session_failure_reason()
        if reason is not None:
            return reason
        assert self.device_session is not None
        verdict = self.safety_guard.evaluate(
            ActionType.WAIT_FOR_STAMINA,
            capabilities=self.device_session.capabilities,
            session_mode=self.session_mode,
        )
        return None if verdict.decision == GuardDecision.ALLOW else verdict.reason

    def _device_session_failure_reason(self) -> str | None:
        session = self.device_session
        if session is None:
            return "active device session required for UI execution"
        if not session.active:
            return "device session is inactive"
        if self.capabilities is None:
            return "explicit capabilities are required for UI execution"
        if session.capabilities != session.source.capabilities:
            return "device session capabilities do not match its observation source"
        if self.capabilities != session.capabilities:
            return "explicit capabilities do not match the device session"
        return None


def _confirmation_token(action: CandidateAction) -> str | None:
    value = action.params.get("confirmation_token")
    return value if isinstance(value, str) else None
