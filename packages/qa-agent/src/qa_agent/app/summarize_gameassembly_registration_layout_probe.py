from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_registration_layout_probe import (
    build_registration_layout_report,
    write_registration_layout_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized GameAssembly IL2CPP registration layout probe evidence."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Round181 GameAssembly registration layout probe JSON artifact.",
    )
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="gameassembly-registration-layout-probe-round106")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_registration_layout_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_registration_layout_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "primary_code_registration_start_rva": report.counts.get(
                    "primary_code_registration_start_rva"
                ),
                "codegen_modules_field_offset": report.counts.get(
                    "codegen_modules_field_offset"
                ),
                "registration_callsite_recovered": report.route_conclusion.get(
                    "registration_callsite_recovered"
                ),
                "metadata_registration_paired_by_callsite": report.route_conclusion.get(
                    "metadata_registration_paired_by_callsite"
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
