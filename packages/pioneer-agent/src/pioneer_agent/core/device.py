from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class DevicePlatform(str, Enum):
    PC_CLIENT = "pc_client"
    ANDROID_EMULATOR = "android_emulator"
    ANDROID = "android"
    IOS = "ios"
    UNKNOWN = "unknown"


class Orientation(str, Enum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    UNKNOWN = "unknown"


class ObservationSourceType(str, Enum):
    SCREENSHOT_FILE = "screenshot_file"
    WATCH_FOLDER = "watch_folder"
    WINDOWS_WINDOW_CAPTURE = "windows_window_capture"
    ADB_SCREENSHOT = "adb_screenshot"
    MIRROR_CAPTURE = "mirror_capture"
    CLIPBOARD_IMAGE = "clipboard_image"


class NormalizedPoint(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class NormalizedRect(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(ge=0.0, le=1.0)
    height: float = Field(ge=0.0, le=1.0)


class PixelRect(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)

    def normalize(self, image_width: int, image_height: int) -> NormalizedRect:
        _validate_size(image_width, image_height)
        return NormalizedRect(
            x=_clamp01(self.x / image_width),
            y=_clamp01(self.y / image_height),
            width=_clamp01(self.width / image_width),
            height=_clamp01(self.height / image_height),
        )

    @classmethod
    def full_image(cls, width: int, height: int) -> PixelRect:
        _validate_size(width, height)
        return cls(x=0, y=0, width=width, height=height)


class CapabilityFlags(BaseModel):
    observe_only: bool = True
    live_capture: bool = False
    input_control: bool = False
    reliable_window_info: bool = False
    supports_adb: bool = False
    supports_clipboard: bool = False

    @model_validator(mode="after")
    def _normalize_observe_only(self) -> CapabilityFlags:
        if self.input_control:
            self.observe_only = False
        return self

    @property
    def can_execute_input(self) -> bool:
        return self.input_control and not self.observe_only


class DeviceProfile(BaseModel):
    profile_id: str = Field(default_factory=lambda: str(uuid4()))
    platform: DevicePlatform = DevicePlatform.UNKNOWN
    resolution: tuple[int, int]
    orientation: Orientation = Orientation.UNKNOWN
    screenshot_size: tuple[int, int] | None = None
    game_content_region: PixelRect | None = None
    status_bar_px: int = Field(default=0, ge=0)
    crop_info: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("resolution", "screenshot_size")
    @classmethod
    def _validate_tuple_size(cls, value: tuple[int, int] | None) -> tuple[int, int] | None:
        if value is None:
            return None
        _validate_size(value[0], value[1])
        return value

    @property
    def image_size(self) -> tuple[int, int]:
        return self.screenshot_size or self.resolution

    @property
    def content_region(self) -> PixelRect:
        width, height = self.image_size
        return self.game_content_region or PixelRect.full_image(width, height)

    def normalize_screen_point(self, x: int, y: int) -> NormalizedPoint:
        width, height = self.image_size
        _validate_size(width, height)
        return NormalizedPoint(x=_clamp01(x / width), y=_clamp01(y / height))

    def normalize_content_point(self, x: int, y: int) -> NormalizedPoint:
        region = self.content_region
        return NormalizedPoint(
            x=_clamp01((x - region.x) / region.width),
            y=_clamp01((y - region.y) / region.height),
        )

    def content_point_to_screen(self, point: NormalizedPoint) -> tuple[int, int]:
        region = self.content_region
        x = round(region.x + point.x * region.width)
        y = round(region.y + point.y * region.height)
        return x, y

    def normalize_content_rect(self, rect: PixelRect) -> NormalizedRect:
        region = self.content_region
        return NormalizedRect(
            x=_clamp01((rect.x - region.x) / region.width),
            y=_clamp01((rect.y - region.y) / region.height),
            width=_clamp01(rect.width / region.width),
            height=_clamp01(rect.height / region.height),
        )


class ObservationSource(BaseModel):
    source_id: str = Field(default_factory=lambda: str(uuid4()))
    source_type: ObservationSourceType
    uri: str | None = None
    display_name: str | None = None
    capabilities: CapabilityFlags = Field(default_factory=CapabilityFlags)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeviceSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    profile: DeviceProfile
    source: ObservationSource
    capabilities: CapabilityFlags = Field(default_factory=CapabilityFlags)
    active: bool = True
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_observed_at: datetime | None = None

    @model_validator(mode="after")
    def _inherit_source_capabilities(self) -> DeviceSession:
        if self.capabilities == CapabilityFlags():
            self.capabilities = self.source.capabilities
        return self

    @property
    def observe_only(self) -> bool:
        return self.capabilities.observe_only

    def mark_observed(self, captured_at: datetime) -> DeviceSession:
        return self.model_copy(update={"last_observed_at": captured_at})

    def assert_can_control(self) -> None:
        if not self.capabilities.can_execute_input:
            raise PermissionError(
                f"device session {self.session_id} is observe-only and cannot dispatch input"
            )


class GridCell(BaseModel):
    cell_id: str
    row: int
    col: int
    land_id: str | None = None
    level: int | None = None
    resource_type: str | None = None
    owner: str | None = None
    center: NormalizedPoint | None = None
    screen_bbox: NormalizedRect | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MapGridState(BaseModel):
    account_session_id: str
    cells: dict[str, GridCell] = Field(default_factory=dict)
    coordinate_system: str = "game_grid"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def upsert_cell(self, cell: GridCell) -> MapGridState:
        cells = dict(self.cells)
        cells[cell.cell_id] = cell
        return self.model_copy(update={"cells": cells, "updated_at": datetime.now(UTC)})


class AccountSession(BaseModel):
    account_session_id: str = Field(default_factory=lambda: str(uuid4()))
    account_label: str | None = None
    server_id: str | None = None
    season_id: str | None = None
    role_name: str | None = None
    active_live_source_id: str | None = None
    map_grid_state: MapGridState | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def bind_live_source(self, device_session: DeviceSession) -> AccountSession:
        if not device_session.capabilities.live_capture:
            return self
        if (
            self.active_live_source_id is not None
            and self.active_live_source_id != device_session.session_id
        ):
            raise ValueError(
                "account session already has an active live source; stop it before binding another"
            )
        return self.model_copy(update={"active_live_source_id": device_session.session_id})

    def with_map_grid(self, map_grid_state: MapGridState) -> AccountSession:
        if map_grid_state.account_session_id != self.account_session_id:
            raise ValueError("map grid belongs to a different account session")
        return self.model_copy(update={"map_grid_state": map_grid_state})


def _validate_size(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
