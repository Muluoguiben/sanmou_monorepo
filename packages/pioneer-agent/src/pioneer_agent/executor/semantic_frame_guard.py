"""Short-lived semantic ROI guards for terminal UI clicks.

The guard hashes decoded RGB pixels inside the exact semantic target bbox.
It intentionally excludes the rest of the frame because animated game UI makes
full-frame hashes unstable even when the target button is unchanged.
"""

from __future__ import annotations

import hashlib
import math
from io import BytesIO
from typing import Any, Literal

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator, model_validator


SEMANTIC_ROI_ALGORITHM = "semantic-roi-rgb24-sha256-v1"
FINAL_MUTATING_AUTHORIZATION_SCOPE = "operator_confirmed_final_mutating_click"
INTERMEDIATE_AUTHORIZATION_SCOPE = "observation_bound_intermediate_click"
ATOMIC_CLICK_AUTHORIZATION_SCOPES = frozenset(
    {
        FINAL_MUTATING_AUTHORIZATION_SCOPE,
        INTERMEDIATE_AUTHORIZATION_SCOPE,
    }
)
FINAL_MUTATING_SEMANTIC_TARGETS = frozenset(
    {"chapter_claim_button", "recruit_button", "upgrade_confirm_button"}
)
INTERMEDIATE_SEMANTIC_TARGETS = frozenset({"building_upgrade_button"})


class PixelPoint(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class PixelRect(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class NormalizedRect(BaseModel):
    x_min: float = Field(ge=0, le=1000)
    y_min: float = Field(ge=0, le=1000)
    x_max: float = Field(ge=0, le=1000)
    y_max: float = Field(ge=0, le=1000)

    @field_validator("x_min", "y_min", "x_max", "y_max", mode="before")
    @classmethod
    def _strict_finite_number(cls, value: Any) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ValueError("semantic target bbox values must be finite numbers")
        return float(value)

    @model_validator(mode="after")
    def _ordered(self) -> NormalizedRect:
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError("semantic target bbox must have positive area")
        return self


class SemanticFrameGuard(BaseModel):
    schema_version: Literal[1] = 1
    algorithm: Literal["semantic-roi-rgb24-sha256-v1"] = SEMANTIC_ROI_ALGORITHM
    semantic_target_key: str = Field(min_length=1)
    frame_size: tuple[int, int]
    normalized_bbox: NormalizedRect
    roi_bbox: PixelRect
    click_point: PixelPoint
    roi_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_geometry(self) -> SemanticFrameGuard:
        width, height = self.frame_size
        if width <= 0 or height <= 0:
            raise ValueError("semantic frame guard requires a positive frame size")
        expected_roi, expected_click = semantic_target_geometry(
            self.frame_size,
            self.normalized_bbox.model_dump(mode="python"),
        )
        if self.roi_bbox != expected_roi or self.click_point != expected_click:
            raise ValueError("semantic frame guard geometry is internally inconsistent")
        if self.roi_bbox.x + self.roi_bbox.width > width:
            raise ValueError("semantic ROI exceeds frame width")
        if self.roi_bbox.y + self.roi_bbox.height > height:
            raise ValueError("semantic ROI exceeds frame height")
        if not _pixel_rect_contains(self.roi_bbox, self.click_point):
            raise ValueError("semantic click point must be inside the half-open ROI")
        return self


def semantic_target_geometry(
    frame_size: tuple[int, int],
    bbox: dict[str, Any],
) -> tuple[PixelRect, PixelPoint]:
    """Resolve a 0..1000 semantic bbox using the same rounding as UIActions."""
    try:
        normalized = NormalizedRect.model_validate(bbox)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid semantic target bbox") from exc
    width, height = frame_size
    if width <= 0 or height <= 0:
        raise ValueError("semantic target requires a positive frame size")
    left = round(normalized.x_min / 1000 * width)
    top = round(normalized.y_min / 1000 * height)
    right = round(normalized.x_max / 1000 * width)
    bottom = round(normalized.y_max / 1000 * height)
    roi = PixelRect(
        x=left,
        y=top,
        width=right - left,
        height=bottom - top,
    )
    # Preserve the normalized midpoint for ordinary boxes, but clamp it to the
    # decoded half-open crop. Tiny normalized boxes can otherwise round the
    # midpoint to ``right``/``bottom`` and hash one pixel while clicking the
    # adjacent, unguarded pixel.
    click = PixelPoint(
        x=min(
            max(
                round((normalized.x_min + normalized.x_max) / 2000 * width),
                left,
            ),
            right - 1,
        ),
        y=min(
            max(
                round((normalized.y_min + normalized.y_max) / 2000 * height),
                top,
            ),
            bottom - 1,
        ),
    )
    return roi, click


def build_semantic_frame_guard(
    frame_bytes: bytes,
    *,
    frame_size: tuple[int, int],
    semantic_target_key: str,
    bbox: dict[str, Any],
) -> SemanticFrameGuard:
    """Hash decoded RGB pixels in the exact terminal target bbox."""
    try:
        with Image.open(BytesIO(frame_bytes)) as image:
            rgb = image.convert("RGB")
            rgb.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("terminal observation frame is not a decodable image") from exc
    if rgb.size != frame_size:
        raise ValueError(
            f"terminal observation frame size mismatch: {rgb.size} != {frame_size}"
        )
    roi_bbox, click_point = semantic_target_geometry(frame_size, bbox)
    crop = rgb.crop(
        (
            roi_bbox.x,
            roi_bbox.y,
            roi_bbox.x + roi_bbox.width,
            roi_bbox.y + roi_bbox.height,
        )
    )
    roi_sha256 = hashlib.sha256(crop.tobytes()).hexdigest()
    return SemanticFrameGuard(
        semantic_target_key=semantic_target_key,
        frame_size=frame_size,
        normalized_bbox=NormalizedRect.model_validate(bbox),
        roi_bbox=roi_bbox,
        click_point=click_point,
        roi_sha256=roi_sha256,
    )


def authorization_scope_for_semantic_target(target_key: str) -> str | None:
    if target_key in FINAL_MUTATING_SEMANTIC_TARGETS:
        return FINAL_MUTATING_AUTHORIZATION_SCOPE
    if target_key in INTERMEDIATE_SEMANTIC_TARGETS:
        return INTERMEDIATE_AUTHORIZATION_SCOPE
    return None


def _pixel_rect_contains(rect: PixelRect, point: PixelPoint) -> bool:
    return (
        rect.x <= point.x < rect.x + rect.width
        and rect.y <= point.y < rect.y + rect.height
    )
