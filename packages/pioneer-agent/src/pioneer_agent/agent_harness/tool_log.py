"""Bounded, secret-safe JSONL logging for MCP calls."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


_SECRET_PARTS = ("authorization", "cookie", "password", "secret", "token", "api_key", "apikey")
_BINARY_PARTS = ("image", "screenshot", "frame", "bytes", "base64", "content")
_REFERENCE_KEYS = {
    "session_id",
    "observation_id",
    "trace_id",
    "frame_sha256",
    "execution_authority",
    "status",
    "action_id",
    "action_type",
    "confidence",
}


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    call_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime
    tool_name: str
    arguments_summary: dict[str, Any]
    result_summary: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = Field(ge=0.0)
    success: bool
    error_type: str | None = None
    observation_refs: list[str] = Field(default_factory=list)
    trace_refs: list[str] = Field(default_factory=list)
    model_id: str
    agent_session_id: str
    game_session_id: str | None = None

    @field_validator("started_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("tool calls require timezone-aware timestamps")
        return value


class ToolLog(Protocol):
    def append(self, record: ToolCallRecord) -> ToolCallRecord: ...


class JsonlToolLog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: ToolCallRecord) -> ToolCallRecord:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json(exclude_none=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return record

    def read(self) -> list[ToolCallRecord]:
        if not self.path.exists():
            return []
        records: list[ToolCallRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    records.append(ToolCallRecord.model_validate_json(line))
        return records


class InMemoryToolLog:
    def __init__(self) -> None:
        self.records: list[ToolCallRecord] = []

    def append(self, record: ToolCallRecord) -> ToolCallRecord:
        self.records.append(record)
        return record


def summarize_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _safe_value(str(key), value) for key, value in sorted(arguments.items())}


def summarize_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"keys": sorted(str(key) for key in payload.keys())[:40]}
    for key in _REFERENCE_KEYS:
        value = payload.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            if value is not None:
                summary[key] = value
    for key in ("domains_run", "unknown_domains", "blockers"):
        value = payload.get(key)
        if isinstance(value, list):
            summary[key] = [str(item)[:80] for item in value[:20]]
    for key in ("candidates", "ranked_actions", "proposals", "items", "entries"):
        value = payload.get(key)
        if isinstance(value, list):
            summary[f"{key}_count"] = len(value)
    observation = _observation_payload(payload)
    if observation is not None:
        for key in ("session_id", "observation_id", "frame_sha256", "confidence"):
            value = observation.get(key)
            if isinstance(value, (str, int, float, bool)):
                summary[key] = value
        for key in ("domains_run", "unknown_domains"):
            value = observation.get(key)
            if isinstance(value, list):
                summary[key] = [str(item)[:80] for item in value[:20]]
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        summary["candidates_count"] = len(candidates)
    return summary


def extract_refs(payload: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    observation_refs: list[str] = []
    trace_refs: list[str] = []
    observation = _observation_payload(payload) or payload
    for key in ("observation_id", "frame_sha256"):
        value = observation.get(key)
        if isinstance(value, str) and value:
            observation_refs.append(f"{key}:{value}")
    for key in ("trace_id", "trace_ref"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            trace_refs.append(f"{key}:{value}")
    return observation_refs, trace_refs


def _observation_payload(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("observation", "latest_observation"):
        value = payload.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _safe_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(part in lowered for part in _SECRET_PARTS):
        return "<redacted>"
    if any(part in lowered for part in _BINARY_PARTS):
        return _omitted(value)
    if isinstance(value, str):
        return {"type": "string", "length": len(value), "sha256": _digest(value.encode("utf-8"))}
    if isinstance(value, bytes):
        return {"type": "bytes", "length": len(value), "sha256": _digest(value)}
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(child): _safe_value(str(child), item) for child, item in list(value.items())[:20]}
    if isinstance(value, Sequence):
        return {"type": "sequence", "length": len(value)}
    return {"type": type(value).__name__}


def _omitted(value: Any) -> dict[str, Any]:
    length = len(value) if hasattr(value, "__len__") else None
    result: dict[str, Any] = {"type": type(value).__name__, "omitted": True}
    if isinstance(length, int):
        result["length"] = length
    return result


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
