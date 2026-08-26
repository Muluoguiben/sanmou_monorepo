from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from threading import Lock, RLock
from typing import Protocol

from pioneer_agent.core.device import DeviceSession
from pioneer_agent.core.models import ObservationSnapshot
from pioneer_agent.core.runtime_state_io import coerce_runtime_state
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.runtime.advisor_loop import AdvisorReport
from pioneer_agent.selector.action_selector import ActionSelector
from pioneer_agent.storage.trace_store import TickTrace, TraceStore

from .contracts import (
    ActionCandidatesResponse,
    ActionProposal,
    AdvisorReportResponse,
    ContractError,
    FixtureEvaluationResponse,
    LastTraceResponse,
    LiveObservation,
    ObserveGameResponse,
    RuntimeStateResponse,
    SessionStatusResponse,
    SessionSummary,
    TraceFrameSummary,
    TraceSummary,
)
from .privacy import (
    ACTION_PARAM_KEYS,
    RISK_KEYS,
    public_required_text,
    public_text,
    project_advisor_report,
    project_candidate_action,
    project_evidence,
    project_mapping,
    project_recommendation,
    project_runtime_state,
    project_selection_reason,
    project_text_list,
)


MAX_TRACE_ACTIONS = 10
MAX_TRACE_FRAMES = 8
MAX_FIXTURE_BYTES = 1_048_576
TRACE_VERIFICATION_KEYS = frozenset(
    {
        "action_id",
        "action_type",
        "actual",
        "decision",
        "expected",
        "failure_reason",
        "match_policy",
        "matched",
        "observation_id",
        "observed_delta",
        "post_observation_id",
        "reason",
        "recovery_required",
        "status",
        "target",
        "target_key",
        "timeout_seconds",
        "verified",
    }
)
TRACE_RECOVERY_KEYS = frozenset(
    {"action_id", "attempt", "reason", "required", "status", "strategy"}
)


@dataclass(frozen=True)
class ObservedAdvisorCycle:
    """One atomic result from the existing observe/perceive/advisor service chain."""

    observation: ObservationSnapshot
    report: AdvisorReport


class ObservationProvider(Protocol):
    def observe(self) -> ObservedAdvisorCycle: ...


class FixtureEvaluator(Protocol):
    def evaluate(self, fixture_bytes: bytes, *, fixture_id: str) -> dict: ...


class OfflineFixtureEvaluator:
    """Pure RuntimeState derive/select evaluator with no executor seam."""

    def __init__(
        self,
        *,
        deriver: StateDeriver | None = None,
        selector: ActionSelector | None = None,
    ) -> None:
        self._deriver = deriver or StateDeriver()
        self._selector = selector or ActionSelector()

    def evaluate(self, fixture_bytes: bytes, *, fixture_id: str) -> dict:
        payload = json.loads(fixture_bytes.decode("utf-8"))
        derived = self._deriver.derive(coerce_runtime_state(payload))
        result = self._selector.select(derived)
        return {
            "fixture": fixture_id,
            "derived_state": project_runtime_state(derived),
            "selected_action": _offline_action(result.selected_action),
            "ranked_actions": [
                _offline_action(action) for action in result.ranked_actions
            ],
            "selection_reason": project_selection_reason(result.selection_reason),
            "next_replan_time": (
                result.next_replan_time.isoformat()
                if result.next_replan_time is not None
                else None
            ),
            "execution_authority": "none",
        }


class GameMCPService:
    """Read-only application service consumed by the MCP transport adapter."""

    def __init__(
        self,
        *,
        observation_provider: ObservationProvider | None = None,
        device_session: DeviceSession | None = None,
        trace_store: TraceStore | None = None,
        fixture_root: Path | None = None,
        fixture_evaluator: FixtureEvaluator | None = None,
    ) -> None:
        self._observation_provider = observation_provider
        self._device_session = device_session
        self._trace_store = trace_store
        self._fixture_root, self._fixture_root_fd = _open_fixture_root(fixture_root)
        self._fixture_evaluator = fixture_evaluator or OfflineFixtureEvaluator()
        self._latest_cycle: ObservedAdvisorCycle | None = None
        self._lock = RLock()
        self._observe_lock = Lock()

    def close(self) -> None:
        lock = getattr(self, "_lock", None)
        if lock is None:
            return
        with lock:
            fixture_root_fd = getattr(self, "_fixture_root_fd", None)
            if fixture_root_fd is not None:
                os.close(fixture_root_fd)
                self._fixture_root_fd = None

    def __del__(self) -> None:
        try:
            self.close()
        except (AttributeError, OSError):
            pass

    def session_status(self) -> SessionStatusResponse:
        with self._lock:
            cycle = self._latest_cycle
            session = cycle.report.device_session if cycle is not None else self._device_session
            observation = self._live_observation(cycle) if cycle is not None else None
            return SessionStatusResponse(
                status="ok",
                session=_session_summary(session, cycle),
                latest_observation=observation,
            )

    def observe_game(self) -> ObserveGameResponse:
        if self._observation_provider is None:
            return ObserveGameResponse(
                status="not_configured",
                error=ContractError(
                    code="observation_not_configured",
                    message="no live observation provider is configured for this server",
                ),
            )
        if not self._observe_lock.acquire(blocking=False):
            return ObserveGameResponse(
                status="error",
                error=ContractError(
                    code="observation_in_progress",
                    message="another observation is already in progress",
                    retryable=True,
                ),
            )
        try:
            try:
                cycle = self._observation_provider.observe()
                _validate_cycle(cycle)
            except Exception:  # noqa: BLE001 - never expose provider exception contents
                return ObserveGameResponse(
                    status="error",
                    error=ContractError(
                        code="observation_failed",
                        message="the configured observation provider failed",
                        retryable=True,
                    ),
                )
            with self._lock:
                if self._latest_cycle is not None:
                    previous = self._latest_cycle.observation
                    if cycle.observation.observation_id == previous.observation_id:
                        return ObserveGameResponse(
                            status="error",
                            error=ContractError(
                                code="observation_not_fresh",
                                message="observation provider reused the cached observation id",
                                retryable=True,
                            ),
                        )
                    if cycle.observation.captured_at < previous.captured_at:
                        return ObserveGameResponse(
                            status="error",
                            error=ContractError(
                                code="observation_time_regressed",
                                message="new observation timestamp precedes the cached observation",
                                retryable=True,
                            ),
                        )
                self._latest_cycle = cycle
                self._device_session = cycle.report.device_session
                return ObserveGameResponse(
                    status="ok",
                    observation=self._live_observation(cycle),
                )
        finally:
            self._observe_lock.release()

    def get_runtime_state(self) -> RuntimeStateResponse:
        with self._lock:
            if self._latest_cycle is None:
                return RuntimeStateResponse(
                    status="not_observed",
                    error=_not_observed_error(),
                )
            return RuntimeStateResponse(
                status="ok",
                observation=self._live_observation(self._latest_cycle),
                runtime_state=project_runtime_state(self._latest_cycle.report.current_state),
            )

    def get_advisor_report(self) -> AdvisorReportResponse:
        with self._lock:
            if self._latest_cycle is None:
                return AdvisorReportResponse(
                    status="not_observed",
                    error=_not_observed_error(),
                )
            return AdvisorReportResponse(
                status="ok",
                observation=self._live_observation(self._latest_cycle),
                advisor_report=project_advisor_report(self._latest_cycle.report),
            )

    def list_action_candidates(self) -> ActionCandidatesResponse:
        with self._lock:
            if self._latest_cycle is None:
                return ActionCandidatesResponse(
                    status="not_observed",
                    error=_not_observed_error(),
                )
            report = self._latest_cycle.report
            return ActionCandidatesResponse(
                status="ok",
                observation=self._live_observation(self._latest_cycle),
                candidates=[_proposal(action) for action in report.available_actions],
                selection_reason=project_selection_reason(report.selection_reason),
            )

    def get_last_trace(self) -> LastTraceResponse:
        if self._trace_store is None:
            return LastTraceResponse(
                status="not_configured",
                error=ContractError(
                    code="trace_store_not_configured",
                    message="no trace store is configured for this server",
                ),
            )
        try:
            traces = self._trace_store.read()
        except Exception:  # noqa: BLE001 - never expose trace-store exception contents
            return LastTraceResponse(
                status="error",
                error=ContractError(
                    code="trace_read_failed",
                    message="the configured trace store could not be read",
                    retryable=True,
                ),
            )
        if not traces:
            return LastTraceResponse(
                status="not_found",
                error=ContractError(
                    code="trace_not_found",
                    message="the configured trace store contains no traces",
                ),
            )
        return LastTraceResponse(status="ok", trace=_trace_summary(traces[-1]))

    def evaluate_fixture(self, fixture: str) -> FixtureEvaluationResponse:
        if self._fixture_root is None:
            return FixtureEvaluationResponse(
                status="not_configured",
                error=ContractError(
                    code="fixture_root_not_configured",
                    message="no offline fixture root is configured for this server",
                ),
            )
        try:
            if self._fixture_root_fd is None:
                raise ValueError("fixture root is not open")
            fixture_id, fixture_bytes = _read_fixture(
                self._fixture_root_fd,
                fixture,
                max_bytes=MAX_FIXTURE_BYTES,
            )
            evaluation = self._fixture_evaluator.evaluate(
                fixture_bytes,
                fixture_id=fixture_id,
            )
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            return FixtureEvaluationResponse(
                status="invalid_request",
                error=ContractError(
                    code="invalid_fixture",
                    message="fixture path or contents are invalid or unsafe",
                ),
            )
        except Exception:  # noqa: BLE001 - never expose evaluator exception contents
            return FixtureEvaluationResponse(
                status="error",
                error=ContractError(
                    code="fixture_evaluation_failed",
                    message="offline fixture evaluation failed",
                ),
            )
        return FixtureEvaluationResponse(
            status="ok",
            fixture_id=fixture_id,
            evaluation=evaluation,
        )

    @staticmethod
    def _live_observation(cycle: ObservedAdvisorCycle) -> LiveObservation:
        observation = cycle.observation
        report = cycle.report
        geometry = observation.capture_geometry
        return LiveObservation(
            session_id=public_required_text(report.device_session.session_id),
            observation_id=public_required_text(observation.observation_id),
            frame_sha256=observation.frame_sha256,
            captured_at=observation.captured_at,
            window_identity=geometry.outer_window if geometry is not None else None,
            capture_geometry=geometry,
            domains_run=project_text_list(observation.domains_run),
            unknown_domains=project_text_list(observation.unknown_domains),
            structured_evidence=[
                project_evidence(item) for item in report.structured_evidence
            ],
            confidence=report.confidence,
        )


def _open_fixture_root(fixture_root: Path | None) -> tuple[Path | None, int | None]:
    if fixture_root is None:
        return None, None
    resolved = fixture_root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("fixture root must be a directory")
    no_follow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if no_follow is None or directory is None or os.open not in os.supports_dir_fd:
        raise RuntimeError("secure fixture reads require dir_fd, O_DIRECTORY, and O_NOFOLLOW")
    root_fd = os.open(resolved, os.O_RDONLY | directory | no_follow)
    return resolved, root_fd


def _read_fixture(root_fd: int, fixture: str, *, max_bytes: int) -> tuple[str, bytes]:
    parts = _fixture_parts(fixture)
    current_fd = os.dup(root_fd)
    file_fd: int | None = None
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        for part in parts[:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd

        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=current_fd)
        before = os.fstat(file_fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("fixture must be a regular file")
        if before.st_nlink != 1:
            raise ValueError("fixture hard links are not allowed")
        if before.st_size > max_bytes:
            raise ValueError("fixture exceeds the maximum size")

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(file_fd, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("fixture exceeds the maximum size")

        after = os.fstat(file_fd)
        before_identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        after_identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if before_identity != after_identity or total != before.st_size:
            raise ValueError("fixture changed while it was being read")
        return PurePosixPath(*parts).as_posix(), b"".join(chunks)
    finally:
        if file_fd is not None:
            os.close(file_fd)
        os.close(current_fd)


def _fixture_parts(fixture: str) -> tuple[str, ...]:
    value = fixture.strip()
    if not value:
        raise ValueError("fixture must not be empty")
    if "\\" in value:
        raise ValueError("fixture paths must use POSIX separators")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute():
        raise ValueError("fixture must be relative to the configured fixture root")
    if ".." in posix.parts or ".." in windows.parts:
        raise ValueError("fixture path traversal is not allowed")
    parts = tuple(part for part in posix.parts if part not in ("", "."))
    if not parts or PurePosixPath(parts[-1]).suffix.lower() != ".json":
        raise ValueError("fixture must name a JSON file")
    if any(part in ("", ".", "..") or "/" in part or "\x00" in part for part in parts):
        raise ValueError("fixture contains an invalid path component")
    return parts


def _validate_cycle(cycle: ObservedAdvisorCycle) -> None:
    observation = cycle.observation
    report = cycle.report
    if observation.captured_at.tzinfo is None or observation.captured_at.utcoffset() is None:
        raise ValueError("observation captured_at must be timezone-aware")
    if report.captured_at != observation.captured_at:
        raise ValueError("advisor report and observation timestamps do not match")
    if any(action.executable for action in report.available_actions):
        raise ValueError("advisor report contains an executable action")
    if report.recommended_action is not None and report.recommended_action.executable:
        raise ValueError("advisor report contains an executable recommendation")
    report_domains = list(report.vision_summary.get("domains_run", []))
    report_unknown = list(report.vision_summary.get("unknown_domains", []))
    if report_domains != observation.domains_run:
        raise ValueError("advisor report domains do not match the observation")
    if report_unknown != observation.unknown_domains:
        raise ValueError("advisor report unknown domains do not match the observation")


def _session_summary(
    session: DeviceSession | None,
    cycle: ObservedAdvisorCycle | None,
) -> SessionSummary | None:
    if session is None:
        return None
    geometry = cycle.observation.capture_geometry if cycle is not None else None
    if cycle is not None:
        health = "ready" if not cycle.observation.unknown_domains else "degraded"
    elif session.capabilities.live_capture:
        health = "unknown"
    else:
        health = "not_configured"
    return SessionSummary(
        session_id=public_required_text(session.session_id),
        active=session.active,
        started_at=session.started_at,
        last_observed_at=(cycle.observation.captured_at if cycle is not None else session.last_observed_at),
        source_id=public_required_text(session.source.source_id),
        source_type=session.source.source_type.value,
        platform=session.profile.platform.value,
        resolution=session.profile.resolution,
        observe_only=session.observe_only,
        live_capture=session.capabilities.live_capture,
        reliable_window_info=session.capabilities.reliable_window_info,
        capture_health=health,
        window_identity=geometry.outer_window if geometry is not None else None,
        latest_report_at=cycle.report.captured_at if cycle is not None else None,
    )


def _proposal(action) -> ActionProposal:  # noqa: ANN001 - Advisor model is the contract source
    projected = project_recommendation(action)
    reason = projected["execution_blocked_reason"]
    return ActionProposal(**projected, blockers=[reason])


def _trace_summary(trace: TickTrace) -> TraceSummary:
    frames = [
        TraceFrameSummary(
            role=frame.role.value,
            frame_sha256=frame.sha256,
            observation_id=public_text(frame.observation.get("observation_id")),
            captured_at=frame.observation.get("captured_at"),
            resource_ref=f"frame-sha256:{frame.sha256}",
        )
        for frame in trace.frames[:MAX_TRACE_FRAMES]
    ]
    return TraceSummary(
        trace_id=public_required_text(trace.trace_id),
        session_id=public_text(trace.session_id),
        iteration=trace.iteration,
        created_at=trace.created_at,
        current_phase=trace.current_phase.value,
        failure_reason=public_text(trace.failure_reason),
        selected_action=_bounded_action(trace.selected_action),
        ranked_actions=[
            _bounded_action(action) or {} for action in trace.ranked_actions[:MAX_TRACE_ACTIONS]
        ],
        frames=frames,
        verification=project_mapping(
            trace.verification,
            allowed_keys=TRACE_VERIFICATION_KEYS,
        ) or None,
        recovery=project_mapping(
            trace.recovery,
            allowed_keys=TRACE_RECOVERY_KEYS,
        ) or None,
    )


def _bounded_action(action: dict | None) -> dict | None:
    if action is None:
        return None
    allowed = (
        "action_id",
        "action_type",
        "params",
        "score_total",
        "risk",
        "preconditions",
        "source_state_refs",
    )
    projected: dict[str, object] = {}
    for key in allowed:
        if key not in action:
            continue
        value = action[key]
        if key == "params":
            projected[key] = project_mapping(value, allowed_keys=ACTION_PARAM_KEYS)
        elif key == "risk":
            projected[key] = project_mapping(value, allowed_keys=RISK_KEYS)
        elif key in {"preconditions", "source_state_refs"}:
            projected[key] = project_text_list(value or [])
        elif key in {"action_id", "action_type"}:
            projected[key] = public_required_text(value)
        elif value is None or isinstance(value, (bool, int, float)):
            projected[key] = value
    return projected


def _offline_action(action) -> dict | None:  # noqa: ANN001 - CandidateAction is optional
    if action is None:
        return None
    return {
        **project_candidate_action(action),
        "executable": False,
        "execution_blocked_reason": "offline_fixture",
        "execution_authority": "none",
    }


def _not_observed_error() -> ContractError:
    return ContractError(
        code="not_observed",
        message="call observe_game before reading cached live state",
    )
