from __future__ import annotations

import unittest

from sanmou_common.ports import Evidence, KnowledgeAnswer, KnowledgeProvider


class _StubKnowledgeProvider:
    def lookup_topic(self, topic: str, domain: str | None = None) -> KnowledgeAnswer:
        return KnowledgeAnswer(
            answer=f"{topic}:{domain or 'any'}",
            evidence=(Evidence(entry_id="entry-1", topic=topic, domain=domain or "term", summary="ok"),),
            confidence=0.9,
            coverage="exact",
        )

    def resolve_term(self, term: str, domain: str | None = None) -> KnowledgeAnswer:
        return self.lookup_topic(term, domain)

    def answer_rule_question(self, question: str, domain: str | None = None) -> KnowledgeAnswer:
        return self.lookup_topic(question, domain)


class PortsTests(unittest.TestCase):
    def test_knowledge_provider_is_runtime_checkable(self) -> None:
        provider = _StubKnowledgeProvider()
        self.assertIsInstance(provider, KnowledgeProvider)
        answer = provider.answer_rule_question("建筑升级", domain="building")
        self.assertEqual(answer.evidence[0].entry_id, "entry-1")
        self.assertEqual(answer.coverage, "exact")


if __name__ == "__main__":
    unittest.main()
