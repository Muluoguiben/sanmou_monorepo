"""Guarded action runner for the canonical AutonomousLoop UI dispatch path."""
from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path

from pioneer_agent.core.device import CapabilityFlags, DeviceSession, ObservationSourceType
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ExecutionResult, ObservationSnapshot
from pioneer_agent.executor.action_handlers import (
    dispatch,
    semantic_click_binding,
)
from pioneer_agent.executor.operator_confirmation import (
    OperatorConfirmationError,
    OperatorConfirmationProvider,
    OperatorConfirmationReceipt,
    validate_confirmation_receipt,
)
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.executor.semantic_frame_guard import (
    FINAL_MUTATING_AUTHORIZATION_SCOPE,
    INTERMEDIATE_AUTHORIZATION_SCOPE,
    SemanticFrameGuard,
    build_semantic_frame_guard,
)
from pioneer_agent.runtime.architecture_gates import (
    ArchitectureGateDecision,
    AutomationMode,
    AutomationReadinessGate,
    validate_low_risk_semantic_target,
)
from pioneer_agent.runtime.observation_gate import (
    ObservationGateDecision,
    validate_dispatch_observation,
)
from pioneer_agent.safety.guard import GuardDecision, SafetyGuard, SessionMode
from pioneer_agent.verifier.registry import (
    UI_ACTIONS_REQUIRING_VERIFIER,
    VerifierGateDecision,
    VerifierRegistry,
)


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
        observation_max_age_seconds: float = 30.0,
        allow_offline_fixture_observations: bool = False,
        operator_confirmation_provider: OperatorConfirmationProvider | None = None,
        kill_switch_path: Path | str | None = None,
    ) -> None:
        self.ui = ui
        self.device_session = device_session
        self.capabilities = capabilities
        self.safety_guard = safety_guard or SafetyGuard()
        self.session_mode = session_mode
        self.verifier_registry = verifier_registry or VerifierRegistry()
        self.automation_mode = automation_mode
        self.automation_gate = automation_gate or AutomationReadinessGate()
        self.observation_max_age_seconds = observation_max_age_seconds
        self.allow_offline_fixture_observations = allow_offline_fixture_observations
        self.operator_confirmation_provider = operator_confirmation_provider
        self.kill_switch_path = (
            str(kill_switch_path) if kill_switch_path is not None else None
        )

    def run(
        self,
        action: CandidateAction,
        *,
        observation: ObservationSnapshot | None = None,
        frame_bytes: bytes | None = None,
    ) -> ExecutionResult:
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
        observation_verdict = validate_dispatch_observation(
            action,
            observation,
            max_age_seconds=self.observation_max_age_seconds,
            allow_fixture_source=self.allows_offline_fixture_observations,
        )
        if observation_verdict.decision == ObservationGateDecision.BLOCK:
            return ExecutionResult(
                action_id=action.action_id,
                status="blocked",
                verification_status="not_applicable",
                failure_reason=observation_verdict.reason,
                recovery_required=False,
                summary={
                    "action_type": action.action_type.value,
                    "blocked_by": "observation_gate",
                    "observation_gate": observation_verdict.to_dict(),
                },
            )
        expected_window, window_guard_error = self._expected_window_guard(
            action,
            observation,
        )
        if window_guard_error is not None:
            return ExecutionResult(
                action_id=action.action_id,
                status="blocked",
                verification_status="not_applicable",
                failure_reason=window_guard_error,
                recovery_required=False,
                summary={
                    "action_type": action.action_type.value,
                    "blocked_by": "window_identity_gate",
                    "observation_gate": observation_verdict.to_dict(),
                },
            )
        if expected_window is not None and not isinstance(self.ui, UIActions):
            return ExecutionResult(
                action_id=action.action_id,
                status="blocked",
                verification_status="not_applicable",
                failure_reason="live dispatch requires guarded UIActions",
                recovery_required=False,
                summary={
                    "action_type": action.action_type.value,
                    "blocked_by": "window_identity_gate",
                    "observation_gate": observation_verdict.to_dict(),
                },
            )
        spec = self.verifier_registry.get_for_action(action)
        if spec is not None and observation_verdict.verifier_state is not None:
            preflight = spec.build().validate_before(
                observation_verdict.verifier_state
            )
            if not preflight.verified:
                return ExecutionResult(
                    action_id=action.action_id,
                    status="blocked",
                    verification_status="not_applicable",
                    failure_reason=preflight.reason,
                    recovery_required=False,
                    summary={
                        "action_type": action.action_type.value,
                        "blocked_by": "verifier_preflight",
                        "observation_gate": observation_verdict.to_dict(),
                        "verifier_preflight": {
                            "status": preflight.status.value,
                            "reason": preflight.reason,
                            "checked": list(preflight.checked),
                        },
                    },
                )
        confirmation_receipt: OperatorConfirmationReceipt | None = None
        semantic_frame_guard: SemanticFrameGuard | None = None
        authorization_scope: str | None = None
        guard_expires_at: str | None = None
        click_binding = semantic_click_binding(action)
        if expected_window is not None and click_binding is not None:
            target_key, target_bbox, terminal_for_verifier = click_binding
            if self.kill_switch_path is None:
                return self._atomic_frame_guard_block(
                    action,
                    "live semantic click requires a Windows-checkable kill-switch path",
                    target_key=target_key,
                    observation=observation,
                )
            if not isinstance(frame_bytes, bytes):
                return self._atomic_frame_guard_block(
                    action,
                    "live semantic click requires its current observation frame bytes",
                    target_key=target_key,
                    observation=observation,
                )
            assert observation is not None
            if hashlib.sha256(frame_bytes).hexdigest() != observation.frame_sha256:
                return self._atomic_frame_guard_block(
                    action,
                    "semantic click frame bytes do not match observation frame_sha256",
                    target_key=target_key,
                    observation=observation,
                )
            if observation.frame_size is None:
                return self._atomic_frame_guard_block(
                    action,
                    "semantic click observation has no frame size for ROI binding",
                    target_key=target_key,
                    observation=observation,
                )
            if observation.capture_geometry is None:
                return self._atomic_frame_guard_block(
                    action,
                    "semantic click observation has no capture geometry binding",
                    target_key=target_key,
                    observation=observation,
                )
            try:
                semantic_frame_guard = build_semantic_frame_guard(
                    frame_bytes,
                    frame_size=observation.frame_size,
                    capture_geometry=observation.capture_geometry,
                    semantic_target_key=target_key,
                    bbox=target_bbox,
                )
            except ValueError as exc:
                return self._atomic_frame_guard_block(
                    action,
                    f"semantic ROI binding failed: {exc}",
                    target_key=target_key,
                    observation=observation,
                )
            if terminal_for_verifier:
                authorization_scope = FINAL_MUTATING_AUTHORIZATION_SCOPE
                provider = self.operator_confirmation_provider
                if provider is None:
                    return self._confirmation_block(
                        action,
                        "live final mutating click requires an operator confirmation provider",
                        target_key=target_key,
                        observation=observation,
                    )
                try:
                    confirmation_receipt = provider.consume_for_dispatch(
                        action=action,
                        observation=observation,
                        target_key=target_key,
                        semantic_frame_guard=semantic_frame_guard,
                    )
                    validate_confirmation_receipt(
                        confirmation_receipt,
                        action=action,
                        observation=observation,
                        target_key=target_key,
                        semantic_frame_guard=semantic_frame_guard,
                    )
                except (OperatorConfirmationError, ValueError, OSError) as exc:
                    return self._confirmation_block(
                        action,
                        f"operator confirmation unavailable: {exc}",
                        target_key=target_key,
                        observation=observation,
                    )
                guard_expires_at = (
                    confirmation_receipt.confirmation.expires_at.isoformat()
                )
            else:
                authorization_scope = INTERMEDIATE_AUTHORIZATION_SCOPE
                guard_expires_at = (
                    observation.captured_at
                    + timedelta(seconds=self.observation_max_age_seconds)
                ).isoformat()

        binder = getattr(self.ui, "bind_observation", None)
        if callable(binder):
            if semantic_frame_guard is None:
                binder(observation, expected_window=expected_window)
            else:
                binder(
                    observation,
                    expected_window=expected_window,
                    operator_confirmation=(
                        confirmation_receipt.to_summary()
                        if confirmation_receipt is not None
                        else None
                    ),
                    dispatch_at=(
                        confirmation_receipt.dispatch_at.isoformat()
                        if confirmation_receipt is not None
                        else None
                    ),
                    semantic_frame_guard=semantic_frame_guard.model_dump(mode="json"),
                    guard_expires_at=guard_expires_at,
                    authorization_scope=authorization_scope,
                    kill_switch_path=self.kill_switch_path,
                )
        try:
            result = dispatch(action, self.ui)
        finally:
            if callable(binder):
                binder(None)
        if semantic_target_verdict.decision != ArchitectureGateDecision.SKIP:
            summary = dict(result.summary)
            summary["semantic_target_gate"] = semantic_target_verdict.to_dict()
            summary["observation_gate"] = observation_verdict.to_dict()
            result = result.model_copy(update={"summary": summary})
        if confirmation_receipt is not None:
            summary = dict(result.summary)
            confirmation_summary = confirmation_receipt.to_summary()
            confirmation_summary["runtime_dispatch"] = {
                "status": result.status,
                "target_key": result.summary.get("target_key"),
                "terminal_for_verifier": result.summary.get(
                    "terminal_for_verifier"
                ),
            }
            summary["dispatch_at"] = confirmation_receipt.dispatch_at.isoformat()
            summary["operator_confirmation"] = confirmation_summary
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

    def _confirmation_block(
        self,
        action: CandidateAction,
        reason: str,
        *,
        target_key: str,
        observation: ObservationSnapshot | None,
    ) -> ExecutionResult:
        return ExecutionResult(
            action_id=action.action_id,
            status="blocked",
            verification_status="not_applicable",
            failure_reason=reason,
            recovery_required=False,
            summary={
                "action_type": action.action_type.value,
                "blocked_by": "operator_confirmation",
                "target_key": target_key,
                "observation_id": (
                    observation.observation_id if observation is not None else None
                ),
                "frame_sha256": (
                    observation.frame_sha256 if observation is not None else None
                ),
            },
        )

    def _atomic_frame_guard_block(
        self,
        action: CandidateAction,
        reason: str,
        *,
        target_key: str,
        observation: ObservationSnapshot | None,
    ) -> ExecutionResult:
        return ExecutionResult(
            action_id=action.action_id,
            status="blocked",
            verification_status="not_applicable",
            failure_reason=reason,
            recovery_required=False,
            summary={
                "action_type": action.action_type.value,
                "blocked_by": "atomic_frame_guard",
                "target_key": target_key,
                "observation_id": (
                    observation.observation_id if observation is not None else None
                ),
                "frame_sha256": (
                    observation.frame_sha256 if observation is not None else None
                ),
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

    @property
    def allows_offline_fixture_observations(self) -> bool:
        session = self.device_session
        return bool(
            self.allow_offline_fixture_observations
            and _is_automation_test(self.session_mode)
            and session is not None
            and session.source.source_type == ObservationSourceType.SCREENSHOT_FILE
            and not session.capabilities.live_capture
            and not session.source.capabilities.live_capture
        )

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

    def _expected_window_guard(
        self,
        action: CandidateAction,
        observation: ObservationSnapshot | None,
    ) -> tuple[dict[str, int] | None, str | None]:
        if action.action_type not in UI_ACTIONS_REQUIRING_VERIFIER:
            return None, None
        session = self.device_session
        if self.allows_offline_fixture_observations:
            return None, None
        if session is None:
            return None, "guarded UI dispatch requires an active device session"
        if session.source.source_type != ObservationSourceType.WINDOWS_WINDOW_CAPTURE:
            return None, "guarded UI dispatch requires a live Windows capture source"
        if not session.capabilities.live_capture:
            return None, "guarded UI dispatch requires live capture capability"
        if not session.capabilities.reliable_window_info:
            return None, "live dispatch requires reliable window identity"
        if observation is None or observation.frame_size is None:
            return None, "live dispatch requires an observed frame size"
        if observation.capture_geometry is None:
            return None, "live dispatch requires server-bound capture geometry"
        metadata = session.source.metadata
        hwnd = metadata.get("hwnd")
        pid = metadata.get("pid")
        values = (hwnd, pid)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            return None, "live dispatch window identity is incomplete"
        geometry = observation.capture_geometry
        if geometry.outer_window.hwnd != hwnd or geometry.outer_window.pid != pid:
            return None, "capture geometry does not match the active window identity"
        if geometry.frame_size != observation.frame_size:
            return None, "capture geometry does not match the observed frame size"
        return geometry.outer_window.model_dump(mode="json"), None


def _confirmation_token(action: CandidateAction) -> str | None:
    value = action.params.get("confirmation_token")
    return value if isinstance(value, str) else None


def _is_automation_test(value: SessionMode | str | None) -> bool:
    return value == SessionMode.AUTOMATION_TEST or value == SessionMode.AUTOMATION_TEST.value
