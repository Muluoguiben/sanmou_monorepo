from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_native_boundary_trace import (
    build_native_loadbuffer_boundary_trace_report,
    write_native_loadbuffer_boundary_trace_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize sanitized native loadbuffer boundary evidence for qa-agent import planning."
    )
    parser.add_argument("--input", required=True, help="Round163 native loadbuffer boundary JSON artifact.")
    parser.add_argument("--output", required=True, help="YAML output path.")
    parser.add_argument("--source-id", default="native-loadbuffer-boundary")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    report = build_native_loadbuffer_boundary_trace_report(
        input_path=Path(args.input),
        source_id=args.source_id,
    )
    write_native_loadbuffer_boundary_trace_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": report.source_id,
                "round": report.round,
                "module_count": report.counts.get("module_count"),
                "loadbuffer_export_signal_count": report.counts.get(
                    "loadbuffer_export_signal_count"
                ),
                "gameassembly_static_xlua_import_present": report.route_conclusion.get(
                    "gameassembly_static_xlua_import_present"
                ),
                "textasset_to_loadbuffer_owner_proven": report.route_conclusion.get(
                    "textasset_to_loadbuffer_owner_proven"
                ),
                "safe_for_publish": report.route_conclusion.get("safe_for_publish"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
