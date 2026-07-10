"""CandidateFilter honors the runbook phase allowlist injected into global_state."""
from __future__ import annotations

import unittest
from datetime import datetime

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState
from pioneer_agent.runbook.lineup_binding import apply_operator_lineup_bindings
from pioneer_agent.selector.filters import CandidateFilter


def _candidate(action_type: ActionType, **params) -> CandidateAction:
    defaults = {
        ActionType.CLAIM_CHAPTER_REWARD: {},
        ActionType.WAIT_FOR_STAMINA: {
            "land_id": "L-1",
            "team_id": "team-1",
            "wait_seconds": 60,
            "target_stamina": 20,
            "current_stamina": 5,
            "unlock_action_type": "attack_land",
            "unlock_land_level": 6,
            "unlock_land_scope": "inner_city",
            "unlock_lineup_preset": "main_team",
        },
        ActionType.ATTACK_LAND: {
            "land_id": "L-1",
            "team_id": "team-1",
            "expected_win_rate": 0.95,
            "current_stamina": 20,
            "required_stamina": 10,
            "level": 6,
            "land_scope": "inner_city",
            "lineup_preset": "main_team",
        },
    }
    merged = {**defaults.get(action_type, {}), **params}
    return CandidateAction(
        action_id=f"c-{action_type.value}", action_type=action_type, params=merged
    )


def _state(
    selector_hints: dict | None,
    *,
    level: int | None = 6,
    land_scope: str | None = "inner_city",
    lineup_preset: str | None = "main_team",
) -> RuntimeState:
    global_state = {"runbook": {"phase_id": "p1", "selector_hints": selector_hints}} \
        if selector_hints is not None else {}
    state = RuntimeState(
        global_state=global_state,
        progress={"chapter_claimable": True},
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
        map_state={
            "candidate_lands": [
                {"land_id": "L-1", "level": level, "land_scope": land_scope}
            ]
        },
        team_containers=[
            {"team_id": "team-1", "lineup_preset": lineup_preset}
        ],
    )
    if lineup_preset is not None:
        apply_operator_lineup_bindings(
            state,
            {"team-1": lineup_preset},
            bound_at=datetime.now().astimezone(),
        )
    return state


class RunbookCandidateFilterTests(unittest.TestCase):
    def test_disallowed_candidates_rejected_so_selector_picks_next_best(self) -> None:
        state = _state({"allowed_action_types": ["claim_chapter_reward"]})
        candidates = [
            _candidate(ActionType.ATTACK_LAND),
            _candidate(ActionType.CLAIM_CHAPTER_REWARD),
        ]
        viable, rejected = CandidateFilter(honor_runbook_hints=True).filter(state, candidates)
        self.assertEqual([c.action_type for c in viable], [ActionType.CLAIM_CHAPTER_REWARD])
        self.assertEqual(rejected[0]["reason"], "runbook_action_filter")
        self.assertEqual(rejected[0]["action_type"], "attack_land")

    def test_wait_actions_exempt_from_allowlist(self) -> None:
        state = _state({"allowed_action_types": []})
        candidates = [
            _candidate(ActionType.WAIT_FOR_STAMINA),
            _candidate(ActionType.ATTACK_LAND),
        ]
        viable, rejected = CandidateFilter(honor_runbook_hints=True).filter(state, candidates)
        self.assertEqual([c.action_type for c in viable], [ActionType.WAIT_FOR_STAMINA])
        self.assertEqual(len(rejected), 1)

    def test_default_filter_ignores_runbook_hints_for_advisor_chains(self) -> None:
        state = _state({"allowed_action_types": []})
        candidates = [
            _candidate(ActionType.CLAIM_CHAPTER_REWARD),
            _candidate(ActionType.ATTACK_LAND),
        ]
        viable, _rejected = CandidateFilter().filter(state, candidates)
        self.assertEqual(len(viable), 2)

    def test_no_runbook_context_fails_closed_when_hints_are_required(self) -> None:
        state = _state(None)
        candidates = [
            _candidate(ActionType.CLAIM_CHAPTER_REWARD),
            _candidate(ActionType.ATTACK_LAND),
        ]
        viable, rejected = CandidateFilter(honor_runbook_hints=True).filter(state, candidates)
        self.assertEqual(viable, [])
        self.assertEqual(
            {item["reason"] for item in rejected},
            {"runbook_context_missing"},
        )

    def test_target_hints_match_actual_candidate_facts(self) -> None:
        state = _state({"lineup_preset": "junk_team"}, lineup_preset="junk_team")
        candidates = [_candidate(ActionType.ATTACK_LAND, lineup_preset="forged")]
        viable, _rejected = CandidateFilter(honor_runbook_hints=True).filter(state, candidates)
        self.assertEqual(len(viable), 1)

    def test_target_hints_reject_unknown_and_mismatched_facts(self) -> None:
        hints = {
            "target_land_levels": [5, 6],
            "land_scope": "inner_city",
            "lineup_preset": "main_team",
        }
        cases = [
            ({"level": None}, "runbook_target_land_level_unknown"),
            ({"level": 7}, "runbook_target_land_level_mismatch"),
            ({"land_scope": None}, "runbook_land_scope_unknown"),
            ({"land_scope": "outer_city"}, "runbook_land_scope_mismatch"),
            ({"lineup_preset": None}, "runbook_lineup_preset_unknown"),
            ({"lineup_preset": "other"}, "runbook_lineup_preset_mismatch"),
        ]
        for state_facts, expected in cases:
            with self.subTest(expected=expected):
                viable, rejected = CandidateFilter(honor_runbook_hints=True).filter(
                    _state(hints, **state_facts),
                    [_candidate(ActionType.ATTACK_LAND)],
                )
                self.assertEqual(viable, [])
                self.assertEqual(rejected[0]["reason"], expected)

    def test_attack_unlock_wait_uses_same_target_constraints(self) -> None:
        hints = {
            "target_land_levels": [6],
            "land_scope": "inner_and_outer",
            "lineup_preset": "main_team",
        }
        viable, _ = CandidateFilter(honor_runbook_hints=True).filter(
            _state(hints, land_scope="outer_city"),
            [_candidate(ActionType.WAIT_FOR_STAMINA, unlock_land_scope="forged")],
        )
        self.assertEqual(len(viable), 1)

        viable, rejected = CandidateFilter(honor_runbook_hints=True).filter(
            _state(hints, lineup_preset=None),
            [_candidate(ActionType.WAIT_FOR_STAMINA, unlock_lineup_preset="main_team")],
        )
        self.assertEqual(viable, [])
        self.assertEqual(rejected[0]["reason"], "runbook_lineup_preset_unknown")

    def test_programmatic_malformed_hints_fail_closed_at_runtime(self) -> None:
        cases = [
            (
                {"allowed_action_types": "attack_land"},
                "runbook_allowed_action_types_invalid",
            ),
            (
                {"target_land_levels": [True]},
                "runbook_target_land_levels_invalid",
            ),
            ({"land_scope": "nearby"}, "runbook_land_scope_invalid"),
            ({"lineup_preset": ""}, "runbook_lineup_preset_invalid"),
        ]
        for hints, expected in cases:
            with self.subTest(expected=expected):
                viable, rejected = CandidateFilter(honor_runbook_hints=True).filter(
                    _state(hints),
                    [_candidate(ActionType.CLAIM_CHAPTER_REWARD)],
                )
                self.assertEqual(viable, [])
                self.assertEqual(rejected[0]["reason"], expected)

    def test_attack_target_hints_do_not_constrain_unrelated_actions_or_waits(self) -> None:
        hints = {
            "target_land_levels": [7],
            "land_scope": "outer_city",
            "lineup_preset": "special_team",
        }
        unrelated_wait = _candidate(
            ActionType.WAIT_FOR_STAMINA,
            unlock_action_type="upgrade_building",
            unlock_land_level=None,
            unlock_land_scope=None,
            unlock_lineup_preset=None,
        )
        viable, rejected = CandidateFilter(honor_runbook_hints=True).filter(
            _state(hints),
            [_candidate(ActionType.CLAIM_CHAPTER_REWARD), unrelated_wait],
        )
        self.assertEqual(len(viable), 2)
        self.assertEqual(rejected, [])


if __name__ == "__main__":
    unittest.main()
