from __future__ import annotations

import unittest
from pathlib import Path

from pioneer_agent.perception.vision_eval import run_vision_eval_fixture


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "vision" / "team_snapshot_mobile_20260514.json"


class VisionEvalTests(unittest.TestCase):
    def test_team_snapshot_fixture_reports_perfect_offline_baseline(self) -> None:
        summary = run_vision_eval_fixture(FIXTURE)

        report = summary.to_report()
        self.assertEqual(report["screenshot_count"], 5)
        self.assertEqual(report["entity_check_count"], 9)
        self.assertEqual(report["page_accuracy"], 1.0)
        self.assertEqual(report["domain_accuracy"], 1.0)
        self.assertEqual(report["entity_accuracy"], 1.0)
        self.assertEqual(report["failed_screenshots"], [])
        self.assertEqual(report["failed_entities"], [])


if __name__ == "__main__":
    unittest.main()
