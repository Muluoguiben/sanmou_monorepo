from __future__ import annotations

import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable
import unittest

from pioneer_agent.record_replay.session_store import load_recording
from tests.unit.record_replay_fixtures import NOW, create_completed_session


def _rewrite_events(
    root: Path,
    mutate: Callable[[list[dict[str, object]]], None],
) -> list[dict[str, object]]:
    records = [
        json.loads(line)
        for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    mutate(records)
    payload = b"".join(
        (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        for record in records
    )
    (root / "events.jsonl").write_bytes(payload)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["events_sha256"] = hashlib.sha256(payload).hexdigest()
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return records


def _rewrite_manifest(
    root: Path,
    mutate: Callable[[dict[str, object]], None],
) -> None:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    mutate(manifest)
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )


class RecordReplaySessionTests(unittest.TestCase):
    def test_loads_and_validates_completed_session(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = create_completed_session(root)
            recording = load_recording(root)

            self.assertEqual(recording.manifest.session_id, manifest.session_id)
            self.assertEqual(len(recording.frames), 3)
            self.assertEqual(len(recording.input_events), 1)

    def test_rejects_tampered_events(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            with (root / "events.jsonl").open("ab") as handle:
                handle.write(b"{}\n")

            with self.assertRaisesRegex(ValueError, "SHA256"):
                load_recording(root)

    def test_rejects_tampered_frame(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            (root / "frames" / "000002-post.png").write_bytes(b"tampered")

            with self.assertRaisesRegex(ValueError, "frame size mismatch"):
                load_recording(root)

    @unittest.skipIf(os.name == "nt", "symlink semantics are covered on the WSL test host")
    def test_rejects_symlinked_frame(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            frame = root / "frames" / "000002-post.png"
            target = root / "outside.png"
            target.write_bytes(frame.read_bytes())
            frame.unlink()
            frame.symlink_to(target)

            with self.assertRaisesRegex(ValueError, "symlink"):
                load_recording(root)

    def test_rejects_path_escape_even_when_manifest_hash_is_updated(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            lines = (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
            first = json.loads(lines[0])
            first["path"] = "../outside.png"
            lines[0] = json.dumps(first)
            payload = ("\n".join(lines) + "\n").encode()
            (root / "events.jsonl").write_bytes(payload)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            import hashlib

            manifest["events_sha256"] = hashlib.sha256(payload).hexdigest()
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "invalid recording event"):
                load_recording(root)

    def test_completed_session_allows_an_optional_pre_input_frame(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            pre_path = root / "frames" / "000001-pre.png"
            pre_payload = (root / "frames" / "000000-start.png").read_bytes()
            pre_path.write_bytes(pre_payload)

            def add_pre_input(records: list[dict[str, object]]) -> None:
                pre_input = dict(records[0])
                pre_input.update(
                    {
                        "sequence": 1,
                        "frame_id": "frame-pre-input",
                        "role": "pre_input",
                        "captured_at": (NOW + timedelta(milliseconds=50)).isoformat(),
                        "elapsed_ms": 50,
                        "path": "frames/000001-pre.png",
                    }
                )
                records.insert(1, pre_input)
                for sequence, record in enumerate(records):
                    record["sequence"] = sequence
                records[2]["before_frame_id"] = "frame-pre-input"

            _rewrite_events(root, add_pre_input)

            def update_counts(manifest: dict[str, object]) -> None:
                manifest["record_count"] = 5
                manifest["frame_count"] = 4
                manifest["total_frame_bytes"] = int(manifest["total_frame_bytes"]) + len(
                    pre_payload
                )

            _rewrite_manifest(root, update_counts)

            recording = load_recording(root)
            self.assertEqual(len(recording.frames), 4)
            self.assertEqual(recording.frames[1].role.value, "pre_input")

    def test_rejects_duplicate_start_frame(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            _rewrite_events(root, lambda records: records[2].update(role="start"))

            with self.assertRaisesRegex(ValueError, "exactly one start"):
                load_recording(root)

    def test_rejects_duplicate_end_frame(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            _rewrite_events(root, lambda records: records[2].update(role="end"))

            with self.assertRaisesRegex(ValueError, "exactly one end"):
                load_recording(root)

    def test_rejects_start_frame_that_is_not_first(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            def move_start(records: list[dict[str, object]]) -> None:
                records[0]["role"] = "pre_input"
                records[2]["role"] = "start"

            _rewrite_events(root, move_start)

            with self.assertRaisesRegex(ValueError, "start frame must be the first"):
                load_recording(root)

    def test_rejects_end_frame_that_is_not_last(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            def move_end(records: list[dict[str, object]]) -> None:
                records[2]["role"] = "end"
                records[3]["role"] = "post_input"

            _rewrite_events(root, move_end)

            with self.assertRaisesRegex(ValueError, "end frame must be the last"):
                load_recording(root)

    def test_rejects_start_geometry_that_differs_from_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            def change_initial_geometry(manifest: dict[str, object]) -> None:
                geometry = manifest["initial_capture_geometry"]
                assert isinstance(geometry, dict)
                geometry["capture_backend"] = "dxgi"

            _rewrite_manifest(root, change_initial_geometry)

            with self.assertRaisesRegex(ValueError, "start frame geometry"):
                load_recording(root)

    def test_rejects_frame_bound_to_another_window(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            def change_frame_target(records: list[dict[str, object]]) -> None:
                records[2]["capture_geometry"]["outer_window"]["hwnd"] = 999

            _rewrite_events(root, change_frame_target)

            with self.assertRaisesRegex(ValueError, "frame target"):
                load_recording(root)

    def test_rejects_capture_error_count_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            _rewrite_manifest(
                root, lambda manifest: manifest.update(capture_error_count=1)
            )

            with self.assertRaisesRegex(ValueError, "capture error count"):
                load_recording(root)

    def test_rejects_event_geometry_that_differs_from_before_frame(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            def change_event_geometry(records: list[dict[str, object]]) -> None:
                records[1]["capture_geometry"]["capture_backend"] = "dxgi"

            _rewrite_events(root, change_event_geometry)

            with self.assertRaisesRegex(ValueError, "event geometry"):
                load_recording(root)

    def test_rejects_geometry_change_when_flag_is_false(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            def change_after_geometry(records: list[dict[str, object]]) -> None:
                records[2]["capture_geometry"]["capture_backend"] = "dxgi"

            _rewrite_events(root, change_after_geometry)

            with self.assertRaisesRegex(ValueError, "geometry_changed flag"):
                load_recording(root)

    def test_rejects_input_after_frame_with_wrong_role(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            _rewrite_events(root, lambda records: records[2].update(role="pre_input"))

            with self.assertRaisesRegex(ValueError, "after frame must be post_input"):
                load_recording(root)

    def test_rejects_event_before_its_before_frame(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            _rewrite_events(
                root,
                lambda records: records[0].update(
                    captured_at=(NOW + timedelta(milliseconds=110)).isoformat(),
                    elapsed_ms=110,
                ),
            )

            with self.assertRaisesRegex(ValueError, "occurs before"):
                load_recording(root)

    def test_rejects_event_after_its_after_frame(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            _rewrite_events(
                root,
                lambda records: records[2].update(
                    captured_at=(NOW + timedelta(milliseconds=110)).isoformat(),
                    elapsed_ms=110,
                ),
            )

            with self.assertRaisesRegex(ValueError, "ends after"):
                load_recording(root)

    def test_rejects_non_chronological_frame_timestamps(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            _rewrite_events(
                root,
                lambda records: records[3].update(
                    captured_at=(NOW + timedelta(milliseconds=400)).isoformat()
                ),
            )

            with self.assertRaisesRegex(ValueError, "frame timestamps"):
                load_recording(root)

    def test_rejects_duplicate_input_event_ids(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            def duplicate_event(records: list[dict[str, object]]) -> None:
                records.insert(2, dict(records[1]))
                for sequence, record in enumerate(records):
                    record["sequence"] = sequence

            _rewrite_events(root, duplicate_event)
            _rewrite_manifest(
                root,
                lambda manifest: manifest.update(
                    record_count=5,
                    input_event_count=2,
                ),
            )

            with self.assertRaisesRegex(ValueError, "duplicate input event id"):
                load_recording(root)

    def test_rejects_input_elapsed_time_that_disagrees_with_timestamp(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            _rewrite_events(
                root, lambda records: records[1].update(elapsed_ms=900)
            )

            with self.assertRaisesRegex(ValueError, "elapsed_ms"):
                load_recording(root)

    def test_rejects_frame_outside_manifest_time_bounds(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            _rewrite_events(
                root,
                lambda records: records[0].update(
                    captured_at=(NOW - timedelta(milliseconds=1)).isoformat()
                ),
            )

            with self.assertRaisesRegex(ValueError, "outside the recording bounds"):
                load_recording(root)

    def test_rejects_foreign_frame_inside_an_input_batch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            foreign_path = root / "frames" / "000002-foreign.png"
            foreign_payload = (root / "frames" / "000000-start.png").read_bytes()
            foreign_path.write_bytes(foreign_payload)

            def insert_foreign_frame(records: list[dict[str, object]]) -> None:
                foreign = dict(records[0])
                foreign.update(
                    {
                        "frame_id": "frame-foreign",
                        "role": "post_input",
                        "captured_at": (NOW + timedelta(milliseconds=300)).isoformat(),
                        "elapsed_ms": 300,
                        "path": "frames/000002-foreign.png",
                    }
                )
                records.insert(2, foreign)
                for sequence, record in enumerate(records):
                    record["sequence"] = sequence

            _rewrite_events(root, insert_foreign_frame)
            _rewrite_manifest(
                root,
                lambda manifest: manifest.update(
                    record_count=5,
                    frame_count=4,
                    total_frame_bytes=int(manifest["total_frame_bytes"])
                    + len(foreign_payload),
                ),
            )

            with self.assertRaisesRegex(ValueError, "input batch is not contiguous"):
                load_recording(root)

    def test_rejects_stale_before_frame_for_input_batch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            def delay_action(records: list[dict[str, object]]) -> None:
                records[1].update(
                    occurred_at=(NOW + timedelta(seconds=5)).isoformat(),
                    ended_at=(NOW + timedelta(seconds=5, milliseconds=20)).isoformat(),
                    elapsed_ms=5_000,
                )
                records[2].update(
                    captured_at=(NOW + timedelta(seconds=5, milliseconds=500)).isoformat(),
                    elapsed_ms=5_500,
                )
                records[3].update(
                    captured_at=(NOW + timedelta(seconds=6)).isoformat(),
                    elapsed_ms=6_000,
                )

            _rewrite_events(root, delay_action)
            _rewrite_manifest(
                root,
                lambda manifest: manifest.update(
                    ended_at=(NOW + timedelta(seconds=6)).isoformat()
                ),
            )

            with self.assertRaisesRegex(ValueError, "before frame is stale"):
                load_recording(root)

    def test_rejects_input_count_above_manifest_capture_limit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            def add_second_event(records: list[dict[str, object]]) -> None:
                second = dict(records[1])
                second["event_id"] = "event-click-second"
                records.insert(2, second)
                for sequence, record in enumerate(records):
                    record["sequence"] = sequence

            _rewrite_events(root, add_second_event)

            def lower_limit(manifest: dict[str, object]) -> None:
                manifest["record_count"] = 5
                manifest["input_event_count"] = 2
                capture = manifest["capture"]
                assert isinstance(capture, dict)
                capture["max_events"] = 1

            _rewrite_manifest(root, lower_limit)

            with self.assertRaisesRegex(ValueError, "exceeds the recording limit"):
                load_recording(root)

    def test_rejects_multi_input_batch_not_marked_ambiguous(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            def add_second_event(records: list[dict[str, object]]) -> None:
                second = dict(records[1])
                second["event_id"] = "event-click-second"
                records.insert(2, second)
                for sequence, record in enumerate(records):
                    record["sequence"] = sequence

            _rewrite_events(root, add_second_event)
            _rewrite_manifest(
                root,
                lambda manifest: manifest.update(
                    record_count=5,
                    input_event_count=2,
                ),
            )

            with self.assertRaisesRegex(ValueError, "marked ambiguous"):
                load_recording(root)


if __name__ == "__main__":
    unittest.main()
