"""Tests for the vision bbox locator (find_elements + pixel-coord converter)."""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from pioneer_agent.perception.vision import (
    ElementBox,
    PixelBox,
    find_elements,
    to_pixel_box,
)


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "stub"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _StubVisionClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.last_instruction: str | None = None
        self.last_schema: dict[str, Any] | None = None

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        self.last_instruction = instruction
        self.last_schema = response_schema
        return _StubResult(data=self._payload)


class FindElementsTests(unittest.TestCase):
    def test_parses_matches(self) -> None:
        stub = _StubVisionClient(
            {
                "matches": [
                    {"label": "征兵所", "y_min": 400, "x_min": 450, "y_max": 560, "x_max": 600},
                    {"label": "仓库", "y_min": 700, "x_min": 200, "y_max": 800, "x_max": 320},
                ]
            }
        )
        boxes = find_elements(stub, b"fake-png", "city building icons")
        self.assertEqual(len(boxes), 2)
        self.assertEqual(boxes[0].label, "征兵所")
        self.assertEqual(boxes[0].y_min, 400)
        self.assertEqual(boxes[1].label, "仓库")
        self.assertIn("city building icons", stub.last_instruction)

    def test_empty_matches(self) -> None:
        stub = _StubVisionClient({"matches": []})
        self.assertEqual(find_elements(stub, b"fake", "nothing"), [])


class PixelConversionTests(unittest.TestCase):
    def test_center_of_image(self) -> None:
        box = ElementBox(label="center", y_min=450, x_min=450, y_max=550, x_max=550)
        pix = to_pixel_box(box, image_width=1000, image_height=1000)
        self.assertEqual(pix.x, 450)
        self.assertEqual(pix.y, 450)
        self.assertEqual(pix.width, 100)
        self.assertEqual(pix.height, 100)
        self.assertEqual(pix.center, (500, 500))

    def test_scales_to_window(self) -> None:
        # Window is 1920x1080, bbox spans top-left quadrant (0-500 x 0-500 in normalized)
        box = ElementBox(label="tl", y_min=0, x_min=0, y_max=500, x_max=500)
        pix = to_pixel_box(box, image_width=1920, image_height=1080)
        self.assertEqual(pix.x, 0)
        self.assertEqual(pix.y, 0)
        self.assertEqual(pix.width, 960)
        self.assertEqual(pix.height, 540)
        self.assertEqual(pix.center, (480, 270))

    def test_inverted_box_is_corrected(self) -> None:
        box = ElementBox(label="bad", y_min=600, x_min=700, y_max=400, x_max=500)
        pix = to_pixel_box(box, image_width=1000, image_height=1000)
        self.assertEqual(pix.x, 500)
        self.assertEqual(pix.y, 400)
        self.assertEqual(pix.width, 200)
        self.assertEqual(pix.height, 200)

    def test_zero_size_box_gets_minimum(self) -> None:
        box = ElementBox(label="dot", y_min=500, x_min=500, y_max=500, x_max=500)
        pix = to_pixel_box(box, image_width=1000, image_height=1000)
        self.assertEqual(pix.width, 1)
        self.assertEqual(pix.height, 1)

    def test_returns_pixel_box_type(self) -> None:
        box = ElementBox(label="x", y_min=0, x_min=0, y_max=100, x_max=100)
        pix = to_pixel_box(box, 800, 600)
        self.assertIsInstance(pix, PixelBox)


if __name__ == "__main__":
    unittest.main()
