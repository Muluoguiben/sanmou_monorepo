from pathlib import Path
import unittest

from qa_agent.retrieval.retriever import Retriever


class RetrieverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        cls.retriever = Retriever.from_knowledge_dir(project_root / "knowledge_sources")

    def test_retrieve_exact_alias_maps_to_canonical(self) -> None:
        chunks = self.retriever.retrieve("卧龙", top_k=3)
        self.assertTrue(chunks)
        self.assertEqual(chunks[0].entry.topic, "诸葛亮")

    def test_retrieve_rule_question_returns_evidence(self) -> None:
        chunks = self.retriever.retrieve("体力不足怎么办", top_k=5)
        self.assertTrue(chunks)
        topics = [c.entry.topic for c in chunks]
        self.assertTrue(any("体力" in t for t in topics))

    def test_retrieve_empty_for_totally_unknown(self) -> None:
        chunks = self.retriever.retrieve("神器熔铸", top_k=3)
        self.assertEqual(chunks, [])

    def test_retrieve_multi_dedups_and_caps(self) -> None:
        chunks = self.retriever.retrieve_multi(
            ["诸葛亮", "蜀国"], top_k_per_query=3, total_cap=5
        )
        self.assertLessEqual(len(chunks), 5)
        ids = [c.entry.id for c in chunks]
        self.assertEqual(len(ids), len(set(ids)))

    def test_prompt_block_format(self) -> None:
        chunks = self.retriever.retrieve("诸葛亮", top_k=1)
        self.assertTrue(chunks)
        block = chunks[0].as_prompt_block()
        self.assertIn("topic=", block)
        self.assertIn("source:", block)


if __name__ == "__main__":
    unittest.main()
