"""Persistent decision journal with a hard observed/inferred boundary."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ObservedFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact: str = Field(min_length=1)
    observed_at: datetime
    observation_id: str | None = None
    evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed facts require timezone-aware timestamps")
        return value


class AgentInference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inference: str = Field(min_length=1)
    inferred_at: datetime
    based_on_evidence_refs: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("inferred_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("inferences require timezone-aware timestamps")
        return value


class JournalSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed: list[ObservedFact] = Field(default_factory=list)
    inferred: list[AgentInference] = Field(default_factory=list)


class VerifiedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str
    action_type: str
    verified_at: datetime
    observation_id: str
    trace_ref: str


class PendingTimer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timer_id: str
    due_at: datetime
    evidence_refs: list[str] = Field(min_length=1)

    @field_validator("due_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("pending timers require timezone-aware timestamps")
        return value


class DecisionJournal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    agent_session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tactical: JournalSection = Field(default_factory=JournalSection)
    strategic: JournalSection = Field(default_factory=JournalSection)
    tooling: JournalSection = Field(default_factory=JournalSection)
    planning: JournalSection = Field(default_factory=JournalSection)
    hypothesis: JournalSection = Field(default_factory=JournalSection)
    evidence_refs: list[str] = Field(default_factory=list)
    last_verified_action: VerifiedAction | None = None
    pending_timers: list[PendingTimer] = Field(default_factory=list)

    @field_validator("created_at", "updated_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("journal timestamps must be timezone-aware")
        return value

    def latest_tooling_fact(self, fact: str) -> ObservedFact | None:
        return next(
            (item for item in reversed(self.tooling.observed) if item.fact == fact),
            None,
        )


class JournalStore(Protocol):
    def load(self, agent_session_id: str) -> DecisionJournal: ...

    def save(self, journal: DecisionJournal) -> None: ...


class JsonJournalStore:
    """Single-session JSON store with atomic replacement."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, agent_session_id: str) -> DecisionJournal:
        if not self.path.exists():
            return DecisionJournal(agent_session_id=agent_session_id)
        journal = DecisionJournal.model_validate_json(self.path.read_text(encoding="utf-8"))
        if journal.agent_session_id != agent_session_id:
            raise ValueError("journal belongs to a different agent session")
        return journal

    def save(self, journal: DecisionJournal) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8") as handle:
                handle.write(journal.model_dump_json(indent=2))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        finally:
            if temporary.exists():
                temporary.unlink()


class InMemoryJournalStore:
    def __init__(self) -> None:
        self.journals: dict[str, DecisionJournal] = {}

    def load(self, agent_session_id: str) -> DecisionJournal:
        journal = self.journals.get(agent_session_id)
        if journal is None:
            return DecisionJournal(agent_session_id=agent_session_id)
        return journal.model_copy(deep=True)

    def save(self, journal: DecisionJournal) -> None:
        self.journals[journal.agent_session_id] = journal.model_copy(deep=True)


def evidence_ref(prefix: str, value: str) -> str:
    return f"{prefix}:{value}"


def canonical_identity(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
