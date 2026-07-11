from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import (
    CandidateAction,
    FieldMeta,
    ObservationSnapshot,
    RuntimeState,
    SelectionResult,
)
from pioneer_agent.runtime.autonomous_loop import _constrain_evidence_selection


BUTTON = {
    "visible": True,
    "enabled": True,
    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
}


class EvidenceActionSelectionTests(unittest.TestCase):
    def test_selects_first_exact_action_bound_to_current_frame(self) -> None:
        now = datetime.now(UTC)
        wrong_top = CandidateAction(
            action_id="claim-17",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
            params={"chapter_id": 17, "claim_button": BUTTON},
            score_total=10_000,
        )
        stale_recruit = CandidateAction(
            action_id="recruit-stale-team",
            action_type=ActionType.RECRUIT_SOLDIERS,
            params={"team_id": "stale-team", "recruit_button": BUTTON},
            score_total=90,
        )
        current_recruit = CandidateAction(
            action_id="recruit-team-2",
            action_type=ActionType.RECRUIT_SOLDIERS,
            params={"team_id": "team-2", "recruit_button": BUTTON},
            score_total=80,
        )
        selection = SelectionResult(
            selected_action=wrong_top,
            ranked_actions=[wrong_top, stale_recruit, current_recruit],
            selection_reason={"summary": "ordinary selection"},
        )

        constrained = _constrain_evidence_selection(
            selection,
            required_action_type=ActionType.RECRUIT_SOLDIERS,
            observation=_recruit_observation(now),
            now=now,
            max_age_seconds=30.0,
            allow_fixture_source=False,
        )

        self.assertEqual(constrained.selected_action, current_recruit)
        evidence = constrained.selection_reason["evidence_action_constraint"]
        self.assertEqual(evidence["required_action_type"], "recruit_soldiers")
        self.assertEqual(evidence["decision"], "selected")
        self.assertEqual(
            [item["action_id"] for item in evidence["evaluated_candidates"]],
            ["recruit-stale-team", "recruit-team-2"],
        )
        self.assertEqual(evidence["evaluated_candidates"][0]["decision"], "block")
        self.assertEqual(evidence["evaluated_candidates"][1]["decision"], "allow")

    def test_selects_nothing_when_exact_candidates_are_not_current(self) -> None:
        now = datetime.now(UTC)
        stale_recruit = CandidateAction(
            action_id="recruit-stale-team",
            action_type=ActionType.RECRUIT_SOLDIERS,
            params={"team_id": "stale-team", "recruit_button": BUTTON},
        )
        selection = SelectionResult(
            selected_action=stale_recruit,
            ranked_actions=[stale_recruit],
        )

        constrained = _constrain_evidence_selection(
            selection,
            required_action_type=ActionType.RECRUIT_SOLDIERS,
            observation=_recruit_observation(now),
            now=now,
            max_age_seconds=30.0,
            allow_fixture_source=False,
        )

        self.assertIsNone(constrained.selected_action)
        evidence = constrained.selection_reason["evidence_action_constraint"]
        self.assertEqual(evidence["decision"], "no_current_frame_candidate")
        self.assertEqual(evidence["evaluated_candidates"][0]["decision"], "block")

    def test_missing_observation_fails_closed_without_dispatch_candidate(self) -> None:
        now = datetime.now(UTC)
        action = CandidateAction(
            action_id="recruit-team-2",
            action_type=ActionType.RECRUIT_SOLDIERS,
            params={"team_id": "team-2", "recruit_button": BUTTON},
        )

        constrained = _constrain_evidence_selection(
            SelectionResult(selected_action=action, ranked_actions=[action]),
            required_action_type=ActionType.RECRUIT_SOLDIERS,
            observation=None,
            now=now,
            max_age_seconds=30.0,
            allow_fixture_source=False,
        )

        self.assertIsNone(constrained.selected_action)
        evaluated = constrained.selection_reason["evidence_action_constraint"][
            "evaluated_candidates"
        ]
        self.assertIn("current frame observation is required", evaluated[0]["reason"])

    def test_high_risk_action_cannot_be_used_as_evidence_constraint(self) -> None:
        with self.assertRaisesRegex(ValueError, "calibrated low-risk"):
            _constrain_evidence_selection(
                SelectionResult(),
                required_action_type=ActionType.ATTACK_LAND,
                observation=None,
                now=datetime.now(UTC),
                max_age_seconds=30.0,
                allow_fixture_source=False,
            )


def _recruit_observation(captured_at: datetime) -> ObservationSnapshot:
    state = RuntimeState(
        teams=[
            {
                "team_id": "team-2",
                "soldiers": 22_000,
                "recruit_button": BUTTON,
            }
        ]
    )
    state.field_meta["teams.recruit_panel"] = FieldMeta(
        value="loaded",
        source="vision.recruit_panel",
        updated_at=captured_at,
        observation_id="recruit-current",
    )
    return ObservationSnapshot(
        observation_id="recruit-current",
        captured_at=captured_at,
        frame_sha256="a" * 64,
        frame_size=(1920, 1080),
        page_type="recruit",
        domains_run=["resource_bar", "recruit_panel"],
        observed_state=state,
        source="vision_sync",
    )


if __name__ == "__main__":
    unittest.main()
