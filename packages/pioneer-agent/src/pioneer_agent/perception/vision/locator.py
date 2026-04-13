"""Element locator — Gemini-backed bbox finder for dynamic UI targets.

Gemini returns bboxes normalized to 0-1000 on each axis of the INPUT image.
Since our screenshots are window-scoped, image pixels map 1:1 to window
client-area pixels, so center coordinates can be clicked directly via
`bridge_client.click(window_x, window_y)`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .prompts import (
    ELEMENT_LOCATION_SCHEMA,
    ElementBox,
    ElementLocation,
    build_element_location_instruction,
)


class _VisionCaller(Protocol):
    def extract(self, image, instruction, response_schema, **kwargs):  # type: ignore[no-untyped-def]
        ...


@dataclass
class PixelBox:
    """Bounding box in window-relative pixel coordinates."""

    label: str
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2


def find_elements(
    client: _VisionCaller,
    image: bytes | Path,
    query: str,
    *,
    temperature: float = 0.0,
) -> list[ElementBox]:
    """Ask Gemini for all UI elements matching `query`. Returns normalized bboxes."""
    result = client.extract(
        image=image,
        instruction=build_element_location_instruction(query),
        response_schema=ELEMENT_LOCATION_SCHEMA,
        temperature=temperature,
    )
    parsed = ElementLocation.model_validate(result.data)
    return parsed.matches


def to_pixel_box(box: ElementBox, image_width: int, image_height: int) -> PixelBox:
    """Convert Gemini's 0-1000 normalized bbox to pixel coordinates.

    Gemini convention: [y_min, x_min, y_max, x_max] on 0-1000 per axis.
    """
    x1 = round(box.x_min / 1000 * image_width)
    x2 = round(box.x_max / 1000 * image_width)
    y1 = round(box.y_min / 1000 * image_height)
    y2 = round(box.y_max / 1000 * image_height)
    # Guard against inverted/zero-size boxes.
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return PixelBox(
        label=box.label,
        x=x1,
        y=y1,
        width=max(1, x2 - x1),
        height=max(1, y2 - y1),
    )
