"""Strict schemas for static MCP scenarios, observations, and score reports.

This package intentionally models tool-call summaries rather than a live MCP
client.  A scenario can replay a captured, bounded summary of a read-only call;
it cannot dispatch input, access a holdout oracle, or publish QA knowledge.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from pioneer_agent.mcp_server.contracts import (
    CONTRACT_VERSION,
    GAME_TOOL_ALLOWLIST,
    GAME_TOOL_ARGUMENTS,
    GAME_TOOL_REQUIRED_ARGUMENTS,
)
from pioneer_agent.record_replay.validation import validate_identifier, validate_unique_strings


SCENARIO_SCHEMA_VERSION = 1
TRANSCRIPT_SCHEMA_VERSION = 1
RUN_SCHEMA_VERSION = 1
SHA256_PATTERN = r"^[0-9a-f]{64}$"
GIT_SHA_PATTERN = r"^[0-9a-f]{40,64}$"
MAX_SUMMARY_BYTES = 65_536

DomainName = Literal[
    "resource_bar",
    "mode_hub",
    "chapter_panel",
    "recruit_panel",
    "team_panel",
    "team_detail",
    "city_buildings",
    "upgrade_dialog",
    "popup",
    "map_land",
    "battle_report",
    "timers",
]
ScenarioSplit = Literal["generation", "holdout"]
TerminalOutcome = Literal["continue", "recommendation", "stop", "recover"]


def _aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone offset")
    return value


def _identifier(value: str, field_name: str) -> str:
    return validate_identifier(value, field_name=field_name, max_length=120)


def _relative_json_path(value: str, field_name: str) -> str:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.suffix != ".json"
    ):
        raise ValueError(f"{field_name} must be a normalized relative JSON path")
    return value


_FORBIDDEN_SUMMARY_KEYS = frozenset(
    {
        "password",
        "passwd",
        "cookie",
        "cookies",
        "authorization",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "private_key",
        "secret",
        "raw_image",
        "image_bytes",
        "printable_input",
        "keystrokes",
    }
)


def _validate_summary(value: dict[str, Any], field_name: str) -> dict[str, Any]:
    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError(f"{field_name} keys must be strings")
                if key.casefold() in _FORBIDDEN_SUMMARY_KEYS:
                    raise ValueError(f"{field_name} contains forbidden sensitive field: {key}")
                visit(child)
            return
        if isinstance(item, list):
            for child in item:
                visit(child)
            return
        if isinstance(item, str):
            if item.startswith("data:image/"):
                raise ValueError(f"{field_name} cannot contain inline images")
            if len(item) > 4_096:
                raise ValueError(f"{field_name} contains an oversized string")
            return
        if item is None or isinstance(item, (bool, int, float)):
            return
        raise ValueError(f"{field_name} contains a non-JSON value")

    visit(value)
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_SUMMARY_BYTES:
        raise ValueError(f"{field_name} exceeds the fixed summary size limit")
    return value


class CandidateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str
    evidence_refs: list[str] = Field(default_factory=list, max_length=32)
    blocked: StrictBool = False
    blockers: list[str] = Field(default_factory=list, max_length=32)
    verifier_ready: StrictBool = False
    executable: Literal[False] = False

    @field_validator("action_type")
    @classmethod
    def _action_type(cls, value: str) -> str:
        return _identifier(value, "action_type")

    @field_validator("evidence_refs", "blockers")
    @classmethod
    def _unique_values(cls, values: list[str], info: Any) -> list[str]:
        return validate_unique_strings(values, field_name=info.field_name)


class ToolResultSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_fields: dict[str, Any] | None = None
    unknown_domains: list[DomainName] | None = None
    candidates: list[CandidateSnapshot] | None = None
    no_change_recognized: StrictBool | None = None
    terminal_outcome: TerminalOutcome | None = None
    stop_reason: str | None = Field(default=None, max_length=240)
    journal_steps: list[str] | None = Field(default=None, max_length=64)

    @field_validator("state_fields")
    @classmethod
    def _safe_state_fields(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return _validate_summary(value, "state_fields")

    @field_validator("unknown_domains")
    @classmethod
    def _unique_unknown_domains(
        cls, values: list[DomainName] | None
    ) -> list[DomainName] | None:
        if values is None:
            return None
        return validate_unique_strings(values, field_name="unknown_domains")  # type: ignore[arg-type]


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    ordinal: int = Field(ge=0)
    tool_name: str
    arguments_summary: dict[str, Any] = Field(default_factory=dict)
    result_summary: ToolResultSummary = Field(default_factory=ToolResultSummary)
    started_at: datetime
    duration_ms: float = Field(ge=0.0, le=600_000.0)
    success: StrictBool
    domains_queried: list[DomainName] = Field(default_factory=list)
    domain_observed_at: dict[DomainName, datetime] = Field(default_factory=dict)
    observation_refs: list[str] = Field(default_factory=list, max_length=32)
    trace_refs: list[str] = Field(default_factory=list, max_length=32)
    model_id: str | None = Field(default=None, max_length=120)
    session_id: str
    tool_cost_units: float = Field(default=0.0, ge=0.0)
    vision_cost_units: float = Field(default=0.0, ge=0.0)
    execution_authority: Literal["none"] = "none"

    @field_validator("call_id", "session_id")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _identifier(value, info.field_name)

    @field_validator("tool_name")
    @classmethod
    def _read_only_tool(cls, value: str) -> str:
        if value not in GAME_TOOL_ALLOWLIST:
            raise ValueError(f"tool is not in the read-only MCP allowlist: {value}")
        return value

    @field_validator("arguments_summary")
    @classmethod
    def _safe_arguments(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_summary(value, "arguments_summary")

    @field_validator("started_at")
    @classmethod
    def _aware_started_at(cls, value: datetime) -> datetime:
        return _aware(value, "started_at")

    @field_validator("domains_queried", "observation_refs", "trace_refs")
    @classmethod
    def _unique_lists(cls, values: list[str], info: Any) -> list[str]:
        return validate_unique_strings(values, field_name=info.field_name)

    @field_validator("domain_observed_at")
    @classmethod
    def _aware_domain_times(
        cls, values: dict[DomainName, datetime]
    ) -> dict[DomainName, datetime]:
        for domain, observed_at in values.items():
            _aware(observed_at, f"domain_observed_at.{domain}")
        return values

    @model_validator(mode="after")
    def _queried_domains_bind_observations(self) -> ToolCallRecord:
        expected_arguments = GAME_TOOL_ARGUMENTS[self.tool_name]
        actual_arguments = frozenset(self.arguments_summary)
        required_arguments = GAME_TOOL_REQUIRED_ARGUMENTS[self.tool_name]
        if (
            not required_arguments.issubset(actual_arguments)
            or not actual_arguments.issubset(expected_arguments)
        ):
            raise ValueError(
                f"arguments_summary must satisfy {self.tool_name} argument contract: "
                f"required={sorted(required_arguments)}, allowed={sorted(expected_arguments)}"
            )
        if self.tool_name == "evaluate_fixture":
            fixture = self.arguments_summary.get("fixture")
            if not isinstance(fixture, str):
                raise ValueError("evaluate_fixture fixture must be a string")
            _relative_json_path(fixture, "arguments_summary.fixture")
            include_details = self.arguments_summary.get("include_details")
            if include_details is not None and type(include_details) is not bool:
                raise ValueError("evaluate_fixture include_details must be a boolean")
        if not set(self.domain_observed_at).issubset(self.domains_queried):
            raise ValueError("domain_observed_at must only reference queried domains")
        return self


class StaticScenarioTranscript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    session_id: str
    capture_group_id: str
    calls: list[ToolCallRecord] = Field(min_length=1, max_length=128)
    failure_at: datetime | None = None
    execution_authority: Literal["none"] = "none"
    live_control_used: Literal[False] = False

    @field_validator("scenario_id", "session_id", "capture_group_id")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _identifier(value, info.field_name)

    @field_validator("failure_at")
    @classmethod
    def _aware_failure_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware(value, "failure_at")

    @model_validator(mode="after")
    def _ordered_bound_calls(self) -> StaticScenarioTranscript:
        if [call.ordinal for call in self.calls] != list(range(len(self.calls))):
            raise ValueError("tool-call ordinals must be contiguous and start at zero")
        call_ids = [call.call_id for call in self.calls]
        validate_unique_strings(call_ids, field_name="call_ids")
        if any(call.session_id != self.session_id for call in self.calls):
            raise ValueError("every tool call must bind to the transcript session")
        timestamps = [call.started_at for call in self.calls]
        if timestamps != sorted(timestamps):
            raise ValueError("tool calls must be ordered by started_at")
        if self.failure_at is not None and self.failure_at < timestamps[0]:
            raise ValueError("failure_at cannot predate the transcript")
        return self


class StaticTranscriptBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = TRANSCRIPT_SCHEMA_VERSION
    artifact_type: Literal["sanmou_mcp_static_transcripts"] = "sanmou_mcp_static_transcripts"
    split: ScenarioSplit
    transcripts: list[StaticScenarioTranscript] = Field(min_length=1, max_length=256)
    execution_authority: Literal["none"] = "none"
    live_control_used: Literal[False] = False
    oracle_labels_included: Literal[False] = False

    @model_validator(mode="after")
    def _unique_transcripts(self) -> StaticTranscriptBundle:
        validate_unique_strings(
            [item.scenario_id for item in self.transcripts], field_name="scenario_ids"
        )
        return self


class SensoriumPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    critical_domains: list[DomainName] = Field(min_length=1)
    stale_after_seconds: dict[DomainName, float]
    required_before_failure: list[DomainName] = Field(default_factory=list)

    @field_validator("critical_domains", "required_before_failure")
    @classmethod
    def _unique_domains(cls, values: list[DomainName], info: Any) -> list[DomainName]:
        return validate_unique_strings(values, field_name=info.field_name)  # type: ignore[arg-type]

    @field_validator("stale_after_seconds")
    @classmethod
    def _positive_stale_windows(
        cls, values: dict[DomainName, float]
    ) -> dict[DomainName, float]:
        if any(value <= 0.0 or value > 86_400.0 for value in values.values()):
            raise ValueError("stale windows must be in (0, 86400] seconds")
        return values

    @model_validator(mode="after")
    def _policy_is_complete(self) -> SensoriumPolicy:
        critical = set(self.critical_domains)
        if set(self.stale_after_seconds) != critical:
            raise ValueError("stale_after_seconds must cover every critical domain exactly")
        if not set(self.required_before_failure).issubset(critical):
            raise ValueError("required_before_failure must be a subset of critical_domains")
        return self


class ScenarioExpectations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_fields: dict[str, Any] = Field(default_factory=dict)
    unknown_domains: list[DomainName] = Field(default_factory=list)
    required_tool_calls: list[str] = Field(default_factory=list)
    grounded_proposals: list[str] = Field(default_factory=list)
    blocked_actions: dict[str, list[str]] = Field(default_factory=dict)
    verifier_readiness: dict[str, StrictBool] = Field(default_factory=dict)
    no_change_recognized: StrictBool | None = None
    terminal_outcome: TerminalOutcome
    stop_reason: str | None = Field(default=None, max_length=240)
    journal_plan: list[str] = Field(default_factory=list)

    @field_validator("state_fields")
    @classmethod
    def _safe_expected_state(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _validate_summary(value, "expected state_fields")

    @field_validator("unknown_domains", "required_tool_calls", "grounded_proposals", "journal_plan")
    @classmethod
    def _unique_lists(cls, values: list[str], info: Any) -> list[str]:
        return validate_unique_strings(values, field_name=info.field_name)

    @field_validator("required_tool_calls")
    @classmethod
    def _required_calls_are_read_only(cls, values: list[str]) -> list[str]:
        invalid = sorted(set(values) - GAME_TOOL_ALLOWLIST)
        if invalid:
            raise ValueError(f"required tools are not read-only: {invalid}")
        return values

    @field_validator("grounded_proposals")
    @classmethod
    def _proposal_ids(cls, values: list[str]) -> list[str]:
        return [_identifier(value, "grounded_proposal") for value in values]

    @field_validator("blocked_actions", "verifier_readiness")
    @classmethod
    def _action_map_ids(cls, values: dict[str, Any], info: Any) -> dict[str, Any]:
        for key in values:
            _identifier(key, f"{info.field_name} action")
        return values


class ScenarioManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCENARIO_SCHEMA_VERSION
    scenario_id: str
    title: str = Field(min_length=1, max_length=160)
    split: ScenarioSplit
    session_id: str
    capture_group_id: str
    fixture_path: str
    fixture_sha256: str = Field(pattern=SHA256_PATTERN)
    contract_version: str
    sensorium: SensoriumPolicy
    expectations: ScenarioExpectations | None = None
    execution_authority: Literal["none"] = "none"
    live_control_allowed: Literal[False] = False
    oracle_access_allowed: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False

    @field_validator("scenario_id", "session_id", "capture_group_id")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _identifier(value, info.field_name)

    @field_validator("fixture_path")
    @classmethod
    def _fixture_path(cls, value: str) -> str:
        return _relative_json_path(value, "fixture_path")

    @field_validator("contract_version")
    @classmethod
    def _contract_version(cls, value: str) -> str:
        if value != CONTRACT_VERSION:
            raise ValueError(f"contract_version must be {CONTRACT_VERSION}")
        return value

    @model_validator(mode="after")
    def _split_boundary(self) -> ScenarioManifest:
        if self.split == "generation" and self.expectations is None:
            raise ValueError("generation scenarios require expectations")
        if self.split == "holdout" and self.expectations is not None:
            raise ValueError("holdout scenarios must not include expectations")
        if self.split == "holdout":
            lowered = self.fixture_path.casefold()
            if any(word in lowered for word in ("oracle", "private-key", "private_key", "ledger", "labels")):
                raise ValueError("holdout fixture path cannot reference evaluator-only artifacts")
        return self


class BatteryManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCENARIO_SCHEMA_VERSION
    artifact_type: Literal["sanmou_mcp_eval_battery"] = "sanmou_mcp_eval_battery"
    battery_id: str
    contract_version: str
    prompt_version: str
    playbook_version: str
    scenarios: list[ScenarioManifest] = Field(min_length=1, max_length=256)
    execution_authority: Literal["none"] = "none"
    live_control_allowed: Literal[False] = False
    holdout_oracle_access_allowed: Literal[False] = False

    @field_validator("battery_id", "prompt_version", "playbook_version")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _identifier(value, info.field_name)

    @field_validator("contract_version")
    @classmethod
    def _contract_version(cls, value: str) -> str:
        if value != CONTRACT_VERSION:
            raise ValueError(f"contract_version must be {CONTRACT_VERSION}")
        return value

    @model_validator(mode="after")
    def _global_split_isolation(self) -> BatteryManifest:
        validate_unique_strings(
            [scenario.scenario_id for scenario in self.scenarios], field_name="scenario_ids"
        )
        for attr, label in (
            ("session_id", "session"),
            ("capture_group_id", "capture group"),
            ("fixture_sha256", "fixture digest"),
        ):
            seen: dict[str, ScenarioSplit] = {}
            for scenario in self.scenarios:
                value = getattr(scenario, attr)
                previous = seen.setdefault(value, scenario.split)
                if previous != scenario.split:
                    raise ValueError(f"{label} crosses generation/holdout split: {value}")
        if any(
            scenario.contract_version != self.contract_version
            for scenario in self.scenarios
        ):
            raise ValueError("scenario contract_version must match the battery contract")
        return self


class ObservedScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_fields: dict[str, Any] = Field(default_factory=dict)
    unknown_domains: list[DomainName] = Field(default_factory=list)
    candidates: list[CandidateSnapshot] = Field(default_factory=list)
    no_change_recognized: StrictBool | None = None
    terminal_outcome: TerminalOutcome = "continue"
    stop_reason: str | None = None
    journal_steps: list[str] = Field(default_factory=list)


class SensoriumMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queried_domains: list[DomainName]
    never_queried_critical_domains: list[DomainName]
    stale_critical_domains_at_end: list[DomainName]
    seconds_since_refresh_at_end: dict[DomainName, float | None]
    missed_risk_domains_before_failure: list[DomainName]
    critical_domain_query_coverage: float = Field(ge=0.0, le=1.0)


class ObservabilityMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call_count: int = Field(ge=0)
    successful_tool_call_count: int = Field(ge=0)
    failed_tool_call_count: int = Field(ge=0)
    success_rate: float = Field(ge=0.0, le=1.0)
    total_duration_ms: float = Field(ge=0.0)
    mean_duration_ms: float = Field(ge=0.0)
    p95_duration_ms: float = Field(ge=0.0)
    tool_cost_units: float = Field(ge=0.0)
    vision_cost_units: float = Field(ge=0.0)
    per_tool_call_count: dict[str, int]
    observation_ref_count: int = Field(ge=0)
    trace_ref_count: int = Field(ge=0)


class MetricScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_field_accuracy: float | None = Field(default=None, ge=0.0, le=1.0)
    unknown_calibration: float | None = Field(default=None, ge=0.0, le=1.0)
    tool_call_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    proposal_grounding: float | None = Field(default=None, ge=0.0, le=1.0)
    blocked_action_correctness: float | None = Field(default=None, ge=0.0, le=1.0)
    verifier_readiness: float | None = Field(default=None, ge=0.0, le=1.0)
    no_change_recognition: float | None = Field(default=None, ge=0.0, le=1.0)
    recovery_stop_correctness: float | None = Field(default=None, ge=0.0, le=1.0)
    journal_plan_adherence: float | None = Field(default=None, ge=0.0, le=1.0)


class ScenarioScoreReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    split: ScenarioSplit
    scored: StrictBool
    scores: MetricScores
    sensorium: SensoriumMetrics
    observability: ObservabilityMetrics
    observed: ObservedScenario
    execution_authority: Literal["none"] = "none"
    live_control_used: Literal[False] = False
    oracle_accessed: Literal[False] = False


class AggregateMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_count: int = Field(ge=1)
    scored_generation_count: int = Field(ge=0)
    unscored_holdout_count: int = Field(ge=0)
    mean_scores: dict[str, float]
    total_tool_calls: int = Field(ge=0)
    total_duration_ms: float = Field(ge=0.0)
    total_tool_cost_units: float = Field(ge=0.0)
    total_vision_cost_units: float = Field(ge=0.0)
    mean_critical_domain_query_coverage: float = Field(ge=0.0, le=1.0)
    scenarios_with_missed_risk_domains: int = Field(ge=0)
    split_isolation_verified: Literal[True] = True
    holdout_oracle_accessed: Literal[False] = False
    live_control_used: Literal[False] = False


class EvalSourceBindings(BaseModel):
    """Digest-only bindings to canonical golden and R&R evidence sources."""

    model_config = ConfigDict(extra="forbid")

    golden_bound: StrictBool = False
    golden_expectations_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    golden_fixture_count: int = Field(default=0, ge=0)
    golden_match_count: int = Field(default=0, ge=0)
    golden_all_matched: StrictBool = False
    record_replay_bound: StrictBool = False
    record_replay_catalog_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    record_replay_audit_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    record_replay_session_count: int = Field(default=0, ge=0)
    record_replay_generation_count: int = Field(default=0, ge=0)
    record_replay_holdout_count: int = Field(default=0, ge=0)
    record_replay_coverage_ready: StrictBool = False
    record_replay_blockers: list[str] = Field(default_factory=list, max_length=64)
    execution_authority: Literal["none"] = "none"
    live_control_used: Literal[False] = False
    holdout_oracle_accessed: Literal[False] = False

    @model_validator(mode="after")
    def _bindings_are_consistent(self) -> EvalSourceBindings:
        if self.golden_match_count > self.golden_fixture_count:
            raise ValueError("golden match count exceeds fixture count")
        if self.golden_bound != (self.golden_expectations_sha256 is not None):
            raise ValueError("golden binding flag and digest disagree")
        if self.golden_all_matched != (
            self.golden_bound
            and self.golden_fixture_count > 0
            and self.golden_match_count == self.golden_fixture_count
        ):
            raise ValueError("golden all-matched flag is inconsistent")
        rr_digests_present = (
            self.record_replay_catalog_sha256 is not None
            and self.record_replay_audit_digest is not None
        )
        if self.record_replay_bound != rr_digests_present:
            raise ValueError("R&R binding flag and digests disagree")
        if self.record_replay_generation_count + self.record_replay_holdout_count != self.record_replay_session_count:
            raise ValueError("R&R split counts do not equal session count")
        return self


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = RUN_SCHEMA_VERSION
    artifact_type: Literal["sanmou_mcp_eval_run_manifest"] = "sanmou_mcp_eval_run_manifest"
    run_id: str
    battery_id: str
    repo_sha: str = Field(pattern=GIT_SHA_PATTERN)
    contract_version: str
    fixture_catalog_digest: str = Field(pattern=SHA256_PATTERN)
    model_provider: str
    model_id: str
    prompt_version: str
    playbook_version: str
    random_seed: int = Field(ge=0)
    started_at: datetime
    ended_at: datetime
    start_state: dict[str, Any]
    end_state: dict[str, Any]
    tool_log_digest: str = Field(pattern=SHA256_PATTERN)
    source_bindings: EvalSourceBindings = Field(default_factory=EvalSourceBindings)
    execution_authority: Literal["none"] = "none"
    live_control_used: Literal[False] = False
    holdout_oracle_accessed: Literal[False] = False

    @field_validator("run_id", "battery_id", "model_provider", "model_id", "prompt_version", "playbook_version")
    @classmethod
    def _ids(cls, value: str, info: Any) -> str:
        return _identifier(value, info.field_name)

    @field_validator("contract_version")
    @classmethod
    def _contract_version(cls, value: str) -> str:
        if value != CONTRACT_VERSION:
            raise ValueError(f"contract_version must be {CONTRACT_VERSION}")
        return value

    @field_validator("started_at", "ended_at")
    @classmethod
    def _aware_times(cls, value: datetime, info: Any) -> datetime:
        return _aware(value, info.field_name)

    @model_validator(mode="after")
    def _time_order(self) -> RunManifest:
        if self.ended_at < self.started_at:
            raise ValueError("run ended before it started")
        return self


class McpEvalRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_manifest: RunManifest
    aggregate: AggregateMetrics
    scenario_reports: list[ScenarioScoreReport]
