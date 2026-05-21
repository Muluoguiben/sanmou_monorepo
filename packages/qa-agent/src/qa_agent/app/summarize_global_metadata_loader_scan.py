from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_global_metadata_loader_scan import (
    build_global_metadata_loader_scan_report,
    write_global_metadata_loader_scan_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized global-metadata.dat loader-mutation scan evidence."
    )
    parser.add_argument("--input", required=True, help="Round168 loader-mutation scan JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="global-metadata-loader-mutation-scan-round67")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_global_metadata_loader_scan_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_global_metadata_loader_scan_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "candidate_count": report.counts.get("candidate_count"),
                "full_loader_mutation_candidate_count": report.counts.get(
                    "full_loader_mutation_candidate_count"
                ),
                "file_16_candidate_count": report.counts.get("file_16_candidate_count"),
                "metadata_ref_candidate_count": report.counts.get(
                    "metadata_ref_candidate_count"
                ),
                "plaintext_metadata_recovered": report.route_conclusion.get(
                    "plaintext_metadata_recovered"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
