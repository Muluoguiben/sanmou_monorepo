from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_payload_cipher_profile import (
    build_luascripts_payload_cipher_profile_report,
    write_luascripts_payload_cipher_profile_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized LuaScripts payload cipher profile evidence for qa-agent import planning."
    )
    parser.add_argument("--input", required=True, help="Round162 LuaScripts payload cipher profile JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="luascripts-payload-cipher-profile")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_luascripts_payload_cipher_profile_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_luascripts_payload_cipher_profile_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "payload_profile_count": report.payload_profile_count,
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
                "lua_payload_decoder_recovered": report.route_conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "single_byte_or_crib_xor_ruled_out": report.route_conclusion.get(
                    "single_byte_or_crib_xor_ruled_out"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
