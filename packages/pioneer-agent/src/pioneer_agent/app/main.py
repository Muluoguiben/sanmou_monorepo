from __future__ import annotations

import argparse
from pathlib import Path

from pioneer_agent.app.bootstrap import build_runtime


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one Sanguo agent sync-plan-execute cycle.")
    parser.add_argument(
        "--sync-input",
        default="data/perception/latest_state.json",
        help="Path to a runtime state JSON/JSONL file or a perception directory.",
    )
    parser.add_argument(
        "--log-dir",
        default="data/agent_runs/bootstrap_logs",
        help="Directory used to append sync/state/selection/execution logs.",
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
    sync_input = _resolve_path(project_root, args.sync_input)
    log_dir = _resolve_path(project_root, args.log_dir)
    runtime = build_runtime(project_root, sync_input=sync_input, log_dir=log_dir)
    runtime.run_once()
    print(f"Sanguo agent run completed. Sync input: {sync_input}")
    print(f"Logs appended under: {log_dir}")


if __name__ == "__main__":
    main()
