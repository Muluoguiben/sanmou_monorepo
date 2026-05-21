from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from qa_agent.ingestion.client_decoded import (
    load_client_decoded_mappings,
    load_decoded_hero_export,
    stage_decoded_heroes,
    write_staging_entries,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a decoded NSLG hero export into qa-agent reviewed-before-publish staging entries."
    )
    parser.add_argument("--input", required=True, help="Path to hero_readable_export_round29.json-like input.")
    parser.add_argument("--output", required=True, help="YAML staging output path.")
    parser.add_argument("--source-id", default="hero-readable-export-round29", help="Stable source id for source_ref.")
    parser.add_argument("--mappings", help="Optional YAML mapping for client hero/skill ids to canonical KB names.")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    export = load_decoded_hero_export(Path(args.input))
    mappings = load_client_decoded_mappings(Path(args.mappings)) if args.mappings else None
    entries = stage_decoded_heroes(
        export,
        source_id=args.source_id,
        captured_at=datetime.now(timezone.utc),
        mappings=mappings,
    )
    write_staging_entries(entries, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": args.source_id,
                "staged_entries": len(entries),
                "input_heroes": len(export.heroes),
                "mappings": args.mappings,
                "review_status": "normalized",
                "publish_default": "blocked_until_reviewed",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
