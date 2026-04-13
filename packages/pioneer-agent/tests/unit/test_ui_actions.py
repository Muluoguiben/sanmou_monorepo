"""Tests for UIActions — the primitive layer between decisions and the bridge."""
from __future__ import annotations

import io
import unittest
from dataclasses import dataclass
from typing import Any

from PIL import Image

from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.perception.ui_registry import UIButton, UIRegistry


def _make_png(w: int = 1920, h: int = 1080) -> bytes:
    img = Image.new("RGB", (w, h), (0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "stub"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _StubVision:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        return _StubResult(data=self.payload)


class _StubBridge:
    def __init__(self, png: bytes, *, click_ok: bool = True) -> None:
        self._png = png
        self._click_ok = click_ok
        self.clicks: list[tuple[int, int]] = []
        self.drags: list[tuple[int, int, int, int]] = []
        self.keys: list[str] = []

    def screenshot(self, save_path=None):  # noqa: ANN001
        return self._png

    def click(self, x, y, button="left"):  # noqa: ANN001
        self.clicks.append((x, y))
        return {"status": "ok" if self._click_ok else "error"}

    def drag(self, x1, y1, x2, y2, duration=0.4, button="left"):  # noqa: ANN001
        self.drags.append((x1, y1, x2, y2))
        return {"status": "ok"}

    def key_press(self, key, modifiers=None):  # noqa: ANN001
        self.keys.append(key)
        return {"status": "ok"}


class UIActionsTests(unittest.TestCase):
    def _registry(self) -> UIRegistry:
        return UIRegistry({
            "wu_jiang": UIButton("wu_jiang", "武将", 0.5, 0.9),
        })

    def test_click_button_resolves_pixel_from_live_size(self) -> None:
        bridge = _StubBridge(_make_png(1920, 1080))
        actions = UIActions(bridge, self._registry())
        out = actions.click_button("wu_jiang")
        self.assertTrue(out.success)
        self.assertEqual(out.px, (960, 972))
        self.assertEqual(bridge.clicks, [(960, 972)])

    def test_click_button_forwards_failure(self) -> None:
        bridge = _StubBridge(_make_png(800, 600), click_ok=False)
        actions = UIActions(bridge, self._registry())
        out = actions.click_button("wu_jiang")
        self.assertFalse(out.success)
        self.assertIsNotNone(out.reason)

    def test_click_element_uses_vision(self) -> None:
        bridge = _StubBridge(_make_png(1000, 1000))
        vision = _StubVision(
            {"matches": [{"label": "征兵所", "y_min": 200, "x_min": 300, "y_max": 300, "x_max": 500}]}
        )
        actions = UIActions(bridge, self._registry(), vision=vision)
        out = actions.click_element("征兵所 building")
        self.assertTrue(out.success)
        # center of (300-500, 200-300) on 1000x1000 = (400, 250)
        self.assertEqual(out.px, (400, 250))
        self.assertEqual(out.matched_label, "征兵所")

    def test_click_element_no_match(self) -> None:
        bridge = _StubBridge(_make_png(1000, 1000))
        vision = _StubVision({"matches": []})
        actions = UIActions(bridge, self._registry(), vision=vision)
        out = actions.click_element("missing target")
        self.assertFalse(out.success)
        self.assertEqual(bridge.clicks, [])

    def test_click_element_requires_vision(self) -> None:
        bridge = _StubBridge(_make_png())
        actions = UIActions(bridge, self._registry(), vision=None)
        with self.assertRaises(RuntimeError):
            actions.click_element("anything")

    def test_pan_map_drags_from_center(self) -> None:
        bridge = _StubBridge(_make_png(2000, 1000))
        actions = UIActions(bridge, self._registry())
        out = actions.pan_map(dx=-400, dy=0)
        self.assertTrue(out.success)
        self.assertEqual(bridge.drags, [(1000, 500, 600, 500)])

    def test_close_popup_sends_escape(self) -> None:
        bridge = _StubBridge(_make_png())
        actions = UIActions(bridge, self._registry())
        out = actions.close_popup()
        self.assertTrue(out.success)
        self.assertEqual(bridge.keys, ["escape"])


if __name__ == "__main__":
    unittest.main()
