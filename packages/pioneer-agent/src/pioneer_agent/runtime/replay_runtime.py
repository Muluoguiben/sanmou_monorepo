from __future__ import annotations

from pathlib import Path

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.core.runtime_state_io import load_runtime_state_record
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.runtime.architecture_gates import validate_low_risk_semantic_target
from pioneer_agent.selector.action_selector import ActionSelector
from pioneer_agent.verifier.base import DeltaMatchPolicy
from pioneer_agent.verifier.registry import VerifierRegistry, serialize_verifier_spec


class ReplayRuntime:
    def __init__(self) -> None:
        self.selector = ActionSelector()
        self.deriver = StateDeriver()
        self.verifier_registry = VerifierRegistry()

    def run_state(self, state: RuntimeState, fixture_label: str = "inline_state") -> dict:
        derived = self.deriver.derive(state)
        result = self.selector.select(derived)
        verifier_gate = None
        verifier_spec = None
        semantic_target_gate = None
        if result.selected_action is not None:
            action_type = result.selected_action.action_type
            gate = self.verifier_registry.evaluate(action_type)
            spec = self.verifier_registry.get(action_type)
            semantic_target_gate = validate_low_risk_semantic_target(result.selected_action).to_dict()
            verifier_gate = {
                "decision": gate.decision.value,
                "reason": gate.reason,
                "timeout_seconds": gate.timeout_seconds,
                "match_policy": _match_policy_value(gate.match_policy),
            }
            verifier_spec = serialize_verifier_spec(spec)
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
