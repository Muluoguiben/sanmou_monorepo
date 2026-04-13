from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from qa_agent.index.search_index import SearchIndex
from qa_agent.knowledge.loader import load_entries
from qa_agent.knowledge.models import Domain, KnowledgeEntry
from qa_agent.knowledge.source_paths import discover_source_paths


@dataclass
class RetrievedChunk:
    entry: KnowledgeEntry
    score: float
    matched_query: str

    def as_prompt_block(self) -> str:
        lines = [
            f"[{self.entry.id}] topic={self.entry.topic} domain={self.entry.domain.value}",
        ]
        if self.entry.aliases:
            lines.append(f"aliases: {'、'.join(self.entry.aliases[:6])}")
        for fact in self.entry.answer_lines():
            lines.append(f"- {fact}")
        if self.entry.constraints:
            lines.append(f"constraints: {'；'.join(self.entry.constraints[:3])}")
        lines.append(f"source: {self.entry.source_ref} (confidence={self.entry.confidence:.2f})")
        return "\n".join(lines)


class Retriever:
    def __init__(self, entries: list[KnowledgeEntry]) -> None:
        self.entries = entries
        self.index = SearchIndex(entries)

    @classmethod
    def from_knowledge_dir(cls, knowledge_dir: Path) -> "Retriever":
        source_paths = discover_source_paths(knowledge_dir)
        return cls(load_entries(source_paths))

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        domain: Domain | None = None,
    ) -> list[RetrievedChunk]:
        results: list[RetrievedChunk] = []
        seen_ids: set[str] = set()

        for entry in self.index.resolve_term(query, domain=domain):
            if entry.id not in seen_ids:
                results.append(RetrievedChunk(entry=entry, score=1.0, matched_query=query))
                seen_ids.add(entry.id)

        for entry in self.index.search(query, domain=domain):
            if entry.id in seen_ids:
                continue
            results.append(RetrievedChunk(entry=entry, score=0.6, matched_query=query))
            seen_ids.add(entry.id)
            if len(results) >= top_k * 2:
                break

        return results[:top_k]

    def retrieve_multi(
        self,
        queries: list[str],
        *,
        top_k_per_query: int = 3,
        total_cap: int = 8,
    ) -> list[RetrievedChunk]:
        merged: dict[str, RetrievedChunk] = {}
        for q in queries:
            for chunk in self.retrieve(q, top_k=top_k_per_query):
                existing = merged.get(chunk.entry.id)
                if existing is None or chunk.score > existing.score:
                    merged[chunk.entry.id] = chunk
        ranked = sorted(
            merged.values(),
            key=lambda c: (c.score, c.entry.priority, c.entry.confidence),
            reverse=True,
        )
        return ranked[:total_cap]
