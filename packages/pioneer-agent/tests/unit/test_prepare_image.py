from __future__ import annotations

import io
import unittest

from PIL import Image

from pioneer_agent.perception.vision.image import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_WIDTH,
    prepare_image,
)


def _make_png(width: int, height: int, *, solid: tuple[int, int, int] | None = None) -> bytes:
    image = Image.new("RGB", (width, height), color=solid or (255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class PrepareImageTests(unittest.TestCase):
    def test_prepare_image_keeps_small_images_within_constraints(self) -> None:
        raw = _make_png(800, 480)

        prepared = prepare_image(raw)

        self.assertEqual(prepared.original_size, (800, 480))
        self.assertEqual(prepared.prepared_size, (800, 480))
        self.assertFalse(prepared.resized)
        self.assertEqual(prepared.data, raw)

    def test_prepare_image_reduces_to_api_fit_for_wide_images(self) -> None:
        raw = _make_png(4000, 1000)
        prepared = prepare_image(raw)

        width, height = prepared.prepared_size
        self.assertLessEqual(width, MAX_IMAGE_WIDTH)
        self.assertLessEqual(height, MAX_IMAGE_WIDTH)
        self.assertLessEqual(width * height, MAX_IMAGE_PIXELS)
        self.assertTrue(prepared.resized)
        self.assertAlmostEqual(width / height, 4.0, delta=0.03)

    def test_prepare_image_reduces_to_api_fit_for_tall_images(self) -> None:
        raw = _make_png(1000, 4000)
        prepared = prepare_image(raw)

        width, height = prepared.prepared_size
        self.assertLessEqual(width, MAX_IMAGE_WIDTH)
        self.assertLessEqual(height, MAX_IMAGE_WIDTH)
        self.assertLessEqual(width * height, MAX_IMAGE_PIXELS)
        self.assertTrue(prepared.resized)

    def test_prepare_image_further_reduces_noisy_large_images(self) -> None:
        noisy = Image.effect_noise((2000, 2000), 100).convert("RGB")
        buffer = io.BytesIO()
        noisy.save(buffer, format="PNG")
        raw = buffer.getvalue()

        prepared = prepare_image(raw)

        self.assertLessEqual(len(prepared.data), MAX_IMAGE_BYTES)
        self.assertLessEqual(prepared.prepared_size[0] * prepared.prepared_size[1], MAX_IMAGE_PIXELS)
        self.assertTrue(prepared.resized)


if __name__ == "__main__":
    unittest.main()
