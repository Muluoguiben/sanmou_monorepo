"""CandidateFilter honors the runbook phase allowlist injected into global_state."""
from __future__ import annotations

import unittest

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState
from pioneer_agent.selector.filters import CandidateFilter


def _candidate(action_type: ActionType, **params) -> CandidateAction:
    defaults = {
        ActionType.CLAIM_CHAPTER_REWARD: {},
        ActionType.WAIT_FOR_STAMINA: {
            "wait_seconds": 60,
            "target_stamina": 20,
            "current_stamina": 5,
            "unlock_action_type": "attack_land",
        },
        ActionType.ATTACK_LAND: {
            "expected_win_rate": 0.95,
            "current_stamina": 20,
            "required_stamina": 10,
        },
    }
    merged = {**defaults.get(action_type, {}), **params}
    return CandidateAction(
        action_id=f"c-{action_type.value}", action_type=action_type, params=merged
    )


def _state(selector_hints: dict | None) -> RuntimeState:
    global_state = {"runbook": {"phase_id": "p1", "selector_hints": selector_hints}} \
        if selector_hints is not None else {}
    return RuntimeState(
        global_state=global_state,
        progress={"chapter_claimable": True},
    )


class RunbookCandidateFilterTests(unittest.TestCase):
    def test_disallowed_candidates_rejected_so_selector_picks_next_best(self) -> None:
        state = _state({"allowed_action_types": ["claim_chapter_reward"]})
        candidates = [
            _candidate(ActionType.ATTACK_LAND),
            _candidate(ActionType.CLAIM_CHAPTER_REWARD),
        ]
        viable, rejected = CandidateFilter().filter(state, candidates)
        self.assertEqual([c.action_type for c in viable], [ActionType.CLAIM_CHAPTER_REWARD])
        self.assertEqual(rejected[0]["reason"], "runbook_action_filter")
        self.assertEqual(rejected[0]["action_type"], "attack_land")

    def test_wait_actions_exempt_from_allowlist(self) -> None:
        state = _state({"allowed_action_types": []})
        candidates = [
            _candidate(ActionType.WAIT_FOR_STAMINA),
            _candidate(ActionType.ATTACK_LAND),
        ]
        viable, rejected = CandidateFilter().filter(state, candidates)
        self.assertEqual([c.action_type for c in viable], [ActionType.WAIT_FOR_STAMINA])
        self.assertEqual(len(rejected), 1)

    def test_no_runbook_context_leaves_filtering_unchanged(self) -> None:
        state = _state(None)
        candidates = [
            _candidate(ActionType.CLAIM_CHAPTER_REWARD),
            _candidate(ActionType.ATTACK_LAND),
        ]
        viable, _rejected = CandidateFilter().filter(state, candidates)
        self.assertEqual(len(viable), 2)

    def test_hints_without_allowlist_do_not_filter(self) -> None:
        state = _state({"lineup_preset": "junk_team"})
        candidates = [_candidate(ActionType.ATTACK_LAND)]
        viable, _rejected = CandidateFilter().filter(state, candidates)
        self.assertEqual(len(viable), 1)


if __name__ == "__main__":
    unittest.main()
