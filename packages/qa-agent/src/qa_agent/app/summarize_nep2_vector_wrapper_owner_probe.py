from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_nep2_vector_wrapper_owner_probe import (
    build_nep2_vector_wrapper_owner_probe_report,
    write_nep2_vector_wrapper_owner_probe_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized NEP2 vector-wrapper owner probe evidence."
    )
    parser.add_argument("--input", required=True, help="Round189 NEP2 wrapper probe JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="nep2-vector-wrapper-owner-probe-round130")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_nep2_vector_wrapper_owner_probe_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_nep2_vector_wrapper_owner_probe_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "wrapper_function_count": report.counts.get("wrapper_function_count"),
                "vector_wrapper_owner_candidate_count": report.counts.get(
                    "vector_wrapper_owner_candidate_count"
                ),
                "vector_wrapper_payload_owner_proven": report.route_conclusion.get(
                    "vector_wrapper_payload_owner_proven"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
