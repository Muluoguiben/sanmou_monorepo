from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_nep2_bridge import (
    build_nep2_init_bridge_report,
    write_nep2_init_bridge_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized NEP2 InitLuaScriptsScan bridge evidence for qa-agent import planning."
    )
    parser.add_argument("--input", required=True, help="Round161 NEP2 InitLuaScriptsScan bridge JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="nep2-init-bridge")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_nep2_init_bridge_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_nep2_init_bridge_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "bridge_record_count": report.counts.get("bridge_record_count"),
                "candidate_function_count": report.counts.get("candidate_function_count"),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
                "decryptor_body_proven": report.route_conclusion.get("decryptor_body_proven"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
