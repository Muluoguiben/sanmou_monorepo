from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class VideoSource(BaseModel):
    video_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    uploader: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    description: str | None = None
    ai_summary: str | None = None
    ai_outline: list[dict[str, Any]] = Field(default_factory=list)
    subtitle_catalog: list[dict] = Field(default_factory=list)
    published_at: datetime | None = None
    captured_at: datetime

    @field_validator("video_id", "title", "uploader", "source_url", mode="before")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be empty")
        return stripped

    @field_validator("description", "ai_summary", mode="before")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("subtitle_catalog")
    @classmethod
    def _normalize_subtitle_catalog(cls, values: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            normalized.append(
                {
                    "lan": str(value.get("lan") or "").strip(),
                    "lan_doc": str(value.get("lan_doc") or "").strip(),
                    "subtitle_url": str(value.get("subtitle_url") or "").strip(),
                }
            )
        return normalized


class VideoFrameRef(BaseModel):
    timestamp_sec: float = Field(ge=0.0)
    image_path: str = Field(min_length=1)
    notes: list[str] = Field(default_factory=list)

    @field_validator("image_path")
    @classmethod
    def _strip_path(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("image_path must not be empty")
        return stripped

    @field_validator("notes")
    @classmethod
    def _strip_notes(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class VideoSegment(BaseModel):
    segment_id: str = Field(min_length=1)
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(gt=0.0)
    transcript: str = ""
    ocr_lines: list[str] = Field(default_factory=list)
    visual_summary: str = ""
    frame_refs: list[VideoFrameRef] = Field(default_factory=list)

    @field_validator("segment_id", "transcript", "visual_summary")
    @classmethod
    def _strip_scalars(cls, value: str) -> str:
        return value.strip()

    @field_validator("ocr_lines")
    @classmethod
    def _strip_ocr_lines(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    @model_validator(mode="after")
    def _validate_range(self) -> "VideoSegment":
        if self.end_sec <= self.start_sec:
            raise ValueError("segment end_sec must be greater than start_sec")
        return self


class VideoLineupCandidate(BaseModel):
    candidate_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    season_tags: list[str] = Field(default_factory=list)
    lineup_rating: str | None = None
    factions: list[str] = Field(default_factory=list)
    hero_names: list[str] = Field(default_factory=list)
    core_skills: list[str] = Field(default_factory=list)
    scenario_tags: list[str] = Field(default_factory=list)
    facts: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("candidate_id", "segment_id", "topic", mode="before")
    @classmethod
    def _strip_required_scalar(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be empty")
        return stripped

    @field_validator("lineup_rating", mode="before")
    @classmethod
    def _strip_optional_scalar(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator(
        "aliases",
        "season_tags",
        "factions",
        "hero_names",
        "core_skills",
        "scenario_tags",
        "facts",
        "constraints",
        "notes",
    )
    @classmethod
    def _strip_lists(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class VideoHeroCandidate(BaseModel):
    candidate_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    hero_name: str = Field(min_length=1)
    facts: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    related_topics: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("candidate_id", "segment_id", "hero_name", mode="before")
    @classmethod
    def _strip_required_scalar(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be empty")
        return stripped

    @field_validator("facts", "constraints", "related_topics")
    @classmethod
    def _strip_lists(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class VideoSkillCandidate(BaseModel):
    candidate_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    skill_name: str = Field(min_length=1)
    facts: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    related_topics: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("candidate_id", "segment_id", "skill_name", mode="before")
    @classmethod
    def _strip_required_scalar(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be empty")
        return stripped

    @field_validator("facts", "constraints", "related_topics")
    @classmethod
    def _strip_lists(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class VideoCombatCandidate(BaseModel):
    candidate_id: str = Field(min_length=1)
    segment_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    facts: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    related_topics: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("candidate_id", "segment_id", "topic", mode="before")
    @classmethod
    def _strip_required_scalar(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be empty")
        return stripped

    @field_validator("facts", "constraints", "related_topics")
    @classmethod
    def _strip_lists(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class VideoKnowledgeDocument(BaseModel):
    source: VideoSource
    segments: list[VideoSegment] = Field(min_length=1)
    lineup_candidates: list[VideoLineupCandidate] = Field(default_factory=list)
    hero_candidates: list[VideoHeroCandidate] = Field(default_factory=list)
    skill_candidates: list[VideoSkillCandidate] = Field(default_factory=list)
    combat_candidates: list[VideoCombatCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_segment_references(self) -> "VideoKnowledgeDocument":
        segment_ids = {segment.segment_id for segment in self.segments}
        candidate_groups = [
            ("lineup", self.lineup_candidates),
            ("hero", self.hero_candidates),
            ("skill", self.skill_candidates),
            ("combat", self.combat_candidates),
        ]
        for group_name, candidates in candidate_groups:
            for candidate in candidates:
                if candidate.segment_id not in segment_ids:
                    raise ValueError(
                        f"{group_name} candidate {candidate.candidate_id} references unknown segment {candidate.segment_id}"
                    )
        return self
