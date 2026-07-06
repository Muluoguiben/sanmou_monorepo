"""Persist the runbook cursor and human-gate confirmations across restarts.

A small JSON file next to the loop logs holds `current_phase_id` and
`confirmed_gates`. The file doubles as the operator confirmation channel:
`python -m pioneer_agent.app.runbook_gate confirm <phase_id>` (or a careful
manual edit) records approval, and the running loop picks it up on the next
tick without restarting.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from pioneer_agent.runbook.engine import RunbookEngine
from pioneer_agent.runbook.models import OpeningRunbook

logger = logging.getLogger(__name__)


@dataclass
class RunbookStateRecord:
    current_phase_id: str | None = None
    confirmed_gates: set[str] = field(default_factory=set)


class RunbookStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> RunbookStateRecord:
        if not self.path.exists():
            return RunbookStateRecord()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("runbook state file unreadable, starting fresh: %s", self.path)
            return RunbookStateRecord()
        if not isinstance(payload, dict):
            logger.warning("runbook state file malformed, starting fresh: %s", self.path)
            return RunbookStateRecord()
        current = payload.get("current_phase_id")
        gates = payload.get("confirmed_gates", [])
        return RunbookStateRecord(
            current_phase_id=current if isinstance(current, str) else None,
            confirmed_gates={g for g in gates if isinstance(g, str)} if isinstance(gates, list) else set(),
        )

    def save(self, *, current_phase_id: str | None, confirmed_gates: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_phase_id": current_phase_id,
            "confirmed_gates": sorted(confirmed_gates),
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def confirm_gate(self, phase_id: str) -> RunbookStateRecord:
        record = self.load()
        record.confirmed_gates.add(phase_id)
        self.save(
            current_phase_id=record.current_phase_id,
            confirmed_gates=record.confirmed_gates,
        )
        return record


def build_engine_from_store(runbook: OpeningRunbook, store: RunbookStateStore) -> RunbookEngine:
    """Resume the engine from a persisted cursor; fall back to a fresh start
    when the stored phase no longer exists (e.g. after a season swap)."""
    record = store.load()
    start_phase_id = record.current_phase_id
    if start_phase_id is not None:
        try:
            runbook.phase_index(start_phase_id)
        except KeyError:
            logger.warning(
                "stored runbook phase %r not in runbook for season %r — starting from the first phase",
                start_phase_id,
                runbook.season,
            )
            start_phase_id = None
    known_gates = {phase.phase_id for phase in runbook.phases}
    stale_gates = record.confirmed_gates - known_gates
    if stale_gates:
        logger.warning("dropping confirmed gates unknown to this runbook: %s", sorted(stale_gates))
    return RunbookEngine(
        runbook,
        start_phase_id=start_phase_id,
        confirmed_gates=record.confirmed_gates & known_gates,
    )
