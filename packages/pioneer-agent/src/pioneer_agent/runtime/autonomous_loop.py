"""Autonomous decision loop: screenshot → vision → decide → act → repeat.

Glues together bridge_client (observe), VisionSync (extract), ActionSelector
(plan), and UIActionRunner (act). The loop is intentionally thin — all real
work lives in the components; this module just sequences them and handles
the wait/sleep cadence between ticks.
"""
from __future__ import annotations

import json
import hashlib
import inspect
import logging
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from typing import Any, Mapping, Protocol

from PIL import Image, UnidentifiedImageError

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import (
    CandidateAction,
    CaptureGeometry,
    ExecutionResult,
    ObservationSnapshot,
    RuntimeState,
    SelectionResult,
)
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.executor.action_handlers import terminal_mutating_target
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.executor.ui_runner import UIActionRunner
from pioneer_agent.perception.vision_sync import VisionSync, VisionSyncSummary
from pioneer_agent.runbook.action_filter import (
    RUNBOOK_ACTION_CONSTRAINT_REASONS,
    resolve_runbook_action_facts,
)
from pioneer_agent.runbook.engine import RunbookEngine
from pioneer_agent.runbook.loader import metrics_from_runtime_state
from pioneer_agent.runbook.lineup_binding import apply_operator_lineup_bindings
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
from pioneer_agent.runtime.architecture_gates import LOW_RISK_AUTOMATION_ACTIONS
from pioneer_agent.runtime.loop_contract import LOOP_PHASE_ORDER, ensure_loop_contract
from pioneer_agent.runtime.observation_gate import (
    ObservationGateDecision,
    validate_dispatch_observation,
    validate_post_observation,
)
from pioneer_agent.safety.kill_switch import KillSwitch
from pioneer_agent.safety.guard import SessionMode
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
    TraceFrameReference,
    TraceFrameRole,
    TracePhase,
    TraceStep,
    TraceStore,
)
from pioneer_agent.verifier.base import (
    VerificationResult,
    VerificationStatus,
    structured_matching_deltas,
)
from pioneer_agent.verifier.registry import (
    UI_ACTIONS_REQUIRING_VERIFIER,
    VerifierRegistry,
    VerifierSpec,
)

logger = logging.getLogger(__name__)


class _Screenshotter(Protocol):
    def screenshot(self, save_path=None) -> bytes: ...  # noqa: ANN001


@dataclass(frozen=True)
class _CapturedFrame:
    png: bytes
    capture_geometry: CaptureGeometry | None


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
        lineup_preset_bindings: Mapping[str, str] | None = None,
        evidence_action_type: ActionType | None = None,
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
        if isinstance(self.runner, UIActionRunner) and self.runner.ui is not ui_actions:
            raise ValueError(
                "AutonomousLoop ui_actions must be the same instance used by UIActionRunner"
            )
        self.sleeper = sleeper
        self.loop_logger = loop_logger
        self.trace_store = trace_store
        self._guard = DispatchGuard(kill_switch=kill_switch)
        self.runbook_engine = runbook_engine
        self.runbook_state_store = runbook_state_store
        self.lineup_preset_bindings = dict(lineup_preset_bindings or {})
        if (
            evidence_action_type is not None
            and evidence_action_type not in LOW_RISK_AUTOMATION_ACTIONS
        ):
            raise ValueError("evidence action must be a calibrated low-risk action")
        self.evidence_action_type = evidence_action_type
        self._lineup_bindings_bound_at = datetime.now().astimezone()
        self._lineup_binding_roster_fingerprints: dict[str, str] = {}
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
        started_at = datetime.now(UTC)
        t0 = time.monotonic()
        state_before = self.state.model_dump(mode="json")
        captured = _capture_bridge_frame(self.bridge)
        png = captured.png
        logger.info("tick %d: captured %d bytes", iteration, len(png))

        if captured.capture_geometry is None:
            self.state, vision_summary = self.vision_sync.sync(
                png,
                state=self.state,
                captured_at=started_at,
            )
        else:
            self.state, vision_summary = self.vision_sync.sync(
                png,
                state=self.state,
                captured_at=started_at,
                capture_geometry=captured.capture_geometry,
            )
        logger.info("tick %d: page=%s domains=%s", iteration, vision_summary.page_type, vision_summary.domains_run)

        derived = self.deriver.derive(self.state)
        self._apply_lineup_preset_bindings(derived)
        # Freeze the runbook while the kill switch is tripped: no cursor
        # advancement and no persistence may happen during an emergency stop.
        kill_switch_active = self._guard.kill_switch_active
        if kill_switch_active and self.runbook_engine is not None:
            logger.info("tick %d: kill switch active — runbook cursor frozen", iteration)
        runbook_decision = None if kill_switch_active else self._evaluate_runbook(iteration, derived)
        self._guard.update_decision(runbook_decision)
        dispatch_observation = vision_summary.observation
        selection = self.selector.select(derived)
        if self.evidence_action_type is not None:
            selection = _constrain_evidence_selection(
                selection,
                required_action_type=self.evidence_action_type,
                observation=dispatch_observation,
                now=started_at,
                max_age_seconds=_runner_observation_max_age(self.runner),
                allow_fixture_source=_runner_allows_fixture_observation(self.runner),
            )
        pre_action_state = self.state.model_dump(mode="json")
        trace_frames: list[TraceFrameReference] = []
        if (
            selection.selected_action is not None
            and selection.selected_action.action_type in LOW_RISK_AUTOMATION_ACTIONS
        ):
            self._record_trace_frame(
                trace_frames,
                iteration=iteration,
                role=TraceFrameRole.PRE_ACTION,
                png=png,
                observation=dispatch_observation,
            )

        execution: ExecutionResult | None = None
        post_action_verification: dict[str, Any] | None = None
        input_trace: list[dict] = []
        sleep_s = IDLE_SLEEP_S
        runbook_blocked = False
        dispatch_block_reason: str | None = None
        if selection.selected_action is not None:
            verdict = self._guard.action_verdict(
                selection.selected_action,
                state=derived,
            )
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
            elif (
                verifier_preflight := _post_action_verifier_preflight_failure(
                    self.runner,
                    selection.selected_action,
                    dispatch_observation,
                    pre_action_state,
                )
            ) is not None:
                logger.warning(
                    "tick %d: verifier preflight blocked action=%s (%s)",
                    iteration,
                    selection.selected_action.action_type.value,
                    verifier_preflight.reason,
                )
                execution = _blocked_execution(
                    selection.selected_action,
                    failure_reason=(
                        f"post-action verifier preflight failed: "
                        f"{verifier_preflight.reason}"
                    ),
                    blocked_by="verifier_preflight",
                    extra_summary={
                        "verifier_preflight": {
                            "status": verifier_preflight.status.value,
                            "reason": verifier_preflight.reason,
                            "checked": list(verifier_preflight.checked),
                        }
                    },
                )
            else:
                _reset_input_trace(self.ui_actions)
                if terminal_mutating_target(selection.selected_action) is not None:
                    self._record_trace_frame(
                        trace_frames,
                        iteration=iteration,
                        role=TraceFrameRole.TERMINAL_DISPATCH,
                        png=png,
                        observation=dispatch_observation,
                    )
                execution = _run_action(
                    self.runner,
                    selection.selected_action,
                    dispatch_observation,
                    frame_bytes=png,
                )
                dispatch_completed_at = datetime.now(UTC)
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
                        trace_frames=trace_frames,
                    )
                    input_trace.extend(extra_input_trace)
                    if flow_decision is not None:
                        runbook_decision = _merge_decisions(runbook_decision, flow_decision)
                        self._guard.update_decision(runbook_decision)
                else:
                    execution, post_action_verification = self._verify_after_action(
                        action=selection.selected_action,
                        execution=execution,
                        baseline_observation=dispatch_observation,
                        dispatch_completed_at=dispatch_completed_at,
                        iteration=iteration,
                        trace_frames=trace_frames,
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
            blocked_reason=(
                dispatch_block_reason
                if dispatch_block_reason in RUNBOOK_ACTION_CONSTRAINT_REASONS
                else None
            ),
            action=selection.selected_action,
            selection=selection,
            state=derived,
        )
        policy_starved = self._is_runbook_policy_starved(
            runbook_decision,
            selection,
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
            recovery_block_reason = self._recovery_input_block_reason()
            if recovery_block_reason is not None:
                # No automated input without explicit runner authority, under
                # a kill switch, or during a blocking hold. A dangling dialog
                # waits for the operator/planner.
                logger.warning(
                    "tick %d: recovery required but input suppressed (%s)",
                    iteration, recovery_block_reason,
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
        elif self._is_stuck(
            vision_summary,
            selection,
            execution,
            policy_starved=policy_starved,
        ):
            self._stuck_count += 1
            if self._stuck_count >= self.stuck_threshold and not self.dry_run:
                recovery_block_reason = self._recovery_input_block_reason()
                if recovery_block_reason is not None:
                    logger.warning(
                        "tick %d: stuck but input suppressed (%s)",
                        iteration, recovery_block_reason,
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
                    frame_evidence=trace_frames,
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
        self._apply_lineup_preset_bindings(derived)
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

    def _apply_lineup_preset_bindings(self, state: RuntimeState) -> None:
        if not self.lineup_preset_bindings:
            return
        apply_operator_lineup_bindings(
            state,
            self.lineup_preset_bindings,
            bound_at=self._lineup_bindings_bound_at,
            roster_fingerprints=self._lineup_binding_roster_fingerprints,
        )

    def _track_runbook_filter_blocks(
        self,
        decision: RunbookDecision | None,
        *,
        blocked_reason: str | None,
        action: CandidateAction | None,
        selection: SelectionResult,
        state: RuntimeState,
    ) -> list[RunbookEscalation]:
        """Backstop against allowlist no-progress: counts both dispatch blocks
        (a selector that ignores hints) and selector starvation (the allowlist
        rejected every candidate, so nothing was selected at all). Either way,
        persistent no-progress escalates to the planner instead of idling
        silently."""
        reason_counts = self._runbook_policy_rejection_counts(decision, selection)
        starved = action is None and any(
            bool(reason_counts.get(reason))
            for reason in RUNBOOK_ACTION_CONSTRAINT_REASONS
        )

        if (blocked_reason is None and not starved) or decision is None:
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
        policy_hints = {
            key: decision.selector_hints.get(key)
            for key in (
                "allowed_action_types",
                "target_land_levels",
                "land_scope",
                "lineup_preset",
            )
            if key in decision.selector_hints
        }
        observed_facts: dict[str, Any] | None = None
        if action is not None:
            resolved_facts = resolve_runbook_action_facts(state, action)
            observed_facts = {
                "source": "current_runtime_state",
                "action_type": action.action_type.value,
                "land_id": action.params.get("land_id"),
                "team_id": action.params.get("team_id"),
                "facts": {
                    key: value
                    for key, value in resolved_facts.items()
                    if not key.startswith("_")
                },
            }
        elif starved:
            observed_facts = self._rejected_candidate_policy_facts(selection)
        return [
            RunbookEscalation(
                kind=EscalationKind.ACTION_FILTER_STUCK,
                route=EscalationRoute.LLM_PLANNER,
                phase_id=decision.phase_id,
                details={
                    "consecutive_blocks": count,
                    "starved": starved,
                    "blocked_reason": blocked_reason,
                    "rejected_by_reason": reason_counts,
                    "blocked_action_type": action.action_type.value if action else None,
                    "allowed_action_types": decision.selector_hints.get("allowed_action_types"),
                    "active_selector_hints": policy_hints,
                    "observed_action_facts": observed_facts,
                },
            )
        ]

    @staticmethod
    def _runbook_policy_rejection_counts(
        decision: RunbookDecision | None,
        selection: SelectionResult,
    ) -> dict[str, Any]:
        if decision is None or selection.selected_action is not None:
            return {}
        if not isinstance(selection.selection_reason, dict):
            return {}
        pipeline = selection.selection_reason.get("pipeline")
        if not isinstance(pipeline, dict):
            return {}
        reason_counts = pipeline.get("rejected_by_reason")
        return reason_counts if isinstance(reason_counts, dict) else {}

    @classmethod
    def _is_runbook_policy_starved(
        cls,
        decision: RunbookDecision | None,
        selection: SelectionResult,
    ) -> bool:
        counts = cls._runbook_policy_rejection_counts(decision, selection)
        return any(
            bool(counts.get(reason)) for reason in RUNBOOK_ACTION_CONSTRAINT_REASONS
        )

    @staticmethod
    def _rejected_candidate_policy_facts(
        selection: SelectionResult,
    ) -> dict[str, Any] | None:
        raw_candidates = selection.selection_reason.get("rejected_candidates")
        if not isinstance(raw_candidates, list):
            return None
        candidates: list[dict[str, Any]] = []
        fact_keys = (
            "land_id",
            "team_id",
            "level",
            "land_scope",
            "lineup_preset",
            "unlock_land_level",
            "unlock_land_scope",
            "unlock_lineup_preset",
        )
        for item in raw_candidates:
            if not isinstance(item, dict) or item.get("reason") not in RUNBOOK_ACTION_CONSTRAINT_REASONS:
                continue
            params = item.get("params")
            if not isinstance(params, dict):
                params = {}
            candidates.append(
                {
                    "action_type": item.get("action_type"),
                    "reason": item.get("reason"),
                    "facts": {key: params.get(key) for key in fact_keys if key in params},
                }
            )
        if not candidates:
            return None
        return {"source": "rejected_candidates", "candidates": candidates[:10]}

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
        *,
        policy_starved: bool = False,
    ) -> bool:
        """A tick is 'stuck' when vision cannot classify the page or no useful
        progress was made: unknown page, no selected action, or a pending/failed
        execution. Accumulating stuck ticks triggers an ESC recovery."""
        if summary.page_type in (None, "unknown"):
            return True
        if selection.selected_action is None:
            return not policy_starved
        if execution is not None and execution.status in ("failed", "pending"):
            return True
        return False

    def _recovery_input_block_reason(self) -> str | None:
        runner_mode = getattr(self.runner, "session_mode", None)
        if runner_mode in {SessionMode.LIVE, SessionMode.LIVE.value}:
            return "live ESC recovery is disabled until guarded key dispatch is calibrated"
        authority_check = getattr(
            self.runner,
            "input_authority_failure_reason",
            None,
        )
        if not callable(authority_check):
            return "runner does not expose input authority"
        try:
            authority_reason = authority_check()
        except Exception:  # noqa: BLE001
            logger.exception("input authority check failed")
            return "input authority check failed"
        if authority_reason is not None:
            return str(authority_reason)
        recovery_verdict = self._guard.recovery_verdict()
        return None if recovery_verdict.allowed else recovery_verdict.reason

    def _attempt_esc_recovery(
        self,
        *,
        iteration: int,
        strategy: str,
    ) -> str | None:
        block_reason = self._recovery_input_block_reason()
        if block_reason is not None:
            logger.warning(
                "tick %d: recovery input suppressed (%s)",
                iteration,
                block_reason,
            )
            return None
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

    def _record_trace_frame(
        self,
        frames: list[TraceFrameReference],
        *,
        iteration: int,
        role: TraceFrameRole,
        png: bytes,
        observation: ObservationSnapshot | None,
        attempt: int | None = None,
    ) -> TraceFrameReference | None:
        if self.trace_store is None or observation is None:
            return None
        reference = self.trace_store.save_frame(
            iteration=iteration,
            role=role,
            png=png,
            observation=observation,
            attempt=attempt,
        )
        frames.append(reference)
        return reference

    def _continue_action_flow(
        self,
        *,
        iteration: int,
        action: CandidateAction,
        execution: ExecutionResult,
        trace_frames: list[TraceFrameReference],
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
            flow_captured_at = datetime.now(UTC)
            captured = _capture_bridge_frame(self.bridge)
            png = captured.png
            if captured.capture_geometry is None:
                self.state, flow_observe = self.vision_sync.sync(
                    png,
                    state=self.state,
                    captured_at=flow_captured_at,
                )
            else:
                self.state, flow_observe = self.vision_sync.sync(
                    png,
                    state=self.state,
                    captured_at=flow_captured_at,
                    capture_geometry=captured.capture_geometry,
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
        self._apply_lineup_preset_bindings(derived)
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
        if _action_target_fingerprint(next_action) != _action_target_fingerprint(action):
            return _fail(
                "action flow changed the verifier target",
                next_action=next_action,
            )

        verdict = self._guard.action_verdict(next_action, state=derived)
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

        flow_preflight = _post_action_verifier_preflight_failure(
            self.runner,
            next_action,
            flow_observe.observation,
            self.state.model_dump(mode="json"),
        )
        if flow_preflight is not None:
            return _fail(
                "post-action verifier preflight failed before terminal dispatch: "
                f"{flow_preflight.reason}",
                next_action=next_action,
            )

        if terminal_mutating_target(next_action) is not None:
            self._record_trace_frame(
                trace_frames,
                iteration=iteration,
                role=TraceFrameRole.TERMINAL_DISPATCH,
                png=png,
                observation=flow_observe.observation,
            )
        _reset_input_trace(self.ui_actions)
        terminal_execution = _run_action(
            self.runner,
            next_action,
            flow_observe.observation,
            frame_bytes=png,
        )
        terminal_dispatch_completed_at = datetime.now(UTC)
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
            baseline_observation=flow_observe.observation,
            dispatch_completed_at=terminal_dispatch_completed_at,
            iteration=iteration,
            trace_frames=trace_frames,
        )
        return terminal_execution, verification, input_trace, flow_decision

    def _verify_after_action(
        self,
        *,
        action: CandidateAction,
        execution: ExecutionResult,
        baseline_observation: ObservationSnapshot | None,
        dispatch_completed_at: datetime,
        iteration: int,
        trace_frames: list[TraceFrameReference],
    ) -> tuple[ExecutionResult, dict[str, Any] | None]:
        spec = _post_action_verifier_spec(self.runner, action)
        if spec is None:
            return execution, None
        if execution.status != "ok":
            return execution, None
        if _requires_flow_continuation(execution):
            return execution, None
        if (
            execution.verification_status not in {"unknown", "unverified"}
            and action.action_type not in LOW_RISK_AUTOMATION_ACTIONS
        ):
            return execution, None

        verifier = spec.build()
        allow_fixture_source = _runner_allows_fixture_observation(self.runner)
        baseline_gate = validate_dispatch_observation(
            action,
            baseline_observation,
            now=dispatch_completed_at,
            max_age_seconds=_runner_observation_max_age(self.runner),
            allow_fixture_source=allow_fixture_source,
        )
        if (
            baseline_gate.decision == ObservationGateDecision.BLOCK
            or baseline_gate.verifier_state is None
            or baseline_observation is None
        ):
            result = VerificationResult(
                status=VerificationStatus.FAILED,
                reason=f"dispatch observation unavailable: {baseline_gate.reason}",
                timeout_seconds=spec.timeout_seconds,
            )
            payload = _verification_payload(
                action=action,
                spec=spec,
                result=result,
                attempts=0,
                summary=None,
                before_state=None,
                after_state=None,
                post_frame=None,
            )
            return (
                _execution_with_verification(
                    execution,
                    result=result,
                    payload=payload,
                    status="failed",
                    failure_reason=f"post-action verifier failed: {result.reason}",
                    recovery_required=True,
                ),
                payload,
            )

        deadline = time.monotonic() + spec.timeout_seconds
        attempts = 0

        while True:
            attempts += 1
            try:
                post_captured_at = datetime.now(UTC)
                captured = _capture_bridge_frame(self.bridge)
                png = captured.png
                if captured.capture_geometry is None:
                    self.state, summary = self.vision_sync.sync(
                        png,
                        state=self.state,
                        captured_at=post_captured_at,
                    )
                else:
                    self.state, summary = self.vision_sync.sync(
                        png,
                        state=self.state,
                        captured_at=post_captured_at,
                        capture_geometry=captured.capture_geometry,
                    )
                post_frame = self._record_trace_frame(
                    trace_frames,
                    iteration=iteration,
                    role=TraceFrameRole.POST_ACTION,
                    png=png,
                    observation=summary.observation,
                    attempt=attempts,
                )
                post_gate = validate_post_observation(
                    action,
                    baseline_observation,
                    summary.observation,
                    dispatch_completed_at=dispatch_completed_at,
                    now=datetime.now(UTC),
                    max_age_seconds=_runner_observation_max_age(self.runner),
                    allow_fixture_source=allow_fixture_source,
                )
                if (
                    post_gate.decision == ObservationGateDecision.BLOCK
                    or post_gate.verifier_state is None
                ):
                    result = VerificationResult(
                        status=VerificationStatus.UNKNOWN,
                        reason=post_gate.reason,
                        timeout_seconds=spec.timeout_seconds,
                    )
                else:
                    result = verifier.verify(
                        baseline_gate.verifier_state,
                        post_gate.verifier_state,
                    )
                payload = _verification_payload(
                    action=action,
                    spec=spec,
                    result=result,
                    attempts=attempts,
                    summary=summary,
                    before_state=baseline_gate.verifier_state,
                    after_state=post_gate.verifier_state,
                    post_frame=post_frame,
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
                    before_state=None,
                    after_state=None,
                    post_frame=None,
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


def _constrain_evidence_selection(
    selection: SelectionResult,
    *,
    required_action_type: ActionType,
    observation: ObservationSnapshot | None,
    now: datetime,
    max_age_seconds: float,
    allow_fixture_source: bool,
) -> SelectionResult:
    """Select only a current-frame-bound candidate for an evidence run.

    The ordinary selector may rank another action first, and derived state can
    contain stale candidates that are absent from the current observation. An
    evidence run is authorized for one exact action type, so scan its ranked
    candidates in order and retain the first one that independently passes the
    dispatch-observation gate. If none passes, select nothing and dispatch no
    input.
    """

    if required_action_type not in LOW_RISK_AUTOMATION_ACTIONS:
        raise ValueError("evidence action must be a calibrated low-risk action")

    evaluated: list[dict[str, Any]] = []
    selected: CandidateAction | None = None
    for candidate in selection.ranked_actions:
        if candidate.action_type != required_action_type:
            continue
        verdict = validate_dispatch_observation(
            candidate,
            observation,
            now=now,
            max_age_seconds=max_age_seconds,
            allow_fixture_source=allow_fixture_source,
        )
        evaluated.append(
            {
                "action_id": candidate.action_id,
                "decision": verdict.decision.value,
                "reason": verdict.reason,
            }
        )
        if verdict.decision == ObservationGateDecision.ALLOW:
            selected = candidate
            break

    reason = dict(selection.selection_reason)
    reason["evidence_action_constraint"] = {
        "required_action_type": required_action_type.value,
        "decision": "selected" if selected is not None else "no_current_frame_candidate",
        "evaluated_candidates": evaluated,
    }
    reason["selected_score"] = selected.score_total if selected is not None else None
    reason["summary"] = (
        f"Evidence capture selected current-frame-bound {required_action_type.value}."
        if selected is not None
        else (
            "Evidence capture dispatched no input: no current-frame-bound "
            f"{required_action_type.value} candidate passed validation."
        )
    )
    return selection.model_copy(
        update={
            "selected_action": selected,
            "selection_reason": reason,
            "next_replan_time": None,
        }
    )


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
    frame_evidence: list[TraceFrameReference] | None = None,
) -> TickTrace:
    action = selection.selected_action
    screenshot_size = _image_size_from_png(png)
    all_vision_traces = list(vision_summary.image_traces)
    if vision_traces:
        all_vision_traces.extend(vision_traces)
    input_events = list(input_trace or [])
    frames = list(frame_evidence or [])
    primary_frame = next(
        (
            frame
            for frame in reversed(frames)
            if frame.role == TraceFrameRole.TERMINAL_DISPATCH
        ),
        frames[0] if frames else None,
    )
    primary_observation = (
        dict(primary_frame.observation)
        if primary_frame is not None
        else _observation_payload(vision_summary.observation)
    )
    return TickTrace(
        iteration=iteration,
        created_at=started_at,
        current_phase=TracePhase.TRACE,
        screenshot=ScreenshotTraceMetadata(
            path=primary_frame.path if primary_frame is not None else screenshot_path,
            raw_size=(
                _image_size_from_frame_reference(primary_frame)
                or screenshot_size
                or _image_size_from_trace(all_vision_traces, "raw_size")
            ),
            prepared_size=_image_size_from_trace(all_vision_traces, "prepared_size"),
            display_coordinate_space=_coordinate_space_from_input(input_events, "display_coordinate_space"),
            window_coordinate_space=_coordinate_space_from_input(input_events, "window_coordinate_space"),
            coordinates=_coordinate_metadata_from_input_trace(input_events),
            metadata={
                "vision": all_vision_traces,
                "input_events": input_events,
                "observation": primary_observation,
                "frames": [frame.model_dump(mode="json") for frame in frames],
            },
        ),
        frames=frames,
        observe=TraceStep(
            phase=TracePhase.OBSERVE,
            outputs={
                "page_type": vision_summary.page_type,
                "domains_run": list(vision_summary.domains_run),
                "unknown_domains": list(vision_summary.unknown_domains),
                "notes": list(vision_summary.notes),
                "observation": _observation_payload(vision_summary.observation),
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
            "unknown_domains": list(vision_summary.unknown_domains),
            "notes": list(vision_summary.notes),
            "image_traces": all_vision_traces,
            "observation": _observation_payload(vision_summary.observation),
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


def _post_action_verifier_spec(
    runner: Any,
    action: CandidateAction,
) -> VerifierSpec | None:
    registry = getattr(runner, "verifier_registry", None)
    if not isinstance(registry, VerifierRegistry):
        return None
    try:
        return registry.get_for_action(action)
    except ValueError:
        return None


def _post_action_verifier_preflight_failure(
    runner: Any,
    action: CandidateAction,
    observation: ObservationSnapshot | None,
    before_state: dict[str, Any],
) -> VerificationResult | None:
    if action.action_type in UI_ACTIONS_REQUIRING_VERIFIER:
        authority_failure = _runner_input_authority_failure(runner)
        if authority_failure is not None:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                reason=authority_failure,
                timeout_seconds=None,
            )
    if (
        action.action_type in LOW_RISK_AUTOMATION_ACTIONS
        and not _runner_supports_observation_dispatch(runner)
    ):
        return VerificationResult(
            status=VerificationStatus.FAILED,
            reason="runner does not support observation-bound dispatch",
            timeout_seconds=None,
        )
    registry = getattr(runner, "verifier_registry", None)
    if not isinstance(registry, VerifierRegistry):
        if action.action_type in UI_ACTIONS_REQUIRING_VERIFIER:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                reason="runner does not expose a verifier registry",
                timeout_seconds=None,
            )
        return None
    gate = registry.evaluate_action(action)
    if not gate.allowed:
        return VerificationResult(
            status=VerificationStatus.FAILED,
            reason=gate.reason,
            timeout_seconds=gate.timeout_seconds,
        )
    observation_gate = validate_dispatch_observation(
        action,
        observation,
        max_age_seconds=_runner_observation_max_age(runner),
        allow_fixture_source=_runner_allows_fixture_observation(runner),
    )
    if observation_gate.decision == ObservationGateDecision.BLOCK:
        return VerificationResult(
            status=VerificationStatus.FAILED,
            reason=observation_gate.reason,
            timeout_seconds=gate.timeout_seconds,
        )
    if observation_gate.verifier_state is not None:
        before_state = observation_gate.verifier_state
    try:
        spec = registry.get_for_action(action)
        if spec is None:
            return None
        result = spec.build().validate_before(before_state)
    except ValueError as exc:
        return VerificationResult(
            status=VerificationStatus.FAILED,
            reason=f"verifier could not be built: {exc}",
            timeout_seconds=None,
        )
    return None if result.verified else result


def _run_action(
    runner: Any,
    action: CandidateAction,
    observation: ObservationSnapshot | None,
    *,
    frame_bytes: bytes | None = None,
) -> ExecutionResult:
    if isinstance(runner, UIActionRunner):
        return runner.run(
            action,
            observation=observation,
            frame_bytes=frame_bytes,
        )
    if action.action_type in LOW_RISK_AUTOMATION_ACTIONS:
        return runner.run(action, observation=observation)
    return runner.run(action)


def _runner_input_authority_failure(runner: Any) -> str | None:
    check = getattr(runner, "input_authority_failure_reason", None)
    if not callable(check):
        return "runner does not expose an input-authority check"
    try:
        reason = check()
    except Exception as exc:  # noqa: BLE001
        return f"runner input-authority check failed: {exc}"
    if reason is None:
        return None
    if not isinstance(reason, str) or not reason.strip():
        return "runner input-authority check returned an invalid result"
    return reason


def _runner_supports_observation_dispatch(runner: Any) -> bool:
    run = getattr(runner, "run", None)
    if not callable(run):
        return False
    try:
        parameters = inspect.signature(run).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        parameter.name == "observation"
        or parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


def _runner_observation_max_age(runner: Any) -> float:
    value = getattr(runner, "observation_max_age_seconds", 30.0)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 30.0
    return parsed if math.isfinite(parsed) and parsed > 0 else 30.0


def _runner_allows_fixture_observation(runner: Any) -> bool:
    return getattr(runner, "allows_offline_fixture_observations", False) is True


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
        "unknown_domains": list(summary.unknown_domains),
        "notes": list(summary.notes),
        "image_traces": list(summary.image_traces),
        "observation": _observation_payload(summary.observation),
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
    before_state: Mapping[str, Any] | None,
    after_state: Mapping[str, Any] | None,
    post_frame: TraceFrameReference | None,
) -> dict[str, Any]:
    target_identity = _verification_target_identity(action)
    post_action_delta = (
        structured_matching_deltas(
            spec.expected_deltas,
            before_state,
            after_state,
        )
        if (
            result.status == VerificationStatus.VERIFIED
            and before_state is not None
            and after_state is not None
        )
        else []
    )
    return {
        "action_type": action.action_type.value,
        "target": target_identity,
        "target_identity": target_identity,
        "target_details": _verification_target(action),
        "post_action_delta": post_action_delta,
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
            "unknown_domains": list(summary.unknown_domains) if summary else [],
            "notes": list(summary.notes) if summary else [],
            "image_traces": list(summary.image_traces) if summary else [],
            "observation": _observation_payload(summary.observation) if summary else None,
            "frame": post_frame.model_dump(mode="json") if post_frame else None,
        },
    }


def _observation_payload(
    observation: ObservationSnapshot | None,
) -> dict[str, Any] | None:
    if observation is None:
        return None
    return {
        "observation_id": observation.observation_id,
        "captured_at": observation.captured_at.isoformat(),
        "frame_sha256": observation.frame_sha256,
        "frame_size": list(observation.frame_size) if observation.frame_size else None,
        "capture_geometry": (
            observation.capture_geometry.model_dump(mode="json")
            if observation.capture_geometry is not None
            else None
        ),
        "page_type": observation.page_type,
        "domains_run": list(observation.domains_run),
        "unknown_domains": list(observation.unknown_domains),
        "source": observation.source,
    }


def _capture_bridge_frame(bridge: _Screenshotter) -> _CapturedFrame:
    capture = getattr(bridge, "screenshot_capture", None)
    if callable(capture):
        shot = capture()
        png = getattr(shot, "png", None)
        frame_sha256 = getattr(shot, "frame_sha256", None)
        geometry = getattr(shot, "capture_geometry", None)
        if not isinstance(png, bytes) or not isinstance(geometry, CaptureGeometry):
            raise RuntimeError("bridge screenshot capture binding is invalid")
        if hashlib.sha256(png).hexdigest() != frame_sha256:
            raise RuntimeError("bridge screenshot capture hash binding is invalid")
        return _CapturedFrame(png=png, capture_geometry=geometry)
    if getattr(bridge, "capture_geometry_version", None) is not None:
        raise RuntimeError(
            "capture-geometry bridge lacks screenshot_capture; update the bridge client"
        )
    png = bridge.screenshot()
    if not isinstance(png, bytes):
        raise RuntimeError("screenshot bridge returned non-bytes payload")
    return _CapturedFrame(png=png, capture_geometry=None)


def _verification_target(action: CandidateAction) -> dict[str, Any]:
    target_fields = {
        ActionType.CLAIM_CHAPTER_REWARD: ("chapter_id",),
        ActionType.RECRUIT_SOLDIERS: ("team_id",),
        ActionType.UPGRADE_BUILDING: (
            "building_id",
            "building_name",
            "current_level",
            "target_level",
        ),
    }.get(action.action_type, ())
    return {
        field: action.params[field]
        for field in target_fields
        if field in action.params
    }


def _verification_target_identity(action: CandidateAction) -> dict[str, Any]:
    target_fields = {
        ActionType.CLAIM_CHAPTER_REWARD: ("chapter_id",),
        ActionType.RECRUIT_SOLDIERS: ("team_id",),
        ActionType.UPGRADE_BUILDING: (
            "building_name",
            "current_level",
            "target_level",
        ),
    }.get(action.action_type, ())
    return {
        field: action.params[field]
        for field in target_fields
        if field in action.params
    }


def _action_target_fingerprint(action: CandidateAction) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(_verification_target(action).items()))


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


def _image_size_from_frame_reference(
    frame: TraceFrameReference | None,
) -> ImageSize | None:
    if frame is None:
        return None
    size = frame.observation.get("frame_size")
    if (
        not isinstance(size, list)
        or len(size) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) for value in size)
        or size[0] <= 0
        or size[1] <= 0
    ):
        return None
    return ImageSize(width=size[0], height=size[1])


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
