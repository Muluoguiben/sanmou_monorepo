from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from threading import RLock
from typing import Protocol

from pioneer_agent.core.device import DeviceSession
from pioneer_agent.core.models import ObservationSnapshot
from pioneer_agent.runtime.advisor_loop import AdvisorReport
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


MAX_TRACE_ACTIONS = 10
MAX_TRACE_FRAMES = 8
MAX_TRACE_COLLECTION_ITEMS = 20
MAX_TRACE_STRING_LENGTH = 500
_PRIVATE_TRACE_KEY_MARKERS = ("path", "image", "png", "bytes", "base64", "raw_frame")


@dataclass(frozen=True)
class ObservedAdvisorCycle:
    """One atomic result from the existing observe/perceive/advisor service chain."""

    observation: ObservationSnapshot
    report: AdvisorReport


class ObservationProvider(Protocol):
    def observe(self) -> ObservedAdvisorCycle: ...


class FixtureEvaluator(Protocol):
    def evaluate(self, fixture_path: Path) -> dict: ...


class ReplayFixtureEvaluator:
    """Lazy adapter over the canonical offline ReplayRuntime."""

    def evaluate(self, fixture_path: Path) -> dict:
        # Lazy import keeps the stdio server's live-observation surface free of
        # executor/control imports. ReplayRuntime is used only after a fixture
        # has passed the closed-root checks below.
        from pioneer_agent.runtime.replay_runtime import ReplayRuntime

        result = ReplayRuntime().run_fixture(fixture_path)
        return {
            "derived_state": result["derived_state"],
            "selected_action": _offline_action(result["selected_action"]),
            "ranked_actions": [
                _offline_action(action) for action in result["ranked_actions"]
            ],
            "selection_reason": result["selection_reason"],
            "semantic_target_gate": result["semantic_target_gate"],
            "verifier_gate": result["verifier_gate"],
            "verifier_spec": result["verifier_spec"],
            "next_replan_time": result["next_replan_time"],
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
        self._fixture_root = _validated_fixture_root(fixture_root)
        self._fixture_evaluator = fixture_evaluator or ReplayFixtureEvaluator()
        self._latest_cycle: ObservedAdvisorCycle | None = None
        self._lock = RLock()

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
        try:
            cycle = self._observation_provider.observe()
            _validate_cycle(cycle)
        except Exception as exc:  # noqa: BLE001 - tool boundary returns structured failure
            return ObserveGameResponse(
                status="error",
                error=ContractError(
                    code="observation_failed",
                    message=str(exc) or type(exc).__name__,
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
                runtime_state=self._latest_cycle.report.current_state.model_dump(mode="json"),
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
                advisor_report=self._latest_cycle.report.model_dump(mode="json"),
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
                selection_reason=dict(report.selection_reason),
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
        except Exception as exc:  # noqa: BLE001 - tool boundary returns structured failure
            return LastTraceResponse(
                status="error",
                error=ContractError(
                    code="trace_read_failed",
                    message=str(exc) or type(exc).__name__,
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
            fixture_path = _resolve_fixture(self._fixture_root, fixture)
            evaluation = self._fixture_evaluator.evaluate(fixture_path)
        except (OSError, ValueError) as exc:
            return FixtureEvaluationResponse(
                status="invalid_request",
                error=ContractError(
                    code="invalid_fixture",
                    message=str(exc),
                ),
            )
        except Exception as exc:  # noqa: BLE001 - tool boundary returns structured failure
            return FixtureEvaluationResponse(
                status="error",
                error=ContractError(
                    code="fixture_evaluation_failed",
                    message=str(exc) or type(exc).__name__,
                ),
            )
        fixture_id = fixture_path.relative_to(self._fixture_root).as_posix()
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
            session_id=report.device_session.session_id,
            observation_id=observation.observation_id,
            frame_sha256=observation.frame_sha256,
            captured_at=observation.captured_at,
            window_identity=geometry.outer_window if geometry is not None else None,
            capture_geometry=geometry,
            domains_run=list(observation.domains_run),
            unknown_domains=list(observation.unknown_domains),
            structured_evidence=[
                item.model_dump(mode="json") for item in report.structured_evidence
            ],
            confidence=report.confidence,
        )


def _validated_fixture_root(fixture_root: Path | None) -> Path | None:
    if fixture_root is None:
        return None
    resolved = fixture_root.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("fixture root must be a directory")
    return resolved


def _resolve_fixture(root: Path, fixture: str) -> Path:
    value = fixture.strip()
    if not value:
        raise ValueError("fixture must not be empty")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if posix.is_absolute() or windows.is_absolute():
        raise ValueError("fixture must be relative to the configured fixture root")
    if ".." in posix.parts or ".." in windows.parts:
        raise ValueError("fixture path traversal is not allowed")
    candidate = (root / Path(*posix.parts)).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("fixture resolves outside the configured fixture root") from exc
    if not candidate.is_file() or candidate.suffix.lower() != ".json":
        raise ValueError("fixture must be an existing JSON file")
    return candidate


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
        session_id=session.session_id,
        active=session.active,
        started_at=session.started_at,
        last_observed_at=(cycle.observation.captured_at if cycle is not None else session.last_observed_at),
        source_id=session.source.source_id,
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
    reason = action.execution_blocked_reason or "advisor_mode"
    return ActionProposal(
        action_id=action.action_id,
        action_type=action.action_type.value,
        params=dict(action.params),
        score=action.score,
        risk=dict(action.risk),
        evidence=list(action.evidence),
        structured_evidence=[
            item.model_dump(mode="json") for item in action.structured_evidence
        ],
        confidence=action.confidence,
        blockers=[reason],
        executable=False,
        execution_blocked_reason=reason,
    )


def _trace_summary(trace: TickTrace) -> TraceSummary:
    frames = [
        TraceFrameSummary(
            role=frame.role.value,
            frame_sha256=frame.sha256,
            observation_id=frame.observation.get("observation_id"),
            captured_at=frame.observation.get("captured_at"),
            resource_ref=f"frame-sha256:{frame.sha256}",
        )
        for frame in trace.frames[:MAX_TRACE_FRAMES]
    ]
    return TraceSummary(
        trace_id=trace.trace_id,
        session_id=trace.session_id,
        iteration=trace.iteration,
        created_at=trace.created_at,
        current_phase=trace.current_phase.value,
        failure_reason=trace.failure_reason,
        selected_action=_bounded_action(trace.selected_action),
        ranked_actions=[
            _bounded_action(action) or {} for action in trace.ranked_actions[:MAX_TRACE_ACTIONS]
        ],
        frames=frames,
        verification=_bounded_trace_value(trace.verification),
        recovery=_bounded_trace_value(trace.recovery),
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
    return {
        key: _bounded_trace_value(action[key])
        for key in allowed
        if key in action
    }


def _bounded_trace_value(value, *, depth: int = 0):  # noqa: ANN001, ANN202
    if depth >= 4:
        return "[truncated]"
    if isinstance(value, dict):
        result = {}
        for key, item in list(value.items())[:MAX_TRACE_COLLECTION_ITEMS]:
            key_text = str(key)
            if any(marker in key_text.lower() for marker in _PRIVATE_TRACE_KEY_MARKERS):
                continue
            result[key_text] = _bounded_trace_value(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [
            _bounded_trace_value(item, depth=depth + 1)
            for item in list(value)[:MAX_TRACE_COLLECTION_ITEMS]
        ]
    if isinstance(value, str):
        return value[:MAX_TRACE_STRING_LENGTH]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:MAX_TRACE_STRING_LENGTH]


def _offline_action(action: dict | None) -> dict | None:
    bounded = _bounded_action(action)
    if bounded is None:
        return None
    return {
        **bounded,
        "executable": False,
        "execution_blocked_reason": "offline_fixture",
        "execution_authority": "none",
    }


def _not_observed_error() -> ContractError:
    return ContractError(
        code="not_observed",
        message="call observe_game before reading cached live state",
    )
