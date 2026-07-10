"""Structured JSONL trace records for autonomous-loop ticks."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from pioneer_agent.core.models import ObservationSnapshot


class TracePhase(str, Enum):
    OBSERVE = "observe"
    DECIDE = "decide"
    ACT = "act"
    VERIFY = "verify"
    TRACE = "trace"
    RECOVER = "recover"


class TraceFrameRole(str, Enum):
    PRE_ACTION = "pre_action"
    TERMINAL_DISPATCH = "terminal_dispatch"
    POST_ACTION = "post_action"


class ImageSize(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class PixelPoint(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class PixelBBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class NormalizedBBox(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(ge=0.0, le=1.0)
    height: float = Field(ge=0.0, le=1.0)


class CoordinateTraceMetadata(BaseModel):
    coordinate_space: str | None = None
    dpr: float | None = Field(default=None, gt=0.0)
    scale: float | None = Field(default=None, gt=0.0)
    normalized_bbox: NormalizedBBox | None = None
    pixel_bbox: PixelBBox | None = None
    click_point: PixelPoint | None = None


class ScreenshotTraceMetadata(BaseModel):
    path: str | None = None
    raw_size: ImageSize | None = None
    prepared_size: ImageSize | None = None
    display_coordinate_space: str | None = None
    window_coordinate_space: str | None = None
    coordinates: list[CoordinateTraceMetadata] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceFrameReference(BaseModel):
    role: TraceFrameRole
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation: dict[str, Any]
    attempt: int | None = Field(default=None, ge=1)

    @field_validator("observation")
    @classmethod
    def _validate_observation(cls, value: dict[str, Any]) -> dict[str, Any]:
        captured_at = value.get("captured_at")
        if not isinstance(captured_at, str):
            raise ValueError("trace frame observation requires captured_at")
        parsed = datetime.fromisoformat(captured_at)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("trace frame captured_at must be timezone-aware")
        for field_name in ("observation_id", "frame_sha256"):
            if not isinstance(value.get(field_name), str) or not value[field_name]:
                raise ValueError(f"trace frame observation requires {field_name}")
        return value

    @model_validator(mode="after")
    def _validate_sha_binding(self) -> TraceFrameReference:
        if self.sha256 != self.observation.get("frame_sha256"):
            raise ValueError("trace frame SHA must match its observation")
        return self


class TraceStep(BaseModel):
    phase: TracePhase
    started_at: datetime | None = None
    ended_at: datetime | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    failure_reason: str | None = None
    recovery_strategy: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TickTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str | None = None
    iteration: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    current_phase: TracePhase = TracePhase.TRACE
    screenshot: ScreenshotTraceMetadata | None = None
    frames: list[TraceFrameReference] = Field(default_factory=list)
    observe: TraceStep | None = None
    decide: TraceStep | None = None
    act: TraceStep | None = None
    verify: TraceStep | None = None
    trace: TraceStep | None = None
    recover: TraceStep | None = None
    state_before: dict[str, Any] = Field(default_factory=dict)
    vision: dict[str, Any] = Field(default_factory=dict)
    state_after: dict[str, Any] = Field(default_factory=dict)
    selected_action: dict[str, Any] | None = None
    ranked_actions: list[dict[str, Any]] = Field(default_factory=list)
    execution: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    recovery: dict[str, Any] | None = None
    failure_reason: str | None = None
    next_recovery_strategy: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.frame_dir = self.path.parent / f"{self.path.stem}_frames"

    def append(self, trace: TickTrace) -> TickTrace:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(trace.model_dump_json(exclude_none=True) + "\n")
        return trace

    def save_frame(
        self,
        *,
        iteration: int,
        role: TraceFrameRole,
        png: bytes,
        observation: ObservationSnapshot,
        attempt: int | None = None,
    ) -> TraceFrameReference:
        actual_sha = hashlib.sha256(png).hexdigest()
        if actual_sha != observation.frame_sha256:
            raise ValueError("trace frame bytes do not match the observation SHA")
        if observation.captured_at.tzinfo is None or observation.captured_at.utcoffset() is None:
            raise ValueError("trace frame observation timestamp must be aware")
        self.frame_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            f"{iteration:06d}-{role.value}-{uuid4().hex}-{actual_sha[:12]}.png"
        )
        frame_path = self.frame_dir / filename
        with frame_path.open("xb") as handle:
            handle.write(png)
            handle.flush()
            os.fsync(handle.fileno())
        return TraceFrameReference(
            role=role,
            path=str(frame_path.resolve()),
            sha256=actual_sha,
            observation={
                "observation_id": observation.observation_id,
                "captured_at": observation.captured_at.isoformat(),
                "frame_sha256": observation.frame_sha256,
                "frame_size": (
                    list(observation.frame_size)
                    if observation.frame_size is not None
                    else None
                ),
                "page_type": observation.page_type,
                "domains_run": list(observation.domains_run),
                "source": observation.source,
            },
            attempt=attempt,
        )

    def read(self) -> list[TickTrace]:
        if not self.path.exists():
            return []
        records: list[TickTrace] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(TickTrace.model_validate(json.loads(line)))
        return records
