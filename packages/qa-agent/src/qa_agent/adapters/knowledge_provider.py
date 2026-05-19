from __future__ import annotations

from pathlib import Path

from qa_agent.knowledge.models import EvidenceItem, QueryResponse
from qa_agent.knowledge.source_paths import discover_source_paths
from qa_agent.service.query_service import QueryService
from sanmou_common.ports import Evidence, KnowledgeAnswer


class QaKnowledgeProvider:
    def __init__(self, service: QueryService) -> None:
        self.service = service

    @classmethod
    def from_source_paths(cls, paths: list[Path]) -> "QaKnowledgeProvider":
        return cls(QueryService.from_source_paths(paths))

    @classmethod
    def from_knowledge_root(cls, root: Path) -> "QaKnowledgeProvider":
        return cls.from_source_paths(discover_source_paths(root))

    def lookup_topic(self, topic: str, domain: str | None = None) -> KnowledgeAnswer:
        return _to_common_answer(self.service.lookup_topic(topic, domain=domain))

    def resolve_term(self, term: str, domain: str | None = None) -> KnowledgeAnswer:
        return _to_common_answer(self.service.resolve_term(term, domain=domain))

    def answer_rule_question(self, question: str, domain: str | None = None) -> KnowledgeAnswer:
        return _to_common_answer(self.service.answer_rule_question(question, domain=domain))


def _to_common_answer(response: QueryResponse) -> KnowledgeAnswer:
    return KnowledgeAnswer(
        answer=response.answer,
        evidence=tuple(_to_common_evidence(item, response.confidence) for item in response.evidence),
        confidence=response.confidence,
        coverage=response.coverage.value,
        followups=tuple(response.followups),
    )

def _to_common_evidence(item: EvidenceItem, confidence: float) -> Evidence:
    return Evidence(
        entry_id=item.entry_id,
        topic=item.topic,
        domain=item.domain.value,
        summary=item.summary,
        source_ref=item.source_ref,
        confidence=confidence,
    )
