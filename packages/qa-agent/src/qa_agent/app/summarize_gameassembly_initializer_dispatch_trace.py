from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_initializer_dispatch_trace import (
    build_initializer_dispatch_trace_report,
    write_initializer_dispatch_trace_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize an offline GameAssembly initializer dispatch trace JSON artifact."
    )
    parser.add_argument("--input", required=True, help="External Round183 JSON artifact.")
    parser.add_argument("--output", required=True, help="Sanitized YAML output path.")
    parser.add_argument("--source-id", default="gameassembly-initializer-dispatch-trace")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_initializer_dispatch_trace_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_initializer_dispatch_trace_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "registration_anchor_ref_function_count": report.counts.get(
                    "registration_anchor_ref_function_count"
                ),
                "metadata_candidate_ref_function_count": report.counts.get(
                    "metadata_candidate_ref_function_count"
                ),
                "global_metadata_string_ref_function_count": report.counts.get(
                    "global_metadata_string_ref_function_count"
                ),
                "initializer_dispatcher_route_recovered": report.route_conclusion.get(
                    "initializer_dispatcher_route_recovered"
                ),
                "init_lua_env_method_pointer_recovered": report.route_conclusion.get(
                    "init_lua_env_method_pointer_recovered"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
