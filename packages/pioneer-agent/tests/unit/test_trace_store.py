"""Tests for structured JSONL trace storage."""
from __future__ import annotations

import unittest
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from pioneer_agent.core.models import ObservationSnapshot, RuntimeState
from pioneer_agent.storage.trace_store import (
    CoordinateTraceMetadata,
    ImageSize,
    NormalizedBBox,
    PixelBBox,
    PixelPoint,
    ScreenshotTraceMetadata,
    TickTrace,
    TraceFrameRole,
    TracePhase,
    TraceStep,
    TraceStore,
)


class TraceStoreTests(unittest.TestCase):
    def test_round_trips_tick_trace_with_coordinate_metadata(self) -> None:
        with TemporaryDirectory() as tmp:
            store = TraceStore(Path(tmp) / "trace.jsonl")
            trace = TickTrace(
                session_id="session-1",
                iteration=7,
                current_phase=TracePhase.TRACE,
                screenshot=ScreenshotTraceMetadata(
                    path="screenshots/0007.png",
                    raw_size=ImageSize(width=2532, height=1170),
                    prepared_size=ImageSize(width=1266, height=585),
                    display_coordinate_space="display:absolute",
                    window_coordinate_space="window:relative",
                    coordinates=[
                        CoordinateTraceMetadata(
                            coordinate_space="window",
                            dpr=2.0,
                            scale=0.5,
                            normalized_bbox=NormalizedBBox(x=0.1, y=0.2, width=0.3, height=0.4),
                            pixel_bbox=PixelBBox(x=126, y=117, width=380, height=234),
                            click_point=PixelPoint(x=316, y=234),
                        )
                    ],
                ),
                observe=TraceStep(
                    phase=TracePhase.OBSERVE,
                    outputs={"page_type": "city"},
                ),
                decide=TraceStep(
                    phase=TracePhase.DECIDE,
                    outputs={"selected_action_id": "claim-1"},
                ),
                act=TraceStep(
                    phase=TracePhase.ACT,
                    inputs={"action_id": "claim-1"},
                    outputs={"status": "pending"},
                ),
                verify=TraceStep(
                    phase=TracePhase.VERIFY,
                    outputs={"status": "skipped"},
                ),
                trace=TraceStep(phase=TracePhase.TRACE),
                recover=TraceStep(
                    phase=TracePhase.RECOVER,
                    recovery_strategy="esc_then_reobserve",
                ),
                state_before={"resources": {"wood": 100}},
                vision={"domains_run": ["resource_bar"]},
                state_after={"resources": {"wood": 100}},
                selected_action={"action_id": "claim-1", "action_type": "claim_chapter_reward"},
                execution={"status": "pending"},
                verification={"status": "skipped"},
                recovery={"strategy": "esc_then_reobserve"},
            )

            store.append(trace)
            records = store.read()

            self.assertEqual(len(records), 1)
            loaded = records[0]
            self.assertEqual(loaded.iteration, 7)
            self.assertEqual(loaded.current_phase, TracePhase.TRACE)
            self.assertEqual(loaded.observe.phase, TracePhase.OBSERVE)
            self.assertEqual(loaded.selected_action["action_id"], "claim-1")
            self.assertEqual(loaded.screenshot.raw_size.width, 2532)
            self.assertEqual(loaded.screenshot.prepared_size.height, 585)
            self.assertEqual(loaded.screenshot.display_coordinate_space, "display:absolute")
            self.assertEqual(loaded.screenshot.window_coordinate_space, "window:relative")
            coord = loaded.screenshot.coordinates[0]
            self.assertEqual(coord.coordinate_space, "window")
            self.assertEqual(coord.dpr, 2.0)
            self.assertEqual(coord.scale, 0.5)
            self.assertEqual(coord.normalized_bbox.x, 0.1)
            self.assertEqual(coord.pixel_bbox.width, 380)
            self.assertEqual(coord.click_point.x, 316)

    def test_missing_optional_fields_do_not_crash(self) -> None:
        with TemporaryDirectory() as tmp:
            store = TraceStore(Path(tmp) / "trace.jsonl")
            store.append(TickTrace(iteration=0))

            records = store.read()

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].iteration, 0)
            self.assertIsNone(records[0].screenshot)
            self.assertIsNone(records[0].observe)
            self.assertEqual(records[0].ranked_actions, [])
            self.assertEqual(records[0].metadata, {})

    def test_read_missing_trace_file_returns_empty_list(self) -> None:
        with TemporaryDirectory() as tmp:
            store = TraceStore(Path(tmp) / "missing.jsonl")

            self.assertEqual(store.read(), [])

    def test_saves_sha_bound_frame_reference_and_round_trips_it(self) -> None:
        with TemporaryDirectory() as tmp:
            store = TraceStore(Path(tmp) / "trace.jsonl")
            buffer = BytesIO()
            Image.new("RGB", (16, 9), (1, 2, 3)).save(buffer, format="PNG")
            png = buffer.getvalue()
            digest = sha256(png).hexdigest()
            observation = ObservationSnapshot(
                observation_id="obs-terminal",
                captured_at=datetime(2026, 7, 10, 12, 0, tzinfo=UTC),
                frame_sha256=digest,
                frame_size=(16, 9),
                page_type="upgrade_dialog",
                domains_run=["resource_bar", "upgrade_dialog"],
                observed_state=RuntimeState(),
                source="vision_sync",
            )

            frame = store.save_frame(
                iteration=3,
                role=TraceFrameRole.TERMINAL_DISPATCH,
                png=png,
                observation=observation,
            )
            store.append(TickTrace(iteration=3, frames=[frame]))

            self.assertTrue(Path(frame.path).is_file())
            self.assertEqual(frame.sha256, digest)
            loaded = store.read()[0].frames[0]
            self.assertEqual(loaded.role, TraceFrameRole.TERMINAL_DISPATCH)
            self.assertEqual(loaded.observation["observation_id"], "obs-terminal")

            with self.assertRaises(ValueError):
                store.save_frame(
                    iteration=3,
                    role=TraceFrameRole.POST_ACTION,
                    png=b"different",
                    observation=observation,
                )


if __name__ == "__main__":
    unittest.main()
