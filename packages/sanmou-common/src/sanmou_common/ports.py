from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class Evidence:
    entry_id: str
    topic: str
    domain: str
    summary: str
    source_ref: str = ""
    confidence: float | None = None


@dataclass(frozen=True)
class KnowledgeAnswer:
    answer: str
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    confidence: float = 0.0
    coverage: str = "not_found"
    followups: tuple[str, ...] = field(default_factory=tuple)


@runtime_checkable
class KnowledgeProvider(Protocol):
    def lookup_topic(self, topic: str, domain: str | None = None) -> KnowledgeAnswer:
        ...

    def resolve_term(self, term: str, domain: str | None = None) -> KnowledgeAnswer:
        ...

    def answer_rule_question(self, question: str, domain: str | None = None) -> KnowledgeAnswer:
        ...


@runtime_checkable
class ModelAdapter(Protocol):
    def generate_structured(
        self,
        *,
        prompt: str,
        schema: Mapping[str, Any],
        images: Sequence[bytes] | None = None,
    ) -> Mapping[str, Any]:
        ...
