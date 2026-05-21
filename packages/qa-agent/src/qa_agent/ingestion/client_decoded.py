from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from qa_agent.ingestion.models import ReviewStatus, StagingEntry, StagingMetadata
from qa_agent.knowledge.models import Domain, EntryKind, HeroStaticProfile, KnowledgeEntry


SOURCE_SITE = "nslg_client_decode"
SOURCE_URL = "local-nslg-client-decoded"

FACTION_MAP = {
    "wei": "魏",
    "shu": "蜀",
    "wu": "吴",
    "qun": "群",
    "other": "其他",
}


class DecodedSkillSlot(BaseModel):
    position: int | None = Field(default=None, ge=1)
    skill_id: int = Field(alias="skillId", ge=1)
    order_level: int | None = Field(default=None, alias="orderLevel", ge=0)
    level: int | None = Field(default=None, ge=0)


class DecodedHeroRecord(BaseModel):
    hero_id: int = Field(alias="heroID", ge=1)
    base_codename: str | None = Field(default=None, alias="baseCodename")
    faction: str | None = None
    variants: list[str] = Field(default_factory=list)
    in_static_master: bool = Field(default=False, alias="inStaticMaster")
    lineup_decoded: bool = Field(default=False, alias="lineupDecoded")
    lineup: dict[str, Any] | None = None
    gvg: dict[str, Any] | None = None

    @field_validator("variants")
    @classmethod
    def _strip_variants(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    @property
    def topic(self) -> str:
        return self.base_codename or f"hero_{self.hero_id}"

    def sanitized_skill_slots(self) -> list[DecodedSkillSlot]:
        slots: list[DecodedSkillSlot] = []
        if self.lineup:
            for raw_slot in self.lineup.get("skillSlots") or []:
                slots.append(DecodedSkillSlot.model_validate(raw_slot))
        if self.gvg:
            for raw_slot in self.gvg.get("skillList") or []:
                slots.append(DecodedSkillSlot.model_validate(raw_slot))
        unique: dict[tuple[int, int | None], DecodedSkillSlot] = {}
        for slot in slots:
            unique.setdefault((slot.skill_id, slot.position), slot)
        return sorted(unique.values(), key=lambda item: (item.position or 99, item.skill_id))

    def sanitized_attr_slots(self) -> list[dict[str, int]]:
        attrs: list[dict[str, int]] = []
        for source in [self.lineup, self.gvg]:
            if not source:
                continue
            for raw_attr in source.get("attrNonzeroSlots") or []:
                slot = raw_attr.get("slot")
                value = raw_attr.get("value")
                if isinstance(slot, int) and isinstance(value, int):
                    attrs.append({"slot": slot, "value": value})
        unique = {(item["slot"], item["value"]): item for item in attrs}
        return sorted(unique.values(), key=lambda item: (item["slot"], item["value"]))

    def warbook_profile_id(self) -> int | None:
        if not self.gvg:
            return None
        warbook = self.gvg.get("warBook") or {}
        value = warbook.get("warBookProfileId")
        return value if isinstance(value, int) else None


class DecodedHeroExport(BaseModel):
    summary: str = ""
    counts: dict[str, int] = Field(default_factory=dict)
    field_semantics: dict[str, str] = Field(default_factory=dict)
    known_limitations: list[str] = Field(default_factory=list)
    heroes: list[DecodedHeroRecord]


class ClientNameMapping(BaseModel):
    canonical_name: str = Field(min_length=1)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)

    @field_validator("notes")
    @classmethod
    def _strip_notes(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class ClientDecodedMappings(BaseModel):
    heroes: dict[str, ClientNameMapping] = Field(default_factory=dict)
    skills: dict[str, ClientNameMapping] = Field(default_factory=dict)

    def hero(self, hero_id: int) -> ClientNameMapping | None:
        return self.heroes.get(str(hero_id))

    def skill(self, skill_id: int) -> ClientNameMapping | None:
        return self.skills.get(str(skill_id))


def load_decoded_hero_export(path: Path) -> DecodedHeroExport:
    data = json.loads(path.read_text(encoding="utf-8"))
    return DecodedHeroExport.model_validate(data)


def load_client_decoded_mappings(path: Path) -> ClientDecodedMappings:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ClientDecodedMappings.model_validate(data)


def stage_decoded_heroes(
    export: DecodedHeroExport,
    *,
    source_id: str,
    captured_at: datetime | None = None,
    mappings: ClientDecodedMappings | None = None,
) -> list[StagingEntry]:
    captured_at = captured_at or datetime.now(timezone.utc)
    entries: list[StagingEntry] = []
    for hero in export.heroes:
        if not hero.in_static_master:
            continue
        entries.append(
            _stage_decoded_hero(
                hero,
                export,
                source_id=source_id,
                captured_at=captured_at,
                mappings=mappings or ClientDecodedMappings(),
            )
        )
    return entries


def write_staging_entries(entries: list[StagingEntry], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump([entry.model_dump(mode="json") for entry in entries], allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _stage_decoded_hero(
    hero: DecodedHeroRecord,
    export: DecodedHeroExport,
    *,
    source_id: str,
    captured_at: datetime,
    mappings: ClientDecodedMappings,
) -> StagingEntry:
    skill_slots = hero.sanitized_skill_slots()
    attr_slots = hero.sanitized_attr_slots()
    skill_summaries = [_format_skill_slot(slot, mappings) for slot in skill_slots[:6]]
    faction = FACTION_MAP.get((hero.faction or "").strip(), hero.faction)
    source_ref = f"NSLG_CLIENT_DECODED:{source_id}:heroID={hero.hero_id}"
    hero_mapping = mappings.hero(hero.hero_id)
    topic = hero_mapping.canonical_name if hero_mapping else hero.topic
    aliases = _build_aliases(hero, topic)
    notes = [
        f"client_hero_id={hero.hero_id}",
        f"client_codename={hero.topic}",
    ]
    if hero_mapping:
        notes.append(f"client_name_mapping_confidence={hero_mapping.confidence}")
        notes.extend(f"client_name_mapping_note={note}" for note in hero_mapping.notes)
    if skill_summaries:
        notes.append(f"decoded_skill_slots={'; '.join(skill_summaries)}")
    if attr_slots:
        attr_summary = "; ".join(f"slot{item['slot']}={item['value']}" for item in attr_slots)
        notes.append(f"decoded_attr_slots={attr_summary}")
    warbook_id = hero.warbook_profile_id()
    if warbook_id is not None:
        notes.append(f"decoded_warbook_profile_id={warbook_id}")
    skill_ids = _unique_skill_ids(skill_slots)

    profile = HeroStaticProfile(
        name=topic,
        aliases=aliases,
        faction=faction,
        rarity=None,
        troop_types=[],
        role_tags=["客户端解码候选"],
        signature_skills=[_skill_display_name(skill_id, mappings) for skill_id in skill_ids[:3]],
        notes=notes,
    )
    if hero_mapping:
        identity_fact = f"客户端离线解码样本中，heroID {hero.hero_id} / codename {hero.topic} 映射到 KB 武将 {topic}。"
    else:
        identity_fact = f"客户端离线解码样本中，heroID {hero.hero_id} 对应 codename {hero.topic}。"
    entry = KnowledgeEntry(
        id=f"client-decoded-hero-{hero.hero_id}",
        domain=Domain.HERO,
        entry_kind=EntryKind.HERO_PROFILE,
        topic=topic,
        aliases=aliases,
        facts=[
            identity_fact,
            "该条目来自本地客户端解码证据，仅作为可审阅候选，不应在未映射中文名和未复核前发布为正式攻略知识。",
        ],
        constraints=[
            "已脱敏：未写入账号、服务器、角色唯一标识、兵力、聊天、邮件或本地路径。",
            "技能 ID、兵书字段和属性槽位仍需映射到正式中文名与业务语义。",
            *[f"{key}: {value}" for key, value in export.field_semantics.items()],
        ],
        source_ref=source_ref,
        updated_at=captured_at.date(),
        confidence=min(0.72, hero_mapping.confidence) if hero_mapping else 0.62,
        related_topics=[_skill_display_name(skill_id, mappings) for skill_id in skill_ids[:5]],
        priority=60,
        structured_data=profile,
    )
    metadata = StagingMetadata(
        source_url=SOURCE_URL,
        source_site=SOURCE_SITE,
        source_captured_at=captured_at,
        review_status=ReviewStatus.NORMALIZED,
        review_notes=[
            "auto-staged from decoded NSLG local hero export",
            "review required before publish; map codename/ids to canonical Chinese KB names first",
        ],
    )
    return StagingEntry(metadata=metadata, entry=entry)


def _build_aliases(hero: DecodedHeroRecord, topic: str) -> list[str]:
    aliases = [hero.topic, *hero.variants]
    return [alias for alias in dict.fromkeys(aliases) if alias and alias != topic]


def _format_skill_slot(slot: DecodedSkillSlot, mappings: ClientDecodedMappings) -> str:
    mapped = mappings.skill(slot.skill_id)
    parts = [f"skillId={slot.skill_id}"]
    if mapped:
        parts.append(f"name={mapped.canonical_name}")
    if slot.position is not None:
        parts.append(f"position={slot.position}")
    if slot.order_level is not None:
        parts.append(f"orderLevel={slot.order_level}")
    if slot.level is not None:
        parts.append(f"level={slot.level}")
    return ",".join(parts)


def _unique_skill_ids(skill_slots: list[DecodedSkillSlot]) -> list[int]:
    ids: list[int] = []
    for slot in skill_slots:
        if slot.skill_id not in ids:
            ids.append(slot.skill_id)
    return ids


def _skill_display_name(skill_id: int, mappings: ClientDecodedMappings) -> str:
    mapped = mappings.skill(skill_id)
    return mapped.canonical_name if mapped else str(skill_id)
