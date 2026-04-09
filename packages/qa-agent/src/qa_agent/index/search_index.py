from __future__ import annotations

from collections import defaultdict
from datetime import date
import re

from qa_agent.knowledge.models import Domain, KnowledgeEntry


def normalize_text(value: str) -> str:
    lowered = value.lower().strip()
    return re.sub(r"[\s\W_]+", "", lowered, flags=re.UNICODE)


class SearchIndex:
    def __init__(self, entries: list[KnowledgeEntry]) -> None:
        self.entries = entries
        self.by_id = {entry.id: entry for entry in entries}
        self.term_to_ids: dict[str, list[str]] = defaultdict(list)
        for entry in entries:
            for term in entry.searchable_terms():
                normalized = normalize_text(term)
                if entry.id not in self.term_to_ids[normalized]:
                    self.term_to_ids[normalized].append(entry.id)

    def resolve_term(self, term: str, domain: Domain | None = None) -> list[KnowledgeEntry]:
        normalized = normalize_text(term)
        entry_ids = self.term_to_ids.get(normalized, [])
        entries = [self.by_id[entry_id] for entry_id in entry_ids]
        return self._filter_and_sort(entries, domain=domain)

    def search(self, query: str, domain: Domain | None = None) -> list[KnowledgeEntry]:
        normalized_query = normalize_text(query)
        scored: list[tuple[int, KnowledgeEntry]] = []
        for entry in self.entries:
            if domain and entry.domain != domain:
                continue
            score = self._score_entry(entry, query, normalized_query)
            if score > 0:
                scored.append((score, entry))
        return [entry for _, entry in sorted(scored, key=self._sort_key, reverse=True)]

    def _filter_and_sort(
        self,
        entries: list[KnowledgeEntry],
        domain: Domain | None = None,
    ) -> list[KnowledgeEntry]:
        filtered = [entry for entry in entries if domain is None or entry.domain == domain]
        return sorted(filtered, key=lambda entry: (entry.priority, entry.confidence, entry.updated_at), reverse=True)

    def _score_entry(self, entry: KnowledgeEntry, raw_query: str, normalized_query: str) -> int:
        score = 0
        raw_query = raw_query.strip().lower()
        for term in entry.searchable_terms():
            normalized_term = normalize_text(term)
            raw_term = term.lower()
            if not normalized_term:
                continue
            if normalized_query == normalized_term:
                score = max(score, 120)
            elif normalized_term in normalized_query:
                score = max(score, 90 + min(len(normalized_term), 20))
            elif normalized_query in normalized_term and len(normalized_query) >= 2:
                score = max(score, 70 + min(len(normalized_query), 10))
            elif raw_term and raw_term in raw_query:
                score = max(score, 65 + min(len(raw_term), 10))
        if score == 0:
            for fact in entry.facts:
                normalized_fact = normalize_text(fact)
                if normalized_query and normalized_query in normalized_fact:
                    score = max(score, 35)
                    break
        return score

    @staticmethod
    def _sort_key(item: tuple[int, KnowledgeEntry]) -> tuple[int, int, float, date]:
        score, entry = item
        return (score, entry.priority, entry.confidence, entry.updated_at)

