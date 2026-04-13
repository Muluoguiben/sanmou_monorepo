"""Per-tick observability for the autonomous loop.

Writes one JSONL record per tick to `<log_dir>/loop.jsonl` and optionally
archives the screenshot PNG to `<log_dir>/screenshots/<ts>-<iter>.png`.
Keeps the raw data needed to replay a loop run or diagnose why a decision
was made — indispensable for calibrating the clickable action handlers.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import ExecutionResult, SelectionResult
from pioneer_agent.perception.vision_sync import VisionSyncSummary


@dataclass
class TickRecord:
    iteration: int
    started_at: str
    elapsed_s: float
    screenshot_bytes: int
    screenshot_path: str | None
    page_type: str | None
    domains_run: list[str]
    notes: list[str]
    selected_action_type: str | None
    selected_action_id: str | None
    selected_action_params: dict[str, Any] = field(default_factory=dict)
    execution_status: str | None = None
    execution_failure_reason: str | None = None
    sleep_s: float = 0.0


class LoopLogger:
    def __init__(self, log_dir: Path, *, archive_screenshots: bool = True) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.log_dir / "loop.jsonl"
        self.archive_screenshots = archive_screenshots
        if archive_screenshots:
            (self.log_dir / "screenshots").mkdir(exist_ok=True)

    def archive_screenshot(self, png: bytes, iteration: int, ts: datetime) -> Path | None:
        if not self.archive_screenshots:
            return None
        stamp = ts.strftime("%Y%m%dT%H%M%S")
        path = self.log_dir / "screenshots" / f"{stamp}-{iteration:04d}.png"
        path.write_bytes(png)
        return path

    def log_tick(
        self,
        *,
        iteration: int,
        started_at: datetime,
        elapsed_s: float,
        png: bytes,
        vision_summary: VisionSyncSummary,
        selection: SelectionResult,
        execution: ExecutionResult | None,
        sleep_s: float,
    ) -> TickRecord:
        screenshot_path = self.archive_screenshot(png, iteration, started_at)
        action = selection.selected_action
        record = TickRecord(
            iteration=iteration,
            started_at=started_at.isoformat(),
            elapsed_s=round(elapsed_s, 3),
            screenshot_bytes=len(png),
            screenshot_path=str(screenshot_path) if screenshot_path else None,
            page_type=vision_summary.page_type,
            domains_run=list(vision_summary.domains_run),
            notes=list(vision_summary.notes)[:10],
            selected_action_type=action.action_type.value if action else None,
            selected_action_id=action.action_id if action else None,
            selected_action_params=dict(action.params) if action else {},
            execution_status=execution.status if execution else None,
            execution_failure_reason=execution.failure_reason if execution else None,
            sleep_s=sleep_s,
        )
        with self.jsonl_path.open("a", encoding="utf-8") as h:
            h.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        return record
