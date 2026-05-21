from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_nep2_provenance import (
    build_nep2_provenance_closure_batch,
    write_nep2_provenance_closure_batch,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized NEP2 provenance closure artifacts into a qa-agent evidence batch."
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing NEP2 provenance JSON artifacts.")
    parser.add_argument("--output", required=True, help="YAML evidence output path.")
    parser.add_argument("--source-id", default="nep2-provenance-closures")
    parser.add_argument("--analysis-log", default=None, help="Optional nslg_local_data_analysis.md path.")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    batch = build_nep2_provenance_closure_batch(
        input_dir=Path(args.input_dir),
        source_id=args.source_id,
        analysis_log_path=Path(args.analysis_log) if args.analysis_log else None,
    )
    write_nep2_provenance_closure_batch(batch, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": batch.source_id,
                "artifact_count": batch.artifact_count,
                "round_range": batch.round_range,
                "closure_status_counts": batch.closure_status_counts,
                "next_unclosed_shape_lead": batch.next_unclosed_shape_lead,
                "safe_for_publish": batch.route_conclusion.get("safe_for_publish"),
                "publishable_knowledge_entries": batch.route_conclusion.get(
                    "publishable_knowledge_entries"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
