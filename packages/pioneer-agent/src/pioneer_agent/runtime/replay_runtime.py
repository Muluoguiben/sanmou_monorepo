from __future__ import annotations

from pathlib import Path

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.core.runtime_state_io import load_runtime_state_record
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.selector.action_selector import ActionSelector


class ReplayRuntime:
    def __init__(self) -> None:
        self.selector = ActionSelector()
        self.deriver = StateDeriver()

    def run_state(self, state: RuntimeState, fixture_label: str = "inline_state") -> dict:
        derived = self.deriver.derive(state)
        result = self.selector.select(derived)
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
            "ranked_actions": [action.model_dump(mode="json") for action in result.ranked_actions],
            "selection_reason": result.selection_reason,
            "next_replan_time": result.next_replan_time.isoformat() if result.next_replan_time else None,
        }

    def run_fixture(self, fixture_path: Path) -> dict:
        record = load_runtime_state_record(fixture_path)
        return self.run_state(record.state, str(fixture_path))
