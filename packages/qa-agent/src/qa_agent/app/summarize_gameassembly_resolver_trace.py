from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_gameassembly_resolver_trace import (
    build_gameassembly_resolver_trace_report,
    write_gameassembly_resolver_trace_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized GameAssembly resolver-candidate evidence for qa-agent import planning."
    )
    parser.add_argument("--input", required=True, help="Round165 GameAssembly resolver trace JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="gameassembly-resolver-trace")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_gameassembly_resolver_trace_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_gameassembly_resolver_trace_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "resolver_candidate_function_found": report.route_conclusion.get(
                    "resolver_candidate_function_found"
                ),
                "descriptor_resolver_pattern_supported": report.route_conclusion.get(
                    "descriptor_resolver_pattern_supported"
                ),
                "textasset_payload_owner_proven": report.route_conclusion.get(
                    "textasset_payload_owner_proven"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
