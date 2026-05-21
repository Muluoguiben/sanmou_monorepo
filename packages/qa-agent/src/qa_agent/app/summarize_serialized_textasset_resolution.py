from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_serialized_textasset_resolution import (
    build_serialized_textasset_resolution_report,
    write_serialized_textasset_resolution_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized SerializedFile TextAsset path_id/object_offset resolution evidence."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Round175 Serialized TextAsset path_id/object_offset resolution JSON artifact.",
    )
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="serialized-textasset-path-resolution-round88")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_serialized_textasset_resolution_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_serialized_textasset_resolution_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "resolved_record_count": report.counts.get("resolved_record_count"),
                "unresolved_record_count": report.counts.get("unresolved_record_count"),
                "unique_resolved_object_offset_count": report.counts.get(
                    "unique_resolved_object_offset_count"
                ),
                "path_id_to_exact_object_offset_resolved": report.route_conclusion.get(
                    "path_id_to_exact_object_offset_resolved"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
