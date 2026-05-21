from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_registration_pair_context_probe import (
    build_registration_pair_context_report,
    write_registration_pair_context_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized GameAssembly IL2CPP registration pair-context probe evidence."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Round182 GameAssembly registration pair-context probe JSON artifact.",
    )
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument(
        "--source-id",
        default="gameassembly-registration-pair-context-probe-round109",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_registration_pair_context_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_registration_pair_context_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "raw_code_registration_start_ref_count": report.counts.get(
                    "raw_code_registration_start_ref_count"
                ),
                "raw_metadata_candidate_ref_count": report.counts.get(
                    "raw_metadata_candidate_ref_count"
                ),
                "paired_neighborhood_count": report.counts.get(
                    "paired_neighborhood_count"
                ),
                "call_argument_pair_window_count": report.counts.get(
                    "call_argument_pair_window_count"
                ),
                "registration_pair_recovered": report.route_conclusion.get(
                    "registration_pair_recovered"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
