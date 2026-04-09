from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class Domain(str, Enum):
    BUILDING = "building"
    CHAPTER = "chapter"
    COMBAT = "combat"
    HERO = "hero"
    RESOURCE = "resource"
    SKILL = "skill"
    SOLUTION = "solution"
    STATUS = "status"
    TEAM = "team"
    TERM = "term"


class SourceType(str, Enum):
    MANUAL_RULE = "manual_rule"


class Coverage(str, Enum):
    EXACT = "exact"
    PARTIAL = "partial"
    NOT_FOUND = "not_found"


class EntryKind(str, Enum):
    GENERIC_RULE = "generic_rule"
    HERO_PROFILE = "hero_profile"
    LINEUP_SOLUTION = "lineup_solution"
    SKILL_PROFILE = "skill_profile"
    STATUS_PROFILE = "status_profile"


class EvidenceItem(BaseModel):
    entry_id: str
    topic: str
    domain: Domain
    summary: str
    source_ref: str


class AttributeSet(BaseModel):
    military: int | None = Field(default=None, ge=0)
    intelligence: int | None = Field(default=None, ge=0)
    command: int | None = Field(default=None, ge=0)
    initiative: int | None = Field(default=None, ge=0)


class AttributeGrowth(BaseModel):
    military: float | None = Field(default=None, ge=0.0)
    intelligence: float | None = Field(default=None, ge=0.0)
    command: float | None = Field(default=None, ge=0.0)
    initiative: float | None = Field(default=None, ge=0.0)


class HeroStaticProfile(BaseModel):
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    faction: str | None = None
    rarity: str | None = None
    troop_types: list[str] = Field(default_factory=list)
    role_tags: list[str] = Field(default_factory=list)
    base_attributes: AttributeSet | None = None
    growth_attributes: AttributeGrowth | None = None
    max_attributes: AttributeSet | None = None
    signature_skills: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("aliases", "troop_types", "role_tags", "signature_skills", "notes")
    @classmethod
    def _strip_list_values(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    def searchable_terms(self) -> list[str]:
        return [self.name, *self.aliases]

    def _format_attrs(self, attrs: AttributeSet, label: str) -> str:
        parts = []
        if attrs.military is not None:
            parts.append(f"武力{attrs.military}")
        if attrs.intelligence is not None:
            parts.append(f"智力{attrs.intelligence}")
        if attrs.command is not None:
            parts.append(f"统率{attrs.command}")
        if attrs.initiative is not None:
            parts.append(f"先攻{attrs.initiative}")
        return f"{label}：{' '.join(parts)}"

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        if self.faction or self.rarity:
            parts = [part for part in [self.faction, self.rarity] if part]
            lines.append(" / ".join(parts))
        if self.troop_types:
            lines.append(f"兵种适性标签：{'、'.join(self.troop_types)}")
        if self.role_tags:
            lines.append(f"定位标签：{'、'.join(self.role_tags)}")
        if self.max_attributes:
            lines.append(self._format_attrs(self.max_attributes, "满级属性(Lv50)"))
        elif self.base_attributes:
            lines.append(self._format_attrs(self.base_attributes, "初始属性"))
        if self.signature_skills:
            lines.append(f"代表战法：{'、'.join(self.signature_skills[:3])}")
        if self.notes:
            lines.append(self.notes[0])
        return lines


class SkillStaticProfile(BaseModel):
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    rarity: str | None = None
    skill_type: str | None = None
    trigger_type: str | None = None
    target_scope: str | None = None
    effect_tags: list[str] = Field(default_factory=list)
    preferred_roles: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("aliases", "effect_tags", "preferred_roles", "notes")
    @classmethod
    def _strip_list_values(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    def searchable_terms(self) -> list[str]:
        return [self.name, *self.aliases]

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        meta = [part for part in [self.rarity, self.skill_type, self.trigger_type] if part]
        if meta:
            lines.append(" / ".join(meta))
        if self.target_scope:
            lines.append(f"目标范围：{self.target_scope}")
        if self.effect_tags:
            lines.append(f"效果标签：{'、'.join(self.effect_tags)}")
        if self.preferred_roles:
            lines.append(f"适配定位：{'、'.join(self.preferred_roles)}")
        if self.notes:
            lines.append(self.notes[0])
        return lines


class StatusProfile(BaseModel):
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    status_group: str | None = None
    polarity: str | None = None
    trigger_notes: list[str] = Field(default_factory=list)
    effect_tags: list[str] = Field(default_factory=list)
    removable_by: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("aliases", "trigger_notes", "effect_tags", "removable_by", "notes")
    @classmethod
    def _strip_list_values(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    def searchable_terms(self) -> list[str]:
        return [self.name, *self.aliases]

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        meta = [part for part in [self.status_group, self.polarity] if part]
        if meta:
            lines.append(" / ".join(meta))
        if self.effect_tags:
            lines.append(f"效果标签：{'、'.join(self.effect_tags)}")
        if self.removable_by:
            lines.append(f"常见处理方式：{'、'.join(self.removable_by)}")
        if self.trigger_notes:
            lines.append(self.trigger_notes[0])
        elif self.notes:
            lines.append(self.notes[0])
        return lines


class LineupSolutionProfile(BaseModel):
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    season_tags: list[str] = Field(default_factory=list)
    lineup_rating: str | None = None
    factions: list[str] = Field(default_factory=list)
    hero_names: list[str] = Field(default_factory=list)
    core_skills: list[str] = Field(default_factory=list)
    scenario_tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("aliases", "season_tags", "factions", "hero_names", "core_skills", "scenario_tags", "notes")
    @classmethod
    def _strip_list_values(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    def searchable_terms(self) -> list[str]:
        return [self.name, *self.aliases, *self.hero_names, *self.core_skills]

    def summary_lines(self) -> list[str]:
        lines: list[str] = []
        meta = [part for part in [self.lineup_rating, *self.season_tags[:2]] if part]
        if meta:
            lines.append(" / ".join(meta))
        if self.hero_names:
            lines.append(f"核心武将：{'、'.join(self.hero_names[:3])}")
        if self.core_skills:
            lines.append(f"核心战法：{'、'.join(self.core_skills[:3])}")
        if self.scenario_tags:
            lines.append(f"适用场景：{'、'.join(self.scenario_tags)}")
        if self.notes:
            lines.append(self.notes[0])
        return lines


class KnowledgeEntry(BaseModel):
    id: str = Field(min_length=3)
    domain: Domain
    entry_kind: EntryKind = EntryKind.GENERIC_RULE
    topic: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    facts: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    source_type: SourceType = SourceType.MANUAL_RULE
    source_ref: str = Field(min_length=1)
    updated_at: date
    confidence: float = Field(ge=0.0, le=1.0)
    related_topics: list[str] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0, le=100)
    structured_data: HeroStaticProfile | SkillStaticProfile | StatusProfile | LineupSolutionProfile | None = None

    @field_validator("aliases", "facts", "constraints", "related_topics")
    @classmethod
    def _strip_values(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("topic must not be empty")
        return stripped

    @model_validator(mode="after")
    def _validate_structured_payload(self) -> "KnowledgeEntry":
        if self.entry_kind == EntryKind.HERO_PROFILE:
            if self.domain != Domain.HERO:
                raise ValueError("hero_profile entries must use hero domain")
            if not isinstance(self.structured_data, HeroStaticProfile):
                raise ValueError("hero_profile entries require hero structured_data")
        elif self.entry_kind == EntryKind.SKILL_PROFILE:
            if self.domain != Domain.SKILL:
                raise ValueError("skill_profile entries must use skill domain")
            if not isinstance(self.structured_data, SkillStaticProfile):
                raise ValueError("skill_profile entries require skill structured_data")
        elif self.entry_kind == EntryKind.STATUS_PROFILE:
            if self.domain != Domain.STATUS:
                raise ValueError("status_profile entries must use status domain")
            if not isinstance(self.structured_data, StatusProfile):
                raise ValueError("status_profile entries require status structured_data")
        elif self.entry_kind == EntryKind.LINEUP_SOLUTION:
            if self.domain != Domain.SOLUTION:
                raise ValueError("lineup_solution entries must use solution domain")
            if not isinstance(self.structured_data, LineupSolutionProfile):
                raise ValueError("lineup_solution entries require solution structured_data")
        return self

    def searchable_terms(self) -> list[str]:
        terms = [self.topic, *self.aliases]
        if self.structured_data is not None:
            terms.extend(self.structured_data.searchable_terms())
        return terms

    def answer_lines(self) -> list[str]:
        lines = list(self.facts)
        if self.structured_data is not None:
            lines.extend(self.structured_data.summary_lines())
        return [line for line in lines if line]


class QueryResponse(BaseModel):
    answer: str
    evidence: list[EvidenceItem]
    confidence: float = Field(ge=0.0, le=1.0)
    coverage: Coverage
    followups: list[str] = Field(default_factory=list)
