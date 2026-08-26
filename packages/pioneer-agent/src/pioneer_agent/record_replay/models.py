"""Schemas for a human demonstration captured by Windows Record & Replay.

These records deliberately do not reuse ``TickTrace``. A demonstration proves
what a person did in one window state; it does not prove that the runtime made
a decision, that an action is generally safe, or that a verifier succeeded.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
import re
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from pioneer_agent.core.models import CaptureGeometry
from pioneer_agent.record_replay.validation import validate_workflow_name


SCHEMA_VERSION = 1
SHA256_PATTERN = r"^[0-9a-f]{64}$"
SAFE_RECORDED_KEYS = frozenset(
    {
        "escape",
        "enter",
        "tab",
        "space",
        "backspace",
        "delete",
        "left",
        "right",
        "up",
        "down",
        "home",
        "end",
        "page_up",
        "page_down",
    }
)
INPUT_CLOCK_TOLERANCE_MS = 100


class RecordingStatus(str, Enum):
    RECORDING = "recording"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class FrameRole(str, Enum):
    START = "start"
    PRE_INPUT = "pre_input"
    POST_INPUT = "post_input"
    END = "end"


class InputKind(str, Enum):
    CLICK = "click"
    DRAG = "drag"
    SCROLL = "scroll"
    KEY_PRESS = "key_press"


class ImageFormat(str, Enum):
    WEBP = "webp"
    PNG = "png"


class ReviewStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    PENDING_REVIEW = "pending_review"


class RecordingSafety(BaseModel):
    """M0 safety invariants. Any future authority requires a new schema."""

    model_config = ConfigDict(extra="forbid")

    observe_only: Literal[True] = True
    input_dispatch: Literal[False] = False
    clipboard_recorded: Literal[False] = False
    printable_text_recorded: Literal[False] = False
    execution_authority: Literal["none"] = "none"
    safe_for_live_replay: Literal[False] = False
    privacy_reviewed: Literal[False] = False


class CaptureSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: Literal["auto", "wgc", "dxgi"] = "auto"
    settle_ms: int = Field(default=350, ge=100, le=2_000)
    long_edge: int = Field(default=1280, ge=320, le=2560)
    image_format: ImageFormat = ImageFormat.WEBP
    webp_quality: int = Field(default=60, ge=20, le=90)
    max_events: int = Field(default=500, ge=1, le=10_000)
    min_input_events: int = Field(default=0, ge=0, le=10_000)
    max_bytes: int = Field(default=268_435_456, ge=1_048_576)

    @model_validator(mode="after")
    def _input_event_bounds_are_consistent(self) -> CaptureSettings:
        if self.min_input_events > self.max_events:
            raise ValueError("min_input_events cannot exceed max_events")
        return self


class TargetWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_name: Literal["com.bilibili.nslg"] = "com.bilibili.nslg"
    window_class: Literal["UnityWndClass"] = "UnityWndClass"
    hwnd: int = Field(gt=0)
    pid: int = Field(gt=0)
    process_started_at: datetime
    title: str = ""

    @field_validator("process_started_at")
    @classmethod
    def _aware_process_time(cls, value: datetime) -> datetime:
        return _require_aware(value, "process_started_at")


class RecordingManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    session_id: str
    workflow_name: str = Field(min_length=1, max_length=120)
    status: RecordingStatus
    started_at: datetime
    ended_at: datetime | None = None
    target: TargetWindow
    initial_capture_geometry: CaptureGeometry
    capture: CaptureSettings = Field(default_factory=CaptureSettings)
    safety: RecordingSafety = Field(default_factory=RecordingSafety)
    events_path: Literal["events.jsonl"] = "events.jsonl"
    events_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    record_count: int = Field(default=0, ge=0)
    frame_count: int = Field(default=0, ge=0)
    input_event_count: int = Field(default=0, ge=0)
    ignored_event_count: int = Field(default=0, ge=0)
    capture_error_count: int = Field(default=0, ge=0)
    total_frame_bytes: int = Field(default=0, ge=0)
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED
    inferred_from_single_demo: Literal[True] = True
    failure_code: str | None = None
    failure_reason: str | None = None
    stop_reason: str | None = None
    recorder_version: str = "windows-standalone-v1"
    recording_model_exercised: Literal[False] = False
    action_correlated_runtime_trace: Literal[False] = False
    closure_eligible: Literal[False] = False

    @field_validator("workflow_name")
    @classmethod
    def _safe_workflow_name(cls, value: str) -> str:
        return validate_workflow_name(value)

    @field_validator("session_id")
    @classmethod
    def _canonical_session_id(cls, value: str) -> str:
        try:
            parsed = UUID(value)
        except (ValueError, AttributeError) as exc:
            raise ValueError("session_id must be a canonical UUID") from exc
        if str(parsed) != value:
            raise ValueError("session_id must be a canonical lowercase UUID")
        return value

    @field_validator("started_at", "ended_at")
    @classmethod
    def _aware_times(cls, value: datetime | None, info: Any) -> datetime | None:
        if value is None:
            return None
        return _require_aware(value, info.field_name)

    @model_validator(mode="after")
    def _status_is_consistent(self) -> RecordingManifest:
        if self.status == RecordingStatus.RECORDING:
            if self.ended_at is not None or self.events_sha256 is not None:
                raise ValueError("active recording cannot be finalized")
            return self
        if self.ended_at is None or self.events_sha256 is None:
            raise ValueError("final recording requires ended_at and events_sha256")
        if self.ended_at < self.started_at:
            raise ValueError("recording ended before it started")
        if self.status == RecordingStatus.FAILED and not self.failure_code:
            raise ValueError("failed recording requires a failure_code")
        if self.status == RecordingStatus.COMPLETED and self.frame_count == 0:
            raise ValueError("completed recording requires at least one frame")
        return self


class PixelPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)


class NormalizedPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class FrameRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    record_type: Literal["frame"] = "frame"
    session_id: str
    sequence: int = Field(ge=0)
    frame_id: str = Field(min_length=1)
    role: FrameRole
    captured_at: datetime
    elapsed_ms: int = Field(ge=0)
    path: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    byte_size: int = Field(gt=0)
    image_format: ImageFormat
    image_size: tuple[int, int]
    source_png_sha256: str = Field(pattern=SHA256_PATTERN)
    capture_geometry: CaptureGeometry

    @field_validator("captured_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        return _require_aware(value, "captured_at")

    @field_validator("path")
    @classmethod
    def _safe_path(cls, value: str) -> str:
        return validate_relative_artifact_path(value)

    @field_validator("image_size", mode="before")
    @classmethod
    def _valid_size(cls, value: Any) -> tuple[int, int]:
        if (
            not isinstance(value, (list, tuple))
            or len(value) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in value)
        ):
            raise ValueError("image_size must contain two positive integers")
        return int(value[0]), int(value[1])


class InputEventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    record_type: Literal["input"] = "input"
    session_id: str
    sequence: int = Field(ge=0)
    event_id: str = Field(min_length=1)
    kind: InputKind
    occurred_at: datetime
    ended_at: datetime
    elapsed_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    window_hwnd: int = Field(gt=0)
    window_pid: int = Field(gt=0)
    foreground_verified: Literal[True] = True
    capture_geometry: CaptureGeometry
    start_point: PixelPoint | None = None
    end_point: PixelPoint | None = None
    start_normalized: NormalizedPoint | None = None
    end_normalized: NormalizedPoint | None = None
    button: Literal["left", "right", "middle"] | None = None
    scroll_delta: int | None = None
    key: str | None = None
    modifiers: list[Literal["ctrl", "shift", "alt"]] = Field(default_factory=list)
    before_frame_id: str
    after_frame_id: str
    ambiguous_burst: bool = False
    geometry_changed: bool = False
    printable_text_omitted: Literal[True] = True

    @field_validator("occurred_at", "ended_at")
    @classmethod
    def _aware_time(cls, value: datetime, info: Any) -> datetime:
        return _require_aware(value, info.field_name)

    @model_validator(mode="after")
    def _kind_fields_match(self) -> InputEventRecord:
        if self.ended_at < self.occurred_at:
            raise ValueError("input event ended before it started")
        wall_duration_ms = (self.ended_at - self.occurred_at).total_seconds() * 1_000
        if abs(wall_duration_ms - self.duration_ms) > INPUT_CLOCK_TOLERANCE_MS:
            raise ValueError("input duration_ms does not match its timestamps")
        if self.kind in {InputKind.CLICK, InputKind.DRAG, InputKind.SCROLL}:
            if self.start_point is None or self.start_normalized is None:
                raise ValueError("pointer event requires a start point")
            self._validate_point_pair(self.start_point, self.start_normalized)
        if self.kind == InputKind.DRAG:
            if self.end_point is None or self.end_normalized is None or self.button is None:
                raise ValueError("drag requires end point and button")
            self._validate_point_pair(self.end_point, self.end_normalized)
        elif self.end_point is not None or self.end_normalized is not None:
            raise ValueError("only drag may contain an end point")
        if self.kind == InputKind.CLICK and self.button is None:
            raise ValueError("click requires a button")
        if self.kind in {InputKind.CLICK, InputKind.DRAG} and self.scroll_delta is not None:
            raise ValueError("click and drag cannot contain a scroll delta")
        if self.kind == InputKind.SCROLL:
            if self.scroll_delta is None:
                raise ValueError("scroll requires a delta")
            if self.button is not None:
                raise ValueError("scroll cannot contain a button")
        if self.kind == InputKind.KEY_PRESS:
            if self.key not in SAFE_RECORDED_KEYS:
                raise ValueError("recorded key is not on the safe navigation allowlist")
            if any(
                value is not None
                for value in (self.start_point, self.start_normalized, self.button, self.scroll_delta)
            ):
                raise ValueError("key event cannot contain pointer fields")
        elif self.key is not None:
            raise ValueError("pointer event cannot contain a key")
        return self

    def _validate_point_pair(self, point: PixelPoint, normalized: NormalizedPoint) -> None:
        width, height = self.capture_geometry.frame_size
        if point.x >= width or point.y >= height:
            raise ValueError("input point is outside the captured frame")
        tolerance_x = 1.0 / max(width, 1)
        tolerance_y = 1.0 / max(height, 1)
        if abs(normalized.x - point.x / width) > tolerance_x:
            raise ValueError("normalized x does not match capture-relative x")
        if abs(normalized.y - point.y / height) > tolerance_y:
            raise ValueError("normalized y does not match capture-relative y")


class CaptureErrorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    record_type: Literal["capture_error"] = "capture_error"
    session_id: str
    sequence: int = Field(ge=0)
    occurred_at: datetime
    elapsed_ms: int = Field(ge=0)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=500)

    @field_validator("occurred_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        return _require_aware(value, "occurred_at")


SessionRecord: TypeAlias = Annotated[
    FrameRecord | InputEventRecord | CaptureErrorRecord,
    Field(discriminator="record_type"),
]
SESSION_RECORD_ADAPTER = TypeAdapter(SessionRecord)


class FrameEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frame_id: str
    path: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    captured_at: datetime
    capture_geometry: CaptureGeometry


class ActionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    candidate_id: str
    session_id: str
    source_events_sha256: str = Field(pattern=SHA256_PATTERN)
    order: int = Field(ge=0)
    source_event_id: str
    primitive: InputKind
    occurred_at: datetime
    input: dict[str, Any]
    before_frame: FrameEvidence
    after_frame: FrameEvidence
    proposed_action_type: None = None
    semantic_target: None = None
    expected_delta: None = None
    review_status: Literal["pending_review"] = "pending_review"
    execution_authority: Literal["none"] = "none"
    inferred_from_single_demo: Literal[True] = True
    verifier_status: Literal["unproven"] = "unproven"
    ambiguous_burst: bool
    geometry_changed: bool
    unresolved_assumptions: list[str]
    promotion_gates: dict[str, Literal[False]] = Field(
        default_factory=lambda: {
            "human_review": False,
            "holdout_eval": False,
            "safety_allowlist": False,
            "verifier_eval": False,
        }
    )


class ReplayPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    session_id: str
    source_events_sha256: str = Field(pattern=SHA256_PATTERN)
    workflow_name: str
    generated_at: datetime
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    mode: Literal["offline_dry_run"] = "offline_dry_run"
    blockers: list[str]
    actions: list[ActionCandidate]


class CompilationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION
    session_id: str
    source_events_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)
    geometry_changed_count: int = Field(ge=0)
    action_candidates_path: str
    replay_plan_path: str
    draft_skill_path: str
    execution_authority: Literal["none"] = "none"


def validate_relative_artifact_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or normalized.startswith("./")
        or "//" in normalized
        or path.is_absolute()
        or ".." in path.parts
        or ":" in normalized
        or path.parts[0] in {"", "."}
        or re.fullmatch(r"[A-Za-z0-9._/-]+", normalized) is None
    ):
        raise ValueError("artifact path must stay relative to the session root")
    return path.as_posix()


def _require_aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value
