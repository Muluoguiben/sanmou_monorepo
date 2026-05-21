from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_runtime_init_registry_probe import (
    build_runtime_init_registry_probe_report,
    write_runtime_init_registry_probe_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized RuntimeInitializeOnLoads registry probe evidence."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Round178 runtime init registry probe JSON artifact.",
    )
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="runtime-init-registry-probe-round97")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_runtime_init_registry_probe_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_runtime_init_registry_probe_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "runtime_initialize_entry_count": report.counts.get(
                    "runtime_initialize_entry_count"
                ),
                "init_lua_env_entry_count": report.counts.get(
                    "runtime_initialize_init_lua_env_entry_count"
                ),
                "registry_address_or_token_field_count": report.counts.get(
                    "registry_address_or_token_field_count"
                ),
                "unityplayer_runtime_json_code_ref_count": report.counts.get(
                    "unityplayer_runtime_json_code_ref_count"
                ),
                "init_lua_env_native_method_address_recovered": report.route_conclusion.get(
                    "init_lua_env_native_method_address_recovered"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
