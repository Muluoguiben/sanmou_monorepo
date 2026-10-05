"""Atomic, version-checked task checkpoints for a single owning runner."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from pioneer_agent.agent_harness.task_contracts import RunState


class RunStore(Protocol):
    def load(self) -> RunState | None: ...
    def save(self, state: RunState) -> None: ...


class JsonRunStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> RunState | None:
        if not self.path.exists():
            return None
        return RunState.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, state: RunState) -> None:
        state = RunState.model_validate(state.model_dump())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8") as handle:
                handle.write(state.model_dump_json(indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)


class MemoryRunStore:
    def __init__(self):
        self.state: RunState | None = None

    def load(self) -> RunState | None:
        return self.state.model_copy(deep=True) if self.state else None

    def save(self, state: RunState) -> None:
        self.state = RunState.model_validate(state.model_dump())
