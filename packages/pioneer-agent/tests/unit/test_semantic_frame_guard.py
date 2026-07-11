from __future__ import annotations

import hashlib
import io
import unittest

from PIL import Image, ImageDraw

from pioneer_agent.core.models import CaptureGeometry
from pioneer_agent.executor.semantic_frame_guard import (
    build_semantic_frame_guard,
    semantic_target_geometry,
)


class SemanticFrameGuardTests(unittest.TestCase):
    bbox = {"x_min": 700, "y_min": 700, "x_max": 900, "y_max": 900}

    def test_hashes_decoded_rgb_crop_not_png_encoding(self) -> None:
        image = Image.new("RGB", (100, 100), (10, 20, 30))
        first = _encode(image, compress_level=0)
        second = _encode(image, compress_level=9)

        self.assertNotEqual(hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest())
        first_guard = build_semantic_frame_guard(
            first,
            frame_size=(100, 100),
            capture_geometry=_capture_geometry((100, 100)),
            semantic_target_key="chapter_claim_button",
            bbox=self.bbox,
        )
        second_guard = build_semantic_frame_guard(
            second,
            frame_size=(100, 100),
            capture_geometry=_capture_geometry((100, 100)),
            semantic_target_key="chapter_claim_button",
            bbox=self.bbox,
        )
        self.assertEqual(first_guard.roi_sha256, second_guard.roi_sha256)

    def test_ignores_pixels_outside_exact_target_but_not_inside(self) -> None:
        baseline = Image.new("RGB", (100, 100), (10, 20, 30))
        outside_changed = baseline.copy()
        ImageDraw.Draw(outside_changed).rectangle((0, 0, 20, 20), fill=(200, 0, 0))
        inside_changed = baseline.copy()
        ImageDraw.Draw(inside_changed).rectangle((75, 75, 80, 80), fill=(0, 200, 0))

        guards = [
            build_semantic_frame_guard(
                _encode(image),
                frame_size=(100, 100),
                capture_geometry=_capture_geometry((100, 100)),
                semantic_target_key="chapter_claim_button",
                bbox=self.bbox,
            )
            for image in (baseline, outside_changed, inside_changed)
        ]

        self.assertEqual(guards[0].roi_sha256, guards[1].roi_sha256)
        self.assertNotEqual(guards[0].roi_sha256, guards[2].roi_sha256)
        self.assertEqual(guards[0].roi_bbox.model_dump(), {"x": 70, "y": 70, "width": 20, "height": 20})
        self.assertEqual(guards[0].click_point.model_dump(), {"x": 80, "y": 80})

    def test_narrow_bbox_clamps_click_inside_half_open_roi(self) -> None:
        roi, click = semantic_target_geometry(
            (1920, 1080),
            {"x_min": 18, "y_min": 18, "x_max": 19, "y_max": 19},
        )

        self.assertEqual(roi.model_dump(), {"x": 35, "y": 19, "width": 1, "height": 2})
        self.assertEqual(click.x, 35)
        self.assertTrue(roi.x <= click.x < roi.x + roi.width)
        self.assertTrue(roi.y <= click.y < roi.y + roi.height)

    def test_rejects_zero_pixel_and_non_finite_or_coerced_bbox(self) -> None:
        invalid = (
            {"x_min": 0, "y_min": 0, "x_max": 0.1, "y_max": 0.1},
            {"x_min": False, "y_min": 0, "x_max": 10, "y_max": 10},
            {"x_min": "0", "y_min": 0, "x_max": 10, "y_max": 10},
            {"x_min": 0, "y_min": 0, "x_max": float("nan"), "y_max": 10},
            {"x_min": 0, "y_min": 0, "x_max": float("inf"), "y_max": 10},
        )
        for bbox in invalid:
            with self.subTest(bbox=bbox), self.assertRaises(ValueError):
                semantic_target_geometry((100, 100), bbox)


def _encode(image: Image.Image, *, compress_level: int = 6) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=compress_level)
    return buffer.getvalue()


def _capture_geometry(size: tuple[int, int]) -> CaptureGeometry:
    width, height = size
    return CaptureGeometry.model_validate(
        {
            "schema_version": 1,
            "capture_backend": "wgc",
            "outer_window": {
                "hwnd": 101,
                "pid": 202,
                "left": 0,
                "top": 0,
                "right": width,
                "bottom": height,
                "width": width,
                "height": height,
            },
            "capture_rect": {
                "left": 0,
                "top": 0,
                "right": width,
                "bottom": height,
                "width": width,
                "height": height,
            },
            "capture_origin": {"x": 0, "y": 0},
            "frame_size": [width, height],
        }
    )


if __name__ == "__main__":
    unittest.main()
