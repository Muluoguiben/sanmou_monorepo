from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_ns_bundle_format_index import (
    build_ns_bundle_format_index_report,
    write_ns_bundle_format_index_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized NSLG .ns UnityFS bundle format-index evidence."
    )
    parser.add_argument("--input", required=True, help="Round191 .ns format-index JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="ns-bundle-format-index-round136")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_ns_bundle_format_index_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_ns_bundle_format_index_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "bundle_count": report.counts.get("bundle_count"),
                "unityfs_parse_ok_count": report.counts.get("unityfs_parse_ok_count"),
                "protected_serialized_metadata_count": report.counts.get(
                    "protected_serialized_metadata_count"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
