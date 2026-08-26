from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pioneer_agent.core.models import CaptureGeometry, CaptureWindowIdentity


CONTRACT_VERSION = "sanmou-game/v1"
EXECUTION_AUTHORITY = "none"
SERVER_NAME = "sanmou-game"
TOOL_ARGUMENTS = {
    "session_status": frozenset(),
    "observe_game": frozenset(),
    "get_runtime_state": frozenset(),
    "get_advisor_report": frozenset(),
    "list_action_candidates": frozenset(),
    "get_last_trace": frozenset(),
    "evaluate_fixture": frozenset({"fixture"}),
}
TOOL_ALLOWLIST = frozenset(TOOL_ARGUMENTS)

ResponseStatus = Literal[
    "ok",
    "not_configured",
    "not_observed",
    "not_found",
    "invalid_request",
    "error",
]


class StrictContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContractError(StrictContractModel):
    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)
    retryable: bool = False


class ContractResponse(StrictContractModel):
    payload_fields: ClassVar[tuple[str, ...]] = ()
    required_ok_payload_fields: ClassVar[tuple[str, ...]] = ()

    contract_version: Literal["sanmou-game/v1"] = CONTRACT_VERSION
    status: ResponseStatus
    execution_authority: Literal["none"] = EXECUTION_AUTHORITY
    error: ContractError | None = None

    @model_validator(mode="after")
    def _status_error_and_payload_match(self) -> ContractResponse:
        if self.status == "ok" and self.error is not None:
            raise ValueError("successful responses cannot include an error")
        if self.status != "ok" and self.error is None:
            raise ValueError("non-success responses require an error")
        if self.status == "ok":
            missing = [
                field_name
                for field_name in self.required_ok_payload_fields
                if getattr(self, field_name, None) is None
            ]
            if missing:
                raise ValueError(
                    "successful response is missing payload: " + ", ".join(missing)
                )
        else:
            present = [
                field_name
                for field_name in self.payload_fields
                if _payload_present(getattr(self, field_name, None))
            ]
            if present:
                raise ValueError(
                    "non-success response cannot include payload: " + ", ".join(present)
                )
        return self


class LiveObservation(StrictContractModel):
    session_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    frame_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: datetime
    window_identity: CaptureWindowIdentity | None = None
    capture_geometry: CaptureGeometry | None = None
    domains_run: list[str] = Field(default_factory=list)
    unknown_domains: list[str] = Field(default_factory=list)
    structured_evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    execution_authority: Literal["none"] = EXECUTION_AUTHORITY

    @field_validator("captured_at")
    @classmethod
    def _captured_at_is_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _domains_and_window_are_consistent(self) -> LiveObservation:
        overlap = set(self.domains_run).intersection(self.unknown_domains)
        if overlap:
            raise ValueError(
                "domains cannot be both completed and unknown: "
                + ", ".join(sorted(overlap))
            )
        if (
            self.capture_geometry is not None
            and self.window_identity is not None
            and self.capture_geometry.outer_window != self.window_identity
        ):
            raise ValueError("window identity must match capture geometry")
        return self


class SessionSummary(StrictContractModel):
    session_id: str = Field(min_length=1)
    active: bool
    started_at: datetime
    last_observed_at: datetime | None = None
    source_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    resolution: tuple[int, int]
    observe_only: bool
    live_capture: bool
    reliable_window_info: bool
    capture_health: Literal["ready", "degraded", "unknown", "not_configured"]
    window_identity: CaptureWindowIdentity | None = None
    latest_report_at: datetime | None = None


class SessionStatusResponse(ContractResponse):
    payload_fields = ("session", "latest_observation")

    session: SessionSummary | None = None
    latest_observation: LiveObservation | None = None


class ObserveGameResponse(ContractResponse):
    payload_fields = ("observation",)
    required_ok_payload_fields = ("observation",)

    observation: LiveObservation | None = None


class RuntimeStateResponse(ContractResponse):
    payload_fields = ("observation", "runtime_state")
    required_ok_payload_fields = ("observation", "runtime_state")

    observation: LiveObservation | None = None
    runtime_state: dict[str, Any] | None = None


class AdvisorReportResponse(ContractResponse):
    payload_fields = ("observation", "advisor_report")
    required_ok_payload_fields = ("observation", "advisor_report")

    observation: LiveObservation | None = None
    advisor_report: dict[str, Any] | None = None


class ActionProposal(StrictContractModel):
    action_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    score: float
    risk: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    structured_evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    blockers: list[str] = Field(default_factory=list)
    executable: Literal[False] = False
    execution_blocked_reason: str = Field(min_length=1)
    execution_authority: Literal["none"] = EXECUTION_AUTHORITY


class ActionCandidatesResponse(ContractResponse):
    payload_fields = ("observation", "candidates", "selection_reason")
    required_ok_payload_fields = ("observation",)

    observation: LiveObservation | None = None
    candidates: list[ActionProposal] = Field(default_factory=list)
    selection_reason: dict[str, Any] = Field(default_factory=dict)


class TraceFrameSummary(StrictContractModel):
    role: str = Field(min_length=1)
    frame_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_id: str | None = None
    captured_at: datetime | None = None
    resource_ref: str = Field(min_length=1)


class TraceSummary(StrictContractModel):
    trace_id: str = Field(min_length=1)
    session_id: str | None = None
    iteration: int = Field(ge=0)
    created_at: datetime
    current_phase: str = Field(min_length=1)
    failure_reason: str | None = None
    selected_action: dict[str, Any] | None = None
    ranked_actions: list[dict[str, Any]] = Field(default_factory=list)
    frames: list[TraceFrameSummary] = Field(default_factory=list)
    verification: dict[str, Any] | None = None
    recovery: dict[str, Any] | None = None


class LastTraceResponse(ContractResponse):
    payload_fields = ("trace",)
    required_ok_payload_fields = ("trace",)

    trace: TraceSummary | None = None


class FixtureEvaluationResponse(ContractResponse):
    payload_fields = ("fixture_id", "evaluation")
    required_ok_payload_fields = ("fixture_id", "evaluation")

    fixture_id: str | None = None
    source: Literal["offline_fixture"] = "offline_fixture"
    live_source_used: Literal[False] = False
    evaluation: dict[str, Any] | None = None


def _payload_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True
