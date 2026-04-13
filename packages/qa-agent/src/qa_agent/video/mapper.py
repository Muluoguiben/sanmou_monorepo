from __future__ import annotations

from datetime import date
from pathlib import Path

from qa_agent.ingestion.models import ReviewStatus, StagingEntry, StagingMetadata
from qa_agent.knowledge.loader import load_entries
from qa_agent.knowledge.models import (
    Domain,
    EntryKind,
    HeroStaticProfile,
    KnowledgeEntry,
    LineupSolutionProfile,
    SkillStaticProfile,
)
from qa_agent.knowledge.source_paths import discover_source_paths

from .models import (
    VideoCombatCandidate,
    VideoHeroCandidate,
    VideoKnowledgeDocument,
    VideoLineupCandidate,
    VideoSegment,
    VideoSkillCandidate,
)


def _build_source_ref(video_id: str, segment: VideoSegment) -> str:
    return f"BILIBILI:{video_id}#{int(segment.start_sec)}-{int(segment.end_sec)}"


def _find_segment(document: VideoKnowledgeDocument, segment_id: str) -> VideoSegment:
    for segment in document.segments:
        if segment.segment_id == segment_id:
            return segment
    raise ValueError(f"unknown segment_id: {segment_id}")


def _load_profile_maps(project_root: Path) -> tuple[dict[str, HeroStaticProfile], dict[str, SkillStaticProfile]]:
    source_paths = discover_source_paths(project_root / "knowledge_sources")
    entries = load_entries(source_paths)
    hero_map: dict[str, HeroStaticProfile] = {}
    skill_map: dict[str, SkillStaticProfile] = {}
    for entry in entries:
        if entry.entry_kind == EntryKind.HERO_PROFILE and isinstance(entry.structured_data, HeroStaticProfile):
            hero_map[entry.topic] = entry.structured_data
        elif entry.entry_kind == EntryKind.SKILL_PROFILE and isinstance(entry.structured_data, SkillStaticProfile):
            skill_map[entry.topic] = entry.structured_data
    return hero_map, skill_map


def _stage_metadata(document: VideoKnowledgeDocument, segment: VideoSegment) -> StagingMetadata:
    source = document.source
    return StagingMetadata(
        source_url=source.source_url,
        source_site="bilibili",
        source_captured_at=source.captured_at,
        review_status=ReviewStatus.NORMALIZED,
        review_notes=[
            f"auto-normalized from bilibili video {source.video_id}",
            f"segment={segment.segment_id}",
        ],
    )


def stage_lineup_candidate(document: VideoKnowledgeDocument, candidate: VideoLineupCandidate) -> StagingEntry:
    segment = _find_segment(document, candidate.segment_id)
    source = document.source
    evidence_summary = segment.visual_summary or segment.transcript or "视频片段待补充摘要。"
    profile = LineupSolutionProfile(
        name=candidate.topic,
        aliases=candidate.aliases,
        season_tags=candidate.season_tags,
        lineup_rating=candidate.lineup_rating,
        factions=candidate.factions,
        hero_names=candidate.hero_names,
        core_skills=candidate.core_skills,
        scenario_tags=candidate.scenario_tags,
        notes=[*candidate.notes, f"证据片段：{int(segment.start_sec)}s-{int(segment.end_sec)}s"],
    )
    entry = KnowledgeEntry(
        id=f"video-lineup-{source.video_id.lower()}-{candidate.candidate_id.lower()}",
        domain=Domain.SOLUTION,
        entry_kind=EntryKind.LINEUP_SOLUTION,
        topic=candidate.topic,
        aliases=candidate.aliases,
        facts=[*candidate.facts, f"视频证据摘要：{evidence_summary}"],
        constraints=candidate.constraints,
        source_ref=_build_source_ref(source.video_id, segment),
        updated_at=date.today(),
        confidence=candidate.confidence,
        related_topics=[*candidate.hero_names[:3], *candidate.core_skills[:3]],
        priority=70,
        structured_data=profile,
    )
    return StagingEntry(metadata=_stage_metadata(document, segment), entry=entry)


def stage_hero_candidate(
    document: VideoKnowledgeDocument,
    candidate: VideoHeroCandidate,
    hero_profiles: dict[str, HeroStaticProfile],
) -> StagingEntry:
    segment = _find_segment(document, candidate.segment_id)
    profile = hero_profiles.get(candidate.hero_name) or HeroStaticProfile(name=candidate.hero_name)
    entry = KnowledgeEntry(
        id=f"video-hero-{document.source.video_id.lower()}-{candidate.candidate_id.lower()}",
        domain=Domain.HERO,
        entry_kind=EntryKind.HERO_PROFILE,
        topic=candidate.hero_name,
        aliases=profile.aliases,
        facts=[*candidate.facts, f"视频证据摘要：{segment.transcript[:120]}"],
        constraints=candidate.constraints,
        source_ref=_build_source_ref(document.source.video_id, segment),
        updated_at=date.today(),
        confidence=candidate.confidence,
        related_topics=candidate.related_topics,
        priority=64,
        structured_data=profile,
    )
    return StagingEntry(metadata=_stage_metadata(document, segment), entry=entry)


def stage_skill_candidate(
    document: VideoKnowledgeDocument,
    candidate: VideoSkillCandidate,
    skill_profiles: dict[str, SkillStaticProfile],
) -> StagingEntry:
    segment = _find_segment(document, candidate.segment_id)
    profile = skill_profiles.get(candidate.skill_name) or SkillStaticProfile(name=candidate.skill_name)
    entry = KnowledgeEntry(
        id=f"video-skill-{document.source.video_id.lower()}-{candidate.candidate_id.lower()}",
        domain=Domain.SKILL,
        entry_kind=EntryKind.SKILL_PROFILE,
        topic=candidate.skill_name,
        aliases=profile.aliases,
        facts=[*candidate.facts, f"视频证据摘要：{segment.transcript[:120]}"],
        constraints=candidate.constraints,
        source_ref=_build_source_ref(document.source.video_id, segment),
        updated_at=date.today(),
        confidence=candidate.confidence,
        related_topics=candidate.related_topics,
        priority=64,
        structured_data=profile,
    )
    return StagingEntry(metadata=_stage_metadata(document, segment), entry=entry)


def build_combat_entry(document: VideoKnowledgeDocument, candidate: VideoCombatCandidate) -> KnowledgeEntry:
    segment = _find_segment(document, candidate.segment_id)
    return KnowledgeEntry(
        id=f"video-combat-{document.source.video_id.lower()}-{candidate.candidate_id.lower()}",
        domain=Domain.COMBAT,
        entry_kind=EntryKind.GENERIC_RULE,
        topic=candidate.topic,
        aliases=[],
        facts=[*candidate.facts, f"视频证据摘要：{segment.transcript[:120]}"],
        constraints=candidate.constraints,
        source_ref=_build_source_ref(document.source.video_id, segment),
        updated_at=date.today(),
        confidence=candidate.confidence,
        related_topics=candidate.related_topics,
        priority=60,
        structured_data=None,
    )


def stage_all_video_entries(
    document: VideoKnowledgeDocument,
    project_root: Path,
) -> tuple[list[StagingEntry], list[KnowledgeEntry]]:
    hero_profiles, skill_profiles = _load_profile_maps(project_root)
    staged_entries: list[StagingEntry] = []
    direct_entries: list[KnowledgeEntry] = []

    staged_entries.extend(stage_lineup_candidate(document, candidate) for candidate in document.lineup_candidates)
    staged_entries.extend(
        stage_hero_candidate(document, candidate, hero_profiles) for candidate in document.hero_candidates
    )
    staged_entries.extend(
        stage_skill_candidate(document, candidate, skill_profiles) for candidate in document.skill_candidates
    )
    direct_entries.extend(build_combat_entry(document, candidate) for candidate in document.combat_candidates)
    return staged_entries, direct_entries
