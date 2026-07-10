"""Tests for UIActions — the primitive layer between decisions and the bridge."""
from __future__ import annotations

import io
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from PIL import Image

from pioneer_agent.core.models import ObservationSnapshot, RuntimeState
from pioneer_agent.executor.input_policy import InputPolicy
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
        self.screenshots = 0

    def screenshot(self, save_path=None):  # noqa: ANN001
        self.screenshots += 1
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
        self.assertEqual(out.trace["click_point"], {"x": 960, "y": 972})
        self.assertEqual(actions.consume_input_trace()[0]["target"]["key"], "wu_jiang")

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
        actions = UIActions(
            bridge,
            self._registry(),
            vision=vision,
            input_policy=InputPolicy(allowed_element_queries=frozenset({"征兵所 building"})),
        )
        out = actions.click_element("征兵所 building")
        self.assertTrue(out.success)
        # center of (300-500, 200-300) on 1000x1000 = (400, 250)
        self.assertEqual(out.px, (400, 250))
        self.assertEqual(out.matched_label, "征兵所")
        self.assertEqual(out.trace["normalized_bbox"]["x"], 0.3)
        self.assertEqual(out.trace["pixel_bbox"], {"x": 300, "y": 200, "width": 200, "height": 100})
        self.assertEqual(actions.consume_input_trace()[0]["click_point"], {"x": 400, "y": 250})

    def test_click_element_blocks_non_allowlisted_query(self) -> None:
        bridge = _StubBridge(_make_png(1000, 1000))
        vision = _StubVision(
            {"matches": [{"label": "征兵所", "y_min": 200, "x_min": 300, "y_max": 300, "x_max": 500}]}
        )
        actions = UIActions(bridge, self._registry(), vision=vision)
        out = actions.click_element("征兵所 building")
        self.assertFalse(out.success)
        self.assertIn("not allowlisted", out.reason or "")
        self.assertEqual(bridge.clicks, [])

    def test_click_element_no_match(self) -> None:
        bridge = _StubBridge(_make_png(1000, 1000))
        vision = _StubVision({"matches": []})
        actions = UIActions(
            bridge,
            self._registry(),
            vision=vision,
            input_policy=InputPolicy(allowed_element_queries=frozenset({"missing target"})),
        )
        out = actions.click_element("missing target")
        self.assertFalse(out.success)
        self.assertEqual(bridge.clicks, [])

    def test_click_element_requires_vision(self) -> None:
        bridge = _StubBridge(_make_png())
        actions = UIActions(bridge, self._registry(), vision=None)
        with self.assertRaises(RuntimeError):
            actions.click_element("anything")

    def test_click_bbox_uses_semantic_target_allowlist(self) -> None:
        bridge = _StubBridge(_make_png(1000, 1000))
        actions = UIActions(bridge, self._registry())

        out = actions.click_bbox(
            "chapter_claim_button",
            {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
            label="章节奖励领取",
        )

        self.assertTrue(out.success)
        self.assertEqual(out.px, (800, 850))
        self.assertEqual(bridge.clicks, [(800, 850)])
        self.assertEqual(out.trace["action"], "click_semantic_bbox")
        self.assertEqual(out.trace["target"]["key"], "chapter_claim_button")
        self.assertEqual(out.trace["normalized_bbox"]["x"], 0.7)

    def test_bound_observation_supplies_frame_size_without_recapture(self) -> None:
        bridge = _StubBridge(_make_png(640, 360))
        actions = UIActions(bridge, self._registry())
        observation = ObservationSnapshot(
            observation_id="obs-1",
            captured_at=datetime.now(UTC),
            frame_sha256="a" * 64,
            frame_size=(1000, 1000),
            page_type="chapter",
            domains_run=["chapter_panel"],
            observed_state=RuntimeState(),
            source="vision_sync",
        )
        actions.bind_observation(observation)

        out = actions.click_bbox(
            "chapter_claim_button",
            {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
        )

        self.assertTrue(out.success)
        self.assertEqual(out.px, (800, 850))
        self.assertEqual(bridge.screenshots, 0)
        self.assertEqual(out.trace["observation"]["observation_id"], "obs-1")

    def test_click_bbox_blocks_unknown_semantic_target(self) -> None:
        bridge = _StubBridge(_make_png(1000, 1000))
        actions = UIActions(bridge, self._registry())

        out = actions.click_bbox(
            "unknown_button",
            {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
        )

        self.assertFalse(out.success)
        self.assertIn("not allowlisted", out.reason or "")
        self.assertEqual(bridge.clicks, [])

    def test_click_bbox_rejects_invalid_bbox(self) -> None:
        bridge = _StubBridge(_make_png(1000, 1000))
        actions = UIActions(bridge, self._registry())

        out = actions.click_bbox(
            "chapter_claim_button",
            {"x_min": 900, "y_min": 800, "x_max": 700, "y_max": 900},
        )

        self.assertFalse(out.success)
        self.assertIn("invalid bbox", out.reason or "")
        self.assertEqual(bridge.clicks, [])

    def test_pan_map_drags_from_center(self) -> None:
        bridge = _StubBridge(_make_png(2000, 1000))
        actions = UIActions(bridge, self._registry(), input_policy=InputPolicy(allow_map_drag=True))
        out = actions.pan_map(dx=-400, dy=0)
        self.assertTrue(out.success)
        self.assertEqual(bridge.drags, [(1000, 500, 600, 500)])
        self.assertEqual(actions.consume_input_trace()[0]["target"]["to"], {"x": 600, "y": 500})

    def test_pan_map_blocks_when_policy_disallows_drag(self) -> None:
        bridge = _StubBridge(_make_png(2000, 1000))
        actions = UIActions(bridge, self._registry())
        out = actions.pan_map(dx=-400, dy=0)
        self.assertFalse(out.success)
        self.assertIn("not enabled", out.reason or "")
        self.assertEqual(bridge.drags, [])

    def test_close_popup_sends_escape(self) -> None:
        bridge = _StubBridge(_make_png())
        actions = UIActions(bridge, self._registry())
        out = actions.close_popup()
        self.assertTrue(out.success)
        self.assertEqual(bridge.keys, ["escape"])
        self.assertEqual(actions.consume_input_trace()[0]["action"], "key_press")


if __name__ == "__main__":
    unittest.main()
