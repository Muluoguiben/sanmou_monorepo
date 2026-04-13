"""High-level UI action primitives used by the controller loop.

Bridges the gap between decision output (PlannedAction) and the low-level
bridge_client mouse/keyboard commands. Two tiers:

  * Fixed-position buttons (bottom menu, ESC close) — resolved via
    UIRegistry against live window size.
  * Dynamic targets (buildings, lands, hero rows) — resolved via the
    Gemini locator (`find_elements` + `to_pixel_box`).
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

from pioneer_agent.perception.ui_registry import UIRegistry
from pioneer_agent.perception.vision import (
    PixelBox,
    VisionClient,
    find_elements,
    to_pixel_box,
)


class _BridgeLike:
    """Protocol-ish type — anything with click/drag/screenshot/key_press."""

    def click(self, x: int, y: int, button: str = "left") -> dict[str, Any]: ...
    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.4, button: str = "left") -> dict[str, Any]: ...
    def screenshot(self, save_path: Path | str | None = None) -> bytes: ...
    def key_press(self, key: str, modifiers: list[str] | None = None) -> dict[str, Any]: ...


@dataclass
class ClickOutcome:
    success: bool
    px: tuple[int, int]
    reason: str | None = None
    matched_label: str | None = None


class UIActions:
    def __init__(
        self,
        bridge: _BridgeLike,
        registry: UIRegistry,
        vision: VisionClient | None = None,
    ) -> None:
        self.bridge = bridge
        self.registry = registry
        self.vision = vision

    # --- fixed positions --------------------------------------------------

    def click_button(self, key: str) -> ClickOutcome:
        png = self.bridge.screenshot()
        w, h = _image_size(png)
        x, y = self.registry.resolve_pixel(key, w, h)
        resp = self.bridge.click(x, y)
        ok = resp.get("status") == "ok"
        return ClickOutcome(success=ok, px=(x, y), reason=None if ok else str(resp))

    # --- dynamic (vision-located) -----------------------------------------

    def click_element(self, query: str, *, index: int = 0) -> ClickOutcome:
        if self.vision is None:
            raise RuntimeError("VisionClient required for dynamic element clicks")
        png = self.bridge.screenshot()
        w, h = _image_size(png)
        boxes = find_elements(self.vision, png, query)
        if not boxes:
            return ClickOutcome(success=False, px=(0, 0), reason=f"no match for: {query}")
        if index >= len(boxes):
            return ClickOutcome(success=False, px=(0, 0), reason=f"only {len(boxes)} matches for: {query}")
        pix: PixelBox = to_pixel_box(boxes[index], w, h)
        cx, cy = pix.center
        resp = self.bridge.click(cx, cy)
        ok = resp.get("status") == "ok"
        return ClickOutcome(
            success=ok,
            px=(cx, cy),
            matched_label=pix.label,
            reason=None if ok else str(resp),
        )

    # --- navigation -------------------------------------------------------

    def pan_map(self, dx: int, dy: int, duration: float = 0.4) -> ClickOutcome:
        """Drag the map by (dx, dy) from the window center."""
        png = self.bridge.screenshot()
        w, h = _image_size(png)
        cx, cy = w // 2, h // 2
        resp = self.bridge.drag(cx, cy, cx + dx, cy + dy, duration=duration)
        ok = resp.get("status") == "ok"
        return ClickOutcome(success=ok, px=(cx + dx, cy + dy), reason=None if ok else str(resp))

    def close_popup(self) -> ClickOutcome:
        # Prefer ESC keystroke over clicking the X, which may not exist on every dialog.
        resp = self.bridge.key_press("escape")
        ok = resp.get("status") == "ok"
        return ClickOutcome(success=ok, px=(0, 0), reason=None if ok else str(resp))


def _image_size(png_bytes: bytes) -> tuple[int, int]:
    img = Image.open(BytesIO(png_bytes))
    return img.width, img.height
