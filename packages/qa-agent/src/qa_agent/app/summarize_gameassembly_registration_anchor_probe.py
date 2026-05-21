from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_registration_anchor_probe import (
    build_registration_anchor_report,
    write_registration_anchor_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized GameAssembly IL2CPP registration anchor probe evidence."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Round180 GameAssembly registration anchor probe JSON artifact.",
    )
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="gameassembly-registration-anchor-probe-round103")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_registration_anchor_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_registration_anchor_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "declared_codegen_module_count": report.counts.get(
                    "declared_codegen_module_count"
                ),
                "parsed_codegen_module_count": report.counts.get(
                    "parsed_codegen_module_count"
                ),
                "assembly_csharp_index": report.counts.get("assembly_csharp_index"),
                "metadata_registration_candidate_recovered": report.route_conclusion.get(
                    "metadata_registration_candidate_recovered"
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
