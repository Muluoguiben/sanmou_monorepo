from __future__ import annotations

import unittest
from pathlib import Path

from pioneer_agent.core.enums import ActionType
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


if __name__ == "__main__":
    unittest.main()
