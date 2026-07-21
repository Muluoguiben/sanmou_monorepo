from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
import unittest
from unittest.mock import patch
from uuid import uuid4

from PIL import Image, ImageDraw, ImageOps

from pioneer_agent.core.models import CaptureGeometry
from pioneer_agent.record_replay.models import FrameRecord, FrameRole, ImageFormat
from pioneer_agent.record_replay.visual_fingerprint import (
    VISUAL_FINGERPRINT_ALGORITHM,
    audit_visual_near_duplicates,
    fingerprint_frame,
)


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)


def _geometry(width: int, height: int) -> CaptureGeometry:
    return CaptureGeometry.model_validate(
        {
            "schema_version": 1,
            "capture_backend": "wgc",
            "outer_window": {
                "hwnd": 123,
                "pid": 456,
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


def _scene() -> Image.Image:
    width, height = 160, 120
    image = Image.new("RGB", (width, height))
    image.putdata(
        [
            (
                (x * 3 + y * 2) % 256,
                (x + y * 5) % 256,
                (x * 7 + y) % 256,
            )
            for y in range(height)
            for x in range(width)
        ]
    )
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 16, 72, 50), outline=(250, 240, 40), width=4)
    draw.ellipse((90, 56, 138, 104), fill=(30, 170, 210), outline=(255, 255, 255))
    draw.line((0, 100, 159, 25), fill=(220, 20, 100), width=3)
    return image


def _encode(image: Image.Image, image_format: ImageFormat) -> bytes:
    buffer = BytesIO()
    if image_format == ImageFormat.WEBP:
        image.save(buffer, format="WEBP", quality=58, method=6)
    else:
        image.save(buffer, format="PNG", compress_level=7)
    return buffer.getvalue()


def _frame(
    image: Image.Image,
    *,
    session_id: str,
    image_format: ImageFormat = ImageFormat.PNG,
) -> tuple[FrameRecord, bytes]:
    payload = _encode(image, image_format)
    suffix = image_format.value
    record = FrameRecord(
        session_id=session_id,
        sequence=0,
        frame_id="frame-0",
        role=FrameRole.START,
        captured_at=NOW,
        elapsed_ms=0,
        path=f"frames/000000-start.{suffix}",
        sha256=sha256(payload).hexdigest(),
        byte_size=len(payload),
        image_format=image_format,
        image_size=image.size,
        source_png_sha256=sha256(b"source-" + session_id.encode()).hexdigest(),
        capture_geometry=_geometry(*image.size),
    )
    return record, payload


class RecordReplayVisualFingerprintTests(unittest.TestCase):
    def test_reencoded_and_resized_scene_is_rejected_across_sessions(self) -> None:
        original_record, original_payload = _frame(
            _scene(), session_id=str(uuid4())
        )
        resized_record, resized_payload = _frame(
            _scene().resize((128, 96), Image.Resampling.LANCZOS),
            session_id=str(uuid4()),
            image_format=ImageFormat.WEBP,
        )

        fingerprints = [
            fingerprint_frame(original_record, original_payload),
            fingerprint_frame(resized_record, resized_payload),
        ]

        with self.assertRaisesRegex(ValueError, "visual near-duplicate"):
            audit_visual_near_duplicates(fingerprints)

    def test_small_center_crop_is_rejected_across_sessions(self) -> None:
        image = _scene()
        cropped = image.crop((4, 3, 156, 117)).resize(
            image.size, Image.Resampling.LANCZOS
        )
        first_record, first_payload = _frame(image, session_id=str(uuid4()))
        second_record, second_payload = _frame(cropped, session_id=str(uuid4()))

        with self.assertRaisesRegex(ValueError, "visual near-duplicate"):
            audit_visual_near_duplicates(
                [
                    fingerprint_frame(first_record, first_payload),
                    fingerprint_frame(second_record, second_payload),
                ]
            )

    def test_meaningfully_different_scene_is_not_rejected(self) -> None:
        first_record, first_payload = _frame(_scene(), session_id=str(uuid4()))
        second_record, second_payload = _frame(
            ImageOps.invert(_scene()).transpose(Image.Transpose.FLIP_LEFT_RIGHT),
            session_id=str(uuid4()),
        )

        report = audit_visual_near_duplicates(
            [
                fingerprint_frame(first_record, first_payload),
                fingerprint_frame(second_record, second_payload),
            ]
        )

        self.assertEqual(report.algorithm, VISUAL_FINGERPRINT_ALGORITHM)
        self.assertEqual(report.frame_count, 2)

    def test_same_session_frames_are_not_a_split_leak(self) -> None:
        session_id = str(uuid4())
        record, payload = _frame(_scene(), session_id=session_id)
        first = fingerprint_frame(record, payload)
        second = replace(first, frame_id="frame-1")

        report = audit_visual_near_duplicates([first, second])

        self.assertEqual(report.frame_count, 2)
        self.assertEqual(report.candidate_comparison_count, 0)

    def test_corrupt_or_mismatched_pixels_fail_closed(self) -> None:
        record, payload = _frame(_scene(), session_id=str(uuid4()))
        with self.assertRaisesRegex(ValueError, "cannot be decoded"):
            fingerprint_frame(record, b"not-an-image")

        webp_claim = record.model_copy(update={"image_format": ImageFormat.WEBP})
        with self.assertRaisesRegex(ValueError, "format does not match"):
            fingerprint_frame(webp_claim, payload)

        wrong_size = record.model_copy(update={"image_size": (159, 120)})
        with self.assertRaisesRegex(ValueError, "dimensions do not match"):
            fingerprint_frame(wrong_size, payload)

    def test_decoder_and_corpus_resource_limits_fail_closed(self) -> None:
        record, payload = _frame(_scene(), session_id=str(uuid4()))
        with patch(
            "pioneer_agent.record_replay.visual_fingerprint.MAX_DECODED_PIXELS",
            10,
        ), self.assertRaisesRegex(ValueError, "decoded pixel limits"):
            fingerprint_frame(record, payload)

        fingerprint = fingerprint_frame(record, payload)
        with patch(
            "pioneer_agent.record_replay.visual_fingerprint.MAX_VISUAL_FRAMES",
            0,
        ), self.assertRaisesRegex(ValueError, "frame limit"):
            audit_visual_near_duplicates([fingerprint])
        with patch(
            "pioneer_agent.record_replay.visual_fingerprint.MAX_TOTAL_DECODED_PIXELS",
            1,
        ), self.assertRaisesRegex(ValueError, "pixel limit"):
            audit_visual_near_duplicates([fingerprint])

        other = replace(
            fingerprint,
            session_id=str(uuid4()),
            frame_id="frame-other",
        )
        with patch(
            "pioneer_agent.record_replay.visual_fingerprint.MAX_VISUAL_CANDIDATE_COMPARISONS",
            0,
        ), self.assertRaisesRegex(ValueError, "comparison limit"):
            audit_visual_near_duplicates([fingerprint, other])


if __name__ == "__main__":
    unittest.main()
