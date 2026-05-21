from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_resolved_payload_native_anchor_scan import (
    build_resolved_payload_native_anchor_scan_report,
    write_resolved_payload_native_anchor_scan_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized resolved LuaScripts payload native-anchor scan evidence."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Round176 resolved payload native anchor scan JSON artifact.",
    )
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="resolved-payload-native-anchor-scan-round91")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_resolved_payload_native_anchor_scan_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_resolved_payload_native_anchor_scan_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "native_strong_anchor_hit_count_capped": report.counts.get(
                    "native_strong_anchor_hit_count_capped"
                ),
                "native_weak_anchor_hit_count_capped": report.counts.get(
                    "native_weak_anchor_hit_count_capped"
                ),
                "native_exact_strong_anchor_found": report.route_conclusion.get(
                    "native_exact_strong_anchor_found"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
