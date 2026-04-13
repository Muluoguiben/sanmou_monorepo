from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from qa_agent.knowledge.models import Domain, EntryKind, KnowledgeEntry


class ReviewStatus(str, Enum):
    RAW = "raw"
    NORMALIZED = "normalized"
    REVIEWED = "reviewed"


class SourceRecord(BaseModel):
    source_url: str = Field(min_length=1)
    source_site: str = Field(min_length=1)
    source_captured_at: datetime


class StagingMetadata(BaseModel):
    source_url: str = Field(min_length=1)
    source_site: str = Field(min_length=1)
    source_captured_at: datetime
    review_status: ReviewStatus
    review_notes: list[str] = Field(default_factory=list)

    @field_validator("review_notes")
    @classmethod
    def _strip_notes(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class StagingEntry(BaseModel):
    metadata: StagingMetadata
    entry: KnowledgeEntry

    @model_validator(mode="after")
    def _validate_staging_entry(self) -> "StagingEntry":
        allowed_kinds = {
            EntryKind.HERO_PROFILE,
            EntryKind.SKILL_PROFILE,
            EntryKind.LINEUP_SOLUTION,
        }
        if self.entry.entry_kind not in allowed_kinds:
            raise ValueError("staging entry must be hero_profile, skill_profile, or lineup_solution")
        return self

    def to_reviewed_entry(self) -> KnowledgeEntry:
        if self.metadata.review_status != ReviewStatus.REVIEWED:
            raise ValueError("only reviewed staging entries may be promoted to formal knowledge entries")
        return self.entry


class HeroRawRecord(BaseModel):
    canonical_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    faction: str | None = None
    rarity: str | None = None
    troop_types: list[str] = Field(default_factory=list)
    role_tags: list[str] = Field(default_factory=list)
    base_attributes: dict[str, int] | None = None
    growth_attributes: dict[str, float] | None = None
    signature_skills: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    source: SourceRecord

    @field_validator("aliases", "troop_types", "role_tags", "signature_skills", "notes")
    @classmethod
    def _strip_lists(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class SkillRawRecord(BaseModel):
    canonical_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    rarity: str | None = None
    skill_type: str | None = None
    trigger_type: str | None = None
    target_scope: str | None = None
    effect_tags: list[str] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    source: SourceRecord

    @field_validator("aliases", "effect_tags", "preferred_roles", "notes")
    @classmethod
    def _strip_lists(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class RawBatchDocument(BaseModel):
    domain: Domain
    records: list[HeroRawRecord | SkillRawRecord]

    @model_validator(mode="after")
    def _validate_domain_records(self) -> "RawBatchDocument":
        if self.domain == Domain.HERO:
            if not all(isinstance(record, HeroRawRecord) for record in self.records):
                raise ValueError("hero raw batch must contain only HeroRawRecord items")
        elif self.domain == Domain.SKILL:
            if not all(isinstance(record, SkillRawRecord) for record in self.records):
                raise ValueError("skill raw batch must contain only SkillRawRecord items")
        else:
            raise ValueError("raw batch document only supports hero or skill domain")
        return self
