from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_global_metadata_transform_probe import (
    build_global_metadata_transform_probe_report,
    write_global_metadata_transform_probe_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized global-metadata.dat transform probe evidence for qa-agent import planning."
    )
    parser.add_argument("--input", required=True, help="Round167 global metadata transform probe JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="global-metadata-transform-probe")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_global_metadata_transform_probe_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_global_metadata_transform_probe_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "transform_candidate_count": report.counts.get("transform_candidate_count"),
                "needle_hit_candidate_count": report.counts.get("needle_hit_candidate_count"),
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
