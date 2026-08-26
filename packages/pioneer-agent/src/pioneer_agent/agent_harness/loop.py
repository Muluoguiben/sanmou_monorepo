"""One recommendation-only decision window over frozen read-only MCP tools."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pioneer_agent.agent_harness.contracts import (
    ANSWER_RULE_QUESTION,
    QA_READ_ONLY_TOOLS,
    McpClient,
    structured_content,
    validate_game_response,
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
from pioneer_agent.mcp_server.contracts import (
    GET_RUNTIME_STATE_TOOL,
    LIST_ACTION_CANDIDATES_TOOL,
    OBSERVE_GAME_TOOL,
    SESSION_STATUS_TOOL,
    ActionCandidatesResponse,
    ActionProposal,
    ContractResponse,
    LiveObservation,
    ObserveGameResponse,
    RuntimeStateResponse,
    SessionStatusResponse,
)


class DecisionWindowStatus(str, Enum):
    RECOMMENDED = "recommended"
    STOPPED = "stopped"


class DecisionWindowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: DecisionWindowStatus
    recommendation: ActionProposal | None = None
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
            status = await self._call_game(SESSION_STATUS_TOOL, {})
        except ValidationError as exc:
            return self._stop(
                journal,
                _validation_stop_reason(exc),
                ["invalid session_status contract"],
            )
        except Exception:
            return self._stop(journal, StopReason.TOOL_FAILURE, [SESSION_STATUS_TOOL])
        if not isinstance(status, SessionStatusResponse):
            return self._stop(journal, StopReason.CONTRACT_VIOLATION, [SESSION_STATUS_TOOL])
        response_stop = _response_stop(status, SESSION_STATUS_TOOL)
        if response_stop.should_stop:
            return self._stop(journal, response_stop.reason, response_stop.details)
        if status.session is None:
            return self._stop(journal, StopReason.CAPTURE_UNHEALTHY, ["session is not configured"])
        if _capture_unhealthy(status.session.capture_health):
            return self._stop(journal, StopReason.CAPTURE_UNHEALTHY, ["session capture health is not healthy"])

        window_identity = _model_payload(status.session.window_identity)
        window_stop = self.stop_policy.window_stop(journal, window_identity)
        if window_stop.should_stop:
            return self._stop(journal, window_stop.reason, window_stop.details)

        try:
            observed = await self._call_game(OBSERVE_GAME_TOOL, {})
        except ValidationError as exc:
            return self._stop(journal, _validation_stop_reason(exc), ["invalid observe_game contract"])
        except Exception:
            return self._stop(journal, StopReason.TOOL_FAILURE, [OBSERVE_GAME_TOOL])
        if not isinstance(observed, ObserveGameResponse):
            return self._stop(journal, StopReason.CONTRACT_VIOLATION, [OBSERVE_GAME_TOOL])
        response_stop = _response_stop(observed, OBSERVE_GAME_TOOL)
        if response_stop.should_stop:
            return self._stop(journal, response_stop.reason, response_stop.details)
        observation = observed.observation
        if observation is None:
            return self._stop(journal, StopReason.CONTRACT_VIOLATION, ["missing observation"])

        observed_identity = _model_payload(observation.window_identity)
        if window_identity is not None and window_identity != observed_identity:
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
            state_response = await self._call_game(GET_RUNTIME_STATE_TOOL, {})
        except ValidationError as exc:
            return self._stop(
                journal,
                _validation_stop_reason(exc),
                ["invalid get_runtime_state contract"],
                observation_id=observation.observation_id,
            )
        except Exception:
            return self._stop(
                journal,
                StopReason.TOOL_FAILURE,
                [GET_RUNTIME_STATE_TOOL],
                observation_id=observation.observation_id,
            )
        if not isinstance(state_response, RuntimeStateResponse):
            return self._stop(journal, StopReason.CONTRACT_VIOLATION, [GET_RUNTIME_STATE_TOOL])
        response_stop = _response_stop(state_response, GET_RUNTIME_STATE_TOOL)
        if response_stop.should_stop:
            return self._stop(journal, response_stop.reason, response_stop.details, observation.observation_id)
        binding_stop = _binding_stop(state_response.observation, observation)
        if binding_stop.should_stop:
            return self._stop(journal, binding_stop.reason, binding_stop.details, observation.observation_id)
        journal = self._record_timers(journal, state_response.runtime_state or {}, observation)

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
            proposal_response = await self._call_game(LIST_ACTION_CANDIDATES_TOOL, {})
            if not isinstance(proposal_response, ActionCandidatesResponse):
                raise TypeError("wrong list_action_candidates response model")
            response_stop = _response_stop(proposal_response, LIST_ACTION_CANDIDATES_TOOL)
            if response_stop.should_stop:
                return self._stop(
                    journal,
                    response_stop.reason,
                    response_stop.details,
                    observation.observation_id,
                )
            binding_stop = _binding_stop(proposal_response.observation, observation)
            if binding_stop.should_stop:
                return self._stop(journal, binding_stop.reason, binding_stop.details, observation.observation_id)
            candidates = proposal_response.candidates
        except ValidationError as exc:
            return self._stop(
                journal,
                _validation_stop_reason(exc),
                ["invalid list_action_candidates contract"],
                observation.observation_id,
            )
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
        recommendation = next(
            candidate for candidate in candidates if not self.stop_policy.recommendation_blockers(candidate)
        )
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

    async def _call_game(self, name: str, arguments: Mapping[str, Any]) -> ContractResponse:
        payload = await self._call(self.game_client, name, arguments)
        return validate_game_response(name, payload)

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
                game_session_id=_game_session_id(payload),
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
                metadata={"window_identity": _model_payload(observation.window_identity)},
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
        recommendation: ActionProposal,
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
        recommendation: ActionProposal | None = None,
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


def _capture_unhealthy(health: str) -> bool:
    return health == "not_configured"


def _binding_stop(
    bound_observation: LiveObservation | None,
    observation: LiveObservation,
) -> StopDecision:
    if bound_observation is None:
        return StopDecision(
            should_stop=True,
            reason=StopReason.CONTRACT_VIOLATION,
            details=["response is missing its bound observation"],
        )
    expected = {
        "session_id": observation.session_id,
        "observation_id": observation.observation_id,
        "frame_sha256": observation.frame_sha256,
    }
    mismatches = [
        f"{key}={getattr(bound_observation, key)!r} expected {value!r}"
        for key, value in expected.items()
        if getattr(bound_observation, key) != value
    ]
    if mismatches:
        return StopDecision(
            should_stop=True,
            reason=StopReason.CONTRACT_VIOLATION,
            details=mismatches,
        )
    return StopDecision()


def _candidate_evidence_refs(candidate: ActionProposal) -> list[str]:
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


def _response_stop(response: ContractResponse, tool_name: str) -> StopDecision:
    if response.status == "ok":
        return StopDecision()
    code = response.error.code if response.error is not None else response.status
    return StopDecision(
        should_stop=True,
        reason=StopReason.TOOL_FAILURE,
        details=[f"{tool_name}:{code}"],
    )


def _validation_stop_reason(exc: ValidationError) -> StopReason:
    if "execution_authority" in str(exc):
        return StopReason.EXECUTION_AUTHORITY_VIOLATION
    return StopReason.CONTRACT_VIOLATION


def _model_payload(value: BaseModel | None) -> dict[str, Any] | None:
    return value.model_dump(mode="json") if value is not None else None


def _game_session_id(payload: Mapping[str, Any]) -> str | None:
    session = payload.get("session")
    if isinstance(session, Mapping):
        value = _optional_string(session.get("session_id"))
        if value is not None:
            return value
    for key in ("observation", "latest_observation"):
        observation = payload.get(key)
        if isinstance(observation, Mapping):
            value = _optional_string(observation.get("session_id"))
            if value is not None:
                return value
    return None
