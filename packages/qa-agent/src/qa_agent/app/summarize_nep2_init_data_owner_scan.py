from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_nep2_init_data_owner_scan import (
    build_nep2_init_data_owner_scan_report,
    write_nep2_init_data_owner_scan_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized NEP2 InitLuaScriptsScan/CGameProtector data-owner scan evidence."
    )
    parser.add_argument("--input", required=True, help="Round171 NEP2 init data owner JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="nep2-init-data-owner-scan-round76")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_nep2_init_data_owner_scan_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_nep2_init_data_owner_scan_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "data_reference_count": report.counts.get("data_reference_count"),
                "inspected_function_count": report.counts.get("inspected_function_count"),
                "payload_owner_candidate_count": report.counts.get(
                    "payload_owner_candidate_count"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
