"""Cooperative local checkpoint ownership and conditional atomic replacement."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol
from threading import Lock, RLock
from uuid import uuid4

from pioneer_agent.agent_harness._checkpoint_lock import LocalLock
from pioneer_agent.agent_harness.task_contracts import CheckpointEnvelope, RunState, TERMINAL_STATUSES


class CheckpointConflict(RuntimeError):
    """Ownership or CAS lost. Never convert this into a checkpoint write."""


class RunStore(Protocol):
    def acquire(self) -> RunOwnership: ...


class RunOwnership:
    """One non-transferable, process-bound lifetime; revisions are not schema versions."""

    def __init__(self, store, release):
        self.store = store
        self.owner_id = uuid4().hex
        self.pid = os.getpid()
        self.revision = 0
        self._release = release
        self.active = True
        self._loaded = False
        self._identity = None
        self._prior_owner = None
        self._runner = None
        self._mutex = RLock()
        self._released = False

    def __enter__(self):
        self.check()
        return self

    def __exit__(self, *args):
        self.close()

    def check(self):
        if self._released or not self.active or self.pid != os.getpid() or self.store._owner is not self:
            raise CheckpointConflict("inactive checkpoint owner")

    def close(self):
        if self.pid != os.getpid():
            return  # Never unlock the parent's inherited flock after fork.
        with self._mutex:
            if self._released:
                return
            if self.store._owner is not self:
                raise CheckpointConflict("cannot release a foreign checkpoint owner")
            if self._runner is not None and getattr(self._runner, "_active", False):
                raise RuntimeError("cannot release an active runner; cancel and await it")
            # This serialized transition revokes authorization before teardown;
            # check() consults it even before the public active flag is updated.
            self._released = True
            self.store._owner = None
            self._release()
        self.active = False

    def bind_runner(self, runner):
        self.check()
        with self._mutex:
            self.check()
            if self._runner is not None and self._runner is not runner:
                raise CheckpointConflict("checkpoint owner already bound to a runner")
            self._runner = runner

    def load(self) -> RunState | None:
        self.check()
        with self._mutex:
            return self._load_owned()

    def _load_owned(self) -> RunState | None:
        self.check()
        state, revision, prior_owner = self.store._read()
        if self._loaded and (revision, prior_owner) != (self.revision, self._prior_owner):
            raise CheckpointConflict("checkpoint revision changed")
        self.revision, self._prior_owner = revision, prior_owner
        self._identity = (state.run_id, state.task.model_dump()) if state else None
        self._loaded = True
        return state

    def save(self, state: RunState):
        self.store.save(state, owner=self, expected_revision=self.revision)


class _ConditionalStore:
    _owner: RunOwnership | None = None

    def load(self) -> RunState | None:
        """Read-only snapshot; runner and CLI use their explicitly owned load."""
        if self._owner is not None:
            return self._owner.load()
        with self.acquire() as owner:
            return owner.load()

    def save(self, state: RunState, *, owner: RunOwnership, expected_revision: int):
        owner.check()
        with owner._mutex:
            return self._save_owned(state, owner=owner, expected_revision=expected_revision)

    def _save_owned(self, state: RunState, *, owner: RunOwnership, expected_revision: int):
        owner.check()
        if owner.store is not self or not owner._loaded:
            raise CheckpointConflict("checkpoint must be loaded by its owner")
        if type(expected_revision) is not int or expected_revision != owner.revision:
            raise CheckpointConflict("stale checkpoint revision")
        state = RunState.model_validate(state.model_dump())
        prior, revision, prior_owner = self._read()
        if (revision, prior_owner) != (owner.revision, owner._prior_owner):
            raise CheckpointConflict("checkpoint revision changed")
        identity = (state.run_id, state.task.model_dump())
        if owner._identity is not None and identity != owner._identity:
            raise CheckpointConflict("checkpoint identity/task mismatch")
        if prior and (prior.run_id, prior.task.model_dump()) != identity:
            raise CheckpointConflict("checkpoint identity/task mismatch")
        if prior and prior.status in TERMINAL_STATUSES and state.status != prior.status:
            raise CheckpointConflict("terminal checkpoint cannot resume")
        envelope = CheckpointEnvelope(revision=revision + 1, owner_id=owner.owner_id, state=state)
        self._write(envelope)
        owner.revision = envelope.revision
        owner._prior_owner = owner.owner_id
        owner._identity = identity


class JsonRunStore(_ConditionalStore):
    def __init__(self, path: Path):
        self.path = Path(os.path.abspath(path))
        self._owner = None

    def acquire(self) -> RunOwnership:
        if self._owner is not None:
            raise CheckpointConflict("checkpoint already owned")
        lock = LocalLock(self.path)
        try:
            lock.acquire()
        except BlockingIOError:
            raise CheckpointConflict("checkpoint already owned") from None
        self._owner = RunOwnership(self, lock.close)
        return self._owner

    def _read(self):
        LocalLock.validate_file(self.path)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None, 0, None
        if isinstance(raw, dict) and "storage_version" in raw:
            if type(raw["storage_version"]) is not int:
                raise ValueError("unsupported checkpoint storage version")
            envelope = CheckpointEnvelope.model_validate(raw)
            return envelope.state, envelope.revision, envelope.owner_id
        if not isinstance(raw, dict) or type(raw.get("version")) is not int or raw["version"] != 1:
            raise ValueError("unsupported checkpoint format")
        return RunState.model_validate(raw), 0, None

    def _write(self, envelope):
        temporary = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(envelope.model_dump_json(indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
            if os.name == "posix":
                fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        finally:
            temporary.unlink(missing_ok=True)


class MemoryRunStore(_ConditionalStore):
    def __init__(self):
        self._envelope: CheckpointEnvelope | None = None
        self._lock = Lock()
        self._owner = None

    def acquire(self):
        if not self._lock.acquire(blocking=False):
            raise CheckpointConflict("checkpoint already owned")
        self._owner = RunOwnership(self, self._lock.release)
        return self._owner

    def _read(self):
        item = self._envelope
        return (item.state.model_copy(deep=True), item.revision, item.owner_id) if item else (None, 0, None)

    def _write(self, envelope):
        self._envelope = envelope.model_copy(deep=True)
