"""Autonomous decision loop: screenshot → vision → decide → act → repeat.

Glues together bridge_client (observe), VisionSync (extract), ActionSelector
(plan), and UIActionRunner (act). The loop is intentionally thin — all real
work lives in the components; this module just sequences them and handles
the wait/sleep cadence between ticks.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any, Protocol

from PIL import Image, UnidentifiedImageError

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import ExecutionResult, RuntimeState, SelectionResult
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.executor.ui_runner import UIActionRunner
from pioneer_agent.perception.vision_sync import VisionSync, VisionSyncSummary
from pioneer_agent.runbook.action_filter import RUNBOOK_FILTER_REJECT_REASON
from pioneer_agent.runbook.engine import RunbookEngine
from pioneer_agent.runbook.loader import metrics_from_runtime_state
from pioneer_agent.runbook.models import (
    EscalationKind,
    EscalationRoute,
    RunbookDecision,
    RunbookEscalation,
)
from pioneer_agent.runbook.state_store import RunbookStateStore
from pioneer_agent.runtime.dispatch_guard import (
    KILL_SWITCH_REASON,
    RUNBOOK_BLOCKING_HOLDS,
    DispatchGuard,
)
from pioneer_agent.runtime.loop_contract import LOOP_PHASE_ORDER, ensure_loop_contract
from pioneer_agent.safety.kill_switch import KillSwitch
from pioneer_agent.selector.action_selector import ActionSelector
from pioneer_agent.storage.loop_logger import LoopLogger
from pioneer_agent.storage.trace_store import (
    CoordinateTraceMetadata,
    ImageSize,
    NormalizedBBox,
    PixelBBox,
    PixelPoint,
    ScreenshotTraceMetadata,
    TickTrace,
    TracePhase,
    TraceStep,
    TraceStore,
)
from pioneer_agent.verifier.base import VerificationResult, VerificationStatus
from pioneer_agent.verifier.registry import VerifierRegistry, VerifierSpec

logger = logging.getLogger(__name__)


class _Screenshotter(Protocol):
    def screenshot(self, save_path=None) -> bytes: ...  # noqa: ANN001


@dataclass
class TickResult:
    iteration: int
    summary: VisionSyncSummary
    selection: SelectionResult
    execution: ExecutionResult | None
    sleep_s: float


WAIT_SLEEP_S = {
    ActionType.WAIT_FOR_STAMINA: 300.0,   # 5 min — stamina ticks every minute
    ActionType.WAIT_FOR_RESOURCE: 120.0,  # 2 min — resource accumulation
}
DEFAULT_SLEEP_S = 5.0                     # after an executed/pending action
IDLE_SLEEP_S = 30.0                       # nothing to do
STUCK_ESC_THRESHOLD = 3                   # consecutive unknown/idle ticks before recovery ESC


class AutonomousLoop:
    def __init__(
        self,
        bridge: _Screenshotter,
        vision_sync: VisionSync,
        ui_actions: UIActions,
        *,
        selector: ActionSelector | None = None,
        deriver: StateDeriver | None = None,
        runner: UIActionRunner | None = None,
        sleeper=time.sleep,
        loop_logger: LoopLogger | None = None,
        trace_store: TraceStore | None = None,
        kill_switch: KillSwitch | None = None,
        runbook_engine: RunbookEngine | None = None,
        runbook_state_store: RunbookStateStore | None = None,
        dry_run: bool = False,
        stuck_threshold: int = STUCK_ESC_THRESHOLD,
        post_action_verify_poll_interval_s: float = 1.0,
    ) -> None:
        self.bridge = bridge
        self.vision_sync = vision_sync
        self.ui_actions = ui_actions
        # The default selector honors runbook hints only when a runbook engine
        # drives this loop, so Advisor/replay chains sharing ActionSelector
        # stay immune to hints a persisted state may carry.
        self.selector = selector or ActionSelector(
            honor_runbook_hints=runbook_engine is not None
        )
        self.deriver = deriver or StateDeriver()
        self.runner = runner or UIActionRunner(ui_actions)
        self.sleeper = sleeper
        self.loop_logger = loop_logger
        self.trace_store = trace_store
        self._guard = DispatchGuard(kill_switch=kill_switch)
        self.runbook_engine = runbook_engine
        self.runbook_state_store = runbook_state_store
        self.dry_run = dry_run
        self.stuck_threshold = stuck_threshold
        self.post_action_verify_poll_interval_s = post_action_verify_poll_interval_s
        self._stuck_count = 0
        self._runbook_saved_signature: tuple[str, frozenset[str], bool] | None = None
        self._active_runbook_escalations: set[str] = set()
        self._runbook_filter_block_phase: str | None = None
        self._runbook_filter_block_count = 0
        self._warned_unknown_gates: set[str] = set()
        self.state = RuntimeState()

    @property
    def kill_switch(self) -> KillSwitch | None:
        return self._guard.kill_switch

    @kill_switch.setter
    def kill_switch(self, value: KillSwitch | None) -> None:
        # The guard owns the reference so a post-construction swap (tests,
        # runtime rewiring) is honored by every dispatch verdict.
        self._guard.kill_switch = value

    def tick(self, iteration: int) -> TickResult:
        started_at = datetime.now()
        t0 = time.monotonic()
        state_before = self.state.model_dump(mode="json")
        png = self.bridge.screenshot()
        logger.info("tick %d: captured %d bytes", iteration, len(png))

        self.state, vision_summary = self.vision_sync.sync(
            png, state=self.state, captured_at=started_at
        )
        logger.info("tick %d: page=%s domains=%s", iteration, vision_summary.page_type, vision_summary.domains_run)

        derived = self.deriver.derive(self.state)
        # Freeze the runbook while the kill switch is tripped: no cursor
        # advancement and no persistence may happen during an emergency stop.
        kill_switch_active = self._guard.kill_switch_active
        if kill_switch_active and self.runbook_engine is not None:
            logger.info("tick %d: kill switch active — runbook cursor frozen", iteration)
        runbook_decision = None if kill_switch_active else self._evaluate_runbook(iteration, derived)
        self._guard.update_decision(runbook_decision)
        selection = self.selector.select(derived)
        pre_action_state = self.state.model_dump(mode="json")

        execution: ExecutionResult | None = None
        post_action_verification: dict[str, Any] | None = None
        input_trace: list[dict] = []
        sleep_s = IDLE_SLEEP_S
        runbook_blocked = False
        dispatch_block_reason: str | None = None
        if selection.selected_action is not None:
            verdict = self._guard.action_verdict(selection.selected_action)
            if not verdict.allowed:
                dispatch_block_reason = verdict.reason
                runbook_blocked = verdict.reason != KILL_SWITCH_REASON
                logger.warning(
                    "tick %d: dispatch blocked action=%s (%s, phase=%s)",
                    iteration,
                    selection.selected_action.action_type.value,
                    verdict.reason,
                    runbook_decision.phase_id if runbook_decision else None,
                )
                execution = _blocked_execution(
                    selection.selected_action,
                    failure_reason=verdict.failure_reason,
                    blocked_by=verdict.reason,
                    extra_summary=(
                        {"runbook_phase": runbook_decision.phase_id if runbook_decision else None}
                        if runbook_blocked
                        else None
                    ),
                )
            elif self.dry_run:
                logger.info(
                    "tick %d: dry_run — skipping action=%s",
                    iteration,
                    selection.selected_action.action_type.value,
                )
                execution = ExecutionResult(
                    action_id=selection.selected_action.action_id,
                    status="dry_run",
                    verification_status="not_applicable",
                    summary={"action_type": selection.selected_action.action_type.value,
                             "note": "dry_run — no UI action dispatched"},
                )
            else:
                _reset_input_trace(self.ui_actions)
                execution = self.runner.run(selection.selected_action)
                input_trace = _consume_input_trace(self.ui_actions)
                if _requires_flow_continuation(execution):
                    (
                        execution,
                        post_action_verification,
                        extra_input_trace,
                        flow_decision,
                    ) = self._continue_action_flow(
                        iteration=iteration,
                        action=selection.selected_action,
                        execution=execution,
                        before_state=pre_action_state,
                    )
                    input_trace.extend(extra_input_trace)
                    if flow_decision is not None:
                        runbook_decision = _merge_decisions(runbook_decision, flow_decision)
                        self._guard.update_decision(runbook_decision)
                else:
                    execution, post_action_verification = self._verify_after_action(
                        action=selection.selected_action,
                        execution=execution,
                        before_state=pre_action_state,
                    )
                logger.info(
                    "tick %d: action=%s status=%s",
                    iteration,
                    selection.selected_action.action_type.value,
                    execution.status,
                )
            if runbook_blocked:
                sleep_s = IDLE_SLEEP_S
            else:
                sleep_s = WAIT_SLEEP_S.get(selection.selected_action.action_type, DEFAULT_SLEEP_S)
        else:
            logger.info("tick %d: no selected action — idle", iteration)

        extra_runbook_escalations = self._track_runbook_filter_blocks(
            runbook_decision,
            blocked=dispatch_block_reason == RUNBOOK_FILTER_REJECT_REASON,
            action=selection.selected_action,
            selection=selection,
        )

        # The verifier inside the action/flow block re-observes and mutates
        # self.state, so a hold/abort may have surfaced since the tick-start
        # decision. Refresh the guard against post-action state before any
        # recovery input, so ESC is suppressed when a fresh decision holds.
        if execution is not None and execution.status in ("ok", "failed", "pending"):
            runbook_decision = self._refresh_runbook_after_action(iteration, runbook_decision)

        state_after = self.state.model_dump(mode="json")
        recovery_strategy: str | None = None
        if execution is not None and execution.recovery_required and not self.dry_run:
            recovery_verdict = self._guard.recovery_verdict()
            if not recovery_verdict.allowed:
                # No automated input under a kill switch or a blocking hold —
                # an operator may be driving the client; a dangling dialog
                # waits for them/the planner.
                logger.warning(
                    "tick %d: recovery required but input suppressed (%s)",
                    iteration, recovery_verdict.reason,
                )
                self._stuck_count = 0
            else:
                recovery_strategy = self._attempt_esc_recovery(
                    iteration=iteration,
                    strategy="esc_after_action_failure",
                )
                input_trace.extend(_consume_input_trace(self.ui_actions))
                self._stuck_count = 0
                sleep_s = DEFAULT_SLEEP_S
        elif self._is_stuck(vision_summary, selection, execution):
            self._stuck_count += 1
            if self._stuck_count >= self.stuck_threshold and not self.dry_run:
                recovery_verdict = self._guard.recovery_verdict()
                if not recovery_verdict.allowed:
                    logger.warning(
                        "tick %d: stuck but input suppressed (%s)",
                        iteration, recovery_verdict.reason,
                    )
                    self._stuck_count = 0
                else:
                    logger.warning(
                        "tick %d: stuck for %d ticks — sending ESC to recover",
                        iteration, self._stuck_count,
                    )
                    recovery_strategy = self._attempt_esc_recovery(
                        iteration=iteration,
                        strategy="esc_close_popup",
                    )
                    input_trace.extend(_consume_input_trace(self.ui_actions))
                    self._stuck_count = 0
                    sleep_s = DEFAULT_SLEEP_S
        else:
            self._stuck_count = 0

        runbook_payload = self._build_runbook_payload(
            iteration, runbook_decision, extra_runbook_escalations
        )
        screenshot_path: str | None = None
        if self.loop_logger is not None:
            record = self.loop_logger.log_tick(
                iteration=iteration,
                started_at=started_at,
                elapsed_s=time.monotonic() - t0,
                png=png,
                vision_summary=vision_summary,
                selection=selection,
                execution=execution,
                sleep_s=sleep_s,
                runbook=runbook_payload,
            )
            screenshot_path = record.screenshot_path

        if self.trace_store is not None:
            trace = ensure_loop_contract(
                _build_tick_trace(
                    iteration=iteration,
                    started_at=started_at,
                    elapsed_s=time.monotonic() - t0,
                    png=png,
                    screenshot_path=screenshot_path,
                    state_before=state_before,
                    state_after=state_after,
                    vision_summary=vision_summary,
                    selection=selection,
                    execution=execution,
                    sleep_s=sleep_s,
                    recovery_strategy=recovery_strategy,
                    post_action_verification=post_action_verification,
                    vision_traces=_consume_remaining_vision_trace_events(self.vision_sync),
                    input_trace=input_trace,
                    runbook=runbook_payload,
                )
            )
            self.trace_store.append(trace)

        return TickResult(iteration=iteration, summary=vision_summary, selection=selection,
                          execution=execution, sleep_s=sleep_s)

    def _evaluate_runbook(
        self,
        iteration: int,
        derived: RuntimeState,
        *,
        allow_transition: bool = True,
    ) -> RunbookDecision | None:
        if self.runbook_engine is None:
            return None

        # Enforce the emergency-stop freeze at the side-effect site so every
        # caller of _evaluate_runbook (tick start, flow continuation, post-action
        # refresh) is covered: no gate confirmations are applied and no state is
        # persisted while the kill switch is active.
        if self.runbook_state_store is not None and not self._guard.kill_switch_active:
            # Operator confirmations arrive via the append-only channel; the
            # read is mtime/size-cached, so the steady-state cost is a stat().
            pending = (
                self.runbook_state_store.read_confirmations(
                    expected_season=self.runbook_engine.runbook.season
                )
                - set(self.runbook_engine.confirmed_gates)
            )
            known_gates = {phase.phase_id for phase in self.runbook_engine.runbook.phases}
            unknown = (pending - known_gates) - self._warned_unknown_gates
            if unknown:
                logger.warning(
                    "runbook confirmations contain unknown gates %s — ignored",
                    sorted(unknown),
                )
                self._warned_unknown_gates |= unknown
            for phase_id in pending & known_gates:
                self.runbook_engine.confirm_human_gate(phase_id)

        decision = self.runbook_engine.evaluate(
            metrics_from_runtime_state(derived), allow_transition=allow_transition
        )
        derived.global_state["runbook"] = {
            "phase_id": decision.phase_id,
            "selector_hints": dict(decision.selector_hints),
            "hold_reason": decision.hold_reason,
            "human_gate_pending": decision.human_gate_pending,
        }
        if decision.transitioned:
            logger.info(
                "tick %d: runbook phase %s -> %s",
                iteration, decision.previous_phase_id, decision.phase_id,
            )
        self._persist_runbook_state()
        return decision

    def _refresh_runbook_after_action(
        self, iteration: int, decision: RunbookDecision | None
    ) -> RunbookDecision | None:
        """Re-evaluate against post-verifier state (transitions frozen — the
        tick already acted; this is a safety refresh, not a phase commit) and
        merge so the tick-start decision's escalations/transition survive. The
        refreshed decision drives the recovery gate and the recorded payload."""
        if self.runbook_engine is None:
            return decision
        derived = self.deriver.derive(self.state)
        fresh = self._evaluate_runbook(iteration, derived, allow_transition=False)
        if fresh is None:
            return decision
        merged = _merge_decisions(decision, fresh) if decision is not None else fresh
        self._guard.update_decision(merged)
        return merged

    def _persist_runbook_state(self) -> None:
        """Loop-owned state file; skipped in dry-run so previews stay side-effect
        free. The saved-signature check keeps idle ticks write-free, but an
        externally deleted file is re-created (a stat per tick, not a read)."""
        if self.runbook_state_store is None or self.dry_run or self._guard.kill_switch_active:
            return
        signature = (
            self.runbook_engine.current_phase.phase_id,
            frozenset(self.runbook_engine.confirmed_gates),
            self.runbook_engine.completed,
        )
        if signature == self._runbook_saved_signature and self.runbook_state_store.path.exists():
            return
        self.runbook_state_store.save(
            current_phase_id=signature[0],
            confirmed_gates=set(signature[1]),
            completed=signature[2],
            season=self.runbook_engine.runbook.season,
        )
        self._runbook_saved_signature = signature

    def _track_runbook_filter_blocks(
        self,
        decision: RunbookDecision | None,
        *,
        blocked: bool,
        action: CandidateAction | None,
        selection: SelectionResult,
    ) -> list[RunbookEscalation]:
        """Backstop against allowlist no-progress: counts both dispatch blocks
        (a selector that ignores hints) and selector starvation (the allowlist
        rejected every candidate, so nothing was selected at all). Either way,
        persistent no-progress escalates to the planner instead of idling
        silently."""
        starved = False
        if decision is not None and action is None:
            reason_counts = {}
            if isinstance(selection.selection_reason, dict):
                pipeline = selection.selection_reason.get("pipeline")
                if isinstance(pipeline, dict):
                    reason_counts = pipeline.get("rejected_by_reason") or {}
            starved = bool(reason_counts.get(RUNBOOK_FILTER_REJECT_REASON))

        if (not blocked and not starved) or decision is None:
            self._runbook_filter_block_phase = None
            self._runbook_filter_block_count = 0
            return []
        if self._runbook_filter_block_phase != decision.phase_id:
            self._runbook_filter_block_phase = decision.phase_id
            self._runbook_filter_block_count = 0
        self._runbook_filter_block_count += 1
        if self._runbook_filter_block_count < self.stuck_threshold:
            return []
        count = self._runbook_filter_block_count
        self._runbook_filter_block_count = 0
        return [
            RunbookEscalation(
                kind=EscalationKind.ACTION_FILTER_STUCK,
                route=EscalationRoute.LLM_PLANNER,
                phase_id=decision.phase_id,
                details={
                    "consecutive_blocks": count,
                    "starved": starved,
                    "blocked_action_type": action.action_type.value if action else None,
                    "allowed_action_types": decision.selector_hints.get("allowed_action_types"),
                },
            )
        ]

    def _build_runbook_payload(
        self,
        iteration: int,
        decision: RunbookDecision | None,
        extra_escalations: list[RunbookEscalation],
    ) -> dict[str, Any] | None:
        """Edge-triggered escalation reporting: a persistent condition is logged
        and recorded once when it appears, not once per tick; `active_escalations`
        keeps the ongoing set visible."""
        if decision is None:
            return None
        all_escalations = list(decision.escalations) + list(extra_escalations)
        signatures = {_escalation_signature(e) for e in all_escalations}
        new_escalations = [
            e for e in all_escalations
            if _escalation_signature(e) not in self._active_runbook_escalations
        ]
        for escalation in new_escalations:
            logger.warning(
                "tick %d: runbook escalation kind=%s route=%s phase=%s details=%s",
                iteration,
                escalation.kind.value,
                escalation.route.value,
                escalation.phase_id,
                escalation.details,
            )
        self._active_runbook_escalations = signatures

        payload = decision.model_dump(mode="json", exclude={"exit_result", "abort_result"})
        payload["escalations"] = [e.model_dump(mode="json") for e in new_escalations]
        payload["active_escalations"] = sorted({e.kind.value for e in all_escalations})
        return payload

    @staticmethod
    def _is_stuck(
        summary: VisionSyncSummary,
        selection: SelectionResult,
        execution: ExecutionResult | None,
    ) -> bool:
        """A tick is 'stuck' when vision cannot classify the page or no useful
        progress was made: unknown page, no selected action, or a pending/failed
        execution. Accumulating stuck ticks triggers an ESC recovery."""
        if summary.page_type in (None, "unknown"):
            return True
        if selection.selected_action is None:
            return True
        if execution is not None and execution.status in ("failed", "pending"):
            return True
        return False

    def _attempt_esc_recovery(self, *, iteration: int, strategy: str) -> str:
        logger.warning("tick %d: attempting recovery strategy=%s", iteration, strategy)
        try:
            outcome = self.ui_actions.close_popup()
        except Exception:  # noqa: BLE001
            logger.exception("ESC recovery failed")
            return f"{strategy}_failed"
        if not getattr(outcome, "success", True):
            logger.warning("tick %d: ESC recovery failed: %s", iteration, getattr(outcome, "reason", None))
            return f"{strategy}_failed"
        return strategy

    def _continue_action_flow(
        self,
        *,
        iteration: int,
        action: CandidateAction,
        execution: ExecutionResult,
        before_state: dict[str, Any],
    ) -> tuple[ExecutionResult, dict[str, Any] | None, list[dict[str, Any]], RunbookDecision | None]:
        input_trace: list[dict[str, Any]] = []
        flow_observe: VisionSyncSummary | None = None
        flow_decision: RunbookDecision | None = None

        def _fail(
            reason: str,
            *,
            next_action: CandidateAction | None = None,
            base: ExecutionResult | None = None,
        ) -> tuple[ExecutionResult, None, list[dict[str, Any]], RunbookDecision | None]:
            return (
                _flow_failure_execution(
                    base if base is not None else execution,
                    reason=reason,
                    flow_observe=flow_observe,
                    next_action=next_action,
                ),
                None,
                input_trace,
                flow_decision,
            )

        try:
            png = self.bridge.screenshot()
            self.state, flow_observe = self.vision_sync.sync(
                png,
                state=self.state,
                captured_at=datetime.now(),
            )
        except Exception as exc:  # noqa: BLE001
            return _fail(f"action flow observe failed: {exc}")

        # The intermediate observation can change the world (abort thresholds
        # crossed, tripped kill switch): the dispatch guard is re-enforced
        # before the terminal click. Phase transitions are frozen
        # (allow_transition=False) so a satisfied exit defers to the next tick
        # boundary instead of swapping the phase — and persisting the new
        # cursor — under this in-flight action.
        derived = self.deriver.derive(self.state)
        flow_decision = self._evaluate_runbook(iteration, derived, allow_transition=False)
        if flow_decision is not None:
            self._guard.update_decision(flow_decision)
        next_selection = self.selector.select(derived)
        next_action = next_selection.selected_action
        if (
            next_action is None
            or next_action.action_type != action.action_type
            or next_action.action_id != action.action_id
        ):
            return _fail(
                "action flow did not produce the same terminal action",
                next_action=next_action,
            )

        verdict = self._guard.action_verdict(next_action)
        if not verdict.allowed:
            logger.warning(
                "tick %d: action flow continuation blocked (%s, phase=%s)",
                iteration,
                verdict.reason,
                flow_decision.phase_id if flow_decision else None,
            )
            reason = (
                "kill switch tripped during action flow"
                if verdict.reason == KILL_SWITCH_REASON
                else f"runbook blocks action flow continuation: {verdict.reason}"
            )
            return _fail(reason, next_action=next_action)

        _reset_input_trace(self.ui_actions)
        terminal_execution = self.runner.run(next_action)
        input_trace.extend(_consume_input_trace(self.ui_actions))
        terminal_execution = _execution_with_flow_continuation(
            initial_execution=execution,
            terminal_execution=terminal_execution,
            flow_observe=flow_observe,
            next_action=next_action,
        )
        if _requires_flow_continuation(terminal_execution):
            return _fail(
                "action flow did not reach a terminal verifier step",
                next_action=next_action,
                base=terminal_execution,
            )
        terminal_execution, verification = self._verify_after_action(
            action=next_action,
            execution=terminal_execution,
            before_state=before_state,
        )
        return terminal_execution, verification, input_trace, flow_decision

    def _verify_after_action(
        self,
        *,
        action: CandidateAction,
        execution: ExecutionResult,
        before_state: dict[str, Any],
    ) -> tuple[ExecutionResult, dict[str, Any] | None]:
        spec = _post_action_verifier_spec(self.runner, action.action_type)
        if spec is None:
            return execution, None
        if execution.status != "ok":
            return execution, None
        if _requires_flow_continuation(execution):
            return execution, None
        if execution.verification_status not in {"unknown", "unverified"}:
            return execution, None

        verifier = spec.build()
        deadline = time.monotonic() + spec.timeout_seconds
        attempts = 0

        while True:
            attempts += 1
            try:
                png = self.bridge.screenshot()
                self.state, summary = self.vision_sync.sync(
                    png,
                    state=self.state,
                    captured_at=datetime.now(),
                )
                after_state = self.state.model_dump(mode="json")
                result = verifier.verify(before_state, after_state)
                payload = _verification_payload(
                    action=action,
                    spec=spec,
                    result=result,
                    attempts=attempts,
                    summary=summary,
                )
            except Exception as exc:  # noqa: BLE001
                result = VerificationResult(
                    status=VerificationStatus.UNKNOWN,
                    reason=f"post-action observe failed: {exc}",
                    checked=(),
                    timeout_seconds=spec.timeout_seconds,
                )
                payload = _verification_payload(
                    action=action,
                    spec=spec,
                    result=result,
                    attempts=attempts,
                    summary=None,
                )
            if result.status == VerificationStatus.VERIFIED:
                return (
                    _execution_with_verification(
                        execution,
                        result=result,
                        payload=payload,
                        status="ok",
                        recovery_required=execution.recovery_required,
                    ),
                    payload,
                )

            remaining = deadline - time.monotonic()
            if remaining <= 0 or self.post_action_verify_poll_interval_s <= 0:
                failure_reason = f"post-action verifier failed: {result.reason}"
                return (
                    _execution_with_verification(
                        execution,
                        result=result,
                        payload=payload,
                        status="failed",
                        failure_reason=failure_reason,
                        recovery_required=True,
                    ),
                    payload,
                )

            self.sleeper(min(self.post_action_verify_poll_interval_s, remaining))

    def run_forever(self, *, max_iterations: int | None = None) -> None:
        i = 0
        while max_iterations is None or i < max_iterations:
            try:
                result = self.tick(i)
            except Exception:  # noqa: BLE001
                logger.exception("tick %d failed — sleeping %ds before retry", i, IDLE_SLEEP_S)
                self.sleeper(IDLE_SLEEP_S)
                i += 1
                continue
            self.sleeper(result.sleep_s)
            i += 1


def _build_tick_trace(
    *,
    iteration: int,
    started_at: datetime,
    elapsed_s: float,
    png: bytes,
    screenshot_path: str | None,
    state_before: dict,
    state_after: dict,
    vision_summary: VisionSyncSummary,
    selection: SelectionResult,
    execution: ExecutionResult | None,
    sleep_s: float,
    recovery_strategy: str | None,
    post_action_verification: dict[str, Any] | None = None,
    vision_traces: list[dict] | None = None,
    input_trace: list[dict] | None = None,
    runbook: dict[str, Any] | None = None,
) -> TickTrace:
    action = selection.selected_action
    screenshot_size = _image_size_from_png(png)
    all_vision_traces = list(vision_summary.image_traces)
    if vision_traces:
        all_vision_traces.extend(vision_traces)
    input_events = list(input_trace or [])
    return TickTrace(
        iteration=iteration,
        created_at=started_at,
        current_phase=TracePhase.TRACE,
        screenshot=ScreenshotTraceMetadata(
            path=screenshot_path,
            raw_size=screenshot_size or _image_size_from_trace(all_vision_traces, "raw_size"),
            prepared_size=_image_size_from_trace(all_vision_traces, "prepared_size"),
            display_coordinate_space=_coordinate_space_from_input(input_events, "display_coordinate_space"),
            window_coordinate_space=_coordinate_space_from_input(input_events, "window_coordinate_space"),
            coordinates=_coordinate_metadata_from_input_trace(input_events),
            metadata={
                "vision": all_vision_traces,
                "input_events": input_events,
            },
        ),
        observe=TraceStep(
            phase=TracePhase.OBSERVE,
            outputs={
                "page_type": vision_summary.page_type,
                "domains_run": list(vision_summary.domains_run),
                "notes": list(vision_summary.notes),
            },
        ),
        decide=TraceStep(
            phase=TracePhase.DECIDE,
            outputs={
                "selected_action_id": action.action_id if action else None,
                "selected_action_type": action.action_type.value if action else None,
                "ranked_action_count": len(selection.ranked_actions),
            },
        ),
        act=TraceStep(
            phase=TracePhase.ACT,
            inputs={"action": action.model_dump(mode="json") if action else None},
            outputs=execution.model_dump(mode="json") if execution else {"status": "idle"},
            failure_reason=execution.failure_reason if execution else None,
        ),
        verify=TraceStep(
            phase=TracePhase.VERIFY,
            outputs=_verify_step_outputs(execution, post_action_verification),
        ),
        trace=TraceStep(
            phase=TracePhase.TRACE,
            outputs={"sleep_s": sleep_s, "elapsed_s": round(elapsed_s, 3)},
        ),
        recover=TraceStep(
            phase=TracePhase.RECOVER,
            outputs={"status": "attempted" if recovery_strategy else "not_required"},
            recovery_strategy=recovery_strategy or "none",
        ),
        state_before=state_before,
        vision={
            "page_type": vision_summary.page_type,
            "domains_run": list(vision_summary.domains_run),
            "notes": list(vision_summary.notes),
            "image_traces": all_vision_traces,
        },
        state_after=state_after,
        selected_action=action.model_dump(mode="json") if action else None,
        ranked_actions=[item.model_dump(mode="json") for item in selection.ranked_actions],
        execution=execution.model_dump(mode="json") if execution else None,
        verification=_verification_trace_payload(execution, post_action_verification),
        recovery={"strategy": recovery_strategy or "none"},
        failure_reason=execution.failure_reason if execution else None,
        next_recovery_strategy=recovery_strategy or "none",
        metadata={
            "loop_contract": [phase.value for phase in LOOP_PHASE_ORDER],
            **({"runbook": runbook} if runbook is not None else {}),
        },
    )


def _blocked_execution(
    action: CandidateAction,
    *,
    failure_reason: str,
    blocked_by: str,
    extra_summary: dict[str, Any] | None = None,
) -> ExecutionResult:
    summary: dict[str, Any] = {
        "action_type": action.action_type.value,
        "blocked_by": blocked_by,
    }
    if extra_summary:
        summary.update(extra_summary)
    return ExecutionResult(
        action_id=action.action_id,
        status="blocked",
        verification_status="not_applicable",
        failure_reason=failure_reason,
        recovery_required=False,
        summary=summary,
    )


def _merge_decisions(
    earlier: RunbookDecision | None, later: RunbookDecision
) -> RunbookDecision:
    """Merge a re-evaluation (flow continuation or post-action refresh) with the
    tick's earlier decision. `later` is the freshest observation and drives the
    guard, but nothing the earlier evaluation observed may be lost: escalations
    are unioned and an earlier transition survives into the recorded payload.
    The stronger (blocking) hold wins, and a real earlier hold is never
    relabeled to the synthetic `transition_deferred` that a frozen re-eval
    emits on an otherwise-productive tick."""
    if earlier is None:
        return later
    update: dict[str, Any] = {}
    if earlier.transitioned and not later.transitioned:
        update["transitioned"] = True
        update["previous_phase_id"] = earlier.previous_phase_id
    if earlier.escalations:
        seen = {_escalation_signature(e) for e in later.escalations}
        update["escalations"] = list(later.escalations) + [
            e for e in earlier.escalations if _escalation_signature(e) not in seen
        ]
    if later.hold_reason not in RUNBOOK_BLOCKING_HOLDS and earlier.hold_reason != later.hold_reason:
        update["hold_reason"] = earlier.hold_reason
        update["human_gate_pending"] = earlier.human_gate_pending
    return later.model_copy(update=update) if update else later


# Full condition-result dumps carry every sibling condition's status, which can
# flip tick to tick when a non-triggering metric flickers dark; excluding them
# keeps a persistent escalation's identity stable so edge-triggering holds,
# while the stable discriminators (checked, missing_metrics, triggered/failed
# metric identity) still distinguish genuinely different escalations.
_VOLATILE_ESCALATION_DETAIL_KEYS = frozenset({"abort_result", "exit_result", "entry_result"})


def _escalation_signature(escalation: RunbookEscalation) -> str:
    """Identity for edge-triggering: two escalations of the same kind in the
    same phase are distinct only if their STABLE details differ (e.g.
    unknown_metrics for a missing abort metric vs a missing exit metric), so a
    changed discriminator re-fires to the planner while a persistent condition
    stays deduped even as volatile sibling-condition statuses churn."""
    stable = {
        key: value
        for key, value in escalation.details.items()
        if key not in _VOLATILE_ESCALATION_DETAIL_KEYS
    }
    details = json.dumps(stable, sort_keys=True, ensure_ascii=False, default=str)
    return f"{escalation.kind.value}|{escalation.phase_id}|{details}"


def _post_action_verifier_spec(runner: Any, action_type: ActionType) -> VerifierSpec | None:
    registry = getattr(runner, "verifier_registry", None)
    if not isinstance(registry, VerifierRegistry):
        return None
    return registry.get(action_type)


def _requires_flow_continuation(execution: ExecutionResult) -> bool:
    return execution.status == "ok" and execution.summary.get("terminal_for_verifier") is False


def _execution_with_flow_continuation(
    *,
    initial_execution: ExecutionResult,
    terminal_execution: ExecutionResult,
    flow_observe: VisionSyncSummary,
    next_action: CandidateAction,
) -> ExecutionResult:
    summary = dict(terminal_execution.summary)
    summary["flow_steps"] = _flow_steps(initial_execution) + _flow_steps(terminal_execution)
    summary["flow_intermediate_observe"] = _vision_summary_payload(flow_observe)
    summary["flow_next_action"] = next_action.model_dump(mode="json")
    return terminal_execution.model_copy(update={"summary": summary})


def _flow_failure_execution(
    execution: ExecutionResult,
    *,
    reason: str,
    flow_observe: VisionSyncSummary | None,
    next_action: CandidateAction | None,
) -> ExecutionResult:
    summary = dict(execution.summary)
    summary["flow_failure"] = {
        "reason": reason,
        "flow_intermediate_observe": _vision_summary_payload(flow_observe) if flow_observe else None,
        "next_action": next_action.model_dump(mode="json") if next_action else None,
    }
    return execution.model_copy(
        update={
            "status": "failed",
            "verification_status": "unknown",
            "failure_reason": reason,
            "recovery_required": True,
            "summary": summary,
        }
    )


def _flow_steps(execution: ExecutionResult) -> list[dict[str, Any]]:
    raw_steps = execution.summary.get("flow_steps")
    if not isinstance(raw_steps, list):
        return []
    return [dict(step) for step in raw_steps if isinstance(step, dict)]


def _vision_summary_payload(summary: VisionSyncSummary) -> dict[str, Any]:
    return {
        "page_type": summary.page_type,
        "domains_run": list(summary.domains_run),
        "notes": list(summary.notes),
        "image_traces": list(summary.image_traces),
    }


def _execution_with_verification(
    execution: ExecutionResult,
    *,
    result: VerificationResult,
    payload: dict[str, Any],
    status: str,
    failure_reason: str | None = None,
    recovery_required: bool,
) -> ExecutionResult:
    summary = dict(execution.summary)
    summary["post_action_verifier"] = payload
    return execution.model_copy(
        update={
            "status": status,
            "verification_status": result.status.value,
            "failure_reason": failure_reason,
            "recovery_required": recovery_required,
            "summary": summary,
        }
    )


def _verification_payload(
    *,
    action: CandidateAction,
    spec: VerifierSpec,
    result: VerificationResult,
    attempts: int,
    summary: VisionSyncSummary | None,
) -> dict[str, Any]:
    return {
        "action_type": action.action_type.value,
        "status": result.status.value,
        "reason": result.reason,
        "checked": list(result.checked),
        "timeout_seconds": spec.timeout_seconds,
        "match_policy": (
            spec.match_policy.value
            if hasattr(spec.match_policy, "value")
            else str(spec.match_policy)
        ),
        "attempts": attempts,
        "post_observe": {
            "page_type": summary.page_type if summary else None,
            "domains_run": list(summary.domains_run) if summary else [],
            "notes": list(summary.notes) if summary else [],
            "image_traces": list(summary.image_traces) if summary else [],
        },
    }


def _verify_step_outputs(
    execution: ExecutionResult | None,
    post_action_verification: dict[str, Any] | None,
) -> dict[str, Any]:
    if execution is None:
        return {"status": "not_applicable"}
    outputs = {"status": execution.verification_status}
    if post_action_verification is not None:
        outputs["post_action_verifier"] = post_action_verification
    return outputs


def _verification_trace_payload(
    execution: ExecutionResult | None,
    post_action_verification: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if execution is None:
        return None
    payload = {"status": execution.verification_status}
    if post_action_verification is not None:
        payload["post_action_verifier"] = post_action_verification
    return payload


def _image_size_from_png(png: bytes) -> ImageSize | None:
    try:
        with Image.open(BytesIO(png)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError):
        return None
    return ImageSize(width=width, height=height)


def _reset_input_trace(ui_actions: UIActions) -> None:
    reset = getattr(ui_actions, "reset_input_trace", None)
    if callable(reset):
        reset()


def _consume_input_trace(ui_actions: UIActions) -> list[dict[str, Any]]:
    consume = getattr(ui_actions, "consume_input_trace", None)
    if not callable(consume):
        return []
    events = consume()
    return list(events) if events else []


def _consume_remaining_vision_trace_events(vision_sync: VisionSync) -> list[dict[str, Any]]:
    client = getattr(vision_sync, "client", None)
    consume = getattr(client, "consume_trace_events", None)
    if not callable(consume):
        return []
    events = consume()
    return list(events) if events else []


def _image_size_from_trace(events: list[dict[str, Any]], key: str) -> ImageSize | None:
    for event in events:
        raw = event.get(key)
        if not isinstance(raw, dict):
            continue
        width = raw.get("width")
        height = raw.get("height")
        if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
            return ImageSize(width=width, height=height)
    return None


def _coordinate_space_from_input(events: list[dict[str, Any]], key: str) -> str | None:
    for event in events:
        value = event.get(key)
        if isinstance(value, str):
            return value
    return None


def _coordinate_metadata_from_input_trace(
    events: list[dict[str, Any]],
) -> list[CoordinateTraceMetadata]:
    coordinates: list[CoordinateTraceMetadata] = []
    for event in events:
        click_point = _pixel_point(event.get("click_point"))
        if click_point is None:
            continue
        coordinates.append(
            CoordinateTraceMetadata(
                coordinate_space=_optional_str(event.get("coordinate_space")),
                dpr=_optional_float(event.get("dpr")),
                scale=_optional_float(event.get("scale")),
                normalized_bbox=_normalized_bbox(event.get("normalized_bbox")),
                pixel_bbox=_pixel_bbox(event.get("pixel_bbox")),
                click_point=click_point,
            )
        )
    return coordinates


def _pixel_point(raw: Any) -> PixelPoint | None:
    if not isinstance(raw, dict):
        return None
    x = raw.get("x")
    y = raw.get("y")
    if isinstance(x, int) and isinstance(y, int):
        return PixelPoint(x=x, y=y)
    return None


def _pixel_bbox(raw: Any) -> PixelBBox | None:
    if not isinstance(raw, dict):
        return None
    x = raw.get("x")
    y = raw.get("y")
    width = raw.get("width")
    height = raw.get("height")
    if all(isinstance(value, int) for value in (x, y, width, height)):
        return PixelBBox(x=x, y=y, width=width, height=height)
    return None


def _normalized_bbox(raw: Any) -> NormalizedBBox | None:
    if not isinstance(raw, dict):
        return None
    x = raw.get("x")
    y = raw.get("y")
    width = raw.get("width")
    height = raw.get("height")
    if all(isinstance(value, (int, float)) for value in (x, y, width, height)):
        return NormalizedBBox(x=x, y=y, width=width, height=height)
    return None


def _optional_str(raw: Any) -> str | None:
    return raw if isinstance(raw, str) else None


def _optional_float(raw: Any) -> float | None:
    return float(raw) if isinstance(raw, (int, float)) else None
