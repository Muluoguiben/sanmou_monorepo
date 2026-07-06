"""Persist the runbook cursor and human-gate confirmations across restarts.

Two files with a single-writer rule each, so the loop and the operator CLI
can never clobber each other:

- ``<state>.json`` — loop-owned: ``current_phase_id``, ``completed``, and the
  gates the engine has applied. Written atomically (temp file + ``os.replace``)
  so a crash mid-write cannot leave a torn file.
- ``<state>.json.confirmations.jsonl`` — operator-owned, append-only: one JSON
  line per human-gate confirmation from ``pioneer_agent.app.runbook_gate
  confirm`` (or a careful manual append). The loop only ever reads this file,
  so a confirmation cannot be lost to a concurrent loop save; the running loop
  picks it up on its next tick without a restart.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pioneer_agent.runbook.engine import RunbookEngine
from pioneer_agent.runbook.models import OpeningRunbook

logger = logging.getLogger(__name__)


@dataclass
class RunbookStateRecord:
    current_phase_id: str | None = None
    confirmed_gates: set[str] = field(default_factory=set)
    completed: bool = False
    season: str | None = None


class RunbookStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.confirmations_path = path.with_name(path.name + ".confirmations.jsonl")
        self._confirmations_cache: list[tuple[str, str | None]] = []
        self._confirmations_signature: tuple[int, int] | None = None
        self._confirmations_cached = False

    def load(self, *, expected_season: str | None = None) -> RunbookStateRecord:
        """Cursor, completion, and gate approvals are only valid for the runbook
        that produced them: a state file stamped with a different season is
        discarded (phase IDs like `er_tuo_yi` recur every season, so ID
        existence alone must never authorize a resume). Records without a
        season stamp are accepted as legacy."""
        record = self._load_state_file()
        if (
            expected_season is not None
            and record.season is not None
            and record.season != expected_season
        ):
            logger.warning(
                "runbook state file %s belongs to season %r but the active season is %r "
                "— ignoring its cursor, completion, and gates",
                self.path,
                record.season,
                expected_season,
            )
            record = RunbookStateRecord(season=expected_season)
        record.confirmed_gates |= self.read_confirmations(expected_season=expected_season)
        return record

    def _load_state_file(self) -> RunbookStateRecord:
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
        season = payload.get("season")
        return RunbookStateRecord(
            current_phase_id=current if isinstance(current, str) else None,
            confirmed_gates={g for g in gates if isinstance(g, str)} if isinstance(gates, list) else set(),
            completed=payload.get("completed") is True,
            season=season if isinstance(season, str) else None,
        )

    def save(
        self,
        *,
        current_phase_id: str | None,
        confirmed_gates: set[str],
        completed: bool = False,
        season: str | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "current_phase_id": current_phase_id,
            "confirmed_gates": sorted(confirmed_gates),
            "completed": completed,
            "season": season,
        }
        tmp_path = self.path.with_name(self.path.name + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(tmp_path, self.path)

    def confirm_gate(
        self,
        phase_id: str,
        *,
        confirmed_by: str | None = None,
        season: str | None = None,
    ) -> RunbookStateRecord:
        """Operator channel: append-only, never touches the loop-owned state file.
        Stamp the season whenever it is known — unstamped confirmations are
        accepted as legacy and would leak into a future season's runbook."""
        self.confirmations_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "phase_id": phase_id,
            "confirmed_at": datetime.now().isoformat(timespec="seconds"),
        }
        if confirmed_by:
            entry["confirmed_by"] = confirmed_by
        if season:
            entry["season"] = season
        with self.confirmations_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._confirmations_cached = False
        return self.load(expected_season=season)

    def read_confirmations(self, *, expected_season: str | None = None) -> set[str]:
        """Confirmed gate ids from the operator channel, mtime/size-cached so the
        per-tick poll is a stat() in the steady state, not a read+parse.
        Entries stamped with a different season are ignored; unstamped entries
        are accepted as legacy."""
        entries = self._read_confirmation_entries()
        gates: set[str] = set()
        for phase_id, season in entries:
            if expected_season is not None and season is not None and season != expected_season:
                continue
            gates.add(phase_id)
        return gates

    def _read_confirmation_entries(self) -> list[tuple[str, str | None]]:
        try:
            stat = self.confirmations_path.stat()
        except FileNotFoundError:
            self._confirmations_cache = []
            self._confirmations_signature = None
            self._confirmations_cached = True
            return []
        signature = (stat.st_mtime_ns, stat.st_size)
        if self._confirmations_cached and signature == self._confirmations_signature:
            return list(self._confirmations_cache)

        entries: list[tuple[str, str | None]] = []
        try:
            lines = self.confirmations_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            logger.warning("runbook confirmations file unreadable: %s", self.confirmations_path)
            return list(self._confirmations_cache)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("skipping malformed confirmation line in %s: %r", self.confirmations_path, line[:80])
                continue
            phase_id = entry.get("phase_id") if isinstance(entry, dict) else None
            if not isinstance(phase_id, str):
                continue
            season = entry.get("season")
            entries.append((phase_id, season if isinstance(season, str) else None))
        self._confirmations_cache = entries
        self._confirmations_signature = signature
        self._confirmations_cached = True
        return list(entries)


def build_engine_from_store(runbook: OpeningRunbook, store: RunbookStateStore) -> RunbookEngine:
    """Resume the engine from a persisted cursor. Resume requires the stored
    season to match the active runbook (phase IDs recur across seasons, so ID
    existence alone must not authorize a resume); a mismatch or an unknown
    phase falls back to a fresh start."""
    record = store.load(expected_season=runbook.season)
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
            record.completed = False
    known_gates = {phase.phase_id for phase in runbook.phases}
    stale_gates = record.confirmed_gates - known_gates
    if stale_gates:
        logger.warning("dropping confirmed gates unknown to this runbook: %s", sorted(stale_gates))
    return RunbookEngine(
        runbook,
        start_phase_id=start_phase_id,
        confirmed_gates=record.confirmed_gates & known_gates,
        completed=record.completed,
    )
