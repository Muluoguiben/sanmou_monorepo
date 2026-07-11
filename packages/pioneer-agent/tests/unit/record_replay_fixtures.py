from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image

from pioneer_agent.core.models import CaptureGeometry
from pioneer_agent.record_replay.models import (
    FrameRecord,
    FrameRole,
    ImageFormat,
    InputEventRecord,
    InputKind,
    NormalizedPoint,
    PixelPoint,
    RecordingManifest,
    RecordingStatus,
    TargetWindow,
)


NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def geometry() -> CaptureGeometry:
    return CaptureGeometry.model_validate(
        {
            "schema_version": 1,
            "capture_backend": "wgc",
            "outer_window": {
                "hwnd": 123,
                "pid": 456,
                "left": 100,
                "top": 200,
                "right": 200,
                "bottom": 300,
                "width": 100,
                "height": 100,
            },
            "capture_rect": {
                "left": 100,
                "top": 200,
                "right": 200,
                "bottom": 300,
                "width": 100,
                "height": 100,
            },
            "capture_origin": {"x": 100, "y": 200},
            "frame_size": [100, 100],
        }
    )


def png_bytes(color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (10, 10), color).save(buffer, format="PNG")
    return buffer.getvalue()


def create_completed_session(root: Path, *, workflow_name: str = "claim reward") -> RecordingManifest:
    session_id = str(uuid4())
    frames_dir = root / "frames"
    frames_dir.mkdir(parents=True)
    before_payload = png_bytes((1, 2, 3))
    after_payload = png_bytes((4, 5, 6))
    end_payload = png_bytes((7, 8, 9))
    payloads = {
        "frames/000000-start.png": before_payload,
        "frames/000002-post.png": after_payload,
        "frames/000003-end.png": end_payload,
    }
    for relative, payload in payloads.items():
        (root / relative).write_bytes(payload)

    before = _frame(
        session_id,
        sequence=0,
        frame_id="frame-before",
        role=FrameRole.START,
        relative="frames/000000-start.png",
        payload=before_payload,
        captured_at=NOW,
        elapsed_ms=0,
    )
    event = InputEventRecord(
        session_id=session_id,
        sequence=1,
        event_id="event-click",
        kind=InputKind.CLICK,
        occurred_at=NOW + timedelta(milliseconds=100),
        ended_at=NOW + timedelta(milliseconds=120),
        elapsed_ms=100,
        duration_ms=20,
        window_hwnd=123,
        window_pid=456,
        capture_geometry=geometry(),
        start_point=PixelPoint(x=50, y=50),
        start_normalized=NormalizedPoint(x=0.5, y=0.5),
        button="left",
        before_frame_id="frame-before",
        after_frame_id="frame-after",
    )
    after = _frame(
        session_id,
        sequence=2,
        frame_id="frame-after",
        role=FrameRole.POST_INPUT,
        relative="frames/000002-post.png",
        payload=after_payload,
        captured_at=NOW + timedelta(milliseconds=500),
        elapsed_ms=500,
    )
    end = _frame(
        session_id,
        sequence=3,
        frame_id="frame-end",
        role=FrameRole.END,
        relative="frames/000003-end.png",
        payload=end_payload,
        captured_at=NOW + timedelta(seconds=1),
        elapsed_ms=1_000,
    )
    records = [before, event, after, end]
    events_payload = b"".join(
        (record.model_dump_json(exclude_none=True) + "\n").encode("utf-8")
        for record in records
    )
    (root / "events.jsonl").write_bytes(events_payload)
    manifest = RecordingManifest(
        session_id=session_id,
        workflow_name=workflow_name,
        status=RecordingStatus.COMPLETED,
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=1),
        target=TargetWindow(
            hwnd=123,
            pid=456,
            process_started_at=NOW - timedelta(minutes=1),
            title="三国：谋定天下",
        ),
        initial_capture_geometry=geometry(),
        events_sha256=sha256(events_payload).hexdigest(),
        record_count=4,
        frame_count=3,
        input_event_count=1,
        total_frame_bytes=sum(len(payload) for payload in payloads.values()),
        stop_reason="duration",
    )
    (root / "manifest.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    return manifest


def _frame(
    session_id: str,
    *,
    sequence: int,
    frame_id: str,
    role: FrameRole,
    relative: str,
    payload: bytes,
    captured_at: datetime,
    elapsed_ms: int,
) -> FrameRecord:
    digest = sha256(payload).hexdigest()
    return FrameRecord(
        session_id=session_id,
        sequence=sequence,
        frame_id=frame_id,
        role=role,
        captured_at=captured_at,
        elapsed_ms=elapsed_ms,
        path=relative,
        sha256=digest,
        byte_size=len(payload),
        image_format=ImageFormat.PNG,
        image_size=(10, 10),
        source_png_sha256=digest,
        capture_geometry=geometry(),
    )
