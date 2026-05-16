from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pioneer_agent.core.runtime_state_io import load_runtime_state_record
from pioneer_agent.runtime.replay_runtime import ReplayRuntime


@dataclass(frozen=True)
class GoldenReplayResult:
    matched: bool
    expected_action_type: str | None
    actual_action_type: str | None
    screenshot_paths: tuple[str, ...]
    replay: dict[str, Any]


class GoldenReplayRunner:
    def __init__(self, replay_runtime: ReplayRuntime | None = None) -> None:
        self.replay_runtime = replay_runtime or ReplayRuntime()

    def run(
        self,
        *,
        log_dir: Path,
        state_fixture: Path,
        record_index: int = 0,
    ) -> GoldenReplayResult:
        records = _read_loop_records(log_dir / "loop.jsonl")
        if record_index >= len(records):
            raise IndexError(f"loop record index out of range: {record_index}")

        screenshot_paths = tuple(
            str(_resolve_existing_screenshot(log_dir, item["screenshot_path"]))
            for item in records
            if item.get("screenshot_path")
        )
        expected_action_type = records[record_index].get("selected_action_type")
        state_record = load_runtime_state_record(state_fixture)
        replay = self.replay_runtime.run_state(state_record.state, str(state_fixture))
        selected = replay.get("selected_action") or {}
        actual_action_type = selected.get("action_type")
        return GoldenReplayResult(
            matched=expected_action_type == actual_action_type,
            expected_action_type=expected_action_type,
            actual_action_type=actual_action_type,
            screenshot_paths=screenshot_paths,
            replay=replay,
        )


def _read_loop_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"loop log not found: {path}")
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    if not records:
        raise ValueError(f"loop log is empty: {path}")
    return records


def _resolve_existing_screenshot(log_dir: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = log_dir / path
    if not path.exists():
        raise FileNotFoundError(f"loop screenshot not found: {path}")
    return path
