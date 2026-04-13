from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from qa_agent.ingestion.config import AliasConfig, load_alias_config
from qa_agent.knowledge.loader import load_entries
from qa_agent.knowledge.source_paths import discover_source_paths

from .models import (
    VideoCombatCandidate,
    VideoHeroCandidate,
    VideoKnowledgeDocument,
    VideoLineupCandidate,
    VideoSkillCandidate,
)

_SCENARIO_KEYWORDS = ("开荒", "打地", "对冲", "转型", "攻城", "驻守", "拆迁")
_ENTITY_STOPWORDS = {"开荒", "打地", "阵容", "搭配", "对冲", "前期", "后期", "实战", "回放"}
_SKILL_STOPWORDS = {"技能", "战法", "控制技能", "主动技能"}
_LINEUP_CUE_PATTERNS = ("最好用的阵容就是这一套", "阵容就是这一套", "这一套阵容")


def _slugify(value: str) -> str:
    lowered = value.lower().strip()
    return "-".join(part for part in lowered.replace("/", " ").replace("_", " ").split() if part)


def _build_reverse_alias_map(config: AliasConfig) -> dict[str, str]:
    reverse = dict(config.canonical_map)
    for canonical, aliases in config.aliases.items():
        reverse[canonical] = canonical
        for alias in aliases:
            reverse[alias] = canonical
    return reverse


def _extract_constraints(text: str) -> list[str]:
    parts = re.split(r"[。！？!?\n]+", text)
    constraints = []
    for part in parts:
        sentence = part.strip()
        if not sentence:
            continue
        if any(flag in sentence for flag in ("不适合", "不建议", "不能", "较怕", "惧怕")):
            constraints.append(sentence if sentence.endswith("。") else f"{sentence}。")
    return constraints[:2]


def _scan_entities(text: str, lookup: dict[str, str]) -> list[str]:
    hits: list[str] = []
    for alias, canonical in lookup.items():
        if alias and alias in text and canonical not in hits:
            hits.append(canonical)
    return hits


def _extract_excluded_hero_terms(text: str) -> set[str]:
    excluded: set[str] = set()
    for match in re.finditer(r"解锁了(.{1,4})的经书", text):
        excluded.add(match.group(1))
    return excluded


@dataclass
class HeuristicVideoKnowledgeExtractor:
    hero_aliases: AliasConfig
    skill_aliases: AliasConfig
    hero_terms: list[str]
    skill_terms: list[str]

    @classmethod
    def from_project_root(cls, project_root: Path) -> "HeuristicVideoKnowledgeExtractor":
        source_paths = discover_source_paths(project_root / "knowledge_sources")
        entries = load_entries(source_paths)
        hero_terms = sorted(
            {
                term
                for entry in entries
                if entry.domain.value == "hero"
                for term in entry.searchable_terms()
                if len(term) >= 2
            },
            key=len,
            reverse=True,
        )
        skill_terms = sorted(
            {
                term
                for entry in entries
                if entry.domain.value == "skill"
                for term in entry.searchable_terms()
                if len(term) >= 2
            },
            key=len,
            reverse=True,
        )
        return cls(
            hero_aliases=load_alias_config(project_root / "configs" / "hero_aliases.yaml"),
            skill_aliases=load_alias_config(project_root / "configs" / "skill_aliases.yaml"),
            hero_terms=hero_terms,
            skill_terms=skill_terms,
        )

    def extract_lineup_candidates(self, document: VideoKnowledgeDocument) -> list[VideoLineupCandidate]:
        hero_lookup = _build_reverse_alias_map(self.hero_aliases)
        skill_lookup = _build_reverse_alias_map(self.skill_aliases)
        season_tags = re.findall(r"S\d+", document.source.title, flags=re.IGNORECASE)

        candidates: list[VideoLineupCandidate] = []
        for segment in document.segments:
            merged_text = " ".join(
                [document.source.title, segment.transcript, segment.visual_summary, *segment.ocr_lines]
            )
            scenario_tags = [tag for tag in _SCENARIO_KEYWORDS if tag in merged_text]

            hero_names: list[str] = []
            core_skills: list[str] = []
            excluded_heroes = _extract_excluded_hero_terms(merged_text)

            for token in segment.ocr_lines:
                canonical_hero = hero_lookup.get(token)
                if canonical_hero and canonical_hero not in hero_names:
                    hero_names.append(canonical_hero)
                    continue
                canonical_skill = skill_lookup.get(token)
                if canonical_skill and canonical_skill not in core_skills:
                    core_skills.append(canonical_skill)
                    continue
                if 2 <= len(token) <= 4 and token not in _ENTITY_STOPWORDS:
                    if len(hero_names) < 3 and token not in hero_names:
                        hero_names.append(token)
                    elif token not in core_skills:
                        core_skills.append(token)

            for canonical in _scan_entities(merged_text, hero_lookup):
                if canonical not in hero_names and canonical not in excluded_heroes:
                    hero_names.append(canonical)
            for canonical in _scan_entities(merged_text, skill_lookup):
                if canonical not in core_skills and canonical not in _SKILL_STOPWORDS:
                    core_skills.append(canonical)
            for term in self.hero_terms:
                if term in merged_text and term not in hero_names and term not in excluded_heroes:
                    hero_names.append(term)
            for term in self.skill_terms:
                if term in merged_text and term not in core_skills and term not in _SKILL_STOPWORDS:
                    core_skills.append(term)

            preferred_lineup = self._extract_preferred_lineup_heroes(merged_text)
            if preferred_lineup:
                hero_names = preferred_lineup + [name for name in hero_names if name not in preferred_lineup]

            if len(hero_names) < 2:
                continue

            topic_prefix = season_tags[0].upper() if season_tags else ""
            topic_suffix = "开荒队" if "开荒" in scenario_tags else "阵容"
            topic = f"{topic_prefix}{hero_names[0]}{topic_suffix}" if hero_names else f"{topic_prefix}视频阵容"

            facts = []
            if scenario_tags:
                facts.append(f"该阵容主要用于{'、'.join(dict.fromkeys(scenario_tags))}。")
            if hero_names:
                facts.append(f"核心武将包括{'、'.join(hero_names[:3])}。")
            if core_skills:
                facts.append(f"高频提及战法包括{'、'.join(core_skills[:3])}。")
            if not facts:
                facts.append("该片段展示了一套可识别的阵容搭配。")

            constraints = _extract_constraints(segment.transcript)
            candidates.append(
                VideoLineupCandidate(
                    candidate_id=_slugify(topic),
                    segment_id=segment.segment_id,
                    topic=topic,
                    season_tags=season_tags[:1],
                    hero_names=hero_names[:3],
                    core_skills=core_skills[:3],
                    scenario_tags=scenario_tags[:3],
                    facts=facts[:3],
                    constraints=constraints,
                    confidence=0.58 if constraints else 0.62,
                )
            )
        if not candidates:
            fallback = self._build_generic_candidate(document, season_tags[:1])
            if fallback is not None:
                candidates.append(fallback)
        return candidates

    def extract_hero_candidates(self, document: VideoKnowledgeDocument) -> list[VideoHeroCandidate]:
        candidates: list[VideoHeroCandidate] = []
        seen: set[tuple[str, str]] = set()
        for segment in document.segments:
            segment_text = " ".join([segment.transcript, segment.visual_summary, *segment.ocr_lines])
            excluded_heroes = _extract_excluded_hero_terms(segment_text)
            hero_names = [name for name in self._extract_hero_names(segment_text) if name not in excluded_heroes]
            if not hero_names:
                continue
            lineup_context = [term for term in self.hero_terms if term in segment_text and term in hero_names]
            for hero_name in hero_names[:4]:
                key = (segment.segment_id, hero_name)
                if key in seen:
                    continue
                seen.add(key)
                facts = [f"视频片段将{hero_name}列为当前阶段的重要武将。"]
                if len(lineup_context) >= 2:
                    partners = [name for name in lineup_context if name != hero_name][:2]
                    if partners:
                        facts.append(f"{hero_name}在片段中与{'、'.join(partners)}一起被讨论。")
                candidates.append(
                    VideoHeroCandidate(
                        candidate_id=_slugify(f"{segment.segment_id}-{hero_name}"),
                        segment_id=segment.segment_id,
                        hero_name=hero_name,
                        facts=facts,
                        related_topics=lineup_context[:3],
                        confidence=0.55,
                    )
                )
        return candidates

    def extract_skill_candidates(self, document: VideoKnowledgeDocument) -> list[VideoSkillCandidate]:
        candidates: list[VideoSkillCandidate] = []
        seen: set[tuple[str, str]] = set()
        for segment in document.segments:
            segment_text = " ".join([segment.transcript, segment.visual_summary, *segment.ocr_lines])
            skill_names = self._extract_skill_names(segment_text)
            if not skill_names:
                continue
            for skill_name in skill_names[:5]:
                key = (segment.segment_id, skill_name)
                if key in seen:
                    continue
                seen.add(key)
                facts = [f"视频片段提到{skill_name}是当前讨论阵容中的关键战法。"]
                candidates.append(
                    VideoSkillCandidate(
                        candidate_id=_slugify(f"{segment.segment_id}-{skill_name}"),
                        segment_id=segment.segment_id,
                        skill_name=skill_name,
                        facts=facts,
                        related_topics=self._extract_hero_names(segment_text)[:3],
                        confidence=0.55,
                    )
                )
        return candidates

    def extract_combat_candidates(self, document: VideoKnowledgeDocument) -> list[VideoCombatCandidate]:
        candidates: list[VideoCombatCandidate] = []
        for segment in document.segments:
            text = segment.transcript
            facts: list[str] = []
            topic = None
            if "守军" in text and any(level in text for level in ("五级地", "六级地", "七级地", "八级地", "九级地")):
                topic = "土地守军建议"
                facts.append("视频片段按土地等级讨论守军难度和选择。")
            if "难度表" in text:
                topic = topic or "土地守军难度"
                facts.append("视频片段提到土地守军难度表。")
            if "推荐" in text and "阵容" in text and "守军" in text:
                facts.append("视频片段说明不同守军对应不同推荐阵容。")
            if topic and facts:
                candidates.append(
                    VideoCombatCandidate(
                        candidate_id=_slugify(f"{segment.segment_id}-{topic}"),
                        segment_id=segment.segment_id,
                        topic=topic,
                        facts=facts[:3],
                        confidence=0.58,
                    )
                )
            if "苦肉弓" in text and "35级" in text and "黄忠" in text and "经书" in text:
                candidates.append(
                    VideoCombatCandidate(
                        candidate_id=_slugify(f"{segment.segment_id}-苦肉弓转型条件"),
                        segment_id=segment.segment_id,
                        topic="苦肉弓转型条件",
                        facts=[
                            "视频片段说明苦肉弓属于35级后的转型选择。",
                            "视频片段把黄忠经书作为35级后转型条件的一部分。",
                        ],
                        constraints=["该片段同时说明35级前更推荐先用孙权、小乔、周瑜开荒。"],
                        related_topics=["苦肉弓", "黄忠", "孙权", "小乔", "周瑜"],
                        confidence=0.62,
                    )
                )
        return candidates

    def enrich_document(self, document: VideoKnowledgeDocument) -> VideoKnowledgeDocument:
        return document.model_copy(
            update={
                "lineup_candidates": self.extract_lineup_candidates(document),
                "hero_candidates": self.extract_hero_candidates(document),
                "skill_candidates": self.extract_skill_candidates(document),
                "combat_candidates": self.extract_combat_candidates(document),
            }
        )

    def _extract_hero_names(self, text: str) -> list[str]:
        names: list[str] = []
        hero_lookup = _build_reverse_alias_map(self.hero_aliases)
        for canonical in _scan_entities(text, hero_lookup):
            if canonical not in names:
                names.append(canonical)
        for term in self.hero_terms:
            if term in text and term not in names:
                names.append(term)
        return names

    def _extract_skill_names(self, text: str) -> list[str]:
        names: list[str] = []
        skill_lookup = _build_reverse_alias_map(self.skill_aliases)
        for canonical in _scan_entities(text, skill_lookup):
            if canonical not in names and canonical not in _SKILL_STOPWORDS:
                names.append(canonical)
        for term in self.skill_terms:
            if term in text and term not in names and term not in _SKILL_STOPWORDS:
                names.append(term)
        return names

    def _build_generic_candidate(
        self,
        document: VideoKnowledgeDocument,
        season_tags: list[str],
    ) -> VideoLineupCandidate | None:
        merged_text = " ".join(
            [document.source.title, document.source.description or "", *[segment.transcript for segment in document.segments]]
        )
        scenario_tags = [tag for tag in _SCENARIO_KEYWORDS if tag in merged_text]
        if not any(flag in merged_text for flag in ("攻略", "开荒", "阵容", "搭配")):
            return None
        topic = f"{season_tags[0].upper()}开荒攻略" if season_tags else document.source.title[:18]
        facts = [f"该视频主题聚焦于{document.source.title}。"]
        if document.source.description:
            facts.append(document.source.description[:80] + ("。" if not document.source.description.endswith("。") else ""))
        subtitle_catalog = document.source.subtitle_catalog or []
        if subtitle_catalog and len(facts) < 3:
            langs = [item.get("lan_doc") or item.get("lan") for item in subtitle_catalog if item.get("lan_doc") or item.get("lan")]
            if langs:
                facts.append(f"登录态已确认字幕目录可见：{'、'.join(langs[:4])}。")
        if scenario_tags:
            if len(facts) < 3:
                facts.append(f"可确认场景标签：{'、'.join(dict.fromkeys(scenario_tags))}。")
        return VideoLineupCandidate(
            candidate_id=_slugify(f"{document.source.video_id}-{topic}"),
            segment_id=document.segments[0].segment_id,
            topic=topic,
            season_tags=season_tags[:1],
            scenario_tags=scenario_tags[:3],
            facts=facts[:3],
            constraints=["当前候选仅基于视频标题/描述等弱证据生成，需后续用字幕或画面证据复核。"],
            confidence=0.34 if subtitle_catalog else 0.28,
        )

    def _extract_preferred_lineup_heroes(self, text: str) -> list[str]:
        cue_index = -1
        for cue in _LINEUP_CUE_PATTERNS:
            idx = text.find(cue)
            if idx != -1:
                cue_index = idx
                break
        if cue_index == -1:
            return []
        hero_hits: list[tuple[int, str]] = []
        for term in self.hero_terms:
            idx = text.find(term, cue_index)
            if idx != -1:
                hero_hits.append((idx, term))
        hero_hits.sort()
        result: list[str] = []
        for _idx, term in hero_hits:
            if term not in result:
                result.append(term)
            if len(result) >= 3:
                break
        return result
