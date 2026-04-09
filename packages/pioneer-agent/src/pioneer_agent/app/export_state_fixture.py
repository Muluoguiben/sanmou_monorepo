from __future__ import annotations

import argparse
from pathlib import Path

from pioneer_agent.core.runtime_state_io import dump_runtime_state_json, load_runtime_state_record, write_runtime_state_fixture


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract one runtime state snapshot from a state log or JSON file.")
    parser.add_argument(
        "--input",
        default="data/agent_runs/bootstrap_logs/state.jsonl",
        help="Path to a state.jsonl, JSONL replay log, or runtime state JSON file.",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=-1,
        help="Zero-based record index. Use -1 for the latest record.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output path for the extracted fixture JSON. If omitted, prints to stdout.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    try:
        record = load_runtime_state_record(input_path, args.index)
    except (OSError, ValueError, IndexError) as exc:
        raise SystemExit(str(exc)) from exc

    rendered = dump_runtime_state_json(record.state)

    if args.output:
        output_path = write_runtime_state_fixture(record.state, Path(args.output))
        print(f"Exported fixture to: {output_path}")
        return

    print(rendered)


if __name__ == "__main__":
    main()
