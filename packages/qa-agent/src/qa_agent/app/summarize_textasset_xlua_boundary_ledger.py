from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_textasset_xlua_boundary_ledger import (
    build_textasset_xlua_boundary_ledger_report,
    write_textasset_xlua_boundary_ledger_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized TextAsset/xLua boundary route ledger evidence."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Round177 TextAsset/xLua boundary ledger JSON artifact.",
    )
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="textasset-xlua-boundary-ledger-round94")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_textasset_xlua_boundary_ledger_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_textasset_xlua_boundary_ledger_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "route_record_count": report.counts.get("route_record_count"),
                "closed_negative_route_count": report.counts.get(
                    "closed_negative_route_count"
                ),
                "next_viable_route": report.route_conclusion.get("next_viable_route"),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
