from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from qa_agent.ingestion.publish import publish_entries
from qa_agent.knowledge.models import KnowledgeEntry


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish generic-rule YAML batches directly into knowledge_sources."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a raw rule YAML file, or a directory containing *.yaml rule files.",
    )
    parser.add_argument(
        "--knowledge-dir",
        default="knowledge_sources",
        help="Root directory for knowledge sources.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print routing without writing any file.",
    )
    return parser


def _resolve_path(raw: str, project_root: Path) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def _collect_input_files(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        return sorted(p for p in input_path.glob("*.yaml") if p.is_file())
    return [input_path]


def _load_entries(path: Path) -> list[KnowledgeEntry]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Rule YAML must be a list of entries: {path}")
    return [KnowledgeEntry.model_validate(item) for item in data]


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    input_path = _resolve_path(args.input, project_root)
    knowledge_dir = _resolve_path(args.knowledge_dir, project_root)

    files = _collect_input_files(input_path)
    if not files:
        print(f"No YAML files found under {input_path}")
        return

    all_entries: list[KnowledgeEntry] = []
    for f in files:
        entries = _load_entries(f)
        all_entries.extend(entries)
        print(f"Loaded {len(entries):3d} entries from {f.relative_to(project_root)}")

    print(f"\nTotal: {len(all_entries)} entries")

    if args.dry_run:
        by_domain: dict[str, int] = {}
        for e in all_entries:
            by_domain[e.domain.value] = by_domain.get(e.domain.value, 0) + 1
        print("\nRouting by domain:")
        for domain, count in sorted(by_domain.items()):
            print(f"  {domain}: {count}")
        return

    stats = publish_entries(all_entries, knowledge_dir)
    print("\nPublish stats (new entries added per bucket; topics matching existing are updated in-place):")
    for bucket, count in sorted(stats.items()):
        print(f"  {bucket}: {count} new")


if __name__ == "__main__":
    main()
