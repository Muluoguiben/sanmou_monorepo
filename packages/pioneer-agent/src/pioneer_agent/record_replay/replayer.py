"""Build an offline replay plan without dispatching any input."""
from __future__ import annotations

from datetime import UTC, datetime

from pioneer_agent.record_replay.models import (
    ActionCandidate,
    FrameEvidence,
    FrameRecord,
    InputEventRecord,
    ReplayPlan,
)
from pioneer_agent.record_replay.session_store import LoadedRecording


LIVE_REPLAY_BLOCKERS = [
    "single demonstration does not establish a general UI locator",
    "semantic targets and preconditions have not been reviewed",
    "no independent verifier false-positive/false-negative eval is attached",
    "no safety allowlist or live execution authority is present",
    "sample coordinates are evidence only and cannot authorize dispatch",
]


def build_replay_plan(recording: LoadedRecording) -> ReplayPlan:
    source_events_sha256 = recording.manifest.events_sha256
    if source_events_sha256 is None:
        raise ValueError("offline replay requires a finalized source events SHA256")
    frame_by_id = {frame.frame_id: frame for frame in recording.frames}
    actions: list[ActionCandidate] = []
    for order, event in enumerate(recording.input_events):
        before = frame_by_id[event.before_frame_id]
        after = frame_by_id[event.after_frame_id]
        actions.append(
            ActionCandidate(
                candidate_id=f"{recording.manifest.session_id}-candidate-{order:04d}",
                session_id=recording.manifest.session_id,
                source_events_sha256=source_events_sha256,
                order=order,
                source_event_id=event.event_id,
                primitive=event.kind,
                occurred_at=event.occurred_at,
                input=_event_input(event),
                before_frame=_frame_evidence(before),
                after_frame=_frame_evidence(after),
                ambiguous_burst=event.ambiguous_burst,
                geometry_changed=event.geometry_changed,
                unresolved_assumptions=_unresolved_assumptions(event),
            )
        )
    return ReplayPlan(
        session_id=recording.manifest.session_id,
        source_events_sha256=source_events_sha256,
        workflow_name=recording.manifest.workflow_name,
        generated_at=datetime.now(UTC),
        blockers=list(LIVE_REPLAY_BLOCKERS),
        actions=actions,
    )


def _event_input(event: InputEventRecord) -> dict[str, object]:
    payload: dict[str, object] = {
        "primitive": event.kind.value,
        "duration_ms": event.duration_ms,
        "modifiers": list(event.modifiers),
        "coordinate_space": "capture:relative",
    }
    if event.start_point is not None:
        payload["start_point"] = event.start_point.model_dump(mode="json")
        payload["start_normalized"] = event.start_normalized.model_dump(mode="json")
    if event.end_point is not None:
        payload["end_point"] = event.end_point.model_dump(mode="json")
        payload["end_normalized"] = event.end_normalized.model_dump(mode="json")
    if event.button is not None:
        payload["button"] = event.button
    if event.scroll_delta is not None:
        payload["scroll_delta"] = event.scroll_delta
    if event.key is not None:
        payload["key"] = event.key
    return payload


def _frame_evidence(frame: FrameRecord) -> FrameEvidence:
    return FrameEvidence(
        frame_id=frame.frame_id,
        path=frame.path,
        sha256=frame.sha256,
        captured_at=frame.captured_at,
        capture_geometry=frame.capture_geometry,
    )


def _unresolved_assumptions(event: InputEventRecord) -> list[str]:
    values = [
        "semantic target is unknown",
        "required preconditions are unknown",
        "expected post-action state delta is unproven",
        "cross-resolution and alternate-layout behavior is untested",
        "popup, timeout, retry, and recovery behavior is untested",
    ]
    if event.ambiguous_burst:
        values.append("multiple inputs share one before/after frame pair")
    if event.geometry_changed:
        values.append("window or capture geometry changed across the input")
    return values
