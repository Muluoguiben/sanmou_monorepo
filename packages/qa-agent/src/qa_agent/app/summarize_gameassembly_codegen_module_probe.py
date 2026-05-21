from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_codegen_module_probe import (
    build_codegen_module_probe_report,
    write_codegen_module_probe_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized GameAssembly IL2CPP CodeGenModule probe evidence."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Round179 GameAssembly CodeGenModule probe JSON artifact.",
    )
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="gameassembly-codegen-module-probe-round100")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_codegen_module_probe_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_codegen_module_probe_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "codegen_module_candidate_count": report.counts.get(
                    "codegen_module_candidate_count"
                ),
                "assembly_csharp_method_pointer_count": report.counts.get(
                    "assembly_csharp_method_pointer_count"
                ),
                "assembly_csharp_method_pointer_text_count": report.counts.get(
                    "assembly_csharp_method_pointer_text_count"
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
