from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from qa_agent.knowledge.loader import load_entries, load_entries_from_file
from qa_agent.knowledge.models import EntryKind, KnowledgeEntry
from qa_agent.knowledge.source_paths import discover_source_paths

SCHEMA_VERSION = "strategy_snapshot.v1"
DEFAULT_GENERATED_AT = "1970-01-01"


def _entry_key(entry: KnowledgeEntry) -> str:
    return entry.id


def _source_summaries(source_root: Path, source_paths: list[Path]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for path in source_paths:
        entries = load_entries_from_file(path)
        summaries.append(
            {
                "path": path.relative_to(source_root).as_posix(),
                "entry_count": len(entries),
                "entry_ids": sorted(entry.id for entry in entries),
            }
        )
    return summaries


def _generated_at(entries: list[KnowledgeEntry]) -> str:
    if not entries:
        return DEFAULT_GENERATED_AT
    return max(entry.updated_at for entry in entries).isoformat()


def _building_priorities(entries: list[KnowledgeEntry]) -> list[dict[str, Any]]:
    building_entries = [entry for entry in entries if entry.domain.value == "building"]
    return [
        {
            "key": _entry_key(entry),
            "entry_ids": [_entry_key(entry)],
            "topic": entry.topic,
            "aliases": entry.aliases,
            "priority": entry.priority,
            "rationale": entry.facts[0] if entry.facts else "",
            "constraints": entry.constraints,
            "source_ref": entry.source_ref,
        }
        for entry in sorted(building_entries, key=lambda item: (-item.priority, item.id))
    ]


def _land_risk_rules(entries: list[KnowledgeEntry]) -> list[dict[str, Any]]:
    keywords = ("地", "战损", "兵力", "体力", "行军")
    combat_entries = [
        entry
        for entry in entries
        if entry.domain.value == "combat"
        and any(keyword in " ".join([entry.topic, *entry.aliases, *entry.related_topics]) for keyword in keywords)
    ]
    return [
        {
            "key": _entry_key(entry),
            "entry_ids": [_entry_key(entry)],
            "topic": entry.topic,
            "priority": entry.priority,
            "signals": sorted({*entry.aliases, *entry.related_topics}),
            "rule": entry.facts[0] if entry.facts else "",
            "constraints": entry.constraints,
            "source_ref": entry.source_ref,
        }
        for entry in sorted(combat_entries, key=lambda item: (-item.priority, item.id))
    ]


def _lineup_hints(entries: list[KnowledgeEntry]) -> list[dict[str, Any]]:
    lineup_entries = [entry for entry in entries if entry.entry_kind == EntryKind.LINEUP_SOLUTION]
    hints: list[dict[str, Any]] = []
    for entry in sorted(lineup_entries, key=lambda item: (-item.priority, item.id)):
        profile = entry.structured_data
        hints.append(
            {
                "key": _entry_key(entry),
                "entry_ids": [_entry_key(entry)],
                "name": getattr(profile, "name", entry.topic),
                "aliases": getattr(profile, "aliases", entry.aliases),
                "season_tags": getattr(profile, "season_tags", []),
                "lineup_rating": getattr(profile, "lineup_rating", None),
                "hero_names": getattr(profile, "hero_names", []),
                "core_skills": getattr(profile, "core_skills", []),
                "scenario_tags": getattr(profile, "scenario_tags", []),
                "notes": getattr(profile, "notes", entry.facts[:1]),
                "source_ref": entry.source_ref,
            }
        )
    return hints


def build_strategy_snapshot(source_root: Path) -> dict[str, Any]:
    source_paths = discover_source_paths(source_root)
    entries = load_entries(source_paths)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _generated_at(entries),
        "sources": _source_summaries(source_root, source_paths),
        "building_priorities": _building_priorities(entries),
        "land_risk_rules": _land_risk_rules(entries),
        "lineup_hints": _lineup_hints(entries),
    }


def write_strategy_snapshot(snapshot: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".json":
        output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    output_path.write_text(yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export an offline pioneer strategy snapshot from local QA knowledge.")
    parser.add_argument(
        "--sources-dir",
        default="knowledge_sources",
        help="Directory that stores YAML knowledge sources.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="YAML or JSON file to write.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    source_root = project_root / args.sources_dir
    snapshot = build_strategy_snapshot(source_root)
    write_strategy_snapshot(snapshot, Path(args.output))


if __name__ == "__main__":
    main()
