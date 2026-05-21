from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_metadata_registration_candidate_taxonomy import (
    build_metadata_registration_candidate_taxonomy_report,
    write_metadata_registration_candidate_taxonomy_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize an offline GameAssembly MetadataRegistration candidate taxonomy JSON artifact."
    )
    parser.add_argument("--input", required=True, help="External Round185 JSON artifact.")
    parser.add_argument("--output", required=True, help="Sanitized YAML output path.")
    parser.add_argument("--source-id", default="gameassembly-metadata-registration-candidate-taxonomy")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_metadata_registration_candidate_taxonomy_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_metadata_registration_candidate_taxonomy_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "metadata_candidate_window_count": report.counts.get(
                    "metadata_candidate_window_count"
                ),
                "exact_ref_candidate_count": report.counts.get("exact_ref_candidate_count"),
                "exact_ref_non_tiny_candidate_count": report.counts.get(
                    "exact_ref_non_tiny_candidate_count"
                ),
                "high_count_candidate_count": report.counts.get("high_count_candidate_count"),
                "referenced_high_count_candidate_count": report.counts.get(
                    "referenced_high_count_candidate_count"
                ),
                "metadata_registration_owner_recovered": report.route_conclusion.get(
                    "metadata_registration_owner_recovered"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
