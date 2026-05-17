from __future__ import annotations

import unittest

from sanmou_common.config import load_game_configs


class ConfigLoaderTests(unittest.TestCase):
    def test_opening_baseline_config_loads(self) -> None:
        configs = load_game_configs()
        baseline = configs["opening_baseline"]["opening_baseline"]
        self.assertEqual(baseline["advisor_priority_order"][0]["action_type"], "claim_chapter_reward")
        self.assertIn("high_risk_action_without_confirmation", baseline["stop_conditions"])


if __name__ == "__main__":
    unittest.main()
