from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_serialized_textasset_layout import (
    build_serialized_textasset_layout_report,
    write_serialized_textasset_layout_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized SerializedFile TextAsset object layout evidence."
    )
    parser.add_argument("--input", required=True, help="Round174 Serialized TextAsset layout JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="serialized-textasset-layout-round85")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_serialized_textasset_layout_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_serialized_textasset_layout_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "match_count": report.counts.get("match_count"),
                "valid_layout_count": report.counts.get("valid_layout_count"),
                "unique_object_offset_count": report.counts.get(
                    "unique_object_offset_count"
                ),
                "serialized_textasset_object_layout_confirmed": report.route_conclusion.get(
                    "serialized_textasset_object_layout_confirmed"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
