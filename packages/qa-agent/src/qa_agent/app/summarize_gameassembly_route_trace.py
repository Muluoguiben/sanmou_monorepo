from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_gameassembly_trace import (
    build_gameassembly_route_trace_batch,
    write_gameassembly_route_trace_batch,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized GameAssembly static route traces for qa-agent import planning."
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing external GameAssembly JSON artifacts.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="gameassembly-route-trace")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    batch = build_gameassembly_route_trace_batch(
        input_dir=Path(args.input_dir),
        source_id=args.source_id,
    )
    write_gameassembly_route_trace_batch(batch, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": batch.source_id,
                "artifact_count": batch.artifact_count,
                "round_range": batch.round_range,
                "status_counts": batch.status_counts,
                "route_signal_record_count": batch.route_signal_record_count,
                "total_target_strings": batch.total_target_strings,
                "total_code_refs": batch.total_code_refs,
                "safe_for_publish": batch.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
