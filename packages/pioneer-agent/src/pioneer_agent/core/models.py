from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import ActionType


class FieldMeta(BaseModel):
    value: Any
    confidence: float = 1.0
    source: str = "unknown"
    updated_at: datetime | None = None
    observation_id: str | None = None


class RuntimeState(BaseModel):
    global_state: dict[str, Any] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    economy: dict[str, Any] = Field(default_factory=dict)
    city: dict[str, Any] = Field(default_factory=dict)
    heroes: list[dict[str, Any]] = Field(default_factory=list)
    teams: list[dict[str, Any]] = Field(default_factory=list)
    map_state: dict[str, Any] = Field(default_factory=dict)
    swap_window: dict[str, Any] = Field(default_factory=dict)
    main_lineup: dict[str, Any] = Field(default_factory=dict)
    team_containers: list[dict[str, Any]] = Field(default_factory=list)
    carrier_pool: list[dict[str, Any]] = Field(default_factory=list)
    swap_constraints: dict[str, Any] = Field(default_factory=dict)
    timing: dict[str, Any] = Field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = Field(default_factory=dict)


class CapturePoint(BaseModel):
    """Physical desktop point used by the Windows capture bridge."""

    model_config = ConfigDict(extra="forbid")

    x: int
    y: int

    @field_validator("x", "y", mode="before")
    @classmethod
    def _strict_int(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("capture point coordinates must be integers")
        return value


class CaptureRect(BaseModel):
    """Half-open physical desktop rectangle."""

    model_config = ConfigDict(extra="forbid")

    left: int
    top: int
    right: int
    bottom: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    @field_validator("left", "top", "right", "bottom", "width", "height", mode="before")
    @classmethod
    def _strict_int(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("capture rectangle values must be integers")
        return value

    @model_validator(mode="after")
    def _consistent_extents(self) -> CaptureRect:
        if self.right <= self.left or self.bottom <= self.top:
            raise ValueError("capture rectangle must have positive area")
        if self.right - self.left != self.width:
            raise ValueError("capture rectangle width is inconsistent")
        if self.bottom - self.top != self.height:
            raise ValueError("capture rectangle height is inconsistent")
        return self


class CaptureWindowIdentity(CaptureRect):
    """Concrete HWND/process identity plus its outer physical-pixel rect."""

    hwnd: int = Field(gt=0)
    pid: int = Field(gt=0)

    @field_validator("hwnd", "pid", mode="before")
    @classmethod
    def _strict_positive_int(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("capture window identity values must be integers")
        return value


class CaptureGeometry(BaseModel):
    """Server-attested mapping from screenshot pixels to desktop pixels.

    ``capture_rect`` is the exact physical desktop region represented by the
    image. It may be smaller than ``outer_window`` because WGC excludes the
    resize border and DXGI clamps an off-screen window to the duplicated
    output. A screenshot-relative point maps to the desktop by adding
    ``capture_origin``; outer-window coordinates are deliberately not used.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    capture_backend: Literal["wgc", "dxgi"]
    outer_window: CaptureWindowIdentity
    capture_rect: CaptureRect
    capture_origin: CapturePoint
    frame_size: tuple[int, int]

    @field_validator("frame_size", mode="before")
    @classmethod
    def _strict_frame_size(cls, value: Any) -> tuple[int, int]:
        if (
            not isinstance(value, (list, tuple))
            or len(value) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) for item in value)
        ):
            raise ValueError("capture frame size must contain two integers")
        return int(value[0]), int(value[1])

    @model_validator(mode="after")
    def _internally_consistent(self) -> CaptureGeometry:
        if self.frame_size != (self.capture_rect.width, self.capture_rect.height):
            raise ValueError("capture frame size does not match capture rectangle")
        if self.capture_origin != CapturePoint(
            x=self.capture_rect.left,
            y=self.capture_rect.top,
        ):
            raise ValueError("capture origin does not match capture rectangle")
        outer = self.outer_window
        rect = self.capture_rect
        if not (
            outer.left <= rect.left < rect.right <= outer.right
            and outer.top <= rect.top < rect.bottom <= outer.bottom
        ):
            raise ValueError("capture rectangle is not contained in the outer window")
        return self


class ObservationSnapshot(BaseModel):
    observation_id: str
    captured_at: datetime
    frame_sha256: str
    frame_size: tuple[int, int] | None = None
    capture_geometry: CaptureGeometry | None = None
    page_type: str | None = None
    domains_run: list[str] = Field(default_factory=list)
    observed_state: RuntimeState = Field(default_factory=RuntimeState)
    source: Literal["vision_sync", "runtime_fixture"]

    @model_validator(mode="after")
    def _capture_geometry_matches_frame(self) -> ObservationSnapshot:
        if self.capture_geometry is None:
            return self
        if self.frame_size is None:
            raise ValueError("capture geometry requires an observed frame size")
        if self.capture_geometry.frame_size != self.frame_size:
            raise ValueError("capture geometry does not match observation frame size")
        return self


class CandidateAction(BaseModel):
    action_id: str
    action_type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    expected_gain: dict[str, Any] = Field(default_factory=dict)
    expected_cost: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    timing: dict[str, Any] = Field(default_factory=dict)
    interruptibility: dict[str, Any] = Field(default_factory=dict)
    source_state_refs: list[str] = Field(default_factory=list)
    score_total: float = 0.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class SelectionResult(BaseModel):
    selected_action: CandidateAction | None = None
    ranked_actions: list[CandidateAction] = Field(default_factory=list)
    selection_reason: dict[str, Any] = Field(default_factory=dict)
    next_replan_time: datetime | None = None


class ExecutionResult(BaseModel):
    action_id: str
    status: str
    verification_status: str = "unknown"
    failure_reason: str | None = None
    recovery_required: bool = False
    summary: dict[str, Any] = Field(default_factory=dict)
