from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.config import load_alias_config, load_enum_config
from qa_agent.ingestion.loader import load_raw_batch
from qa_agent.ingestion.normalize import normalize_hero_record, normalize_skill_record
from qa_agent.ingestion.publish import publish_entries
from qa_agent.knowledge.models import Domain


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize raw hero/skill ingestion batches and optionally publish to knowledge_sources.")
    parser.add_argument("--input", required=True, help="Path to the raw YAML batch file.")
    parser.add_argument("--publish", action="store_true", help="Write normalized entries directly into knowledge_sources (skip staging/review).")
    parser.add_argument("--hero-aliases", default="configs/hero_aliases.yaml")
    parser.add_argument("--skill-aliases", default="configs/skill_aliases.yaml")
    parser.add_argument("--enums", default="configs/enums.yaml")
    parser.add_argument("--knowledge-dir", default="knowledge_sources", help="Root directory for knowledge sources.")
    return parser


def _resolve_path(raw: str, project_root: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    input_path = _resolve_path(args.input, project_root)
    hero_aliases_path = _resolve_path(args.hero_aliases, project_root)
    skill_aliases_path = _resolve_path(args.skill_aliases, project_root)
    enums_path = _resolve_path(args.enums, project_root)
    knowledge_dir = _resolve_path(args.knowledge_dir, project_root)

    raw_batch = load_raw_batch(input_path)
    enum_config = load_enum_config(enums_path)

    if raw_batch.domain == Domain.HERO:
        alias_config = load_alias_config(hero_aliases_path)
        staged = [normalize_hero_record(record, alias_config, enum_config) for record in raw_batch.records]
    elif raw_batch.domain == Domain.SKILL:
        alias_config = load_alias_config(skill_aliases_path)
        staged = [normalize_skill_record(record, alias_config, enum_config) for record in raw_batch.records]
    else:
        raise ValueError(f"Unsupported raw batch domain: {raw_batch.domain}")

    entries = [s.entry for s in staged]

    if args.publish:
        stats = publish_entries(entries, knowledge_dir)
        for bucket, count in stats.items():
            print(f"{bucket}: {count} new, others updated in-place")
    else:
        print(json.dumps([e.model_dump(mode="json") for e in entries], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
