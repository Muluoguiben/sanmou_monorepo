from __future__ import annotations

from pathlib import Path
import unittest

from qa_agent.adapters import QaKnowledgeProvider
from sanmou_common.ports import KnowledgeAnswer, KnowledgeProvider


class QaKnowledgeProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.provider = QaKnowledgeProvider.from_knowledge_root(project_root / "knowledge_sources")

    def test_provider_matches_common_protocol(self) -> None:
        self.assertIsInstance(self.provider, KnowledgeProvider)

    def test_answer_rule_question_returns_common_evidence(self) -> None:
        response = self.provider.answer_rule_question("建筑升级需要满足什么条件？", domain="building")
        self.assertIsInstance(response, KnowledgeAnswer)
        self.assertEqual(response.coverage, "exact")
        self.assertEqual(response.evidence[0].entry_id, "building-upgrade")
        self.assertEqual(response.evidence[0].domain, "building")
        self.assertGreater(response.confidence, 0)


if __name__ == "__main__":
    unittest.main()
