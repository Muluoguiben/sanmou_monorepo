from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_gameassembly_global_metadata_owner_probe import (
    build_gameassembly_global_metadata_owner_probe_report,
    write_gameassembly_global_metadata_owner_probe_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized GameAssembly global-metadata owner probe evidence."
    )
    parser.add_argument("--input", required=True, help="Round188 GameAssembly probe JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="gameassembly-global-metadata-owner-probe-round127")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_gameassembly_global_metadata_owner_probe_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_gameassembly_global_metadata_owner_probe_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "target_count": report.counts.get("target_count"),
                "loader_owner_candidate_count": report.counts.get(
                    "loader_owner_candidate_count"
                ),
                "global_metadata_owner_candidate_found": report.route_conclusion.get(
                    "global_metadata_owner_candidate_found"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
