from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.loader import load_staging_entries
from qa_agent.ingestion.models import ReviewStatus
from qa_agent.ingestion.publish import publish_entries


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish reviewed staging entries into knowledge_sources.")
    parser.add_argument("--input", required=True, help="Path to a staging YAML file.")
    parser.add_argument("--knowledge-dir", default="knowledge_sources", help="Root directory for knowledge sources.")
    parser.add_argument(
        "--include-unreviewed",
        action="store_true",
        help="Allow publishing normalized entries. By default only reviewed entries are published.",
    )
    return parser


def _resolve_path(raw: str, project_root: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    return (project_root / path).resolve()


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    input_path = _resolve_path(args.input, project_root)
    knowledge_dir = _resolve_path(args.knowledge_dir, project_root)

    staged_entries = load_staging_entries(input_path)
    publishable = []
    skipped = 0
    for staged in staged_entries:
        if args.include_unreviewed or staged.metadata.review_status == ReviewStatus.REVIEWED:
            publishable.append(staged.entry)
        else:
            skipped += 1

    stats = publish_entries(publishable, knowledge_dir) if publishable else {}
    print(
        json.dumps(
            {
                "published_entries": len(publishable),
                "skipped_entries": skipped,
                "bucket_stats": stats,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
