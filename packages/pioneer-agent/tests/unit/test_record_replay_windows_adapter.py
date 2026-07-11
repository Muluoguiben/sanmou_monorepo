from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import queue
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import threading
import time
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from pioneer_agent.adapters.win_record_replay import (
    MAX_BATCH_EVENTS,
    _build_input_record,
    _collect_input_batch,
    _manifest,
    _prepare_frame_file,
    _validate_record_args,
    record,
)
from pioneer_agent.record_replay.models import RecordingManifest
from pioneer_agent.record_replay.session_store import load_recording
from tests.unit.record_replay_fixtures import NOW, geometry, png_bytes


class RecordReplayWindowsAdapterTests(unittest.TestCase):
    def test_helper_finalizes_a_strictly_loadable_session(self) -> None:
        class StopAfterBatch:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls >= 4

        class FakeCollector:
            def __init__(self, *_: object, **__: object) -> None:
                now_ns = time.perf_counter_ns()
                now_iso = datetime.now(UTC).isoformat()
                self.events: queue.Queue[dict[str, object]] = queue.Queue()
                self.events.put(
                    {
                        "kind": "click",
                        "button": "left",
                        "start_abs": {"x": 150, "y": 250},
                        "end_abs": {"x": 150, "y": 250},
                        "started_ns": now_ns,
                        "ended_ns": now_ns,
                        "occurred_at": now_iso,
                        "ended_at": now_iso,
                        "modifiers": [],
                    }
                )
                self.stop_requested = StopAfterBatch()
                self.pointer_gesture_active = threading.Event()
                self.fatal_error = None
                self.ignored_event_count = 0

            def start(self) -> None:
                return None

            def stop(self) -> None:
                return None

        args = argparse.Namespace(
            session_id=str(uuid4()),
            workflow_name="open recruit panel",
            duration_seconds=0.0,
            backend="auto",
            settle_ms=100,
            long_edge=1280,
            image_format="webp",
            webp_quality=60,
            max_events=10,
            max_bytes=1_048_576,
        )
        capture_module = Mock()
        capture_payload = png_bytes((1, 2, 3))
        capture_geometry = geometry().model_dump(mode="json")

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / args.session_id
            with (
                patch(
                    "pioneer_agent.adapters.win_record_replay._require_windows_runtime"
                ),
                patch(
                    "pioneer_agent.adapters.win_record_replay._load_capture_module",
                    return_value=capture_module,
                ),
                patch(
                    "pioneer_agent.adapters.win_record_replay._resolve_target_window",
                    return_value=(123, 456, "三国：谋定天下", NOW.isoformat()),
                ),
                patch(
                    "pioneer_agent.adapters.win_record_replay._capture",
                    return_value=(capture_payload, capture_geometry),
                ),
                patch(
                    "pioneer_agent.adapters.win_record_replay._assert_same_target"
                ),
                patch(
                    "pioneer_agent.adapters.win_record_replay._session_root",
                    return_value=root,
                ),
                patch(
                    "pioneer_agent.adapters.win_record_replay.RawInputCollector",
                    FakeCollector,
                ),
            ):
                completed_root = record(args)

            recording = load_recording(completed_root)

        capture_module._enable_physical_pixel_coordinates.assert_called_once_with()
        self.assertEqual(recording.manifest.status.value, "completed")
        self.assertEqual(recording.manifest.stop_reason, "hotkey")
        self.assertEqual(len(recording.input_events), 1)
        self.assertEqual(recording.frames[0].role.value, "start")
        self.assertEqual(recording.frames[-1].role.value, "end")

    def test_helper_manifest_obeys_non_executable_schema(self) -> None:
        value = _manifest(
            session_id=str(uuid4()),
            workflow_name="open recruit panel",
            status="recording",
            started_at=NOW,
            target={
                "process_name": "com.bilibili.nslg",
                "window_class": "UnityWndClass",
                "hwnd": 123,
                "pid": 456,
                "process_started_at": NOW.isoformat(),
                "title": "三国：谋定天下",
            },
            initial_geometry=geometry().model_dump(mode="json"),
            settings={
                "backend": "auto",
                "settle_ms": 350,
                "long_edge": 1280,
                "image_format": "webp",
                "webp_quality": 60,
                "max_events": 500,
                "max_bytes": 268_435_456,
            },
        )

        manifest = RecordingManifest.model_validate(value)

        self.assertTrue(manifest.safety.observe_only)
        self.assertFalse(manifest.safety.input_dispatch)
        self.assertFalse(manifest.safety.safe_for_live_replay)
        self.assertFalse(manifest.closure_eligible)

    def test_build_pointer_record_uses_pre_input_capture_geometry(self) -> None:
        value = _build_input_record(
            {
                "kind": "click",
                "button": "left",
                "start_abs": {"x": 150, "y": 250},
                "end_abs": {"x": 150, "y": 250},
                "started_ns": 1_100_000_000,
                "ended_ns": 1_120_000_000,
                "occurred_at": NOW.isoformat(),
                "ended_at": NOW.isoformat(),
                "modifiers": [],
            },
            session_id=str(uuid4()),
            started_ns=1_000_000_000,
            hwnd=123,
            pid=456,
            geometry=geometry().model_dump(mode="json"),
            before_frame_id="before",
            after_frame_id="after",
            ambiguous_burst=False,
            geometry_changed=False,
        )

        self.assertIsNotNone(value)
        self.assertEqual(value["start_point"], {"x": 50, "y": 50})
        self.assertEqual(value["before_frame_id"], "before")
        self.assertTrue(value["printable_text_omitted"])

    def test_build_pointer_record_rejects_point_outside_capture(self) -> None:
        value = _build_input_record(
            {
                "kind": "click",
                "button": "left",
                "start_abs": {"x": 99, "y": 250},
                "end_abs": {"x": 99, "y": 250},
                "started_ns": 1,
                "ended_ns": 2,
                "occurred_at": NOW.isoformat(),
                "ended_at": NOW.isoformat(),
                "modifiers": [],
            },
            session_id=str(uuid4()),
            started_ns=0,
            hwnd=123,
            pid=456,
            geometry=geometry().model_dump(mode="json"),
            before_frame_id="before",
            after_frame_id="after",
            ambiguous_burst=False,
            geometry_changed=False,
        )

        self.assertIsNone(value)

    def test_batch_has_hard_event_cap_even_without_quiet_period(self) -> None:
        events: queue.Queue[dict[str, object]] = queue.Queue()
        for sequence in range(MAX_BATCH_EVENTS + 20):
            events.put({"sequence": sequence})
        collector = SimpleNamespace(events=events)

        batch, stop_reason = _collect_input_batch(
            {"sequence": -1},
            collector=collector,
            settle_ms=100,
            remaining_event_budget=1_000,
            stop_check=lambda: None,
        )

        self.assertEqual(len(batch), MAX_BATCH_EVENTS)
        self.assertIsNone(stop_reason)
        self.assertFalse(events.empty())

    def test_batch_obeys_stop_before_waiting_for_quiet(self) -> None:
        collector = SimpleNamespace(events=queue.Queue())

        batch, stop_reason = _collect_input_batch(
            {"sequence": 1},
            collector=collector,
            settle_ms=2_000,
            remaining_event_budget=10,
            stop_check=lambda: "hotkey",
        )

        self.assertEqual(batch, [{"sequence": 1}])
        self.assertEqual(stop_reason, "hotkey")

    def test_compressed_frame_filenames_cannot_collide(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = png_bytes((1, 2, 3))

            first = _prepare_frame_file(
                root,
                sequence=2,
                role="post-input",
                png=payload,
                image_format="webp",
                long_edge=1280,
                webp_quality=60,
            )
            second = _prepare_frame_file(
                root,
                sequence=2,
                role="post-input",
                png=payload,
                image_format="webp",
                long_edge=1280,
                webp_quality=60,
            )

            self.assertNotEqual(first["path"], second["path"])
            self.assertEqual(len(list(root.glob("*.webp"))), 2)

    def test_direct_helper_arguments_enforce_same_limits_as_cli(self) -> None:
        args = argparse.Namespace(
            workflow_name="valid workflow",
            duration_seconds=60.0,
            settle_ms=350,
            long_edge=1280,
            webp_quality=60,
            max_events=500,
            max_bytes=1_048_576,
        )
        _validate_record_args(args)

        for unsafe_name in ("frontmatter\ninjection", "zero\u200bwidth"):
            with self.subTest(unsafe_name=repr(unsafe_name)):
                args.workflow_name = unsafe_name
                with self.assertRaisesRegex(ValueError, "control characters"):
                    _validate_record_args(args)


if __name__ == "__main__":
    unittest.main()
