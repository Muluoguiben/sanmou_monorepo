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

    def test_recruit_and_building_cases_use_real_any_delta_gates(self) -> None:
        cases = load_action_verifier_eval(FIXTURE)
        by_id = {case.case_id: case for case in cases}

        recruit = by_id["recruit_soldiers_success"]
        self.assertEqual(recruit.match_policy, DeltaMatchPolicy.ANY)
        self.assertEqual(
            [(delta.path, delta.operator) for delta in recruit.expected_deltas],
            [
                ("teams.0.soldiers", DeltaOperator.GREATER_THAN_BEFORE),
                ("teams.0.recruit_finish_time", DeltaOperator.PRESENT),
                ("economy.reserve_troops", DeltaOperator.LESS_THAN_BEFORE),
            ],
        )

        upgrade = by_id["upgrade_building_success"]
        self.assertEqual(upgrade.match_policy, DeltaMatchPolicy.ANY)
        self.assertEqual(
            [(delta.path, delta.operator) for delta in upgrade.expected_deltas],
            [
                ("city.buildings.0.level", DeltaOperator.GREATER_THAN_BEFORE),
                ("economy.resources.wood", DeltaOperator.LESS_THAN_BEFORE),
            ],
        )


if __name__ == "__main__":
    unittest.main()
