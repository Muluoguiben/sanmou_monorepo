from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_textasset_payload_owner_trace import (
    build_textasset_payload_owner_trace_report,
    write_textasset_payload_owner_trace_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized TextAsset/LuaScripts payload owner route evidence."
    )
    parser.add_argument("--input", required=True, help="Round173 TextAsset payload owner JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="textasset-payload-owner-trace-round82")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_textasset_payload_owner_trace_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_textasset_payload_owner_trace_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "term_hit_count": report.counts.get("term_hit_count"),
                "exact_asset_path_or_stem_hit_count": report.counts.get(
                    "exact_asset_path_or_stem_hit_count"
                ),
                "code_ref_count": report.counts.get("code_ref_count"),
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
