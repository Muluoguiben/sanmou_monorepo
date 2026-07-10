from __future__ import annotations

import unittest
from pathlib import Path

from pioneer_agent.core.enums import ActionType
from pioneer_agent.verifier.base import DeltaMatchPolicy, DeltaOperator
from pioneer_agent.verifier.eval import (
    load_action_verifier_eval,
    run_action_verifier_eval,
)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "verifier" / "action_verifier_eval.json"


class ActionVerifierEvalTests(unittest.TestCase):
    def test_fixture_covers_p0_action_verifier_cases(self) -> None:
        cases = load_action_verifier_eval(FIXTURE)

        self.assertEqual(
            {case.action_type for case in cases},
            {
                ActionType.CLAIM_CHAPTER_REWARD,
                ActionType.RECRUIT_SOLDIERS,
                ActionType.UPGRADE_BUILDING,
            },
        )
        self.assertTrue(
            {"success", "no_change", "misrecognition", "timeout", "popup_interrupt"}.issubset(
                {case.case_type for case in cases}
            )
        )

    def test_action_verifier_eval_passes_expected_outcomes(self) -> None:
        cases = load_action_verifier_eval(FIXTURE)

        results = run_action_verifier_eval(cases)

        failures = [result.case.case_id for result in results if not result.passed]
        self.assertEqual(failures, [])

    def test_recruit_and_building_cases_are_bound_to_target_identity(self) -> None:
        cases = load_action_verifier_eval(FIXTURE)
        by_id = {case.case_id: case for case in cases}

        recruit = by_id["recruit_soldiers_success"]
        self.assertEqual(recruit.match_policy, DeltaMatchPolicy.ANY)
        self.assertEqual(
            [
                (
                    delta.collection_path,
                    delta.identity_field,
                    delta.identity_value,
                    delta.path,
                    delta.operator,
                )
                for delta in recruit.expected_deltas
            ],
            [
                (
                    "teams",
                    "team_id",
                    "team-2",
                    "soldiers",
                    DeltaOperator.GREATER_THAN_BEFORE,
                ),
                (
                    "teams",
                    "team_id",
                    "team-2",
                    "recruit_finish_time",
                    DeltaOperator.BECOMES_PRESENT,
                ),
            ],
        )

        upgrade = by_id["upgrade_building_reordered_success"]
        self.assertEqual(upgrade.match_policy, DeltaMatchPolicy.ALL)
        self.assertEqual(
            [
                (
                    delta.collection_path,
                    delta.identity_field,
                    delta.identity_value,
                    delta.path,
                    delta.operator,
                )
                for delta in upgrade.expected_deltas
            ],
            [
                (
                    "city.buildings",
                    "name",
                    "仓库",
                    "level",
                    DeltaOperator.INCREASES_TO,
                ),
            ],
        )

        for case_id in (
            "claim_chapter_reward_wrong_chapter",
            "recruit_soldiers_wrong_team_change",
            "recruit_soldiers_stale_countdown",
            "recruit_soldiers_duplicate_target",
            "upgrade_building_other_target_and_wood_change",
            "upgrade_building_target_missing",
            "upgrade_building_duplicate_target",
        ):
            self.assertIn(case_id, by_id)


if __name__ == "__main__":
    unittest.main()
