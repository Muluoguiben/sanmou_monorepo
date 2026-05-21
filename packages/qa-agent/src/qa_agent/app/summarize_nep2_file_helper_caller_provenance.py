from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_nep2_file_helper_caller_provenance import (
    build_nep2_file_helper_caller_provenance_report,
    write_nep2_file_helper_caller_provenance_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized NEP2 file-helper caller provenance evidence."
    )
    parser.add_argument("--input", required=True, help="Round187 NEP2 file-helper JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="nep2-file-helper-caller-provenance-round124")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_nep2_file_helper_caller_provenance_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_nep2_file_helper_caller_provenance_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "target_count": report.counts.get("target_count"),
                "payload_keyword_ref_function_count": report.counts.get(
                    "payload_keyword_ref_function_count"
                ),
                "file_helper_payload_owner_proven": report.route_conclusion.get(
                    "file_helper_payload_owner_proven"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
