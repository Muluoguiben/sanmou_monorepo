from pathlib import Path
import unittest

from qa_agent.knowledge.source_paths import discover_source_paths
from qa_agent.service.query_service import QueryService


class LandOccupationKnowledgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        source_paths = discover_source_paths(project_root / "knowledge_sources")
        cls.service = QueryService.from_source_paths(source_paths)

    def test_player_observed_countdown_is_queryable_and_time_bounded(self) -> None:
        for question in ("占领土地要多久？", "新手期占领要多久？"):
            with self.subTest(question=question):
                response = self.service.answer_rule_question(question, domain="combat")
                self.assertEqual(
                    response.evidence[0].entry_id,
                    "mech-land-occupation-countdown-player-test",
                )
                self.assertEqual(
                    response.evidence[0].source_ref,
                    "user_live_test:2026-07-11#land-occupation-countdown",
                )
                self.assertIn("非新手期通常约 3 分钟", response.answer)
                self.assertIn("新手期通常约 1 分钟", response.answer)
                self.assertIn("战斗胜利、倒计时开始、最终占领完成", response.answer)
                self.assertIn("不是官方永久规则", response.answer)


if __name__ == "__main__":
    unittest.main()
