from __future__ import annotations

from pathlib import Path

import yaml

from qa_agent.knowledge.models import EntryKind, KnowledgeEntry


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

# Generic-rule domain → top-level bucket file mapping
_GENERIC_RULE_BUCKET: dict[str, str] = {
    "building": "building.yaml",
    "chapter": "chapter.yaml",
    "combat": "combat.yaml",
    "hero": "hero_skill.yaml",
    "resource": "resource_team.yaml",
    "skill": "hero_skill.yaml",
    "team": "resource_team.yaml",
    "term": "terms.yaml",
}


def _resolve_hero_bucket(entry: KnowledgeEntry) -> str:
    rarity = getattr(entry.structured_data, "rarity", None) or ""
    if rarity != "橙":
        return "minor.yaml"
    faction = getattr(entry.structured_data, "faction", None) or ""
    return _HERO_FACTION_BUCKET.get(faction, "other.yaml")


def _resolve_skill_bucket(entry: KnowledgeEntry) -> str:
    trigger = getattr(entry.structured_data, "trigger_type", None) or ""
    return _SKILL_TRIGGER_BUCKET.get(trigger, "active.yaml")


def _slugify(value: str) -> str:
    lowered = value.lower().strip()
    return "-".join(part for part in lowered.replace("/", " ").replace("_", " ").split() if part)


def _resolve_lineup_bucket(entry: KnowledgeEntry) -> str:
    season_tags = list(getattr(entry.structured_data, "season_tags", []) or [])
    if not season_tags:
        return "season-misc.yaml"
    return f"season-{_slugify(season_tags[0])}.yaml"


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
    lineup_dir = knowledge_root / "solutions" / "lineups"
    combat_file = knowledge_root / "combat.yaml"

    # Group entries by target bucket path
    buckets: dict[Path, list[KnowledgeEntry]] = {}
    for entry in entries:
        if entry.entry_kind == EntryKind.GENERIC_RULE:
            bucket_name = _GENERIC_RULE_BUCKET.get(entry.domain.value)
            if not bucket_name:
                continue
            bucket_path = knowledge_root / bucket_name
        elif entry.domain.value == "hero":
            bucket_path = hero_dir / _resolve_hero_bucket(entry)
        elif entry.domain.value == "skill":
            bucket_path = skill_dir / _resolve_skill_bucket(entry)
        elif entry.domain.value == "solution" and entry.entry_kind.value == "lineup_solution":
            bucket_path = lineup_dir / _resolve_lineup_bucket(entry)
        elif entry.domain.value == "combat" and entry.entry_kind.value == "generic_rule":
            bucket_path = combat_file
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
