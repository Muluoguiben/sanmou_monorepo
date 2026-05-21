from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_function_pointer_table_probe import (
    build_function_pointer_table_probe_report,
    write_function_pointer_table_probe_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize an offline GameAssembly function pointer table probe JSON artifact."
    )
    parser.add_argument("--input", required=True, help="External Round184 JSON artifact.")
    parser.add_argument("--output", required=True, help="Sanitized YAML output path.")
    parser.add_argument("--source-id", default="gameassembly-function-pointer-table-probe")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_function_pointer_table_probe_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_function_pointer_table_probe_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "function_pointer_hit_count": report.counts.get("function_pointer_hit_count"),
                "dispatcher_pointer_hit_count": report.counts.get("dispatcher_pointer_hit_count"),
                "dispatcher_pointer_hits_outside_known_tables": report.counts.get(
                    "dispatcher_pointer_hits_outside_known_tables"
                ),
                "global_metadata_function_pointer_hit_count": report.counts.get(
                    "global_metadata_function_pointer_hit_count"
                ),
                "initializer_table_route_recovered": report.route_conclusion.get(
                    "initializer_table_route_recovered"
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
