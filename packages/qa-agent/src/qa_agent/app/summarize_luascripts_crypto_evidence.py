from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_lua_crypto import (
    build_lua_crypto_evidence_report,
    load_lua_crypto_evidence,
    write_lua_crypto_evidence_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sanitize NSLG LuaScripts crypto/decode evidence into qa-agent ingestion evidence."
    )
    parser.add_argument("--input", required=True, help="Path to luascripts_decryptor_evidence_round32.json-like input.")
    parser.add_argument("--output", required=True, help="YAML evidence output path.")
    parser.add_argument("--source-id", default="luascripts-crypto-round32", help="Stable source id for this report.")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    evidence = load_lua_crypto_evidence(Path(args.input))
    report = build_lua_crypto_evidence_report(evidence, source_id=args.source_id)
    write_lua_crypto_evidence_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": args.source_id,
                "binary_summaries": len(report.binary_string_hits),
                "payload_samples": len(report.payload_block_samples),
                "payload_status_counts": report.payload_status_counts,
                "runtime_lua_entries": len(report.runtime_initialize_lua_entries),
                "skipped_runtime_patch_samples": report.skipped_runtime_patch_samples,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
