from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from qa_agent.ingestion.config import load_alias_config
from qa_agent.knowledge.loader import load_entries
from qa_agent.knowledge.models import EntryKind
from qa_agent.knowledge.source_paths import discover_source_paths

from .models import (
    VideoCombatCandidate,
    VideoHeroCandidate,
    VideoKnowledgeDocument,
    VideoLineupCandidate,
    VideoSegment,
    VideoSkillCandidate,
)

ALLOWED_FRAME_KINDS = {
    "lineup_table",
    "hero_detail",
    "skill_detail",
    "battle_report",
    "land_risk",
    "gameplay_ui",
}
REJECTED_FRAME_KINDS = {"cover_title", "ad", "menu", "unknown", "no_frame"}

_AD_TERMS = ("广告", "赞助", "礼包码", "下载", "福利", "预约")
_COVER_TERMS = ("点赞", "投币", "关注", "三连", "教程", "攻略", "封面", "标题")
_MENU_TERMS = ("寻访", "排行榜", "背包", "邮箱", "活动", "个人奖励", "同盟奖励", "直落席位")
_UI_TERMS = ("部队", "阵容", "编队", "兵力", "体力", "等级", "战法", "已激活")
_LAND_TERMS = ("守军", "土地", "级地", "地块", "战损", "兵力")
_BATTLE_TERMS = ("战报", "胜利", "失败", "平局", "回合", "杀敌", "战损")
_HERO_DETAIL_TERMS = ("属性", "武力", "智力", "统率", "先攻", "兵种", "体力", "等级")
_SKILL_DETAIL_TERMS = ("战法", "发动", "概率", "伤害", "治疗", "控制", "追击")


@dataclass(frozen=True)
class EvidenceQualityContext:
    hero_names: frozenset[str]
    skill_names: frozenset[str]
    hero_aliases: dict[str, str]
    skill_aliases: dict[str, str]

    def canonical_hero(self, value: str) -> str | None:
        return _canonicalize(value, self.hero_names, self.hero_aliases)

    def canonical_skill(self, value: str) -> str | None:
        return _canonicalize(value, self.skill_names, self.skill_aliases)

    def heroes_in_text(self, text: str) -> set[str]:
        return _terms_in_text(text, self.hero_names, self.hero_aliases)

    def skills_in_text(self, text: str) -> set[str]:
        return _terms_in_text(text, self.skill_names, self.skill_aliases)


def load_evidence_quality_context(package_root: Path) -> EvidenceQualityContext:
    source_paths = discover_source_paths(package_root / "knowledge_sources")
    entries = load_entries(source_paths)
    hero_names = {
        entry.structured_data.name
        for entry in entries
        if entry.entry_kind == EntryKind.HERO_PROFILE and entry.structured_data is not None
    }
    skill_names = {
        entry.structured_data.name
        for entry in entries
        if entry.entry_kind == EntryKind.SKILL_PROFILE and entry.structured_data is not None
    }
    hero_aliases = _load_aliases(package_root / "configs" / "hero_aliases.yaml", hero_names)
    skill_aliases = _load_aliases(package_root / "configs" / "skill_aliases.yaml", skill_names)
    for entry in entries:
        if entry.entry_kind == EntryKind.HERO_PROFILE and entry.structured_data is not None:
            _extend_aliases(hero_aliases, entry.structured_data.name, set(entry.searchable_terms()))
        elif entry.entry_kind == EntryKind.SKILL_PROFILE and entry.structured_data is not None:
            _extend_aliases(skill_aliases, entry.structured_data.name, set(entry.searchable_terms()))
    return EvidenceQualityContext(
        hero_names=frozenset(hero_names),
        skill_names=frozenset(skill_names),
        hero_aliases=hero_aliases,
        skill_aliases=skill_aliases,
    )


def classify_vision_frame_kind(
    *,
    hero_count: int,
    skill_count: int,
    text_snippets: list[str],
) -> str:
    text = " ".join(text_snippets)
    if any(term in text for term in _AD_TERMS):
        return "ad"
    if hero_count >= 2 and any(term in text for term in _UI_TERMS):
        return "lineup_table"
    if skill_count and any(term in text for term in _SKILL_DETAIL_TERMS):
        return "skill_detail"
    if hero_count and any(term in text for term in _HERO_DETAIL_TERMS):
        return "hero_detail"
    if any(term in text for term in _BATTLE_TERMS):
        return "battle_report"
    if any(term in text for term in _LAND_TERMS):
        return "land_risk"
    if (hero_count or skill_count) and any(term in text for term in _UI_TERMS):
        return "gameplay_ui"
    if any(term in text for term in _MENU_TERMS) and not hero_count and not skill_count:
        return "menu"
    if any(term in text for term in _COVER_TERMS) and not hero_count and not skill_count:
        return "cover_title"
    return "unknown"


def classify_segment_frame_kind(segment: VideoSegment, context: EvidenceQualityContext) -> str:
    if not segment.frame_refs:
        return "no_frame"
    explicit = _explicit_frame_kind(segment)
    if explicit:
        return explicit
    visual_heroes = _vision_entities(segment, "hero", context)
    visual_skills = _vision_entities(segment, "skill", context)
    text = _segment_visual_text(segment)
    return classify_vision_frame_kind(
        hero_count=len(visual_heroes),
        skill_count=len(visual_skills),
        text_snippets=[text],
    )


def filter_document_for_evidence_quality(
    document: VideoKnowledgeDocument,
    context: EvidenceQualityContext,
    *,
    require_vision: bool = True,
) -> tuple[VideoKnowledgeDocument, dict[str, object]]:
    segment_by_id = {segment.segment_id: segment for segment in document.segments}
    allowed_segments: set[str] = set()
    rejected_segment_kinds: Counter[str] = Counter()
    for segment in document.segments:
        kind = classify_segment_frame_kind(segment, context)
        if kind in ALLOWED_FRAME_KINDS and (not require_vision or _segment_has_vision_signal(segment)):
            allowed_segments.add(segment.segment_id)
        else:
            rejected_segment_kinds[kind] += 1

    lineups: list[VideoLineupCandidate] = []
    heroes: list[VideoHeroCandidate] = []
    skills: list[VideoSkillCandidate] = []
    combats: list[VideoCombatCandidate] = []
    reject_reasons: Counter[str] = Counter()

    for candidate in document.lineup_candidates:
        segment = segment_by_id.get(candidate.segment_id)
        if segment is None or candidate.segment_id not in allowed_segments:
            reject_reasons["lineup_segment_not_allowed"] += 1
            continue
        canonical_heroes = _dedupe(
            hero for name in candidate.hero_names if (hero := context.canonical_hero(name))
        )
        if len(canonical_heroes) < 2:
            reject_reasons["lineup_missing_two_canonical_heroes"] += 1
            continue
        candidate_heroes = set(canonical_heroes)
        visual_heroes = candidate_heroes & _vision_entities(segment, "hero", context)
        if require_vision and len(visual_heroes) < min(2, len(candidate_heroes)):
            reject_reasons["lineup_missing_visual_hero_support"] += 1
            continue
        if not (candidate_heroes & context.heroes_in_text(segment.transcript)):
            reject_reasons["lineup_missing_subtitle_hero_support"] += 1
            continue
        canonical_skills = _dedupe(
            skill for name in candidate.core_skills if (skill := context.canonical_skill(name))
        )
        facts = _rewrite_lineup_facts(candidate.facts, canonical_heroes, canonical_skills)
        lineups.append(
            candidate.model_copy(
                update={
                    "hero_names": canonical_heroes[:3],
                    "core_skills": canonical_skills[:3],
                    "facts": facts,
                }
            )
        )

    for candidate in document.hero_candidates:
        segment = segment_by_id.get(candidate.segment_id)
        hero = context.canonical_hero(candidate.hero_name)
        if segment is None or candidate.segment_id not in allowed_segments or hero is None:
            reject_reasons["hero_not_canonical_or_segment_not_allowed"] += 1
            continue
        if require_vision and hero not in _vision_entities(segment, "hero", context):
            reject_reasons["hero_missing_visual_support"] += 1
            continue
        if hero not in context.heroes_in_text(segment.transcript):
            reject_reasons["hero_missing_subtitle_support"] += 1
            continue
        heroes.append(candidate.model_copy(update={"hero_name": hero}))

    for candidate in document.skill_candidates:
        segment = segment_by_id.get(candidate.segment_id)
        skill = context.canonical_skill(candidate.skill_name)
        if segment is None or candidate.segment_id not in allowed_segments or skill is None:
            reject_reasons["skill_not_canonical_or_segment_not_allowed"] += 1
            continue
        if require_vision and skill not in _vision_entities(segment, "skill", context):
            reject_reasons["skill_missing_visual_support"] += 1
            continue
        skills.append(candidate.model_copy(update={"skill_name": skill}))

    for candidate in document.combat_candidates:
        segment = segment_by_id.get(candidate.segment_id)
        if segment is None or candidate.segment_id not in allowed_segments:
            reject_reasons["combat_segment_not_allowed"] += 1
            continue
        if not any(term in segment.transcript for term in (*_LAND_TERMS, *_BATTLE_TERMS)):
            reject_reasons["combat_missing_subtitle_support"] += 1
            continue
        combats.append(candidate)

    filtered = document.model_copy(
        update={
            "lineup_candidates": lineups,
            "hero_candidates": heroes,
            "skill_candidates": skills,
            "combat_candidates": combats,
        }
    )
    stats = {
        "segments": len(document.segments),
        "allowed_segments": len(allowed_segments),
        "rejected_segment_kinds": dict(sorted(rejected_segment_kinds.items())),
        "before": {
            "lineup": len(document.lineup_candidates),
            "hero": len(document.hero_candidates),
            "skill": len(document.skill_candidates),
            "combat": len(document.combat_candidates),
        },
        "after": {
            "lineup": len(lineups),
            "hero": len(heroes),
            "skill": len(skills),
            "combat": len(combats),
        },
        "reject_reasons": dict(sorted(reject_reasons.items())),
    }
    return filtered, stats


def _load_aliases(path: Path, canonical_names: set[str]) -> dict[str, str]:
    aliases: dict[str, str] = {name: name for name in canonical_names}
    if not path.exists():
        return aliases
    config = load_alias_config(path)
    for raw, canonical in config.canonical_map.items():
        if canonical in canonical_names:
            aliases[raw] = canonical
    for canonical, values in config.aliases.items():
        if canonical not in canonical_names:
            continue
        aliases[canonical] = canonical
        for value in values:
            aliases[value] = canonical
    return aliases


def _extend_aliases(aliases: dict[str, str], canonical: str, values: set[str]) -> None:
    for value in values:
        if value:
            aliases.setdefault(value, canonical)


def _canonicalize(value: str, canonical_names: frozenset[str], aliases: dict[str, str]) -> str | None:
    text = value.strip()
    if not text:
        return None
    if text.startswith("vision:hero:") or text.startswith("vision:skill:"):
        text = text.split(":", 2)[2]
    if text in canonical_names:
        return text
    return aliases.get(text)


def _terms_in_text(text: str, canonical_names: frozenset[str], aliases: dict[str, str]) -> set[str]:
    hits: set[str] = set()
    for alias, canonical in aliases.items():
        if alias and alias in text and canonical in canonical_names:
            hits.add(canonical)
    return hits


def _segment_has_vision_signal(segment: VideoSegment) -> bool:
    if "[视觉补充]" in segment.visual_summary:
        return True
    if any(line.startswith("vision:") for line in segment.ocr_lines):
        return True
    return bool(segment.ocr_lines)


def _explicit_frame_kind(segment: VideoSegment) -> str | None:
    for line in segment.ocr_lines:
        if line.startswith("vision:frame_kind:"):
            return line.rsplit(":", 1)[-1].strip()
    return None


def _vision_entities(segment: VideoSegment, entity_type: str, context: EvidenceQualityContext) -> set[str]:
    prefix = f"vision:{entity_type}:"
    hits: set[str] = set()
    canonicalize = context.canonical_hero if entity_type == "hero" else context.canonical_skill
    for line in segment.ocr_lines:
        if not line.startswith(prefix):
            continue
        canonical = canonicalize(line[len(prefix) :])
        if canonical:
            hits.add(canonical)
    return hits


def _segment_visual_text(segment: VideoSegment) -> str:
    return " ".join([segment.visual_summary, *segment.ocr_lines])


def _dedupe(values: object) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _rewrite_lineup_facts(facts: list[str], hero_names: list[str], core_skills: list[str]) -> list[str]:
    rewritten: list[str] = []
    for fact in facts:
        if fact.startswith("核心武将包括"):
            continue
        if fact.startswith("高频提及战法包括"):
            continue
        rewritten.append(fact)
    rewritten.append(f"核心武将包括{'、'.join(hero_names[:3])}。")
    if core_skills:
        rewritten.append(f"高频提及战法包括{'、'.join(core_skills[:3])}。")
    return rewritten[:3]
