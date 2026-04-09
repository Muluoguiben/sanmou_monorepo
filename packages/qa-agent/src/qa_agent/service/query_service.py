from __future__ import annotations

from pathlib import Path

from qa_agent.index.search_index import SearchIndex
from qa_agent.knowledge.loader import load_entries
from qa_agent.knowledge.models import Coverage, Domain, EvidenceItem, KnowledgeEntry, QueryResponse


class QueryService:
    def __init__(self, entries: list[KnowledgeEntry]) -> None:
        self.entries = entries
        self.index = SearchIndex(entries)

    @classmethod
    def from_source_paths(cls, paths: list[Path]) -> "QueryService":
        return cls(load_entries(paths))

    def lookup_topic(self, topic: str, domain: str | None = None) -> QueryResponse:
        parsed_domain = self._parse_domain(domain)
        exact_matches = self.index.resolve_term(topic, domain=parsed_domain)
        if exact_matches:
            return self._entry_response(exact_matches[0], coverage=Coverage.EXACT)

        matches = self.index.search(topic, domain=parsed_domain)
        if matches:
            return self._entry_response(matches[0], coverage=Coverage.PARTIAL)

        return self._not_found_response(topic, parsed_domain)

    def resolve_term(self, term: str, domain: str | None = None) -> QueryResponse:
        parsed_domain = self._parse_domain(domain)
        matches = self.index.resolve_term(term, domain=parsed_domain)
        if matches:
            entry = matches[0]
            aliases = "、".join(entry.aliases[:5]) if entry.aliases else "无已登记别名"
            return QueryResponse(
                answer=f"术语“{term}”对应标准主题“{entry.topic}”。",
                evidence=[self._to_evidence(entry, f"标准主题：{entry.topic}；别名：{aliases}")],
                confidence=entry.confidence,
                coverage=Coverage.EXACT,
                followups=entry.related_topics,
            )

        matches = self.index.search(term, domain=parsed_domain)
        if matches:
            entry = matches[0]
            return QueryResponse(
                answer=f"未找到术语“{term}”的精确映射，最接近的标准主题是“{entry.topic}”。",
                evidence=[self._to_evidence(entry, entry.facts[0])],
                confidence=min(entry.confidence, 0.7),
                coverage=Coverage.PARTIAL,
                followups=entry.related_topics,
            )

        return self._not_found_response(term, parsed_domain)

    def answer_rule_question(self, question: str, domain: str | None = None) -> QueryResponse:
        parsed_domain = self._parse_domain(domain)
        matches = self.index.search(question, domain=parsed_domain)
        if not matches:
            return self._not_found_response(question, parsed_domain)

        top = matches[0]
        answer = "；".join(top.answer_lines()[:3])
        coverage = Coverage.EXACT if self._question_has_explicit_term(question, top) else Coverage.PARTIAL
        confidence = top.confidence if coverage is Coverage.EXACT else min(top.confidence, 0.78)
        return QueryResponse(
            answer=answer,
            evidence=[self._to_evidence(top, top.answer_lines()[0])],
            confidence=confidence,
            coverage=coverage,
            followups=top.related_topics,
        )

    def _entry_response(self, entry: KnowledgeEntry, coverage: Coverage) -> QueryResponse:
        answer = "；".join(entry.answer_lines()[:3])
        return QueryResponse(
            answer=answer,
            evidence=[self._to_evidence(entry, entry.answer_lines()[0])],
            confidence=entry.confidence,
            coverage=coverage,
            followups=entry.related_topics,
        )

    def _not_found_response(self, query: str, domain: Domain | None) -> QueryResponse:
        domain_hint = f"（domain={domain.value}）" if domain else ""
        return QueryResponse(
            answer=f"知识库暂未收录“{query}”的可靠规则{domain_hint}。",
            evidence=[],
            confidence=0.0,
            coverage=Coverage.NOT_FOUND,
            followups=self._suggest_followups(query, domain),
        )

    def _suggest_followups(self, query: str, domain: Domain | None) -> list[str]:
        nearby = self.index.search(query, domain=domain)
        return [entry.topic for entry in nearby[:3]]

    @staticmethod
    def _question_has_explicit_term(question: str, entry: KnowledgeEntry) -> bool:
        lowered = question.lower()
        return any(term.lower() in lowered for term in entry.searchable_terms())

    @staticmethod
    def _to_evidence(entry: KnowledgeEntry, summary: str) -> EvidenceItem:
        return EvidenceItem(
            entry_id=entry.id,
            topic=entry.topic,
            domain=entry.domain,
            summary=summary,
            source_ref=entry.source_ref,
        )

    @staticmethod
    def _parse_domain(domain: str | None) -> Domain | None:
        if domain is None:
            return None
        return Domain(domain)
