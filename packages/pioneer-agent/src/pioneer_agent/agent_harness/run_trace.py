"""Secret-minimal run trace sinks; transport success never implies validity."""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .task_contracts import TraceEvent
from .tool_log import summarize_arguments


_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:@+-]{1,160}\Z")
_VERSION_KEYS = frozenset({"policy_id", "policy_version", "model_id", "model_version",
                           "prompt_version", "skill_version", "kb_version"})


def _identifier(value: str) -> str:
    if _IDENTIFIER.fullmatch(value):
        return value
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_event(event: TraceEvent) -> TraceEvent:
    event = TraceEvent.model_validate(event.model_dump(mode="json"))
    if event.contract == "ok" and event.transport != "ok":
        raise ValueError("contract_ok_requires_transport_ok")
    # Scalar fields are identifier/classification slots, never free-form messages.
    for field in ("run_id", "step_id", "event", "name", "attempt_id", "observation_id",
                  "business", "error_type"):
        value = getattr(event, field)
        if value is not None:
            setattr(event, field, _identifier(value))
    event.evidence_refs = [_identifier(ref) for ref in event.evidence_refs]
    safe = summarize_arguments(event.metadata)
    for key in _VERSION_KEYS:
        value = event.metadata.get(key)
        if isinstance(value, str):
            safe[key] = _identifier(value)
    event.metadata = safe
    return event


class InMemoryRunTrace:
    def __init__(self) -> None:
        self._events: list[TraceEvent] = []
        self._lock = threading.RLock()

    @property
    def events(self) -> list[TraceEvent]:
        with self._lock:
            return [event.model_copy(deep=True) for event in self._events]

    def emit(self, event: TraceEvent) -> None:
        with self._lock:
            self._events.append(_safe_event(event))


class JsonlRunTrace:
    """One in-process sink per file; no cross-process writer/lease guarantee."""
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def emit(self, event: TraceEvent) -> None:
        safe = _safe_event(event)
        record = {"trace_version": 1, "event_id": uuid4().hex,
                  "emitted_at": datetime.now(UTC).isoformat(),
                  "trace_id": safe.run_id, **safe.model_dump(mode="json")}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
