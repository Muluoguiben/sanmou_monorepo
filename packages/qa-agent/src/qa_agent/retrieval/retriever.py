from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from qa_agent.index.search_index import SearchIndex, normalize_text
from qa_agent.knowledge.loader import load_entries
from qa_agent.knowledge.models import Domain, KnowledgeEntry
from qa_agent.knowledge.source_paths import discover_source_paths

# Stopwords that should NEVER be used as retrieval tokens on their own — they
# match nothing useful and only add noise.
_CHINESE_STOPWORDS: frozenset[str] = frozenset(
    {
        "什么", "怎么", "如何", "多少", "哪个", "哪些", "哪里",
        "可以", "需要", "有没", "没有", "为什", "为啥",
        "的", "是", "在", "有", "和", "与", "或", "及",
        "这个", "那个", "这些", "那些", "就是", "还是",
        "吗", "呢", "吧", "了", "么", "过", "后",
    }
)


def _chinese_ngrams(text: str, sizes: tuple[int, ...] = (4, 3, 2)) -> list[str]:
    """Extract candidate n-gram search tokens from a Chinese question.

    Strips ASCII/whitespace, slides windows of the given sizes, drops stopwords.
    Preserves order and dedupes.
    """
    clean = re.sub(r"[A-Za-z0-9\s\W_]+", "", text, flags=re.UNICODE)
    seen: set[str] = set()
    tokens: list[str] = []
    for size in sizes:
        if len(clean) < size:
            continue
        for i in range(len(clean) - size + 1):
            tok = clean[i : i + size]
            if tok in _CHINESE_STOPWORDS or tok in seen:
                continue
            seen.add(tok)
            tokens.append(tok)
    return tokens


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

        # N-gram fallback: if the whole-query index missed (common for multi-term
        # Chinese questions), try sliding windows over the question and do
        # fact-level substring matching. Lower score than whole-query hits.
        if len(results) < top_k:
            ngram_hits = self._ngram_fact_search(query, domain=domain, limit=top_k * 2)
            for entry in ngram_hits:
                if entry.id in seen_ids:
                    continue
                results.append(RetrievedChunk(entry=entry, score=0.4, matched_query=query))
                seen_ids.add(entry.id)
                if len(results) >= top_k:
                    break

        return results[:top_k]

    def _ngram_fact_search(
        self,
        query: str,
        *,
        domain: Domain | None,
        limit: int,
    ) -> list[KnowledgeEntry]:
        tokens = _chinese_ngrams(query)
        if not tokens:
            return []

        scored: dict[str, tuple[int, KnowledgeEntry]] = {}
        for token in tokens:
            normalized_token = normalize_text(token)
            if not normalized_token:
                continue
            for entry in self.entries:
                if domain and entry.domain != domain:
                    continue
                score = 0
                for term in entry.searchable_terms():
                    if normalized_token and normalized_token in normalize_text(term):
                        score += 3 * len(token)
                        break
                for fact in entry.facts:
                    if token in fact:
                        score += len(token)
                        break
                if score == 0:
                    continue
                prev = scored.get(entry.id)
                # Sum scores across tokens — entries hit by multiple tokens
                # of the same query rank higher than entries hit by one token.
                accumulated = score + (prev[0] if prev else 0)
                scored[entry.id] = (accumulated, entry)

        ranked = sorted(
            scored.values(),
            key=lambda item: (item[0], item[1].priority, item[1].confidence),
            reverse=True,
        )
        return [entry for _, entry in ranked[:limit]]

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
