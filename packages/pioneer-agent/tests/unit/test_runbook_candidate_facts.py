from __future__ import annotations

import unittest
from datetime import datetime

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import RuntimeState
from pioneer_agent.runbook.lineup_binding import apply_operator_lineup_bindings
from pioneer_agent.selector.candidate_generator import CandidateGenerator


def _state(*, land_scope="outer_city", lineup_preset="actual_team") -> RuntimeState:
    land = {
        "land_id": "L-6",
        "level": 6,
        "land_scope": land_scope,
        "reachable": True,
        "occupied": False,
        "protected": False,
        "can_attack": True,
        "expected_win_rate": 0.95,
        "required_stamina": 15,
    }
    state = RuntimeState(
        global_state={
            "runbook": {
                "selector_hints": {
                    "target_land_levels": [7],
                    "land_scope": "inner_city",
                    "lineup_preset": "hint_must_not_be_copied",
                }
            }
        },
        main_lineup={"current_host_team_id": "team-1"},
        teams=[
            {
                "team_id": "team-1",
                "page_type": "team_panel",
                "heroes": [
                    {"hero_id": "hero-1", "position": 1},
                    {"hero_id": "hero-2", "position": 2},
                    {"hero_id": "hero-3", "position": 3},
                ],
            }
        ],
        team_containers=[
            {
                "team_id": "team-1",
                "container_stamina": 5,
                "lineup_preset": lineup_preset,
            }
        ],
        map_state={"candidate_lands": [land]},
        swap_constraints={"stamina_regen_per_hour": 12},
    )
    if lineup_preset is not None:
        apply_operator_lineup_bindings(
            state,
            {"team-1": lineup_preset},
            bound_at=datetime.now().astimezone(),
        )
    return state


class RunbookCandidateFactTests(unittest.TestCase):
    def test_attack_and_wait_copy_actual_facts_not_policy_hints(self) -> None:
        actions = CandidateGenerator().generate(_state())
        attack = next(action for action in actions if action.action_type == ActionType.ATTACK_LAND)
        wait = next(
            action for action in actions if action.action_type == ActionType.WAIT_FOR_STAMINA
        )

        self.assertEqual(attack.params["level"], 6)
        self.assertEqual(attack.params["land_scope"], "outer_city")
        self.assertEqual(attack.params["lineup_preset"], "actual_team")
        self.assertEqual(wait.params["unlock_land_level"], 6)
        self.assertEqual(wait.params["unlock_land_scope"], "outer_city")
        self.assertEqual(wait.params["unlock_lineup_preset"], "actual_team")
        self.assertIn("team_containers.lineup_preset", attack.source_state_refs)
        self.assertNotIn("hint_must_not_be_copied", attack.params.values())
        self.assertNotIn("hint_must_not_be_copied", wait.params.values())

    def test_missing_actual_scope_and_preset_remain_unknown(self) -> None:
        actions = CandidateGenerator().generate(_state(land_scope=None, lineup_preset=None))
        attack = next(action for action in actions if action.action_type == ActionType.ATTACK_LAND)
        wait = next(
            action for action in actions if action.action_type == ActionType.WAIT_FOR_STAMINA
        )

        self.assertIsNone(attack.params["land_scope"])
        self.assertIsNone(attack.params["lineup_preset"])
        self.assertIsNone(wait.params["unlock_land_scope"])
        self.assertIsNone(wait.params["unlock_lineup_preset"])


if __name__ == "__main__":
    unittest.main()
