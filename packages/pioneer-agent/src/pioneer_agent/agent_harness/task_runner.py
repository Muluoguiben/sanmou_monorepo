"""Bounded read-only task lifecycle over the existing decision window."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import datetime
from threading import RLock
from typing import Any

from pydantic import ValidationError

from pioneer_agent.agent_harness.contracts import structured_content, validate_game_response
from pioneer_agent.agent_harness.loop import RecommendationHarness, DecisionWindowStatus
from pioneer_agent.agent_harness.run_store import (
    CheckpointConflict, RunOwnership, RunStore, _checkpoint_cleanup, _close_preserving_primary,
)
from pioneer_agent.agent_harness.task_approval import check_response, request_approval, task_digest
from pioneer_agent.agent_harness.task_contracts import (
    BudgetExceeded, BudgetRequest, ContextBuilder, ContextOverflow, ContextRequest,
    DecisionPolicy, PolicyContext, PolicyDecision, RunBudget, RunState, RunTrace, TaskSpec,
    TERMINAL_STATUSES, TraceEvent, Usage, SyntheticApprovalRecord, SyntheticApprovalResponse,
    SyntheticApprovalRunState, parse_run_state,
)
from pioneer_agent.agent_harness.task_trace import CausalTraceProducer
from pioneer_agent.mcp_server.contracts import (
    GET_RUNTIME_STATE_TOOL, OBSERVE_GAME_TOOL, SESSION_STATUS_TOOL,
    LiveObservation, ObserveGameResponse, RuntimeStateResponse, SessionStatusResponse,
)
from pioneer_agent.runbook.models import ConditionStatus, evaluate_all, evaluate_any


_CLIENT_BINDING_LOCK = RLock()


class _Interrupt(BaseException):
    def __init__(self, status: str, reason: str):
        self.status, self.reason = status, reason


class TaskRunner:
    """Own one checkpoint through run/pause/cancel; no device lease or effect ledger.

    Construction acquires ownership. Call close() if never running the instance.
    Reuse reacquires and reloads; caller-owned MCP lifetime is not managed here.
    """

    def __init__(self, *, task: TaskSpec, run_id: str, harness: RecommendationHarness,
                 store: RunStore, policy: DecisionPolicy, context_builder: ContextBuilder,
                 budget: RunBudget, trace: RunTrace, ownership: RunOwnership | None = None,
                 synthetic_approval: bool = False, causal_trace: bool = False):
        if harness.qa_client is not None:
            raise ValueError("task v1 uses Game-only windows; legacy QA windows are separate")
        with _CLIENT_BINDING_LOCK:
            if isinstance(harness.game_client, _TaskClient):
                raise CheckpointConflict("harness already bound to a runner")
            self._client = harness.game_client
        self.harness, self.store, self.policy = harness, store, policy
        self.context_builder, self.budget, self.trace = context_builder, budget, trace
        self._synthetic_approval = synthetic_approval is True
        self._causal_enabled = causal_trace is True
        self._causal = None
        self._task, self._run_id = task.model_copy(deep=True), run_id
        self._external_owner = ownership is not None
        self._ownership = ownership or store.acquire()
        self._checkpoint_failed = False
        self._checkpoint_error: BaseException | None = None
        self._budget_checkpoint = None
        try:
            if self._ownership.store is not store:
                raise CheckpointConflict("foreign checkpoint owner")
            self._ownership.bind_runner(self)
            self._reload()
        except BaseException as primary:
            _close_preserving_primary(self.close, primary)
            raise
        self._cancelled = False
        self._paused = False
        self._active = False
        self._wake = asyncio.Event()
        self._responses: dict[str, Any] = {}
        self._current_step_id = f"{run_id}:{self.state.completed_steps + 1}"
        self._task_client = _TaskClient(self)
        try:
            self._install_client()
        except BaseException as primary:
            _close_preserving_primary(self.close, primary)
            raise

    def _check_client_binding(self):
        with _CLIENT_BINDING_LOCK:
            if self.harness.game_client is not self._client and self.harness.game_client is not self._task_client:
                raise CheckpointConflict("harness client belongs to another lifetime")

    def _install_client(self, *, activate=False):
        with _CLIENT_BINDING_LOCK:
            if activate and self._active:
                raise RuntimeError("runner already active")
            self._check_client_binding()
            self.harness.game_client = self._task_client
            if activate:
                self._active = True

    def _reload(self):
        saved = self._ownership.load()
        if saved and (saved.run_id != self._run_id or saved.task != self._task):
            raise ValueError("checkpoint identity/task mismatch")
        self.state = saved or RunState(run_id=self._run_id, task=self._task.model_copy(deep=True))
        if isinstance(self.state, SyntheticApprovalRunState):
            if self.state.approval.request.task_digest != task_digest(self.state.task):
                raise ValueError("approval task digest mismatch")
        if saved and saved.budget_state:
            if self._budget_checkpoint is None:
                self.budget.restore(saved.budget_state)
            elif saved.budget_state != self._budget_checkpoint and saved.status not in TERMINAL_STATUSES:
                # Budget ports deliberately cannot restore over a spent ledger.
                # Another owner progressed: require a fresh runner/ledger, never
                # silently reuse the old counters or grant a fresh deadline.
                raise CheckpointConflict("checkpoint advanced; construct a fresh runner and budget")
            self._budget_checkpoint = saved.budget_state.copy()

    def close(self):
        with _CLIENT_BINDING_LOCK:
            if getattr(self, "_active", False):
                raise RuntimeError("cannot close an active runner; cancel and await it")
            wrapper = getattr(self, "_task_client", None)
            if wrapper is not None and self.harness.game_client is wrapper:
                self.harness.game_client = self._client
            if not self._external_owner:
                self._ownership.close()

    def _ensure_ownership(self):
        if self._checkpoint_failed:
            raise CheckpointConflict("runner checkpoint failed; construct a new runner")
        if not self._ownership.active and not self._external_owner:
            self._ownership = self.store.acquire()
            try:
                self._ownership.bind_runner(self)
                self._reload()
            except BaseException as primary:
                _close_preserving_primary(self.close, primary)
                raise
        self._ownership.check()

    @property
    def step_id(self) -> str:
        return self._current_step_id

    def cancel(self) -> None:
        if self._causal_enabled:
            return self._causal_control("cancel")
        if not self._active:
            self._ensure_ownership()
        if self.state.status not in TERMINAL_STATUSES:
            self._cancelled = True
            self.budget.cancel()
            self._wake.set()
            if not self._active:
                with _checkpoint_cleanup(self.close):
                    self._finish("cancelled", "cancel_requested")
        elif not self._active:
            self.close()

    def pause(self) -> None:
        if self._causal_enabled:
            return self._causal_control("pause")
        if not self._active:
            self._ensure_ownership()
        if self.state.status not in TERMINAL_STATUSES:
            if self.state.status in {"awaiting_approval", "revalidating_approval"}:
                if not self._active:
                    self.close()
                return  # An ordinary pause must not erase the approval gate.
            self._paused = True
            self._wake.set()
            if not self._active:
                with _checkpoint_cleanup(self.close):
                    self._finish("paused", "pause_requested")
        elif not self._active:
            self.close()

    def _check(self) -> None:
        if self._checkpoint_failed:
            if self._checkpoint_error is not None:
                raise self._checkpoint_error
            raise CheckpointConflict("runner checkpoint failed")
        try:
            self._ownership.check()
        except CheckpointConflict as exc:
            self._checkpoint_failed = True
            self._checkpoint_error = exc
            raise
        if self._cancelled:
            raise _Interrupt("cancelled", "cancel_requested")
        if self._paused:
            raise _Interrupt("paused", "pause_requested")
        if self.budget.remaining_seconds() <= 0:
            raise _Interrupt("failed", "run_deadline")

    def _timeout_interrupt(self) -> _Interrupt:
        # Cancellation makes a real budget's remaining time zero. It must not
        # be reclassified as deadline failure if it races with an awaited call.
        if self._cancelled:
            return _Interrupt("cancelled", "cancel_requested")
        if self._paused:
            return _Interrupt("paused", "pause_requested")
        return _Interrupt("failed", "run_deadline")

    def _save(self) -> None:
        if self._checkpoint_failed:
            if self._checkpoint_error is not None:
                raise self._checkpoint_error
            raise CheckpointConflict("checkpoint persistence already failed")
        self.state.budget_state = self.budget.snapshot()
        try:
            self._ownership.save(self.state)
            self._budget_checkpoint = self.state.model_copy(deep=True).budget_state
        except BaseException as exc:
            self._checkpoint_failed = True
            self._checkpoint_error = exc
            raise

    def _emit(self, event: str, **kwargs) -> None:
        record = TraceEvent(run_id=self.state.run_id, step_id=self.step_id, event=event, **kwargs)
        if self._causal is not None:
            self._causal.emit(record, advance=False)
        else:
            self.trace.emit(record)

    @contextmanager
    def _trace_window(self):
        if self._causal is None:
            yield
            return
        self._causal.start_window()
        primary = None
        try:
            yield
        except BaseException as error:
            primary = error
            raise
        finally:
            self._causal.outcome(primary=primary)
            if primary is None:
                self._causal.check(exit=True)

    def _causal_control(self, name):
        idle = not self._active
        if idle:
            self._ensure_ownership()
            self._causal = CausalTraceProducer(self)
            self._causal.start(name)
        primary = None
        try:
            self._causal.control(name)
            if self.state.status not in TERMINAL_STATUSES:
                ignored = name == "pause" and self.state.status in {"awaiting_approval", "revalidating_approval"}
                if not ignored:
                    if name == "cancel":
                        self._cancelled = True
                        self.budget.cancel()
                    else:
                        self._paused = True
                    self._wake.set()
                    if idle:
                        self._finish("cancelled" if name == "cancel" else "paused", name + "_requested")
        except BaseException as error:
            primary = error
            self._causal.remember(error)
            raise
        finally:
            if idle:
                try:
                    _close_preserving_primary(self.close, primary)
                except BaseException as error:
                    primary = error
                    raise
                finally:
                    self._causal.outcome(primary=primary, end=True)
                    if primary is None:
                        self._causal.check(exit=True)

    def _finish(self, status: str, reason: str, *, primary=None) -> RunState:
        self.state.status = status
        self.state.reason = reason
        self.state.pending_call = None
        self._save()
        if self._causal is not None:
            self._causal.remember(primary)
        if self._causal is not None and status == "failed":
            self._causal.failed_business(reason)
        metadata = {"reason": reason}
        if isinstance(self.state, SyntheticApprovalRunState):
            metadata.update(request_id=self.state.approval.request.request_id,
                            approval_origin="synthetic", scope="resume_read_only_task")
        self._emit("lifecycle", business=status, metadata=metadata)
        return self.state.model_copy(deep=True)

    async def run(self, *, resume: bool = False) -> RunState:
        return await self._run_entry(resume=resume)

    async def resume_synthetic(self, response: SyntheticApprovalResponse) -> RunState:
        """Consume only a synthetic read-only response; there is no dispatch port."""
        if not self._synthetic_approval:
            raise ValueError("synthetic approval is not enabled")
        response = SyntheticApprovalResponse.model_validate(response.model_dump())
        return await self._run_entry(resume=True, response=response)

    async def _run_entry(self, *, resume=False, response=None) -> RunState:
        if self._causal_enabled:
            return await self._run_causal_entry(resume=resume, response=response)
        if self._active:
            raise RuntimeError("runner already active")
        with _checkpoint_cleanup(self.close):
            self._check_client_binding()
            self._ensure_ownership()
            self._install_client(activate=True)
            try:
                return await self._run_owned(resume=resume, response=response)
            finally:
                with _CLIENT_BINDING_LOCK:
                    self._active = False

    async def _run_causal_entry(self, *, resume=False, response=None):
        if self._active:
            raise RuntimeError("runner already active")
        producer = None
        primary = None
        try:
            with _checkpoint_cleanup(self.close):
                self._check_client_binding()
                self._ensure_ownership()
                producer = self._causal = CausalTraceProducer(self)
                self._install_client(activate=True)
                try:
                    producer.start("resume_synthetic" if response is not None else "resume" if resume else "run")
                    result = await self._run_owned(resume=resume, response=response)
                    producer.check(exit=True)
                    return result
                finally:
                    with _CLIENT_BINDING_LOCK:
                        self._active = False
        except BaseException as error:
            primary = error
            if producer is not None:
                producer.remember(error)
            raise
        finally:
            if producer is not None:
                producer.outcome(primary=primary, end=True)
                if primary is None:
                    producer.check(exit=True)

    async def _run_owned(self, *, resume: bool = False, response=None) -> RunState:
        if response is not None and self.state.status != "awaiting_approval":
            raise ValueError("approval is not awaiting a response")
        if self.state.status in TERMINAL_STATUSES:
            return self.state.model_copy(deep=True)
        if self.state.status == "paused" and not resume:
            return self.state.model_copy(deep=True)
        if resume:
            self._paused = False
            self._wake.clear()
        try:
            self._check()
            if self.state.status == "revalidating_approval":
                return self._finish("failed", "approval_revalidation_interrupted")
            if self.state.status == "awaiting_approval":
                if self.state.completed_steps >= self.state.task.max_steps:
                    return self._finish("failed", "step_limit")
                request = self.state.approval.request
                now = self.harness.clock()
                if now.tzinfo is None or now.utcoffset() is None:
                    return self._finish("failed", "approval_clock_invalid")
                if now < self.state.approval.last_checked_at:
                    return self._finish("failed", "approval_clock_rollback")
                if now >= request.expires_at:
                    return self._finish("failed", "approval_expired")
                if response is None:
                    if now > self.state.approval.last_checked_at:
                        self.state.approval.last_checked_at = now
                        self._save()  # Remember observed waiting time across owners/restarts.
                    return self.state.model_copy(deep=True)
                rejection = check_response(request, response, task=self.state.task, now=now)
                if rejection:
                    return self._finish("failed", rejection)
                item = self.state.approval.model_dump()
                item.update(response=response.model_dump(), consumed_at=now, last_checked_at=now)
                denied = response.decision == "deny"
                self.state = parse_run_state({**self.state.model_dump(), "approval": item,
                    "status": "failed" if denied else "revalidating_approval",
                    "reason": "approval_denied" if denied else "approval_consumed"})
                self._save()  # Durable one-shot consumption before any follow-up call.
                self._emit("approval", business=self.state.reason,
                    metadata={"request_id": request.request_id, "approval_origin": "synthetic",
                              "scope": "resume_read_only_task"})
                if denied:
                    return self.state.model_copy(deep=True)
            else:
                self.state.status = "running"
            self.state.reason = "reobserve_before_decision"
            self.state.pending_call = None
            self._save()
            while self.state.completed_steps < self.state.task.max_steps:
                self._check()
                self._current_step_id = f"{self.state.run_id}:{self.state.completed_steps + 1}"
                with self._trace_window():
                    step_reservation = self.budget.reserve(BudgetRequest(
                        run_id=self.state.run_id, step_id=self.step_id, kind="step", name="decision_window"))
                    try:
                        self._save()
                        result = await self._step()
                    finally:
                        if not self._checkpoint_failed:
                            self.budget.settle(step_reservation, Usage(), outcome=self.state.status)
                            self._save()
                if result is not None:
                    return self.state.model_copy(deep=True)
                if self.state.task.wait_seconds:
                    self.state.status = "waiting"
                    self.state.reason = "await_next_observation"
                    self._save()
                    self._emit("lifecycle", business="waiting")
                    try:
                        await asyncio.wait_for(self._wake.wait(), timeout=min(
                            self.state.task.wait_seconds, self.budget.remaining_seconds()))
                    except TimeoutError:
                        pass
                    self._check()
                    self.state.status = "running"
            return self._finish("failed", "step_limit")
        except CheckpointConflict:
            raise
        except _Interrupt as exc:
            return self._finish(exc.status, exc.reason, primary=exc)
        except BudgetExceeded as exc:
            return self._finish("failed", "budget_exhausted", primary=exc)
        except ContextOverflow as exc:
            return self._finish("failed", "context_overflow", primary=exc)
        except asyncio.CancelledError as exc:
            self.budget.cancel()
            self._finish("cancelled", "async_cancelled", primary=exc)
            raise
        except TimeoutError as exc:
            interruption = self._timeout_interrupt()
            return self._finish(interruption.status, interruption.reason, primary=exc)
        except Exception as exc:
            if self._checkpoint_failed or (self._causal is not None and exc is self._causal.failure):
                raise
            # Store only class, never exception text that may contain provider data.
            return self._finish("failed", f"runtime_error:{type(exc).__name__}", primary=exc)

    async def _step(self) -> RunState | None:
        self._responses.clear()
        result = await self.harness.run_decision_window()
        self._check()
        if self._causal is not None:
            self._causal.check(exit=True)  # A wrapped trace failure is not a genuine tool failure.
        if result.status != DecisionWindowStatus.RECOMMENDED:
            return self._finish("failed", result.stop.reason.value if result.stop.reason else "window_stopped")
        response = self._responses.get(GET_RUNTIME_STATE_TOOL)
        if not isinstance(response, RuntimeStateResponse) or response.observation is None:
            return self._finish("failed", "missing_state_evidence")
        observation = response.observation
        current = response.runtime_state or {}
        refs = [f"observation:{observation.observation_id}", f"frame_sha256:{observation.frame_sha256}"]
        self.state.observation_ids.append(observation.observation_id)
        self.state.session_id = observation.session_id
        self.state.window_identity = observation.window_identity.model_dump() if observation.window_identity else None
        self.state.last_captured_at = observation.captured_at
        self.state.evidence_refs = refs
        approval_revalidation = self.state.status == "revalidating_approval"
        self._save()
        if self._causal is not None:
            self._causal.emit(self._causal.event("observation", observation_id=observation.observation_id,
                evidence_refs=refs, business="observation_guarded"))
        if approval_revalidation:
            self._check_approval_observation(observation)
            task = self.state.task
            if task.stop_when and evaluate_any(task.stop_when, current).status != ConditionStatus.NOT_SATISFIED:
                return self._finish("failed", "approval_stop_condition")
            if not self._goal_evidence(current, observation):
                return self._finish("failed", "approval_insufficient_evidence")
            item = self.state.approval.model_dump()
            item["revalidated_observation_id"] = observation.observation_id
            self.state = parse_run_state({**self.state.model_dump(), "status": "running", "approval": item,
                                         "reason": "approval_revalidated"})
            self._save()
            self._emit("approval", business="approval_revalidated", observation_id=observation.observation_id,
                evidence_refs=refs, metadata={"request_id": self.state.approval.request.request_id,
                                             "approval_origin": "synthetic"})
            self._check_approval_observation(observation)
            if evaluate_all(task.success_when, current).status == ConditionStatus.SATISFIED:
                self.state.completed_steps += 1
                return self._finish("succeeded", "goal_verified")
        request = ContextRequest(run_id=self.state.run_id, step_id=self.step_id,
            task=self.state.task.model_copy(deep=True), observation_id=observation.observation_id,
            authoritative_state=current, evidence_refs=refs)
        context = self.context_builder.build(request.model_copy(deep=True))
        if (context.run_id, context.step_id, context.observation_id) != (
                self.state.run_id, self.step_id, observation.observation_id):
            return self._finish("failed", "context_binding_mismatch")
        self._check()
        reservation = None
        invocation_id = provenance = None
        if self.policy.uses_model:
            reservation = self.budget.reserve(BudgetRequest(run_id=self.state.run_id,
                step_id=self.step_id, kind="model", name=self.policy.policy_id,
                input_tokens=context.estimated_input_tokens, output_tokens=context.reserved_output_tokens))
        self.state.pending_call = f"policy:{self.policy.policy_id}"
        outcome = "error"
        policy_error = None
        policy_primary = None
        transport = "not_attempted"
        contract = "not_checked"
        try:
            self._save()
            if approval_revalidation:
                self._check_approval_observation(observation)
            else:
                self._check()
            if self._causal is not None:
                context = PolicyContext.model_validate(context.model_dump(mode="json"))
                if (context.run_id, context.step_id, context.observation_id) != (
                        self.state.run_id, self.step_id, observation.observation_id):
                    return self._finish("failed", "context_binding_mismatch")
                invocation_id, provenance = self._causal.invocation(context)
            transport = "error"  # Attempted, but no returned response yet.
            raw = await asyncio.wait_for(self.policy.decide(context), self.budget.remaining_seconds())
            transport = "ok"
            contract = "error"  # A returned value exists; validation may fail.
            decision = PolicyDecision.model_validate(raw.model_dump() if isinstance(raw, PolicyDecision) else raw)
            contract = "ok"
            outcome = decision.action
        except _Interrupt as exc:
            policy_primary = exc
            outcome = exc.reason
            raise
        except asyncio.CancelledError as exc:
            policy_primary = exc
            transport = "cancelled"
            policy_error = "CancelledError"
            raise
        except BaseException as exc:
            policy_primary = exc
            policy_error = type(exc).__name__
            raise
        finally:
            if not self._checkpoint_failed:
                if reservation is not None:
                    self.budget.settle(reservation, Usage(), outcome=outcome)
                self.state.pending_call = None
                self._save()
                policy_identity = provenance.policy_id if provenance is not None else self.policy.policy_id
                values = dict(name=policy_identity, attempt_id=reservation,
                    observation_id=observation.observation_id, evidence_refs=refs,
                    transport=transport, contract=contract, business=outcome,
                    error_type=policy_error, usage=Usage() if reservation else None,
                    metadata={"policy_id": policy_identity, "task_version": 1})
                if self._causal is not None:
                    if invocation_id is None:
                        values.update(transport="not_attempted", contract="not_checked")
                    self._causal.emit(self._causal.event("policy", **values), primary=policy_primary,
                        invocation_id=invocation_id, provenance=provenance)
                else:
                    self._emit("policy", **values)
        if self._causal is not None:
            self._causal.check(exit=True)
        if approval_revalidation:
            self._check_approval_observation(observation)
        else:
            self._check()
            stale = self.harness.stop_policy.observation_stop(captured_at=observation.captured_at,
                now=self.harness.clock(), unknown_domains=observation.unknown_domains)
            if stale.should_stop:
                return self._finish("failed", stale.reason.value)
        # Policy cannot change the goal, and all condition evaluation uses the
        # original validated state, never the context projection or history.
        task = self.state.task
        self.state.completed_steps += 1
        if evaluate_any(task.stop_when, current).status == ConditionStatus.SATISFIED:
            return self._finish("failed", "stop_condition")
        sufficient = self._goal_evidence(current, observation)
        reached = sufficient and evaluate_all(task.success_when, current).status == ConditionStatus.SATISFIED
        if decision.action == "stop":
            return self._finish("failed", "policy_stop")
        if decision.action == "pause":
            return self._finish("paused", "policy_pause")
        if decision.action == "request_approval":
            if not self._synthetic_approval:
                return self._finish("failed", "synthetic_approval_disabled")
            if not sufficient:
                return self._finish("failed", "approval_insufficient_evidence")
            request = request_approval(self.state, step_id=self.step_id,
                frame_sha256=observation.frame_sha256, now=self.harness.clock(),
                remaining_seconds=self.budget.remaining_seconds(), reason=decision.reason)
            self.state = SyntheticApprovalRunState.model_validate({**self.state.model_dump(),
                "version": 2, "status": "awaiting_approval", "reason": "policy_request_approval",
                "approval": SyntheticApprovalRecord(request=request, last_checked_at=request.created_at).model_dump()})
            self._save()
            self._emit("approval", business="awaiting_approval", observation_id=observation.observation_id,
                evidence_refs=refs, metadata={"request_id": request.request_id,
                    "approval_origin": "synthetic", "scope": "resume_read_only_task"})
            return self.state.model_copy(deep=True)
        if reached:
            return self._finish("succeeded", "goal_verified")
        if decision.action == "succeed":
            return self._finish("failed", "unverified_success_proposal")
        self.state.reason = "goal_not_reached" if sufficient else "insufficient_goal_evidence"
        if decision.action == "wait":
            self.state.status = "waiting"
            self._emit("lifecycle", business="waiting", metadata={"reason": self.state.reason})
        self._save()
        return None

    def _check_approval_observation(self, observation: LiveObservation) -> None:
        """Persistence/context work can spend the deadline or age the fresh frame."""
        # At most one watermark write per boundary; recheck that write as well.
        # A later post-write sample stays in memory until the next owned save.
        for persist in (True, False):
            self._check()
            now = self.harness.clock()
            item = self.state.approval
            if now.tzinfo is None or now.utcoffset() is None:
                raise _Interrupt("failed", "approval_clock_invalid")
            if now < item.last_checked_at:
                raise _Interrupt("failed", "approval_clock_rollback")
            stale = self.harness.stop_policy.observation_stop(captured_at=observation.captured_at,
                now=now, unknown_domains=observation.unknown_domains)
            if stale.should_stop:
                raise _Interrupt("failed", stale.reason.value)
            advanced = now > item.last_checked_at
            item.last_checked_at = now
            if not persist or not advanced:
                return
            self._save()

    def _goal_evidence(self, current: dict, observation: LiveObservation) -> bool:
        task = self.state.task
        if not set(task.required_domains).issubset(observation.domains_run):
            return False
        metadata = current.get("field_meta", {})
        for condition in task.success_when:
            meta = metadata.get(condition.metric, {})
            if meta.get("observation_id") != observation.observation_id:
                return False
            if meta.get("confidence", 1) <= 0:
                return False
            if not str(meta.get("source", "")).startswith("vision."):
                return False
            domain = meta["source"].split(".", 1)[1]
            if domain not in observation.domains_run:
                return False
            try:
                if datetime.fromisoformat(meta.get("updated_at", "")) != observation.captured_at:
                    return False
            except (TypeError, ValueError):
                return False
        return bool(observation.structured_evidence)


class _TaskClient:
    def __init__(self, runner: TaskRunner):
        self.runner = runner

    async def call_tool(self, name, arguments):
        r = self.runner
        r._check()
        if r._causal is not None:
            r._causal.check()
        if name not in r.state.task.allowed_tools:
            raise _Interrupt("failed", "tool_not_allowed")
        try:
            reservation = r.budget.reserve(BudgetRequest(run_id=r.state.run_id,
                step_id=r.step_id, kind="tool", name=name))
        except BudgetExceeded:
            raise _Interrupt("failed", "budget_exhausted") from None
        event = TraceEvent(run_id=r.state.run_id, step_id=r.step_id, event="tool",
                           name=name, attempt_id=reservation)
        r.state.pending_call = name
        invocation_id = provenance = None
        primary = None
        try:
            r._save()
            r._check()
            if r._causal is not None:
                invocation_id, provenance = r._causal.invocation()
            raw = await asyncio.wait_for(r._client.call_tool(name, arguments), r.budget.remaining_seconds())
            event.transport = "ok"
            response = validate_game_response(name, structured_content(raw))
            event.contract = "ok"
            event.business = response.status
            r._check()
            if isinstance(response, SessionStatusResponse) and response.session:
                if not response.session.active or not response.session.observe_only:
                    raise _Interrupt("failed", "session_permission_violation")
                if r.state.session_id and response.session.session_id != r.state.session_id:
                    raise _Interrupt("failed", "session_identity_changed")
            if isinstance(response, ObserveGameResponse) and response.observation:
                obs = response.observation
                event.observation_id = obs.observation_id
                event.evidence_refs = [f"frame_sha256:{obs.frame_sha256}"]
                if obs.observation_id in r.state.observation_ids:
                    raise _Interrupt("failed", "reused_observation")
                if r.state.last_captured_at and obs.captured_at <= r.state.last_captured_at:
                    raise _Interrupt("failed", "nonincreasing_capture_time")
                if r.state.session_id and obs.session_id != r.state.session_id:
                    raise _Interrupt("failed", "session_identity_changed")
                identity = obs.window_identity.model_dump() if obs.window_identity else None
                if r.state.observation_ids and identity != r.state.window_identity:
                    raise _Interrupt("failed", "window_identity_changed")
            r._responses[name] = response
            return raw
        except ValidationError as exc:
            primary = exc
            event.contract = "error"
            event.error_type = type(exc).__name__
            raise
        except asyncio.CancelledError as exc:
            primary = exc
            event.transport = "cancelled"
            event.error_type = "CancelledError"
            raise
        except TimeoutError:
            event.transport = "error"
            event.error_type = "TimeoutError"
            interruption = r._timeout_interrupt()
            primary = interruption
            event.business = interruption.reason
            raise interruption from None
        except _Interrupt as exc:
            primary = exc
            event.business = exc.reason
            raise
        except BaseException as exc:
            primary = exc
            if event.transport != "ok":
                event.transport = "error"
            event.error_type = type(exc).__name__
            raise
        finally:
            if not r._checkpoint_failed:
                r.budget.settle(reservation, Usage(), outcome=event.business or event.error_type or "error")
                r.state.pending_call = None
                r._save()
                if r._causal is not None:
                    if invocation_id is None:
                        event.transport, event.contract = "not_attempted", "not_checked"
                    r._causal.emit(event, primary=primary, invocation_id=invocation_id, provenance=provenance)
                else:
                    r.trace.emit(event)
