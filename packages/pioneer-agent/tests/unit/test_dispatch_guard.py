"""DispatchGuard: the single seam for every input-dispatch decision."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState
from pioneer_agent.runbook.models import RunbookDecision
from pioneer_agent.runbook.lineup_binding import apply_operator_lineup_bindings
from pioneer_agent.runtime.dispatch_guard import KILL_SWITCH_REASON, DispatchGuard
from pioneer_agent.safety.kill_switch import KillSwitch


def _action(
    action_type: ActionType = ActionType.ATTACK_LAND,
    **params,
) -> CandidateAction:
    if action_type == ActionType.ATTACK_LAND:
        params = {"land_id": "L-1", "team_id": "team-1", **params}
    return CandidateAction(action_id="a", action_type=action_type, params=params)


def _state(
    *,
    level: int = 6,
    land_scope: str | None = "inner_city",
    lineup_preset: str | None = "main_team",
) -> RuntimeState:
    state = RuntimeState(
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


def _decision(**kwargs) -> RunbookDecision:
    defaults = {"phase_id": "p1", "previous_phase_id": "p1"}
    defaults.update(kwargs)
    return RunbookDecision(**defaults)


class DispatchGuardTests(unittest.TestCase):
    def test_allows_by_default(self) -> None:
        guard = DispatchGuard()
        self.assertTrue(guard.action_verdict(_action()).allowed)
        self.assertTrue(guard.recovery_verdict().allowed)

    def test_kill_switch_denies_action_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            switch = KillSwitch(Path(tmp) / "STOP")
            guard = DispatchGuard(kill_switch=switch)
            switch.trigger()
            self.assertEqual(guard.action_verdict(_action()).reason, KILL_SWITCH_REASON)
            self.assertEqual(guard.recovery_verdict().reason, KILL_SWITCH_REASON)
            switch.clear()
            self.assertTrue(guard.action_verdict(_action()).allowed)
            self.assertTrue(guard.recovery_verdict().allowed)

    def test_blocking_hold_denies_action_and_recovery(self) -> None:
        guard = DispatchGuard()
        for hold in ("abort_triggered", "human_gate_pending", "runbook_completed"):
            guard.update_decision(_decision(hold_reason=hold))
            self.assertEqual(guard.action_verdict(_action()).reason, f"runbook_hold:{hold}")
            self.assertEqual(guard.recovery_verdict().reason, f"runbook_hold:{hold}")

    def test_non_blocking_holds_allow_dispatch(self) -> None:
        guard = DispatchGuard()
        for hold in (None, "exit_metrics_unknown", "abort_metrics_unknown", "transition_deferred"):
            guard.update_decision(_decision(hold_reason=hold))
            self.assertTrue(
                guard.action_verdict(_action(), state=_state()).allowed,
                hold,
            )
            self.assertTrue(guard.recovery_verdict().allowed, hold)

    def test_allowlist_denies_action_but_not_recovery(self) -> None:
        guard = DispatchGuard()
        guard.update_decision(
            _decision(selector_hints={"allowed_action_types": ["claim_chapter_reward"]})
        )
        self.assertEqual(guard.action_verdict(_action()).reason, "runbook_action_filter")
        self.assertTrue(guard.action_verdict(_action(ActionType.WAIT_FOR_STAMINA)).allowed)
        self.assertTrue(guard.recovery_verdict().allowed)

    def test_target_constraints_are_rechecked_before_dispatch(self) -> None:
        guard = DispatchGuard()
        guard.update_decision(
            _decision(
                selector_hints={
                    "target_land_levels": [5, 6],
                    "land_scope": "inner_city",
                    "lineup_preset": "main_team",
                }
            )
        )
        matching = _action(
            level=6,
            land_scope="inner_city",
            lineup_preset="main_team",
        )
        self.assertTrue(guard.action_verdict(matching, state=_state()).allowed)

        # A custom selector cannot satisfy policy by forging matching params:
        # dispatch resolves the target from the current RuntimeState instead.
        mismatch = matching.model_copy(
            update={"params": {**matching.params, "land_scope": "inner_city"}}
        )
        self.assertEqual(
            guard.action_verdict(
                mismatch,
                state=_state(land_scope="outer_city"),
            ).reason,
            "runbook_land_scope_mismatch",
        )
        self.assertTrue(guard.recovery_verdict().allowed)

    def test_missing_current_target_identity_fails_closed(self) -> None:
        guard = DispatchGuard()
        guard.update_decision(
            _decision(selector_hints={"target_land_levels": [6]})
        )
        action = _action(land_id="missing", level=6)
        self.assertEqual(
            guard.action_verdict(action, state=_state()).reason,
            "runbook_target_land_level_unknown",
        )

        missing_identity_state = _state()
        missing_identity_state.map_state = {
            "candidate_lands": [
                {"land_id": None, "level": 6, "land_scope": "inner_city"}
            ]
        }
        action_without_identity = _action(land_id=None, level=6)
        self.assertEqual(
            guard.action_verdict(
                action_without_identity,
                state=missing_identity_state,
            ).reason,
            "runbook_target_land_level_unknown",
        )

        duplicate_identity_state = _state()
        duplicate_identity_state.map_state = {
            "candidate_lands": [
                {"land_id": "L-1", "level": 6, "land_scope": "inner_city"},
                {"land_id": "L-1", "level": 6, "land_scope": "inner_city"},
            ]
        }
        self.assertEqual(
            guard.action_verdict(
                _action(level=6),
                state=duplicate_identity_state,
            ).reason,
            "runbook_target_land_level_unknown",
        )

    def test_non_current_team_cannot_bypass_with_matching_binding(self) -> None:
        guard = DispatchGuard()
        guard.update_decision(
            _decision(selector_hints={"lineup_preset": "main_team"})
        )
        state = RuntimeState(
            main_lineup={"current_host_team_id": "team-1"},
            map_state={
                "candidate_lands": [
                    {"land_id": "L-1", "level": 6, "land_scope": "inner_city"}
                ]
            },
            team_containers=[{"team_id": "team-1"}, {"team_id": "team-2"}],
            teams=[
                {
                    "team_id": "team-1",
                    "page_type": "team_panel",
                    "heroes": [
                        {"hero_id": "hero-1a"},
                        {"hero_id": "hero-1b"},
                        {"hero_id": "hero-1c"},
                    ],
                },
                {
                    "team_id": "team-2",
                    "page_type": "team_panel",
                    "heroes": [
                        {"hero_id": "hero-2a"},
                        {"hero_id": "hero-2b"},
                        {"hero_id": "hero-2c"},
                    ],
                },
            ],
        )
        apply_operator_lineup_bindings(
            state,
            {"team-1": "main_team", "team-2": "main_team"},
            bound_at=datetime.now().astimezone(),
        )
        forged = _action(team_id="team-2", lineup_preset="main_team")
        self.assertEqual(
            guard.action_verdict(forged, state=state).reason,
            "runbook_attack_team_mismatch",
        )

    def test_attack_unlock_wait_is_rechecked_before_dispatch(self) -> None:
        guard = DispatchGuard()
        guard.update_decision(
            _decision(selector_hints={"lineup_preset": "main_team"})
        )
        wait = _action(
            ActionType.WAIT_FOR_STAMINA,
            unlock_action_type="attack_land",
            land_id="L-1",
            team_id="team-1",
            unlock_lineup_preset=None,
        )
        self.assertEqual(
            guard.action_verdict(
                wait,
                state=_state(lineup_preset="other"),
            ).reason,
            "runbook_lineup_preset_mismatch",
        )
        self.assertTrue(guard.recovery_verdict().allowed)

    def test_malformed_target_policy_blocks_unrelated_action(self) -> None:
        guard = DispatchGuard()
        guard.update_decision(
            _decision(selector_hints={"target_land_levels": [True]})
        )
        verdict = guard.action_verdict(_action(ActionType.CLAIM_CHAPTER_REWARD))
        self.assertEqual(verdict.reason, "runbook_target_land_levels_invalid")


if __name__ == "__main__":
    unittest.main()
