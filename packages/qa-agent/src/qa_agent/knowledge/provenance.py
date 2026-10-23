"""Versioned, non-authoritative provenance sidecars; existing KB models stay unchanged."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import KnowledgeEntry

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(min_length=1, pattern=r"^\S(?:.*\S)?$")]


def content_digest(content: str) -> str:
    """SHA256 of exact UTF-8 content: no whitespace or Unicode normalization."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def canonical_digest(value: object) -> str:
    return content_digest(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False))


def entry_digest(entry: KnowledgeEntry) -> str:
    return canonical_digest(entry.model_dump(mode="json"))


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceCategory(str, Enum):
    BASIC_KNOWLEDGE = "basic_knowledge"
    REA_EXPORT = "rea_export"
    PLAYER_GUIDE = "player_guide"


class ContentNature(str, Enum):
    CONFIRMED_RULE = "confirmed_rule"
    CLIENT_FIELD = "client_field"
    PLAYER_EXPERIENCE = "player_experience"
    UNVERIFIED_STATEMENT = "unverified_statement"


class SourceLocation(StrictModel):
    kind: Literal["yaml_pointer", "json_pointer", "video_time", "paragraph", "document_section", "unknown"]
    reference: Identifier
    start_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False, strict=True)
    end_seconds: float | None = Field(default=None, ge=0, allow_inf_nan=False, strict=True)

    @model_validator(mode="after")
    def consistent_time_range(self) -> "SourceLocation":
        if self.kind == "video_time":
            if self.start_seconds is None or self.end_seconds is None or self.end_seconds < self.start_seconds:
                raise ValueError("video location requires an ordered start/end range")
        elif self.start_seconds is not None or self.end_seconds is not None:
            raise ValueError("time offsets apply only to video_time")
        return self


class SourceDescription(StrictModel):
    category: SourceCategory
    document_id: Identifier
    source_ref: Identifier
    author: Identifier | None = None
    original_sha256: Digest | None = None
    original_hash_unknown_reason: Identifier | None = None
    revision: Identifier | None = None
    revision_unknown_reason: Identifier | None = None
    published_at: date | None = None
    collected_at: datetime | None = None
    time_unknown_reason: Identifier | None = None
    parser_version: Identifier | None = None
    derived_from: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def explain_unknowns(self) -> "SourceDescription":
        if self.original_sha256 is None and self.original_hash_unknown_reason is None:
            raise ValueError("unknown original hash needs a reason")
        if self.revision is None and self.revision_unknown_reason is None:
            raise ValueError("unknown source revision needs a reason")
        if (self.published_at is None or self.collected_at is None) and self.time_unknown_reason is None:
            raise ValueError("unknown publication/collection time needs a reason")
        if self.collected_at is not None and self.collected_at.utcoffset() is None:
            raise ValueError("collected_at requires a timezone")
        if len(set(self.derived_from)) != len(self.derived_from) or self.document_id in self.derived_from:
            raise ValueError("derived_from must be unique and cannot contain the document itself")
        return self


class Applicability(StrictModel):
    game_version: Identifier | None = None
    season_tags: tuple[Identifier, ...] = ()
    valid_from: date | None = None
    valid_until: date | None = None
    unknown_reason: Identifier | None = None
    conditions: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def validate_scope(self) -> "Applicability":
        if (self.game_version is None or not self.season_tags or self.valid_from is None or self.valid_until is None) and self.unknown_reason is None:
            raise ValueError("incomplete applicability needs an explicit unknown reason")
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until precedes valid_from")
        if len(set(self.season_tags)) != len(self.season_tags):
            raise ValueError("season tags must be unique")
        return self


class ReviewMetadata(StrictModel):
    status: Literal["unreviewed", "reviewed", "rejected", "withdrawn"] = "unreviewed"
    reviewer: Identifier | None = None
    reviewed_at: datetime | None = None
    note: str = ""

    @model_validator(mode="after")
    def validate_review(self) -> "ReviewMetadata":
        if self.status != "unreviewed" and (self.reviewer is None or self.reviewed_at is None):
            raise ValueError("declared review decision needs reviewer and reviewed_at")
        if self.status == "unreviewed" and (self.reviewer is not None or self.reviewed_at is not None):
            raise ValueError("unreviewed record cannot claim reviewer metadata")
        if self.reviewed_at is not None and self.reviewed_at.utcoffset() is None:
            raise ValueError("reviewed_at requires a timezone")
        return self


class KnowledgeProvenance(StrictModel):
    protocol: Literal["knowledge-provenance-v1"] = "knowledge-provenance-v1"
    source: SourceDescription
    nature: ContentNature
    entity_id: Identifier
    entity_name: Identifier
    aliases: tuple[Identifier, ...] = ()
    assertion_key: Identifier
    location: SourceLocation
    content: str = Field(min_length=1)
    content_sha256: Digest
    applicability: Applicability
    review: ReviewMetadata = Field(default_factory=ReviewMetadata)
    legacy_entry_id: Identifier | None = None
    legacy_entry_sha256: Digest | None = None
    synthetic: bool = Field(default=False, strict=True)
    # These sidecars describe evidence. A string claiming "reviewed" is not authorization.
    knowledge_publishable: Literal[False] = False
    execution_authority: Literal["none"] = "none"
    human_gold: Literal[False] = False

    @field_validator("knowledge_publishable", "human_gold", mode="before")
    @classmethod
    def require_literal_false(cls, value: object) -> bool:
        if value is not False:
            raise ValueError("metadata sidecars require literal false authority flags")
        return False

    @model_validator(mode="after")
    def validate_bindings(self) -> "KnowledgeProvenance":
        if content_digest(self.content) != self.content_sha256:
            raise ValueError("content_sha256 does not match exact content")
        if (self.legacy_entry_id is None) != (self.legacy_entry_sha256 is None):
            raise ValueError("legacy entry id and digest must be supplied together")
        if self.nature == ContentNature.CONFIRMED_RULE and self.review.status != "reviewed":
            raise ValueError("confirmed_rule requires a declared reviewed record")
        if self.source.category == SourceCategory.REA_EXPORT and self.nature not in (ContentNature.CLIENT_FIELD, ContentNature.UNVERIFIED_STATEMENT):
            raise ValueError("REA export fields cannot certify a game rule or player experience")
        return self

    @property
    def import_identity(self) -> str:
        """Same document revision/location/object/assertion identifies a repeated import."""
        return canonical_digest({
            "category": self.source.category.value, "document_id": self.source.document_id,
            "revision": self.source.revision, "location": self.location.model_dump(mode="json"),
            "entity_id": self.entity_id, "assertion_key": self.assertion_key,
        })


class ImportConflict(StrictModel):
    import_identity: Digest | None = None
    document_identity: Digest | None = None
    record_digests: tuple[Digest, ...]
    reason: Literal["same_identity_different_record", "same_document_revision_different_original_hash"]


class ImportAudit(StrictModel):
    input_count: int
    exact_duplicates: int
    records: tuple[KnowledgeProvenance, ...]
    conflicts: tuple[ImportConflict, ...]


def audit_imports(records: list[KnowledgeProvenance]) -> ImportAudit:
    """Deduplicate exact imports; preserve every divergent variant for human resolution."""
    unique: dict[str, KnowledgeProvenance] = {}
    identities: dict[str, set[str]] = {}
    documents: dict[str, dict[str, set[str]]] = {}
    for record in records:
        digest = canonical_digest(record.model_dump(mode="json"))
        unique.setdefault(digest, record)
        identities.setdefault(record.import_identity, set()).add(digest)
        if record.source.original_sha256 is not None:
            document = canonical_digest({"document_id": record.source.document_id, "revision": record.source.revision})
            documents.setdefault(document, {}).setdefault(record.source.original_sha256, set()).add(digest)
    conflicts = [ImportConflict(import_identity=identity, record_digests=tuple(sorted(digests)),
                                reason="same_identity_different_record")
                 for identity, digests in sorted(identities.items()) if len(digests) > 1]
    conflicts.extend(ImportConflict(document_identity=identity,
                                    record_digests=tuple(sorted(set().union(*hashes.values()))),
                                    reason="same_document_revision_different_original_hash")
                     for identity, hashes in sorted(documents.items()) if len(hashes) > 1)
    return ImportAudit(input_count=len(records), exact_duplicates=len(records) - len(unique),
                       records=tuple(unique[key] for key in sorted(unique)), conflicts=tuple(conflicts))


def load_provenance_json(text: str) -> list[KnowledgeProvenance]:
    """Only explicit JSON sidecars; never fetch or open their source references."""
    def unique_keys(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    value = json.loads(text, object_pairs_hook=unique_keys)
    if not isinstance(value, list):
        raise ValueError("provenance JSON must contain a list")
    return [KnowledgeProvenance.model_validate(item) for item in value]
