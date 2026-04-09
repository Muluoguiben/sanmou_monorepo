from __future__ import annotations

from pathlib import Path

import yaml

from qa_agent.knowledge.models import KnowledgeEntry


# Hero faction → bucket file mapping
_HERO_FACTION_BUCKET: dict[str, str] = {
    "魏": "wei.yaml",
    "蜀": "shu.yaml",
    "吴": "wu.yaml",
    "群": "qun.yaml",
}

# Skill trigger_type → bucket file mapping
_SKILL_TRIGGER_BUCKET: dict[str, str] = {
    "主动": "active.yaml",
    "被动": "passive.yaml",
    "指挥": "command.yaml",
    "追击": "pursuit.yaml",
}


def _resolve_hero_bucket(entry: KnowledgeEntry) -> str:
    faction = getattr(entry.structured_data, "faction", None) or ""
    return _HERO_FACTION_BUCKET.get(faction, "other.yaml")


def _resolve_skill_bucket(entry: KnowledgeEntry) -> str:
    trigger = getattr(entry.structured_data, "trigger_type", None) or ""
    return _SKILL_TRIGGER_BUCKET.get(trigger, "active.yaml")


def _load_bucket(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None or data == []:
        return []
    if not isinstance(data, list):
        raise ValueError(f"Bucket file must be a list: {path}")
    return data


def _save_bucket(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.dump(items, allow_unicode=True, default_flow_style=False, sort_keys=False)
    path.write_text(text, encoding="utf-8")


def publish_entries(
    entries: list[KnowledgeEntry],
    knowledge_root: Path,
) -> dict[str, int]:
    """Write entries directly into knowledge_sources bucket files.

    Returns a mapping of bucket file name → number of new entries added.
    """
    hero_dir = knowledge_root / "profiles" / "heroes"
    skill_dir = knowledge_root / "profiles" / "skills"

    # Group entries by target bucket path
    buckets: dict[Path, list[KnowledgeEntry]] = {}
    for entry in entries:
        if entry.domain.value == "hero":
            bucket_path = hero_dir / _resolve_hero_bucket(entry)
        elif entry.domain.value == "skill":
            bucket_path = skill_dir / _resolve_skill_bucket(entry)
        else:
            continue
        buckets.setdefault(bucket_path, []).append(entry)

    stats: dict[str, int] = {}
    for bucket_path, new_entries in buckets.items():
        existing = _load_bucket(bucket_path)
        existing_topics = {
            item["topic"] for item in existing if isinstance(item, dict) and "topic" in item
        }

        added = 0
        for entry in new_entries:
            dumped = entry.model_dump(mode="json")
            if entry.topic in existing_topics:
                # Update the first matching entry in-place, preserving the original id
                updated = []
                for item in existing:
                    if isinstance(item, dict) and item.get("topic") == entry.topic:
                        dumped["id"] = item.get("id", dumped["id"])
                        updated.append(dumped)
                    else:
                        updated.append(item)
                existing = updated
            else:
                existing.append(dumped)
                existing_topics.add(entry.topic)
                added += 1

        _save_bucket(bucket_path, existing)
        stats[bucket_path.name] = added

    return stats
