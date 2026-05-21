from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from qa_agent.ingestion.client_decoded import (
    ClientDecodedMappings,
    DecodedHeroExport,
    SOURCE_SITE,
    SOURCE_URL,
    stage_decoded_heroes,
)
from qa_agent.ingestion.models import ReviewStatus
from qa_agent.knowledge.loader import load_entries
from qa_agent.knowledge.models import Domain, HeroStaticProfile, KnowledgeEntry


SENSITIVE_LITERAL_MARKERS = [
    "LocalPersistentData",
    "ChatData",
    "currentRoster",
    "uniqueId",
    "heroTroop",
    "serverId",
    "server_id",
]

SENSITIVE_REGEX_MARKERS = {
    "windows_absolute_path": re.compile(r"[A-Za-z]:[\\/][^\s\"']+"),
    "wsl_mount_path": re.compile(r"/mnt/[a-z]/[^\s\"']+"),
}


class ClientDecodedAuditReport(BaseModel):
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    export_summary: str
    export_counts: dict[str, int] = Field(default_factory=dict)
    field_semantics: dict[str, str] = Field(default_factory=dict)
    known_limitations: list[str] = Field(default_factory=list)
    staging: dict[str, Any] = Field(default_factory=dict)
    hero_coverage: dict[str, Any] = Field(default_factory=dict)
    skill_coverage: dict[str, Any] = Field(default_factory=dict)
    knowledge_validation: dict[str, Any] = Field(default_factory=dict)
    security_scan: dict[str, Any] = Field(default_factory=dict)
    review_blockers: list[str] = Field(default_factory=list)
    next_review_actions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)


def load_knowledge_entries_from_dir(path: Path) -> list[KnowledgeEntry]:
    if not path.exists():
        return []
    return load_entries(sorted(path.rglob("*.yaml")))


def build_client_decoded_audit_report(
    export: DecodedHeroExport,
    *,
    source_id: str,
    mappings: ClientDecodedMappings | None = None,
    knowledge_entries: list[KnowledgeEntry] | None = None,
    generated_at: datetime | None = None,
) -> ClientDecodedAuditReport:
    mappings = mappings or ClientDecodedMappings()
    generated_at = generated_at or datetime.now(timezone.utc)
    staged_entries = stage_decoded_heroes(
        export,
        source_id=source_id,
        captured_at=generated_at,
        mappings=mappings,
    )
    static_heroes = [hero for hero in export.heroes if hero.in_static_master]
    skill_ids = _unique_skill_ids(static_heroes)

    hero_coverage = _build_hero_coverage(static_heroes, mappings)
    skill_coverage = _build_skill_coverage(skill_ids, mappings)
    knowledge_validation = _build_knowledge_validation(
        hero_coverage,
        skill_coverage,
        knowledge_entries or [],
    )
    security_scan = _scan_staged_entries_for_sensitive_markers(staged_entries)
    review_blockers = _build_review_blockers(hero_coverage, skill_coverage, knowledge_validation, security_scan)

    return ClientDecodedAuditReport(
        source_id=source_id,
        generated_at=generated_at,
        export_summary=export.summary,
        export_counts=export.counts,
        field_semantics=export.field_semantics,
        known_limitations=export.known_limitations,
        staging={
            "candidate_entries": len(staged_entries),
            "review_status": ReviewStatus.NORMALIZED.value,
            "publish_default": "blocked_until_reviewed",
            "skipped_non_static_records": len(export.heroes) - len(static_heroes),
        },
        hero_coverage=hero_coverage,
        skill_coverage=skill_coverage,
        knowledge_validation=knowledge_validation,
        security_scan=security_scan,
        review_blockers=review_blockers,
        next_review_actions=_build_next_review_actions(hero_coverage, skill_coverage, knowledge_validation),
        evidence_refs=[entry.entry.source_ref for entry in staged_entries],
    )


def write_client_decoded_audit_report(report: ClientDecodedAuditReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _build_hero_coverage(static_heroes: list[Any], mappings: ClientDecodedMappings) -> dict[str, Any]:
    mapped = []
    unmapped = []
    low_confidence = []
    for hero in static_heroes:
        mapping = mappings.hero(hero.hero_id)
        item = {"hero_id": hero.hero_id, "codename": hero.topic}
        if mapping:
            mapped.append({**item, "canonical_name": mapping.canonical_name, "confidence": mapping.confidence})
            if mapping.confidence < 0.8:
                low_confidence.append({**item, "canonical_name": mapping.canonical_name, "confidence": mapping.confidence})
        else:
            unmapped.append(item)
    return {
        "total_static_heroes": len(static_heroes),
        "mapped_heroes": len(mapped),
        "mapped_hero_items": mapped,
        "unmapped_heroes": unmapped,
        "low_confidence_mappings": low_confidence,
    }


def _build_skill_coverage(skill_ids: list[int], mappings: ClientDecodedMappings) -> dict[str, Any]:
    mapped = []
    unmapped = []
    low_confidence = []
    for skill_id in skill_ids:
        mapping = mappings.skill(skill_id)
        if mapping:
            item = {"skill_id": skill_id, "canonical_name": mapping.canonical_name, "confidence": mapping.confidence}
            mapped.append(item)
            if mapping.confidence < 0.8:
                low_confidence.append(item)
        else:
            unmapped.append(skill_id)
    return {
        "total_unique_skill_ids": len(skill_ids),
        "mapped_skill_ids": len(mapped),
        "mapped_skill_items": mapped,
        "unmapped_skill_ids": unmapped,
        "low_confidence_mappings": low_confidence,
    }


def _build_knowledge_validation(
    hero_coverage: dict[str, Any],
    skill_coverage: dict[str, Any],
    knowledge_entries: list[KnowledgeEntry],
) -> dict[str, Any]:
    if not knowledge_entries:
        return {"knowledge_entries_loaded": 0}

    hero_terms = _terms_for_domain(knowledge_entries, Domain.HERO)
    skill_terms = _terms_for_domain(knowledge_entries, Domain.SKILL)
    hero_signature_skill_terms = _hero_signature_skill_terms(knowledge_entries)

    hero_missing = [item for item in _mapped_items(hero_coverage) if item["canonical_name"] not in hero_terms]
    skill_items = _mapped_items(skill_coverage)
    skill_missing_profiles = [item for item in skill_items if item["canonical_name"] not in skill_terms]
    skill_found_as_hero_signature = [
        item for item in skill_items if item["canonical_name"] in hero_signature_skill_terms
    ]
    return {
        "knowledge_entries_loaded": len(knowledge_entries),
        "mapped_hero_names_checked": hero_coverage["mapped_heroes"],
        "mapped_skill_names_checked": skill_coverage["mapped_skill_ids"],
        "hero_mappings_missing_kb_topic": hero_missing,
        "skill_mappings_missing_skill_profile": skill_missing_profiles,
        "skill_mappings_found_as_hero_signature": skill_found_as_hero_signature,
    }


def _scan_staged_entries_for_sensitive_markers(staged_entries: list[Any]) -> dict[str, Any]:
    dumped = json.dumps([entry.model_dump(mode="json") for entry in staged_entries], ensure_ascii=False)
    hits: list[dict[str, str]] = []
    for marker in SENSITIVE_LITERAL_MARKERS:
        if marker in dumped:
            hits.append({"marker": marker, "type": "literal"})
    for marker_name, pattern in SENSITIVE_REGEX_MARKERS.items():
        if pattern.search(dumped):
            hits.append({"marker": marker_name, "type": "regex"})
    return {
        "checked_staged_entries": len(staged_entries),
        "sensitive_markers_found": hits,
    }


def _build_review_blockers(
    hero_coverage: dict[str, Any],
    skill_coverage: dict[str, Any],
    knowledge_validation: dict[str, Any],
    security_scan: dict[str, Any],
) -> list[str]:
    blockers = ["staging entries are normalized, not reviewed; publish_staging skips them by default"]
    if hero_coverage["unmapped_heroes"]:
        blockers.append("some static hero ids are not mapped to canonical KB hero names")
    if skill_coverage["unmapped_skill_ids"]:
        blockers.append("some decoded skill ids are not mapped to canonical skill names")
    if hero_coverage["low_confidence_mappings"] or skill_coverage["low_confidence_mappings"]:
        blockers.append("some mappings are below confidence 0.8 and need manual review")
    if knowledge_validation.get("hero_mappings_missing_kb_topic"):
        blockers.append("some mapped hero names are missing from formal knowledge_sources")
    if knowledge_validation.get("skill_mappings_missing_skill_profile"):
        blockers.append("some mapped skill names are not formal skill_profile topics")
    if security_scan["sensitive_markers_found"]:
        blockers.append("sensitive marker scan found runtime/account-local fields in staged output")
    return blockers


def _build_next_review_actions(
    hero_coverage: dict[str, Any],
    skill_coverage: dict[str, Any],
    knowledge_validation: dict[str, Any],
) -> list[str]:
    actions = [
        "review unmapped hero ids and decide whether they are missing KB topics, variants, or non-publishable records",
        "map remaining decoded skill ids to canonical skill names with evidence before publish",
        "promote entries from normalized to reviewed only after Chinese names, skill ids, and field semantics are checked",
    ]
    if knowledge_validation.get("skill_mappings_missing_skill_profile"):
        actions.append("add or confirm formal skill_profile entries for mapped skill names that currently only appear as hero signature skills")
    if hero_coverage["low_confidence_mappings"] or skill_coverage["low_confidence_mappings"]:
        actions.append("manually confirm mappings below confidence 0.8")
    return actions


def _unique_skill_ids(static_heroes: list[Any]) -> list[int]:
    ids: set[int] = set()
    for hero in static_heroes:
        for slot in hero.sanitized_skill_slots():
            ids.add(slot.skill_id)
    return sorted(ids)


def _mapped_items(coverage: dict[str, Any]) -> list[dict[str, Any]]:
    mapped = []
    for key in ["mapped_hero_items", "mapped_skill_items"]:
        value = coverage.get(key)
        if isinstance(value, list):
            mapped.extend(value)
    return mapped


def _terms_for_domain(entries: list[KnowledgeEntry], domain: Domain) -> set[str]:
    terms: set[str] = set()
    for entry in entries:
        if entry.domain != domain:
            continue
        terms.update(entry.searchable_terms())
    return {term for term in terms if term}


def _hero_signature_skill_terms(entries: list[KnowledgeEntry]) -> set[str]:
    terms: set[str] = set()
    for entry in entries:
        if entry.domain != Domain.HERO or not isinstance(entry.structured_data, HeroStaticProfile):
            continue
        terms.update(entry.structured_data.signature_skills)
    return {term for term in terms if term}
