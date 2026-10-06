"""Synthetic read-only handoff bindings; not human authentication or dispatch grants."""
from datetime import datetime, timedelta
from hashlib import sha256
import json
from uuid import uuid4

from .task_contracts import RunState, SyntheticApprovalRequest, SyntheticApprovalResponse, TaskSpec


def task_digest(task: TaskSpec) -> str:
    canonical = json.dumps(task.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def request_approval(state: RunState, *, step_id: str, frame_sha256: str,
                     now: datetime, remaining_seconds: float, reason: str) -> SyntheticApprovalRequest:
    return SyntheticApprovalRequest(request_id=uuid4().hex, run_id=state.run_id,
        step_id=step_id, task_digest=task_digest(state.task), session_id=state.session_id,
        window_identity=state.window_identity, observation_id=state.observation_ids[-1],
        frame_sha256=frame_sha256, evidence_refs=list(state.evidence_refs), created_at=now,
        expires_at=now + timedelta(seconds=remaining_seconds), reason=reason)


def synthetic_response(request: SyntheticApprovalRequest, *, decision: str,
                       now: datetime) -> SyntheticApprovalResponse:
    """Explicit test/caller response; intentionally makes no claim of human identity."""
    return SyntheticApprovalResponse(request=request.model_copy(deep=True), decision=decision, responded_at=now)


def check_response(request: SyntheticApprovalRequest, response: SyntheticApprovalResponse,
                   *, task: TaskSpec, now: datetime) -> str | None:
    if response.request != request or request.task_digest != task_digest(task):
        return "approval_binding_mismatch"
    if now.tzinfo is None or now.utcoffset() is None:
        return "approval_clock_invalid"
    if now < request.created_at or response.responded_at < request.created_at or response.responded_at > now:
        return "approval_clock_rollback"
    if now >= request.expires_at or response.responded_at >= request.expires_at:
        return "approval_expired"
    return None
