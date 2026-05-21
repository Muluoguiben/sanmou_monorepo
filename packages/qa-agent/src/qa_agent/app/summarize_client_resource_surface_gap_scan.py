from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_resource_surface_gap_scan import (
    build_client_resource_surface_gap_scan_report,
    write_client_resource_surface_gap_scan_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized NSLG client resource-surface gap scan evidence."
    )
    parser.add_argument("--input", required=True, help="Round190 resource-surface JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="client-resource-surface-gap-scan-round133")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_client_resource_surface_gap_scan_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_client_resource_surface_gap_scan_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "ns_bundle_count": report.counts.get("ns_bundle_count"),
                "ns_total_bytes": report.counts.get("ns_total_bytes"),
                "resource_surface_gap_identified": report.route_conclusion.get(
                    "resource_surface_gap_identified"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
