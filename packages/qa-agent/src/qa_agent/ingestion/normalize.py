from __future__ import annotations

from datetime import date

from qa_agent.ingestion.config import AliasConfig, EnumConfig
from qa_agent.ingestion.models import HeroRawRecord, ReviewStatus, SkillRawRecord, StagingEntry, StagingMetadata
from qa_agent.knowledge.models import (
    AttributeGrowth,
    AttributeSet,
    Domain,
    EntryKind,
    HeroStaticProfile,
    KnowledgeEntry,
    SkillStaticProfile,
)


def _slugify(value: str) -> str:
    lowered = value.lower().strip()
    return "-".join(part for part in lowered.replace("/", " ").replace("_", " ").split() if part)


def _normalize_scalar(value: str | None, mapping: dict[str, str]) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return mapping.get(normalized, normalized)


def _normalize_list(values: list[str], mapping: dict[str, str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        candidate = mapping.get(value.strip(), value.strip())
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def normalize_hero_record(record: HeroRawRecord, aliases: AliasConfig, enums: EnumConfig) -> StagingEntry:
    canonical_name = aliases.canonical_map.get(record.canonical_name, record.canonical_name)
    merged_aliases = list(dict.fromkeys([*record.aliases, *aliases.aliases.get(canonical_name, [])]))
    # Build structured attribute sets from raw record
    base_attrs = None
    growth_attrs = None
    max_attrs = None
    if record.base_attributes:
        ba = record.base_attributes
        base_attrs = AttributeSet(
            military=ba.get("military"),
            intelligence=ba.get("intelligence"),
            command=ba.get("command"),
            initiative=ba.get("initiative"),
        )
    if record.growth_attributes:
        ga = record.growth_attributes
        growth_attrs = AttributeGrowth(
            military=ga.get("military"),
            intelligence=ga.get("intelligence"),
            command=ga.get("command"),
            initiative=ga.get("initiative"),
        )
    if base_attrs and growth_attrs:
        # Heroes start at Lv5, max Lv50 → 45 levels of growth
        max_attrs = AttributeSet(
            military=round((base_attrs.military or 0) + (growth_attrs.military or 0) * 45),
            intelligence=round((base_attrs.intelligence or 0) + (growth_attrs.intelligence or 0) * 45),
            command=round((base_attrs.command or 0) + (growth_attrs.command or 0) * 45),
            initiative=round((base_attrs.initiative or 0) + (growth_attrs.initiative or 0) * 45),
        )

    profile = HeroStaticProfile(
        name=canonical_name,
        aliases=merged_aliases,
        faction=_normalize_scalar(record.faction, enums.factions),
        rarity=_normalize_scalar(record.rarity, enums.rarities),
        troop_types=_normalize_list(record.troop_types, enums.troop_types),
        role_tags=_normalize_list(record.role_tags, enums.role_tags),
        base_attributes=base_attrs,
        growth_attributes=growth_attrs,
        max_attributes=max_attrs,
        signature_skills=record.signature_skills,
        notes=record.notes,
    )
    has_attrs = base_attrs is not None
    entry = KnowledgeEntry(
        id=f"hero-{_slugify(canonical_name)}",
        domain=Domain.HERO,
        entry_kind=EntryKind.HERO_PROFILE,
        topic=canonical_name,
        aliases=merged_aliases,
        facts=[
            f"{canonical_name}是{profile.faction or '未知阵营'}阵营可录入的核心武将静态资料条目。",
            "当前条目优先收录稳定身份、兵种和定位标签，不直接表达版本强度结论。",
        ],
        constraints=[] if has_attrs else ["属性与成长数值待后续有稳定来源后再补录。"],
        source_ref=f"INGESTION-{record.source.source_site.upper()}-HERO",
        updated_at=date.today(),
        confidence=0.9,
        related_topics=profile.signature_skills[:3],
        priority=88,
        structured_data=profile,
    )
    metadata = StagingMetadata(
        source_url=record.source.source_url,
        source_site=record.source.source_site,
        source_captured_at=record.source.source_captured_at,
        review_status=ReviewStatus.NORMALIZED,
        review_notes=["auto-normalized from raw hero record"],
    )
    return StagingEntry(metadata=metadata, entry=entry)


def normalize_skill_record(record: SkillRawRecord, aliases: AliasConfig, enums: EnumConfig) -> StagingEntry:
    canonical_name = aliases.canonical_map.get(record.canonical_name, record.canonical_name)
    merged_aliases = list(dict.fromkeys([*record.aliases, *aliases.aliases.get(canonical_name, [])]))
    profile = SkillStaticProfile(
        name=canonical_name,
        aliases=merged_aliases,
        rarity=_normalize_scalar(record.rarity, enums.rarities),
        skill_type=_normalize_scalar(record.skill_type, enums.skill_types),
        trigger_type=_normalize_scalar(record.trigger_type, enums.trigger_types),
        target_scope=_normalize_scalar(record.target_scope, enums.target_scopes),
        effect_tags=record.effect_tags,
        preferred_roles=_normalize_list(record.preferred_roles, enums.role_tags),
        notes=record.notes,
    )
    entry = KnowledgeEntry(
        id=f"skill-{_slugify(canonical_name)}",
        domain=Domain.SKILL,
        entry_kind=EntryKind.SKILL_PROFILE,
        topic=canonical_name,
        aliases=merged_aliases,
        facts=[
            f"{canonical_name}是可录入的高频战法静态资料条目。",
            "当前条目优先收录稳定分类、目标范围与效果标签，不直接表达版本强度结论。",
        ],
        constraints=["具体数值与发动率待后续有稳定来源后再补录。"],
        source_ref=f"INGESTION-{record.source.source_site.upper()}-SKILL",
        updated_at=date.today(),
        confidence=0.9,
        related_topics=profile.preferred_roles[:3],
        priority=88,
        structured_data=profile,
    )
    metadata = StagingMetadata(
        source_url=record.source.source_url,
        source_site=record.source.source_site,
        source_captured_at=record.source.source_captured_at,
        review_status=ReviewStatus.NORMALIZED,
        review_notes=["auto-normalized from raw skill record"],
    )
    return StagingEntry(metadata=metadata, entry=entry)

