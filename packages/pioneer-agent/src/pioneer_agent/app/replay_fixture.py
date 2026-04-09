from __future__ import annotations

import argparse
import json
from pathlib import Path

from pioneer_agent.core.runtime_state_io import load_runtime_state_record, write_runtime_state_fixture
from pioneer_agent.runtime.replay_runtime import ReplayRuntime


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay one or more runtime state fixtures.")
    parser.add_argument(
        "--fixture",
        action="append",
        default=[],
        help="Fixture path to replay. Repeat the flag to replay multiple fixtures.",
    )
    parser.add_argument(
        "--from-log",
        default="",
        help="Optional state.jsonl path. When provided, replay the selected record from this log instead of fixture files.",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=-1,
        help="Record index used with --from-log. Use -1 for the latest line.",
    )
    parser.add_argument(
        "--write-fixture",
        default="",
        help="Optional output path. When replaying from a log, also export the selected state as a replay fixture.",
    )
    return parser


def _resolve_path(project_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (project_root / candidate).resolve()


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    runtime = ReplayRuntime()

    if args.from_log:
        log_path = _resolve_path(project_root, args.from_log)
        record = load_runtime_state_record(log_path, args.index)
        if args.write_fixture:
            write_runtime_state_fixture(record.state, _resolve_path(project_root, args.write_fixture))
        record_label = f"{log_path}::record[{record.record_index if record.record_index is not None else 0}]"
        results = [runtime.run_state(record.state, record_label)]
    else:
        if args.fixture:
            fixture_paths = [_resolve_path(project_root, value) for value in args.fixture]
        else:
            fixture_dir = project_root / "tests" / "fixtures"
            fixture_paths = [path for path in sorted(fixture_dir.glob("*.json")) if not path.name.startswith("template_")]
        results = [runtime.run_fixture(path) for path in fixture_paths]

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
