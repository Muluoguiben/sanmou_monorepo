"""Validate reviewed PC-client screenshot fixture metadata."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from PIL import Image


FIXTURE_DIR = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "screenshots"
    / "pc_client"
    / "live_20260518"
)


class PCClientScreenshotFixtureTests(unittest.TestCase):
    def test_manifest_images_exist_with_expected_size(self) -> None:
        manifest = _load_manifest()
        fixture_size = (
            manifest["device"]["fixture_size"]["width"],
            manifest["device"]["fixture_size"]["height"],
        )

        screenshots = manifest["screenshots"]
        self.assertGreaterEqual(len(screenshots), 4)
        pages = {shot["page"] for shot in screenshots}
        self.assertIn("startup_notice_popup", pages)
        self.assertIn("server_selection", pages)
        self.assertIn("main_city", pages)
        self.assertIn("world_map_target", pages)

        for shot in screenshots:
            image_path = FIXTURE_DIR / shot["image"]
            self.assertTrue(image_path.exists(), shot["id"])
            self.assertEqual(image_path.suffix, ".jpg", shot["id"])
            self.assertGreater(image_path.stat().st_size, 40_000, shot["id"])
            self.assertLess(image_path.stat().st_size, 300_000, shot["id"])
            with Image.open(image_path) as image:
                self.assertEqual(image.size, fixture_size, shot["id"])

    def test_click_targets_are_normalized_and_match_pixels(self) -> None:
        manifest = _load_manifest()
        live_width = manifest["device"]["capture_size"]["width"]
        live_height = manifest["device"]["capture_size"]["height"]
        fixture_width = manifest["device"]["fixture_size"]["width"]
        fixture_height = manifest["device"]["fixture_size"]["height"]

        for shot in manifest["screenshots"]:
            for target in shot["click_targets"]:
                rx = target["rx"]
                ry = target["ry"]
                self.assertGreaterEqual(rx, 0.0, target["key"])
                self.assertLessEqual(rx, 1.0, target["key"])
                self.assertGreaterEqual(ry, 0.0, target["key"])
                self.assertLessEqual(ry, 1.0, target["key"])

                live_px, live_py = target["live_pixel"]
                self.assertLessEqual(
                    abs(round(rx * live_width) - live_px), 2, target["key"]
                )
                self.assertLessEqual(
                    abs(round(ry * live_height) - live_py), 2, target["key"]
                )

                fixture_px, fixture_py = target["fixture_pixel"]
                self.assertLessEqual(
                    abs(round(rx * fixture_width) - fixture_px), 2, target["key"]
                )
                self.assertLessEqual(
                    abs(round(ry * fixture_height) - fixture_py), 2, target["key"]
                )


def _load_manifest() -> dict:
    return json.loads((FIXTURE_DIR / "manifest.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
