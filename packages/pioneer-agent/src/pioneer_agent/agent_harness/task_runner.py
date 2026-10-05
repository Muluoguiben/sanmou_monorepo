"""Bounded read-only task lifecycle over the existing decision window."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from pioneer_agent.agent_harness.contracts import structured_content, validate_game_response
from pioneer_agent.agent_harness.loop import RecommendationHarness, DecisionWindowStatus
from pioneer_agent.agent_harness.run_store import CheckpointConflict, RunOwnership, RunStore
from pioneer_agent.agent_harness.task_contracts import (
    BudgetExceeded, BudgetRequest, ContextBuilder, ContextOverflow, ContextRequest,
    DecisionPolicy, PolicyDecision, RunBudget, RunState, RunTrace, TaskSpec,
    TERMINAL_STATUSES, TraceEvent, Usage,
)
from pioneer_agent.mcp_server.contracts import (
    GET_RUNTIME_STATE_TOOL, OBSERVE_GAME_TOOL, SESSION_STATUS_TOOL,
    LiveObservation, ObserveGameResponse, RuntimeStateResponse, SessionStatusResponse,
)
from pioneer_agent.runbook.models import ConditionStatus, evaluate_all, evaluate_any


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
                 budget: RunBudget, trace: RunTrace, ownership: RunOwnership | None = None):
        if harness.qa_client is not None:
            raise ValueError("task v1 uses Game-only windows; legacy QA windows are separate")
        self.harness, self.store, self.policy = harness, store, policy
        self.context_builder, self.budget, self.trace = context_builder, budget, trace
        self._task, self._run_id = task.model_copy(deep=True), run_id
        self._external_owner = ownership is not None
        self._ownership = ownership or store.acquire()
        self._checkpoint_failed = False
        self._budget_checkpoint = None
        try:
            if self._ownership.store is not store:
                raise CheckpointConflict("foreign checkpoint owner")
            self._ownership.bind_runner(self)
            self._reload()
        except BaseException:
            self.close()
            raise
        self._cancelled = False
        self._paused = False
        self._active = False
        self._wake = asyncio.Event()
        self._responses: dict[str, Any] = {}
        self._current_step_id = f"{run_id}:{self.state.completed_steps + 1}"
        self._client = harness.game_client
        harness.game_client = _TaskClient(self)

    def _reload(self):
        saved = self._ownership.load()
        if saved and (saved.run_id != self._run_id or saved.task != self._task):
            raise ValueError("checkpoint identity/task mismatch")
        self.state = saved or RunState(run_id=self._run_id, task=self._task.model_copy(deep=True))
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
        if getattr(self, "_active", False):
            raise RuntimeError("cannot close an active runner; cancel and await it")
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
            except BaseException:
                self.close()
                raise
        self._ownership.check()

    @property
    def step_id(self) -> str:
        return self._current_step_id

    def cancel(self) -> None:
        if not self._active:
            self._ensure_ownership()
        if self.state.status not in TERMINAL_STATUSES:
            self._cancelled = True
            self.budget.cancel()
            self._wake.set()
            if not self._active:
                try:
                    self._finish("cancelled", "cancel_requested")
                finally:
                    self.close()
        elif not self._active:
            self.close()

    def pause(self) -> None:
        if not self._active:
            self._ensure_ownership()
        if self.state.status not in TERMINAL_STATUSES:
            self._paused = True
            self._wake.set()
            if not self._active:
                try:
                    self._finish("paused", "pause_requested")
                finally:
                    self.close()
        elif not self._active:
            self.close()

    def _check(self) -> None:
        if self._checkpoint_failed:
            raise CheckpointConflict("runner checkpoint failed")
        try:
            self._ownership.check()
        except CheckpointConflict:
            self._checkpoint_failed = True
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
            raise CheckpointConflict("checkpoint persistence already failed")
        self.state.budget_state = self.budget.snapshot()
        try:
            self._ownership.save(self.state)
            self._budget_checkpoint = self.state.model_copy(deep=True).budget_state
        except BaseException:
            self._checkpoint_failed = True
            raise

    def _emit(self, event: str, **kwargs) -> None:
        self.trace.emit(TraceEvent(run_id=self.state.run_id, step_id=self.step_id,
                                   event=event, **kwargs))

    def _finish(self, status: str, reason: str) -> RunState:
        self.state.status = status
        self.state.reason = reason
        self.state.pending_call = None
        self._save()
        self._emit("lifecycle", business=status, metadata={"reason": reason})
        return self.state.model_copy(deep=True)

    async def run(self, *, resume: bool = False) -> RunState:
        if self._active:
            raise RuntimeError("runner already active")
        self._ensure_ownership()
        try:
            return await self._run_owned(resume=resume)
        finally:
            self.close()

    async def _run_owned(self, *, resume: bool = False) -> RunState:
        if self.state.status in TERMINAL_STATUSES:
            return self.state.model_copy(deep=True)
        if self.state.status == "paused" and not resume:
            return self.state.model_copy(deep=True)
        self._active = True
        if resume:
            self._paused = False
            self._wake.clear()
        try:
            self._check()
            self.state.status = "running"
            self.state.reason = "reobserve_before_decision"
            self.state.pending_call = None
            self._save()
            while self.state.completed_steps < self.state.task.max_steps:
                self._check()
                self._current_step_id = f"{self.state.run_id}:{self.state.completed_steps + 1}"
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
            return self._finish(exc.status, exc.reason)
        except BudgetExceeded:
            return self._finish("failed", "budget_exhausted")
        except ContextOverflow:
            return self._finish("failed", "context_overflow")
        except asyncio.CancelledError:
            self.budget.cancel()
            self._finish("cancelled", "async_cancelled")
            raise
        except TimeoutError:
            interruption = self._timeout_interrupt()
            return self._finish(interruption.status, interruption.reason)
        except Exception as exc:
            if self._checkpoint_failed:
                raise
            # Store only class, never exception text that may contain provider data.
            return self._finish("failed", f"runtime_error:{type(exc).__name__}")
        finally:
            self._active = False

    async def _step(self) -> RunState | None:
        self._responses.clear()
        result = await self.harness.run_decision_window()
        self._check()
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
        self._save()
        request = ContextRequest(run_id=self.state.run_id, step_id=self.step_id,
            task=self.state.task.model_copy(deep=True), observation_id=observation.observation_id,
            authoritative_state=current, evidence_refs=refs)
        context = self.context_builder.build(request.model_copy(deep=True))
        if (context.run_id, context.step_id, context.observation_id) != (
                self.state.run_id, self.step_id, observation.observation_id):
            return self._finish("failed", "context_binding_mismatch")
        self._check()
        reservation = None
        if self.policy.uses_model:
            reservation = self.budget.reserve(BudgetRequest(run_id=self.state.run_id,
                step_id=self.step_id, kind="model", name=self.policy.policy_id,
                input_tokens=context.estimated_input_tokens, output_tokens=context.reserved_output_tokens))
        self.state.pending_call = f"policy:{self.policy.policy_id}"
        outcome = "error"
        policy_error = None
        transport = "not_attempted"
        contract = "not_checked"
        try:
            self._save()
            self._check()
            transport = "error"  # Attempted, but no returned response yet.
            raw = await asyncio.wait_for(self.policy.decide(context), self.budget.remaining_seconds())
            transport = "ok"
            contract = "error"  # A returned value exists; validation may fail.
            decision = PolicyDecision.model_validate(raw.model_dump() if isinstance(raw, PolicyDecision) else raw)
            contract = "ok"
            outcome = decision.action
        except _Interrupt as exc:
            outcome = exc.reason
            raise
        except asyncio.CancelledError:
            transport = "cancelled"
            policy_error = "CancelledError"
            raise
        except BaseException as exc:
            policy_error = type(exc).__name__
            raise
        finally:
            if not self._checkpoint_failed:
                if reservation is not None:
                    self.budget.settle(reservation, Usage(), outcome=outcome)
                self.state.pending_call = None
                self._save()
                self._emit("policy", name=self.policy.policy_id, attempt_id=reservation,
                    observation_id=observation.observation_id, evidence_refs=refs,
                    transport=transport, contract=contract, business=outcome,
                    error_type=policy_error, usage=Usage() if reservation else None,
                    metadata={"policy_id": self.policy.policy_id, "task_version": 1})
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
        try:
            r._save()
            r._check()
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
            event.contract = "error"
            event.error_type = type(exc).__name__
            raise
        except asyncio.CancelledError:
            event.transport = "cancelled"
            event.error_type = "CancelledError"
            raise
        except TimeoutError:
            event.transport = "error"
            event.error_type = "TimeoutError"
            interruption = r._timeout_interrupt()
            event.business = interruption.reason
            raise interruption from None
        except _Interrupt as exc:
            event.business = exc.reason
            raise
        except BaseException as exc:
            if event.transport != "ok":
                event.transport = "error"
            event.error_type = type(exc).__name__
            raise
        finally:
            if not r._checkpoint_failed:
                r.budget.settle(reservation, Usage(), outcome=event.business or event.error_type or "error")
                r.state.pending_call = None
                r._save()
                r.trace.emit(event)
