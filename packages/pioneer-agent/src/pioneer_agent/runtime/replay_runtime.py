from __future__ import annotations

from pathlib import Path

from pioneer_agent.core.device import (
    CapabilityFlags,
    DevicePlatform,
    DeviceProfile,
    DeviceSession,
    ObservationSource,
    ObservationSourceType,
)
from pioneer_agent.core.models import RuntimeState
from pioneer_agent.core.runtime_state_io import load_runtime_state_record
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.executor.ui_actions import ClickOutcome
from pioneer_agent.executor.ui_runner import UIActionRunner
from pioneer_agent.runtime.architecture_gates import (
    LOW_RISK_AUTOMATION_ACTIONS,
    validate_low_risk_semantic_target,
)
from pioneer_agent.selector.action_selector import ActionSelector
from pioneer_agent.safety.guard import SessionMode
from pioneer_agent.verifier.base import DeltaMatchPolicy
from pioneer_agent.verifier.registry import VerifierRegistry, serialize_verifier_spec


class ReplayRuntime:
    def __init__(self) -> None:
        self.selector = ActionSelector()
        self.deriver = StateDeriver()
        self.verifier_registry = VerifierRegistry()
        device_session = _replay_device_session()
        self.dispatch_runner = UIActionRunner(
            _ReplayUI(),
            device_session=device_session,
            capabilities=device_session.capabilities,
            session_mode=SessionMode.AUTOMATION_TEST,
            verifier_registry=self.verifier_registry,
        )

    def run_state(self, state: RuntimeState, fixture_label: str = "inline_state") -> dict:
        derived = self.deriver.derive(state)
        result = self.selector.select(derived)
        verifier_gate = None
        verifier_spec = None
        semantic_target_gate = None
        runtime_dispatch = None
        if result.selected_action is not None:
            action_type = result.selected_action.action_type
            gate = self.verifier_registry.evaluate_action(result.selected_action)
            spec = None
            if gate.allowed:
                try:
                    spec = self.verifier_registry.get_for_action(result.selected_action)
                except ValueError:
                    spec = None
            semantic_target_gate = validate_low_risk_semantic_target(result.selected_action).to_dict()
            verifier_gate = {
                "decision": gate.decision.value,
                "reason": gate.reason,
                "timeout_seconds": gate.timeout_seconds,
                "match_policy": _match_policy_value(gate.match_policy),
            }
            verifier_spec = serialize_verifier_spec(spec)
            if action_type in LOW_RISK_AUTOMATION_ACTIONS:
                runtime_dispatch = self.dispatch_runner.run(result.selected_action).model_dump(mode="json")
        return {
            "fixture": fixture_label,
            "derived_state": {
                "phase_tag": derived.global_state.get("phase_tag"),
                "main_lineup": derived.main_lineup,
                "team_containers": derived.team_containers,
                "candidate_lands": derived.map_state.get("candidate_lands", []),
                "upgradeable_buildings": derived.city.get("upgradeable_buildings", []),
                "timing": derived.timing,
            },
            "selected_action": result.selected_action.model_dump(mode="json") if result.selected_action else None,
            "semantic_target_gate": semantic_target_gate,
            "runtime_dispatch": runtime_dispatch,
            "verifier_gate": verifier_gate,
            "verifier_spec": verifier_spec,
            "ranked_actions": [action.model_dump(mode="json") for action in result.ranked_actions],
            "selection_reason": result.selection_reason,
            "next_replan_time": result.next_replan_time.isoformat() if result.next_replan_time else None,
        }

    def run_fixture(self, fixture_path: Path) -> dict:
        record = load_runtime_state_record(fixture_path)
        return self.run_state(record.state, str(fixture_path))


def _match_policy_value(value: DeltaMatchPolicy | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, DeltaMatchPolicy):
        return value.value
    return DeltaMatchPolicy(str(value)).value


class _ReplayUI:
    def click_bbox(self, target_key, bbox, *, label=None):  # noqa: ANN001
        return ClickOutcome(
            success=True,
            px=(800, 850),
            matched_label=label,
            trace={
                "target": {"key": target_key, "label": label or target_key},
                "normalized_bbox": dict(bbox),
            },
        )


def _replay_device_session() -> DeviceSession:
    capabilities = CapabilityFlags(input_control=True)
    return DeviceSession(
        profile=DeviceProfile(
            platform=DevicePlatform.PC_CLIENT,
            resolution=(1286, 666),
        ),
        source=ObservationSource(
            source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
            capabilities=capabilities,
            display_name="offline replay UI",
        ),
        capabilities=capabilities,
    )
