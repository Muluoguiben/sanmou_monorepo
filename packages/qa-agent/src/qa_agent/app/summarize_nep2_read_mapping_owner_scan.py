from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_nep2_read_mapping_owner_scan import (
    build_nep2_read_mapping_owner_scan_report,
    write_nep2_read_mapping_owner_scan_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized NEP2 read/mapping import-owner scan evidence."
    )
    parser.add_argument("--input", required=True, help="Round170 NEP2 read/mapping owner JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="nep2-read-mapping-owner-scan-round73")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_nep2_read_mapping_owner_scan_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_nep2_read_mapping_owner_scan_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "read_mapping_owner_count": report.counts.get("read_mapping_owner_count"),
                "metadata_provenance_owner_count": report.counts.get(
                    "metadata_provenance_owner_count"
                ),
                "provenance_linked_owner_count": report.counts.get(
                    "provenance_linked_owner_count"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
