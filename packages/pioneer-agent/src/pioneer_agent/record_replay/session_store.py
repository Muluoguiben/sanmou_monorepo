"""Fail-closed loading and integrity validation for demonstration sessions."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
import warnings

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from pioneer_agent.record_replay.models import (
    CaptureErrorRecord,
    FrameRecord,
    FrameRole,
    InputEventRecord,
    RecordingManifest,
    RecordingStatus,
    SESSION_RECORD_ADAPTER,
    SessionRecord,
)
from pioneer_agent.record_replay.validation import (
    RegularFileIdentity,
    load_strict_json_bytes,
    read_bounded_regular_file,
    reject_linked_path_components,
)


TIMELINE_TOLERANCE_MS = 100
MAX_PRE_INPUT_AGE_MS = 1_000
MAX_MANIFEST_BYTES = 1_048_576
MAX_EVENTS_BYTES = 67_108_864
MAX_FRAME_BYTES = 16_777_216
MAX_SESSION_FRAME_BYTES = 268_435_456


@dataclass(frozen=True)
class LoadedRecording:
    root: Path
    manifest: RecordingManifest
    manifest_sha256: str
    records: tuple[SessionRecord, ...]
    raw_file_identities: tuple[tuple[str, RegularFileIdentity], ...]

    @property
    def frames(self) -> tuple[FrameRecord, ...]:
        return tuple(record for record in self.records if isinstance(record, FrameRecord))

    @property
    def input_events(self) -> tuple[InputEventRecord, ...]:
        return tuple(
            record for record in self.records if isinstance(record, InputEventRecord)
        )


def load_recording(
    root: Path,
    *,
    require_complete: bool = True,
    verify_images: bool = True,
) -> LoadedRecording:
    root = _require_directory(root)
    manifest_path = _safe_child(root, "manifest.json")
    events_path = _safe_child(root, "events.jsonl")

    try:
        manifest_read = read_bounded_regular_file(
            manifest_path,
            max_bytes=MAX_MANIFEST_BYTES,
            label="recording manifest",
        )
        manifest_value = load_strict_json_bytes(manifest_read.payload)
        manifest = RecordingManifest.model_validate(manifest_value)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ValueError(f"recording manifest is invalid: {exc}") from exc
    manifest_sha256 = manifest_read.identity.sha256
    if require_complete and manifest.status != RecordingStatus.COMPLETED:
        raise ValueError(f"recording is not complete: {manifest.status.value}")

    try:
        events_read = read_bounded_regular_file(
            events_path,
            max_bytes=MAX_EVENTS_BYTES,
            label="recording events file",
        )
    except ValueError as exc:
        raise ValueError(f"recording events file is invalid: {exc}") from exc

    if manifest.events_sha256 is None:
        if require_complete:
            raise ValueError("active recording has no finalized events SHA256")
        _parse_records(events_read.payload)
        return LoadedRecording(
            root=root,
            manifest=manifest,
            manifest_sha256=manifest_sha256,
            records=(),
            raw_file_identities=(
                ("manifest.json", manifest_read.identity),
                ("events.jsonl", events_read.identity),
            ),
        )
    if manifest.events_sha256 != events_read.identity.sha256:
        raise ValueError("recording events SHA256 does not match the manifest")

    records = _parse_records(events_read.payload)
    frame_identities = _validate_records(
        root, manifest, records, verify_images=verify_images
    )
    return LoadedRecording(
        root=root,
        manifest=manifest,
        manifest_sha256=manifest_sha256,
        records=tuple(records),
        raw_file_identities=(
            ("manifest.json", manifest_read.identity),
            ("events.jsonl", events_read.identity),
            *frame_identities,
        ),
    )


def _parse_records(payload: bytes) -> list[SessionRecord]:
    records: list[SessionRecord] = []
    for line_number, raw_line in enumerate(BytesIO(payload), start=1):
        if not raw_line.strip():
            continue
        try:
            value = load_strict_json_bytes(raw_line)
            record = SESSION_RECORD_ADAPTER.validate_python(value)
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            raise ValueError(f"invalid recording event at line {line_number}") from exc
        records.append(record)
    return records


def revalidate_loaded_recording(recording: LoadedRecording) -> LoadedRecording:
    """Re-open every raw artifact and reject a stale in-memory recording view."""

    current = load_recording(
        recording.root,
        require_complete=True,
        verify_images=True,
    )
    if (
        current.manifest_sha256 != recording.manifest_sha256
        or current.manifest.events_sha256 != recording.manifest.events_sha256
        or current.raw_file_identities != recording.raw_file_identities
    ):
        raise ValueError("recording raw evidence changed after it was loaded")
    return current


def _validate_records(
    root: Path,
    manifest: RecordingManifest,
    records: list[SessionRecord],
    *,
    verify_images: bool,
) -> tuple[tuple[str, RegularFileIdentity], ...]:
    if len(records) != manifest.record_count:
        raise ValueError("record count does not match the manifest")
    sequences = [record.sequence for record in records]
    if sequences != list(range(len(records))):
        raise ValueError("recording sequence must be contiguous and ordered")
    if any(record.session_id != manifest.session_id for record in records):
        raise ValueError("recording contains a foreign session id")

    frames = [record for record in records if isinstance(record, FrameRecord)]
    inputs = [record for record in records if isinstance(record, InputEventRecord)]
    capture_errors = [
        record for record in records if isinstance(record, CaptureErrorRecord)
    ]
    if len(frames) != manifest.frame_count:
        raise ValueError("frame count does not match the manifest")
    if len(inputs) != manifest.input_event_count:
        raise ValueError("input event count does not match the manifest")
    if len(capture_errors) != manifest.capture_error_count:
        raise ValueError("capture error count does not match the manifest")
    if sum(frame.byte_size for frame in frames) != manifest.total_frame_bytes:
        raise ValueError("frame byte count does not match the manifest")
    if manifest.input_event_count > manifest.capture.max_events:
        raise ValueError("input event count exceeds the recording limit")
    if (
        manifest.status == RecordingStatus.COMPLETED
        and manifest.input_event_count < manifest.capture.min_input_events
    ):
        raise ValueError("completed recording does not meet its minimum input event floor")
    if manifest.total_frame_bytes > manifest.capture.max_bytes:
        raise ValueError("frame byte count exceeds the recording limit")
    if manifest.total_frame_bytes > MAX_SESSION_FRAME_BYTES:
        raise ValueError("frame byte count exceeds the fixed session size limit")
    if any(frame.byte_size > MAX_FRAME_BYTES for frame in frames):
        raise ValueError("frame exceeds the fixed per-frame size limit")

    if manifest.status == RecordingStatus.COMPLETED:
        start_frames = [frame for frame in frames if frame.role == FrameRole.START]
        end_frames = [frame for frame in frames if frame.role == FrameRole.END]
        if len(start_frames) != 1:
            raise ValueError("completed recording requires exactly one start frame")
        if len(end_frames) != 1:
            raise ValueError("completed recording requires exactly one end frame")
        if not isinstance(records[0], FrameRecord) or records[0].role != FrameRole.START:
            raise ValueError("start frame must be the first recording record")
        if not isinstance(records[-1], FrameRecord) or records[-1].role != FrameRole.END:
            raise ValueError("end frame must be the last recording record")
        if start_frames[0].capture_geometry != manifest.initial_capture_geometry:
            raise ValueError("start frame geometry does not match the manifest")

    frame_ids: dict[str, FrameRecord] = {}
    frame_identities: list[tuple[str, RegularFileIdentity]] = []
    previous_frame: FrameRecord | None = None
    for frame in frames:
        if frame.frame_id in frame_ids:
            raise ValueError("duplicate frame id")
        outer_window = frame.capture_geometry.outer_window
        if (
            outer_window.hwnd != manifest.target.hwnd
            or outer_window.pid != manifest.target.pid
        ):
            raise ValueError(f"frame target does not match the manifest: {frame.frame_id}")
        if previous_frame is not None and frame.captured_at < previous_frame.captured_at:
            raise ValueError("frame timestamps must be chronological")
        if previous_frame is not None and frame.elapsed_ms < previous_frame.elapsed_ms:
            raise ValueError("frame elapsed times must be chronological")
        _validate_manifest_time(
            manifest,
            timestamp=frame.captured_at,
            elapsed_ms=frame.elapsed_ms,
            label=f"frame {frame.frame_id}",
        )
        previous_frame = frame
        frame_ids[frame.frame_id] = frame
        frame_path = _safe_child(root, frame.path)
        try:
            frame_read = read_bounded_regular_file(
                frame_path,
                max_bytes=MAX_FRAME_BYTES,
                label=f"frame {frame.frame_id}",
            )
        except ValueError as exc:
            raise ValueError(f"frame is unreadable: {frame.frame_id}: {exc}") from exc
        payload = frame_read.payload
        if len(payload) != frame.byte_size:
            raise ValueError(f"frame size mismatch: {frame.frame_id}")
        if frame_read.identity.sha256 != frame.sha256:
            raise ValueError(f"frame SHA256 mismatch: {frame.frame_id}")
        frame_identities.append((frame.path, frame_read.identity))
        if verify_images:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(BytesIO(payload)) as image:
                        if (
                            image.width > manifest.capture.long_edge
                            or image.height > manifest.capture.long_edge
                        ):
                            raise ValueError("decoded frame exceeds the configured dimensions")
                        image.load()
                        decoded_size = image.size
                        decoded_format = (image.format or "").lower()
            except (
                UnidentifiedImageError,
                OSError,
                ValueError,
                Image.DecompressionBombWarning,
                Image.DecompressionBombError,
            ) as exc:
                raise ValueError(f"frame cannot be decoded: {frame.frame_id}") from exc
            if decoded_size != frame.image_size:
                raise ValueError(f"frame decoded size mismatch: {frame.frame_id}")
            if decoded_format != frame.image_format.value:
                raise ValueError(f"frame format mismatch: {frame.frame_id}")

    event_ids: set[str] = set()
    previous_event_ended_at = manifest.started_at
    for event in inputs:
        if event.event_id in event_ids:
            raise ValueError(f"duplicate input event id: {event.event_id}")
        event_ids.add(event.event_id)
        if event.ended_at < previous_event_ended_at:
            raise ValueError("input event completion times must be chronological")
        previous_event_ended_at = event.ended_at
        _validate_manifest_time(
            manifest,
            timestamp=event.occurred_at,
            elapsed_ms=event.elapsed_ms,
            label=f"input event {event.event_id}",
        )
        if manifest.ended_at is not None and event.ended_at > manifest.ended_at:
            raise ValueError(f"input event exceeds the recording bounds: {event.event_id}")
        if event.before_frame_id not in frame_ids or event.after_frame_id not in frame_ids:
            raise ValueError(f"input event references an unknown frame: {event.event_id}")
        before = frame_ids[event.before_frame_id]
        after = frame_ids[event.after_frame_id]
        if before.sequence >= event.sequence or after.sequence <= event.sequence:
            raise ValueError(f"input frame ordering is invalid: {event.event_id}")
        if event.window_hwnd != manifest.target.hwnd or event.window_pid != manifest.target.pid:
            raise ValueError(f"input event target does not match the manifest: {event.event_id}")
        if event.capture_geometry != before.capture_geometry:
            raise ValueError(
                f"input event geometry does not match its before frame: {event.event_id}"
            )
        if before.role not in {
            FrameRole.START,
            FrameRole.PRE_INPUT,
            FrameRole.POST_INPUT,
        }:
            raise ValueError(f"input before frame has an invalid role: {event.event_id}")
        if after.role != FrameRole.POST_INPUT:
            raise ValueError(f"input after frame must be post_input: {event.event_id}")
        if event.geometry_changed != (
            before.capture_geometry != after.capture_geometry
        ):
            raise ValueError(
                f"input geometry_changed flag does not match its frames: {event.event_id}"
            )
        if event.occurred_at < before.captured_at:
            raise ValueError(
                f"input event occurs before its before frame: {event.event_id}"
            )
        if event.ended_at > after.captured_at:
            raise ValueError(
                f"input event ends after its after frame: {event.event_id}"
            )
    groups: dict[tuple[str, str], list[InputEventRecord]] = {}
    for event in inputs:
        groups.setdefault(
            (event.before_frame_id, event.after_frame_id), []
        ).append(event)
    for (before_id, after_id), group in groups.items():
        ordered = sorted(group, key=lambda event: event.sequence)
        before = frame_ids[before_id]
        after = frame_ids[after_id]
        earliest_elapsed_ms = min(event.elapsed_ms for event in ordered)
        pre_input_age_ms = earliest_elapsed_ms - before.elapsed_ms
        if not 0 <= pre_input_age_ms <= MAX_PRE_INPUT_AGE_MS:
            raise ValueError("input batch before frame is stale or postdated")
        expected_sequences = list(range(before.sequence + 1, after.sequence))
        actual_sequences = [event.sequence for event in ordered]
        if actual_sequences != expected_sequences:
            raise ValueError("input batch is not contiguous between its boundary frames")
        if len(ordered) > 1 and not all(
            event.ambiguous_burst for event in ordered
        ):
            raise ValueError("multi-input batch must be marked ambiguous")
        for sequence in expected_sequences:
            record = records[sequence]
            if not isinstance(record, InputEventRecord) or (
                record.before_frame_id,
                record.after_frame_id,
            ) != (before_id, after_id):
                raise ValueError("input batch contains a foreign intermediate record")

    for error in capture_errors:
        _validate_manifest_time(
            manifest,
            timestamp=error.occurred_at,
            elapsed_ms=error.elapsed_ms,
            label=f"capture error {error.code}",
        )
    return tuple(frame_identities)


def _validate_manifest_time(
    manifest: RecordingManifest,
    *,
    timestamp: datetime,
    elapsed_ms: int,
    label: str,
) -> None:
    if timestamp < manifest.started_at or (
        manifest.ended_at is not None and timestamp > manifest.ended_at
    ):
        raise ValueError(f"{label} timestamp is outside the recording bounds")
    wall_elapsed_ms = (timestamp - manifest.started_at).total_seconds() * 1_000
    if abs(wall_elapsed_ms - elapsed_ms) > TIMELINE_TOLERANCE_MS:
        raise ValueError(f"{label} elapsed_ms does not match its timestamp")


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    if temp.exists():
        raise FileExistsError(temp)
    with temp.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def atomic_write_json(path: Path, value: object) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    atomic_write_bytes(path, payload)


def _require_directory(path: Path) -> Path:
    reject_linked_path_components(path, label="recording root")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError("recording root does not exist") from exc
    if not resolved.is_dir():
        raise ValueError("recording root is not a directory")
    return resolved


def _safe_child(root: Path, relative: str) -> Path:
    candidate = root.joinpath(*relative.replace("\\", "/").split("/"))
    try:
        resolved_parent = candidate.parent.resolve(strict=True)
    except OSError as exc:
        raise ValueError("recording artifact parent does not exist") from exc
    if resolved_parent != root and root not in resolved_parent.parents:
        raise ValueError("recording artifact escapes the session root")
    return candidate
