from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_luascripts_variant_corpus import (
    build_luascripts_payload_variant_corpus_report,
    write_luascripts_payload_variant_corpus_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized LuaScripts payload variant corpus evidence."
    )
    parser.add_argument("--input", required=True, help="Round172 LuaScripts variant corpus JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="luascripts-payload-variant-corpus-round79")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_luascripts_payload_variant_corpus_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_luascripts_payload_variant_corpus_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "payload_variant_count": report.corpus_summary.get("payload_variant_count"),
                "unique_ciphertext_hash_count": report.corpus_summary.get(
                    "unique_ciphertext_hash_count"
                ),
                "simple_offset_skip_route_ruled_out": report.route_conclusion.get(
                    "simple_offset_skip_route_ruled_out"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
