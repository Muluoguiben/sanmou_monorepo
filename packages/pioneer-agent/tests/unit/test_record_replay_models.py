from __future__ import annotations

import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from pioneer_agent.adapters.win_record_replay import capture_relative_point, safe_key_name
from pioneer_agent.record_replay.models import (
    InputEventRecord,
    InputKind,
    RecordingManifest,
    RecordingSafety,
    validate_relative_artifact_path,
)
from tests.unit.record_replay_fixtures import NOW, create_completed_session, geometry


class RecordReplayModelTests(unittest.TestCase):
    def test_m0_safety_cannot_grant_execution_authority(self) -> None:
        with self.assertRaises(ValidationError):
            RecordingSafety.model_validate(
                {
                    "observe_only": False,
                    "input_dispatch": True,
                    "clipboard_recorded": False,
                    "printable_text_recorded": False,
                    "execution_authority": "live",
                    "safe_for_live_replay": True,
                    "privacy_reviewed": False,
                }
            )

    def test_printable_key_is_rejected_and_never_named(self) -> None:
        self.assertIsNone(safe_key_name(ord("A")))
        self.assertEqual(safe_key_name(0x1B), "escape")
        with self.assertRaises(ValidationError):
            InputEventRecord(
                session_id="session",
                sequence=1,
                event_id="event",
                kind=InputKind.KEY_PRESS,
                occurred_at=NOW,
                ended_at=NOW,
                elapsed_ms=0,
                duration_ms=0,
                window_hwnd=123,
                window_pid=456,
                capture_geometry=geometry(),
                key="a",
                before_frame_id="before",
                after_frame_id="after",
            )

    def test_capture_relative_point_uses_capture_origin_not_outer_origin(self) -> None:
        mapped = capture_relative_point(150, 250, geometry().model_dump(mode="json"))
        self.assertEqual(mapped, ({"x": 50, "y": 50}, {"x": 0.5, "y": 0.5}))
        self.assertIsNone(
            capture_relative_point(99, 250, geometry().model_dump(mode="json"))
        )

    def test_naive_input_timestamp_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            InputEventRecord(
                session_id="session",
                sequence=1,
                event_id="event",
                kind=InputKind.KEY_PRESS,
                occurred_at=datetime(2026, 7, 11, 12, 0),
                ended_at=NOW,
                elapsed_ms=0,
                duration_ms=0,
                window_hwnd=123,
                window_pid=456,
                capture_geometry=geometry(),
                key="escape",
                before_frame_id="before",
                after_frame_id="after",
            )

    def test_pointer_kind_rejects_fields_from_another_primitive(self) -> None:
        click = InputEventRecord(
            session_id="session",
            sequence=1,
            event_id="event",
            kind=InputKind.CLICK,
            occurred_at=NOW,
            ended_at=NOW,
            elapsed_ms=0,
            duration_ms=0,
            window_hwnd=123,
            window_pid=456,
            capture_geometry=geometry(),
            start_point={"x": 50, "y": 50},
            start_normalized={"x": 0.5, "y": 0.5},
            button="left",
            before_frame_id="before",
            after_frame_id="after",
        )
        payload = click.model_dump()
        payload["scroll_delta"] = 120

        with self.assertRaisesRegex(ValidationError, "scroll delta"):
            InputEventRecord.model_validate(payload)

    def test_input_duration_must_match_wall_clock_timestamps(self) -> None:
        with self.assertRaisesRegex(ValidationError, "duration_ms"):
            InputEventRecord(
                session_id="session",
                sequence=1,
                event_id="event",
                kind=InputKind.KEY_PRESS,
                occurred_at=NOW,
                ended_at=NOW,
                elapsed_ms=0,
                duration_ms=250,
                window_hwnd=123,
                window_pid=456,
                capture_geometry=geometry(),
                key="escape",
                before_frame_id="before",
                after_frame_id="after",
            )

    def test_artifact_path_must_stay_inside_session(self) -> None:
        self.assertEqual(validate_relative_artifact_path("frames/a.webp"), "frames/a.webp")
        for invalid in (
            "../a.webp",
            "/tmp/a.webp",
            "C:\\a.webp",
            "./a.webp",
            "frames/a\n## injected.webp",
            "frames/a|b.webp",
            "frames/`a`.webp",
            "frames/a b.webp",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_relative_artifact_path(invalid)

    def test_workflow_name_rejects_multiline_and_control_characters(self) -> None:
        with TemporaryDirectory() as tmp:
            manifest = create_completed_session(Path(tmp))
            payload = manifest.model_dump()
            for unsafe_name in (
                "claim reward\n---\nname: injected",
                "claim\treward",
                "claim\x00reward",
                "claim\u200breward",
                "claim\u2028reward",
            ):
                with self.subTest(unsafe_name=repr(unsafe_name)):
                    payload["workflow_name"] = unsafe_name
                    with self.assertRaisesRegex(ValidationError, "control characters"):
                        RecordingManifest.model_validate(payload)

    def test_completed_manifest_requires_a_frame(self) -> None:
        with TemporaryDirectory() as tmp:
            manifest = create_completed_session(Path(tmp))
            payload = manifest.model_dump()
            payload["frame_count"] = 0

            with self.assertRaisesRegex(ValidationError, "at least one frame"):
                RecordingManifest.model_validate(payload)

    def test_manifest_rejects_noncanonical_session_id(self) -> None:
        with TemporaryDirectory() as tmp:
            manifest = create_completed_session(Path(tmp))
            payload = manifest.model_dump()
            payload["session_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa----"

            with self.assertRaisesRegex(ValidationError, "canonical.*UUID"):
                RecordingManifest.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
