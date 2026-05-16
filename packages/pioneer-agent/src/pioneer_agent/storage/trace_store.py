"""Structured JSONL trace records for autonomous-loop ticks."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TracePhase(str, Enum):
    OBSERVE = "observe"
    DECIDE = "decide"
    ACT = "act"
    VERIFY = "verify"
    TRACE = "trace"
    RECOVER = "recover"


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

    def append(self, trace: TickTrace) -> TickTrace:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(trace.model_dump_json(exclude_none=True) + "\n")
        return trace

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
