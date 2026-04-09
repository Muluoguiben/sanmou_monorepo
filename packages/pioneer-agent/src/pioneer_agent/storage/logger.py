from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pioneer_agent.core.models import ExecutionResult, SelectionResult
from pioneer_agent.perception.sync_service import SyncSummary


class AgentLogger:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _append_jsonl(self, filename: str, payload: dict) -> None:
        path = self.log_dir / filename
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def log_sync_summary(self, session_id: str, summary: SyncSummary) -> None:
        self._append_jsonl(
            "sync.jsonl",
            {
                "session_id": session_id,
                "created_at": datetime.utcnow().isoformat(),
                "mode": summary.mode,
                "domains_refreshed": summary.domains_refreshed,
                "warnings": summary.warnings,
                "source_path": summary.source_path,
                "captured_at": summary.captured_at,
                "record_index": summary.record_index,
                "non_empty_state": summary.non_empty_state,
            },
        )

    def log_selection(self, session_id: str, result: SelectionResult) -> None:
        self._append_jsonl(
            "selection.jsonl",
            {
                "session_id": session_id,
                "created_at": datetime.utcnow().isoformat(),
                "selected_action": result.selected_action.model_dump(mode="json") if result.selected_action else None,
                "ranked_actions": [action.model_dump(mode="json") for action in result.ranked_actions],
                "selection_reason": result.selection_reason,
                "next_replan_time": result.next_replan_time.isoformat() if result.next_replan_time else None,
            },
        )

    def log_execution(self, session_id: str, execution: ExecutionResult) -> None:
        self._append_jsonl(
            "execution.jsonl",
            {
                "session_id": session_id,
                "created_at": datetime.utcnow().isoformat(),
                **execution.model_dump(),
            },
        )

    def log_runtime_state(self, session_id: str, state: dict, sync_summary: SyncSummary | None = None) -> None:
        payload = {
            "session_id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "state": state,
        }
        if sync_summary is not None:
            payload["sync"] = {
                "mode": sync_summary.mode,
                "domains_refreshed": sync_summary.domains_refreshed,
                "warnings": sync_summary.warnings,
                "source_path": sync_summary.source_path,
                "captured_at": sync_summary.captured_at,
                "record_index": sync_summary.record_index,
                "non_empty_state": sync_summary.non_empty_state,
            }
        self._append_jsonl("state.jsonl", payload)
