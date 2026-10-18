from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any

import yaml

from .models import (
    ClientImportQueueItem,
    _CLIENT_HERO_ID_RE,
    _HERO_ID_RE,
    _SKILL_ID_RE,
)


def _missing_input_item(path: Path, repo_root: Path, *, queue_type: str) -> ClientImportQueueItem:
    portable = _portable_path(path, repo_root)
    return ClientImportQueueItem(
        queue_id=f"missing-input-{_slug(portable)}",
        queue_type=queue_type,
        priority=10,
        readiness="blocked_missing_artifact",
        domain="evidence_inventory",
        topic=portable,
        source_artifact=portable,
        blockers=[f"expected client evidence artifact is missing: {portable}"],
        next_actions=["rebuild the missing offline client evidence artifact"],
        counts={"blocker_count": 1},
    )


def _build_publish_readiness(
    items: list[ClientImportQueueItem],
    evidence_bundle: dict[str, Any],
) -> dict[str, Any]:
    import_readiness = evidence_bundle.get("import_readiness") or {}
    publishable_now = [
        item for item in items if item.readiness in {"reviewed_import_candidate", "ready_for_import"}
    ]
    return {
        "safe_for_publish": False,
        "auto_publish_allowed": False,
        "publishable_now_count": len(publishable_now),
        "queue_blocker_count": sum(len(item.blockers) for item in items),
        "upstream_bundle_safe_for_publish": bool(import_readiness.get("safe_for_publish")),
        "reason": (
            "client import queue is a review and decoder planning artifact; no entry is promoted automatically"
        ),
    }


def _build_decoded_audit_index(audit: dict[str, Any]) -> dict[str, Any]:
    hero_coverage = audit.get("hero_coverage") or {}
    skill_coverage = audit.get("skill_coverage") or {}
    return {
        "unmapped_hero_ids": {
            int(item.get("hero_id"))
            for item in hero_coverage.get("unmapped_heroes") or []
            if isinstance(item, dict) and isinstance(item.get("hero_id"), int)
        },
        "low_confidence_heroes": {
            int(item.get("hero_id")): item
            for item in hero_coverage.get("low_confidence_mappings") or []
            if isinstance(item, dict) and isinstance(item.get("hero_id"), int)
        },
        "unmapped_skill_ids": {
            int(item)
            for item in skill_coverage.get("unmapped_skill_ids") or []
            if isinstance(item, int)
        },
        "low_confidence_skills": {
            int(item.get("skill_id")): item
            for item in skill_coverage.get("low_confidence_mappings") or []
            if isinstance(item, dict) and isinstance(item.get("skill_id"), int)
        },
    }


def _decoded_hero_priority(
    *,
    confidence: float,
    review_status: str,
    has_unmapped_hero: bool,
    unmapped_skill_count: int,
    low_confidence_mapping_count: int,
) -> int:
    priority = 78
    if confidence >= 0.9:
        priority += 6
    elif confidence < 0.75:
        priority -= 8
    if review_status != "reviewed":
        priority -= 4
    if has_unmapped_hero:
        priority -= 18
    priority -= min(unmapped_skill_count, 4) * 3
    priority -= min(low_confidence_mapping_count, 3) * 4
    return max(priority, 20)


def _luascript_priority(*, stem: str, domains: list[str], record_count: int) -> int:
    domain_scores = {
        "hero": 92,
        "skill": 90,
        "combat": 86,
        "building": 84,
        "map": 82,
        "chapter_task": 80,
        "story_plot": 76,
        "season": 74,
        "economy_item": 68,
        "system_text": 64,
        "unknown": 40,
    }
    priority = max((domain_scores.get(domain, 50) for domain in domains), default=40)
    if stem in {"heros", "skills", "warbook", "custom_hero"}:
        priority += 5
    return min(priority + min(record_count, 8), 99)


def _lua_crypto_priority(target: str) -> int:
    text = target.lower()
    if "xlual_loadbuffer" in text or "textasset::get_bytes" in text:
        return 98
    if "metadata" in text:
        return 95
    if "16-byte" in text or "block transform" in text:
        return 92
    return 88


def _nep2_priority(target: str) -> int:
    text = target.lower()
    if "initluascriptsscan" in text:
        return 99
    if "lua" in text and "loadbuffer" in text:
        return 96
    if "0x180021240" in text or "string-decode" in text:
        return 90
    return 86


def _primary_domain(domains: list[str]) -> str:
    order = [
        "hero",
        "skill",
        "combat",
        "building",
        "map",
        "chapter_task",
        "story_plot",
        "season",
    ]
    for domain in order:
        if domain in domains:
            return domain
    return domains[0] if domains else "unknown"


def _hero_id_from_entry(entry: dict[str, Any]) -> int | None:
    source_ref = str(entry.get("source_ref") or "")
    match = _HERO_ID_RE.search(source_ref)
    if match:
        return int(match.group(1))
    structured = entry.get("structured_data") if isinstance(entry.get("structured_data"), dict) else {}
    for note in _str_list(structured.get("notes")):
        match = _CLIENT_HERO_ID_RE.search(note)
        if match:
            return int(match.group(1))
    entry_id = str(entry.get("id") or "")
    tail = entry_id.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else None


def _skill_ids_from_entry(entry: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    structured = entry.get("structured_data") if isinstance(entry.get("structured_data"), dict) else {}
    for note in _str_list(structured.get("notes")):
        ids.update(int(match.group(1)) for match in _SKILL_ID_RE.finditer(note))
    for topic in _str_list(entry.get("related_topics")):
        if topic.isdigit():
            ids.add(int(topic))
    return ids


def _client_version(bundle: dict[str, Any]) -> dict[str, Any]:
    version = bundle.get("client_version")
    return version if isinstance(version, dict) else {}


def _input_path(repo_root: Path, path: Path | None, default: Path) -> Path:
    selected = path or default
    return selected if selected.is_absolute() else repo_root / selected


def _load_yaml_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_yaml_list(path: Path) -> list[Any]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _portable_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return path.name


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item)]


def _float_value(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _csv_ints(values: list[int]) -> str:
    return ", ".join(str(value) for value in values)


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "-", value).strip("-").lower()
    return slug or "item"


def _unique_strs(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    return {str(key): int(raw or 0) for key, raw in value.items()}


def _prefixed_counts(prefix: str, counts: Counter[str]) -> dict[str, int]:
    return {f"{prefix}:{key}": int(value) for key, value in sorted(counts.items())}
