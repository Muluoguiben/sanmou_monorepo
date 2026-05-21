from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_nep2_metadata_loader_deep_slice import (
    build_nep2_metadata_loader_deep_slice_report,
    write_nep2_metadata_loader_deep_slice_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized NEP2 global-metadata loader candidate deep-slice evidence."
    )
    parser.add_argument("--input", required=True, help="Round169 NEP2 deep-slice JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="nep2-global-metadata-loader-deep-slice-round70")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_nep2_metadata_loader_deep_slice_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_nep2_metadata_loader_deep_slice_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "target_count": report.counts.get("target_count"),
                "closed_target_count": report.counts.get("closed_target_count"),
                "read_or_mapping_target_count": report.counts.get(
                    "read_or_mapping_target_count"
                ),
                "metadata_ref_target_count": report.counts.get("metadata_ref_target_count"),
                "targets_closed": report.route_conclusion.get(
                    "targets_closed_as_metadata_loader_candidates"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
