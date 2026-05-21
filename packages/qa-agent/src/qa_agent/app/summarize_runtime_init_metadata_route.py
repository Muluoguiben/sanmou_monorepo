from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_runtime_init_route import (
    build_runtime_init_metadata_route_report,
    write_runtime_init_metadata_route_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized runtime init / metadata route evidence for qa-agent import planning."
    )
    parser.add_argument("--input", required=True, help="Round164 runtime init metadata route JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="runtime-init-metadata-route")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_runtime_init_metadata_route_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_runtime_init_metadata_route_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "runtime_init_anchor_known": report.route_conclusion.get(
                    "runtime_init_anchor_known"
                ),
                "global_metadata_protected_wrapper_confirmed": report.route_conclusion.get(
                    "global_metadata_protected_wrapper_confirmed"
                ),
                "init_lua_env_method_address_recovered": report.route_conclusion.get(
                    "init_lua_env_method_address_recovered"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
