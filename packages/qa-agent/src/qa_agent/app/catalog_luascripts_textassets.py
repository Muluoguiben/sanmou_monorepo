from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_luascripts import (
    build_luascripts_textasset_catalog,
    load_luascripts_extract_summary,
    write_luascripts_textasset_catalog,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Catalog offline NSLG LuaScripts TextAssets into sanitized qa-agent ingestion evidence."
    )
    parser.add_argument("--input", required=True, help="Path to luascripts_textasset_extract_round31.json-like input.")
    parser.add_argument("--output", required=True, help="YAML catalog output path.")
    parser.add_argument("--source-id", default="luascripts-textasset-round31", help="Stable source id for evidence_ref.")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    summary = load_luascripts_extract_summary(Path(args.input))
    catalog = build_luascripts_textasset_catalog(summary, source_id=args.source_id)
    write_luascripts_textasset_catalog(catalog, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": args.source_id,
                "cataloged_records": catalog.cataloged_records,
                "unique_stems": catalog.unique_stems,
                "scenarios": len(catalog.scenarios),
                "extraction_status_counts": catalog.extraction_status_counts,
                "high_value_stems": len(catalog.high_value_stems),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
