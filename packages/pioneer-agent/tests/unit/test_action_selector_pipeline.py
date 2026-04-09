from pathlib import Path
import unittest

from pioneer_agent.runtime.replay_runtime import ReplayRuntime


FIXTURE_EXPECTATIONS = [
    ("chapter_claimable_state.json", "claim_chapter_reward", "priority_rule.chapter_claimable"),
    ("transfer_priority_state.json", "transfer_main_lineup_to_team", "priority_rule.transfer_to_preserve_tempo"),
    ("sample_state.json", "attack_land", "highest_score_after_scoring"),
    ("recruit_priority_state.json", "recruit_soldiers", "highest_score_after_scoring"),
    ("recruit_rule_state.json", "recruit_soldiers", "priority_rule.recruit_main_host_before_risky_attack"),
    ("wait_resource_state.json", "wait_for_resource", "highest_score_after_scoring"),
    ("wait_stamina_state.json", "wait_for_stamina", "highest_score_after_scoring"),
]


class ActionSelectorReplayTests(unittest.TestCase):
    def test_replay_fixture_selects_expected_action(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        runtime = ReplayRuntime()

        for fixture_name, expected_action_type, expected_mode in FIXTURE_EXPECTATIONS:
            with self.subTest(fixture_name=fixture_name):
                fixture_path = project_root / "tests" / "fixtures" / fixture_name
                result = runtime.run_fixture(fixture_path)

                self.assertIsNotNone(result["selected_action"])
                self.assertEqual(result["selected_action"]["action_type"], expected_action_type)
                self.assertEqual(result["selection_reason"]["selection_mode"], expected_mode)
                self.assertGreaterEqual(
                    result["selection_reason"]["pipeline"]["generated"],
                    result["selection_reason"]["pipeline"]["viable"],
                )
                self.assertIsInstance(result["selection_reason"]["rejected_candidates"], list)


if __name__ == "__main__":
    unittest.main()
