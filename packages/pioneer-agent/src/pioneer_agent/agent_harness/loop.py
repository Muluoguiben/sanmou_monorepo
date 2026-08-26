"""One recommendation-only decision window over frozen read-only MCP tools."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from pioneer_agent.agent_harness.contracts import (
    ANSWER_RULE_QUESTION,
    GAME_READ_ONLY_TOOLS,
    GET_RUNTIME_STATE,
    LIST_ACTION_CANDIDATES,
    OBSERVE_GAME,
    QA_READ_ONLY_TOOLS,
    SESSION_STATUS,
    McpClient,
    structured_content,
)
from pioneer_agent.agent_harness.journal import (
    AgentInference,
    DecisionJournal,
    JournalStore,
    ObservedFact,
    PendingTimer,
    evidence_ref,
)
from pioneer_agent.agent_harness.policy import StopDecision, StopPolicy, StopReason
from pioneer_agent.agent_harness.tool_log import (
    ToolCallRecord,
    ToolLog,
    extract_refs,
    summarize_arguments,
    summarize_result,
)


class LiveObservation(BaseModel):
    """Only fields frozen in todo-list.md M0; extra service fields pass through."""

    model_config = ConfigDict(extra="allow")

    session_id: str
    observation_id: str
    frame_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: datetime
    window_identity: dict[str, Any]
    capture_geometry: dict[str, Any]
    domains_run: list[str]
    unknown_domains: list[str]
    structured_evidence: list[dict[str, Any]]
    confidence: float = Field(ge=0.0, le=1.0)
    execution_authority: Literal["none"]

    @field_validator("captured_at")
    @classmethod
    def _aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware")
        return value


class SessionStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    window_identity: dict[str, Any]
    capture_health: dict[str, Any]
    execution_authority: Literal["none"]


class CandidateProposal(BaseModel):
    model_config = ConfigDict(extra="allow")

    action_id: str
    action_type: str
    risk: dict[str, Any]
    evidence: list[Any]
    confidence: float = Field(ge=0.0, le=1.0)
    blockers: list[str]
    executable: Literal[False]


class DecisionWindowStatus(str, Enum):
    RECOMMENDED = "recommended"
    STOPPED = "stopped"


class DecisionWindowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DecisionWindowStatus
    recommendation: CandidateProposal | None = None
    stop: StopDecision = Field(default_factory=StopDecision)
    observation_id: str | None = None
    journal: DecisionJournal


class RecommendationHarness:
    """Read-only decision loop. It has no execution client and no action method."""

    def __init__(
        self,
        *,
        game_client: McpClient,
        journal_store: JournalStore,
        tool_log: ToolLog,
        agent_session_id: str,
        model_id: str,
        qa_client: McpClient | None = None,
        stop_policy: StopPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        self.game_client = game_client
        self.qa_client = qa_client
        self.journal_store = journal_store
        self.tool_log = tool_log
        self.agent_session_id = agent_session_id
        self.model_id = model_id
        self.stop_policy = stop_policy or StopPolicy()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.monotonic = monotonic or time.perf_counter
        self._consecutive_tool_failures = 0

    async def run_decision_window(
        self,
        *,
        qa_questions: Sequence[str] = (),
    ) -> DecisionWindowResult:
        journal = self.journal_store.load(self.agent_session_id)
        try:
            status_payload = await self._call_game(SESSION_STATUS, {})
        except Exception:
            return self._stop(journal, StopReason.TOOL_FAILURE, [SESSION_STATUS])
        try:
            status = SessionStatus.model_validate(status_payload)
        except ValidationError as exc:
            reason = (
                StopReason.EXECUTION_AUTHORITY_VIOLATION
                if "execution_authority" in str(exc)
                else StopReason.CONTRACT_VIOLATION
            )
            return self._stop(journal, reason, ["invalid session_status contract"])
        if _capture_unhealthy(status.capture_health):
            return self._stop(journal, StopReason.CAPTURE_UNHEALTHY, ["session capture health is not healthy"])

        window_identity = status.window_identity
        window_stop = self.stop_policy.window_stop(journal, window_identity)
        if window_stop.should_stop:
            return self._stop(journal, window_stop.reason, window_stop.details)

        try:
            observation_payload = await self._call_game(OBSERVE_GAME, {})
            observation = LiveObservation.model_validate(observation_payload)
        except Exception as exc:
            return self._stop(journal, StopReason.CONTRACT_VIOLATION, [type(exc).__name__])

        if window_identity != observation.window_identity:
            return self._stop(
                journal,
                StopReason.WINDOW_IDENTITY_CHANGED,
                ["window identity changed inside the decision window"],
                observation_id=observation.observation_id,
            )
        journal = self._record_observation(journal, observation)
        observation_stop = self.stop_policy.observation_stop(
            captured_at=observation.captured_at,
            now=self.clock(),
            unknown_domains=observation.unknown_domains,
        )
        if observation_stop.should_stop:
            return self._stop(
                journal,
                observation_stop.reason,
                observation_stop.details,
                observation_id=observation.observation_id,
            )
        checkpoint_stop = self.stop_policy.checkpoint_stop(journal, self.clock())
        if checkpoint_stop.should_stop:
            return self._stop(
                journal,
                checkpoint_stop.reason,
                checkpoint_stop.details,
                observation_id=observation.observation_id,
            )
        journal = self._record_due_checkpoints(journal, observation)

        try:
            runtime_state = await self._call_game(GET_RUNTIME_STATE, {})
        except Exception:
            return self._stop(
                journal,
                StopReason.TOOL_FAILURE,
                [GET_RUNTIME_STATE],
                observation_id=observation.observation_id,
            )
        authority_stop = _authority_stop(runtime_state, required=True)
        if authority_stop.should_stop:
            return self._stop(journal, authority_stop.reason, authority_stop.details, observation.observation_id)
        binding_stop = _binding_stop(runtime_state, observation)
        if binding_stop.should_stop:
            return self._stop(journal, binding_stop.reason, binding_stop.details, observation.observation_id)
        journal = self._record_timers(journal, runtime_state, observation)

        if self.qa_client is not None:
            for question in qa_questions:
                try:
                    qa_payload = await self._call_qa(ANSWER_RULE_QUESTION, {"question": question})
                    journal = self._record_qa_evidence(journal, qa_payload, observation)
                except Exception:
                    if self._consecutive_tool_failures >= self.stop_policy.max_consecutive_tool_failures:
                        return self._stop(
                            journal,
                            StopReason.CONSECUTIVE_TOOL_FAILURES,
                            [ANSWER_RULE_QUESTION],
                            observation.observation_id,
                        )

        try:
            proposal_payload = await self._call_game(LIST_ACTION_CANDIDATES, {})
            authority_stop = _authority_stop(proposal_payload, required=True)
            if authority_stop.should_stop:
                return self._stop(journal, authority_stop.reason, authority_stop.details, observation.observation_id)
            binding_stop = _binding_stop(proposal_payload, observation)
            if binding_stop.should_stop:
                return self._stop(journal, binding_stop.reason, binding_stop.details, observation.observation_id)
            candidates = [CandidateProposal.model_validate(item) for item in _candidate_items(proposal_payload)]
        except Exception as exc:
            return self._stop(
                journal,
                StopReason.CONTRACT_VIOLATION,
                [type(exc).__name__],
                observation.observation_id,
            )

        candidates_stop = self.stop_policy.candidates_stop(candidates)
        if candidates_stop.should_stop:
            return self._stop(
                journal,
                candidates_stop.reason,
                candidates_stop.details,
                observation.observation_id,
            )
        recommendation = next(candidate for candidate in candidates if not candidate.blockers)
        journal = self._record_recommendation(journal, recommendation, observation)
        confirmation_stop = self.stop_policy.confirmation_stop(recommendation)
        if confirmation_stop.should_stop:
            return self._stop(
                journal,
                confirmation_stop.reason,
                confirmation_stop.details,
                observation.observation_id,
                recommendation=recommendation,
            )

        journal.updated_at = self.clock()
        self.journal_store.save(journal)
        return DecisionWindowResult(
            status=DecisionWindowStatus.RECOMMENDED,
            recommendation=recommendation,
            observation_id=observation.observation_id,
            journal=journal,
        )

    async def _call_game(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if name not in GAME_READ_ONLY_TOOLS:
            raise ValueError(f"game tool is outside frozen read-only contract: {name}")
        return await self._call(self.game_client, name, arguments)

    async def _call_qa(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if self.qa_client is None:
            raise ValueError("qa_client is not configured")
        if name not in QA_READ_ONLY_TOOLS:
            raise ValueError(f"QA tool is outside frozen read-only contract: {name}")
        return await self._call(self.qa_client, name, arguments)

    async def _call(
        self,
        client: McpClient,
        name: str,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        started_at = self.clock()
        started = self.monotonic()
        try:
            raw_result = await client.call_tool(name, arguments)
            payload = structured_content(raw_result)
        except Exception as exc:
            self._consecutive_tool_failures += 1
            self.tool_log.append(
                ToolCallRecord(
                    started_at=started_at,
                    tool_name=name,
                    arguments_summary=summarize_arguments(arguments),
                    duration_ms=max(0.0, (self.monotonic() - started) * 1000),
                    success=False,
                    error_type=type(exc).__name__,
                    model_id=self.model_id,
                    agent_session_id=self.agent_session_id,
                )
            )
            raise
        self._consecutive_tool_failures = 0
        observation_refs, trace_refs = extract_refs(payload)
        self.tool_log.append(
            ToolCallRecord(
                started_at=started_at,
                tool_name=name,
                arguments_summary=summarize_arguments(arguments),
                result_summary=summarize_result(payload),
                duration_ms=max(0.0, (self.monotonic() - started) * 1000),
                success=True,
                observation_refs=observation_refs,
                trace_refs=trace_refs,
                model_id=self.model_id,
                agent_session_id=self.agent_session_id,
                game_session_id=_optional_string(payload.get("session_id")),
            )
        )
        return payload

    def _record_observation(self, journal: DecisionJournal, observation: LiveObservation) -> DecisionJournal:
        obs_ref = evidence_ref("observation", observation.observation_id)
        frame_ref = evidence_ref("frame_sha256", observation.frame_sha256)
        journal.tactical.observed.append(
            ObservedFact(
                fact="live_observation",
                observed_at=observation.captured_at,
                observation_id=observation.observation_id,
                evidence_refs=[obs_ref, frame_ref],
                metadata={
                    "confidence": observation.confidence,
                    "domains_run": observation.domains_run,
                    "unknown_domains": observation.unknown_domains,
                },
            )
        )
        journal.tooling.observed.append(
            ObservedFact(
                fact="window_identity",
                observed_at=observation.captured_at,
                observation_id=observation.observation_id,
                evidence_refs=[obs_ref, frame_ref],
                metadata={"window_identity": observation.window_identity},
            )
        )
        for checkpoint in self.stop_policy.checkpoints:
            if any(domain in observation.domains_run for domain in checkpoint.domains):
                journal.tooling.observed.append(
                    ObservedFact(
                        fact=f"checkpoint:{checkpoint.name}",
                        observed_at=observation.captured_at,
                        observation_id=observation.observation_id,
                        evidence_refs=[obs_ref, frame_ref],
                        metadata={
                            "domains": [domain for domain in checkpoint.domains if domain in observation.domains_run],
                            "refresh_every_s": checkpoint.refresh_every_s,
                            "stale_after_s": checkpoint.stale_after_s,
                        },
                    )
                )
        journal.evidence_refs = _merge_unique(journal.evidence_refs, [obs_ref, frame_ref])
        return journal

    def _record_due_checkpoints(
        self,
        journal: DecisionJournal,
        observation: LiveObservation,
    ) -> DecisionJournal:
        due = self.stop_policy.due_checkpoints(journal, self.clock())
        if not due:
            return journal
        obs_ref = evidence_ref("observation", observation.observation_id)
        for checkpoint_name in due:
            previous_due = next(
                (
                    item
                    for item in reversed(journal.tooling.inferred)
                    if item.metadata.get("checkpoint_name") == checkpoint_name
                ),
                None,
            )
            observed = journal.latest_tooling_fact(f"checkpoint:{checkpoint_name}")
            if previous_due is not None and (observed is None or previous_due.inferred_at > observed.observed_at):
                continue
            inference = AgentInference(
                inference=f"checkpoint_due:{checkpoint_name}",
                inferred_at=self.clock(),
                based_on_evidence_refs=[obs_ref],
                metadata={"checkpoint_name": checkpoint_name},
            )
            journal.tooling.inferred.append(inference)
            journal.planning.inferred.append(inference.model_copy(deep=True))
        return journal

    def _record_timers(
        self,
        journal: DecisionJournal,
        runtime_state: Mapping[str, Any],
        observation: LiveObservation,
    ) -> DecisionJournal:
        timing = runtime_state.get("timing")
        if timing is None and isinstance(runtime_state.get("state"), Mapping):
            timing = runtime_state["state"].get("timing")
        if not isinstance(timing, Mapping):
            return journal
        timers: list[PendingTimer] = []
        obs_ref = evidence_ref("observation", observation.observation_id)
        for timer_id, value in timing.items():
            if not isinstance(value, str):
                continue
            try:
                due_at = datetime.fromisoformat(value)
                timers.append(PendingTimer(timer_id=str(timer_id), due_at=due_at, evidence_refs=[obs_ref]))
            except (ValueError, ValidationError):
                continue
        journal.pending_timers = timers
        return journal

    def _record_qa_evidence(
        self,
        journal: DecisionJournal,
        payload: Mapping[str, Any],
        observation: LiveObservation,
    ) -> DecisionJournal:
        refs = _qa_evidence_refs(payload)
        if not refs:
            return journal
        journal.strategic.observed.append(
            ObservedFact(
                fact="reviewed_qa_evidence",
                observed_at=self.clock(),
                observation_id=observation.observation_id,
                evidence_refs=refs,
                metadata={"status": payload.get("status")},
            )
        )
        journal.evidence_refs = _merge_unique(journal.evidence_refs, refs)
        return journal

    def _record_recommendation(
        self,
        journal: DecisionJournal,
        recommendation: CandidateProposal,
        observation: LiveObservation,
    ) -> DecisionJournal:
        refs = _candidate_evidence_refs(recommendation)
        if not refs:
            refs = [evidence_ref("observation", observation.observation_id)]
        journal.planning.inferred.append(
            AgentInference(
                inference=f"recommend {recommendation.action_type}:{recommendation.action_id}",
                inferred_at=self.clock(),
                based_on_evidence_refs=refs,
                metadata={
                    "action_id": recommendation.action_id,
                    "action_type": recommendation.action_type,
                    "confidence": recommendation.confidence,
                    "recommendation_only": True,
                    "executable": False,
                },
            )
        )
        journal.evidence_refs = _merge_unique(journal.evidence_refs, refs)
        return journal

    def _stop(
        self,
        journal: DecisionJournal,
        reason: StopReason | None,
        details: list[str],
        observation_id: str | None = None,
        recommendation: CandidateProposal | None = None,
    ) -> DecisionWindowResult:
        resolved_reason = reason or StopReason.CONTRACT_VIOLATION
        refs = journal.evidence_refs[-10:] or [f"stop:{resolved_reason.value}"]
        journal.tooling.inferred.append(
            AgentInference(
                inference=f"stop:{resolved_reason.value}",
                inferred_at=self.clock(),
                based_on_evidence_refs=refs,
                metadata={"details": details},
            )
        )
        journal.updated_at = self.clock()
        self.journal_store.save(journal)
        return DecisionWindowResult(
            status=DecisionWindowStatus.STOPPED,
            recommendation=recommendation,
            stop=StopDecision(should_stop=True, reason=resolved_reason, details=details),
            observation_id=observation_id,
            journal=journal,
        )


def _authority_stop(payload: Mapping[str, Any], *, required: bool = False) -> StopDecision:
    authority = payload.get("execution_authority")
    if authority is None and not required:
        return StopDecision()
    if authority != "none":
        return StopDecision(
            should_stop=True,
            reason=StopReason.EXECUTION_AUTHORITY_VIOLATION,
            details=[f"execution_authority={authority!r}"],
        )
    return StopDecision()


def _capture_unhealthy(health: Mapping[str, Any]) -> bool:
    return str(health.get("status", "unknown")).lower() not in {"healthy", "ok"}


def _binding_stop(payload: Mapping[str, Any], observation: LiveObservation) -> StopDecision:
    expected = {
        "session_id": observation.session_id,
        "observation_id": observation.observation_id,
        "frame_sha256": observation.frame_sha256,
    }
    mismatches = [
        f"{key}={payload.get(key)!r} expected {value!r}"
        for key, value in expected.items()
        if payload.get(key) != value
    ]
    if mismatches:
        return StopDecision(
            should_stop=True,
            reason=StopReason.CONTRACT_VIOLATION,
            details=mismatches,
        )
    return StopDecision()


def _candidate_items(payload: Mapping[str, Any]) -> list[Any]:
    value = payload.get("candidates")
    if isinstance(value, list):
        return value
    raise ValueError("list_action_candidates returned no candidate list")


def _candidate_evidence_refs(candidate: CandidateProposal) -> list[str]:
    refs: list[str] = []
    for item in candidate.evidence:
        if isinstance(item, str) and item:
            refs.append(item)
        elif isinstance(item, Mapping):
            for key in ("evidence_id", "entry_id", "source_ref", "ref"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    refs.append(value)
                    break
    return _merge_unique([], refs)


def _qa_evidence_refs(payload: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("items", "entries", "evidence"):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, Mapping):
                for ref_key in ("entry_id", "id", "source_ref"):
                    value = item.get(ref_key)
                    if isinstance(value, str) and value:
                        refs.append(value)
                        break
    return _merge_unique([], refs)


def _merge_unique(existing: list[str], incoming: list[str]) -> list[str]:
    return list(dict.fromkeys([*existing, *incoming]))


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
