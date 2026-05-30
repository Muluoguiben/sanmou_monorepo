"""Autonomous decision loop: screenshot → vision → decide → act → repeat.

Glues together bridge_client (observe), VisionSync (extract), ActionSelector
(plan), and UIActionRunner (act). The loop is intentionally thin — all real
work lives in the components; this module just sequences them and handles
the wait/sleep cadence between ticks.
"""
from __future__ import annotations

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
        dry_run: bool = False,
        stuck_threshold: int = STUCK_ESC_THRESHOLD,
        post_action_verify_poll_interval_s: float = 1.0,
    ) -> None:
        self.bridge = bridge
        self.vision_sync = vision_sync
        self.ui_actions = ui_actions
        self.selector = selector or ActionSelector()
        self.deriver = deriver or StateDeriver()
        self.runner = runner or UIActionRunner(ui_actions)
        self.sleeper = sleeper
        self.loop_logger = loop_logger
        self.trace_store = trace_store
        self.kill_switch = kill_switch
        self.dry_run = dry_run
        self.stuck_threshold = stuck_threshold
        self.post_action_verify_poll_interval_s = post_action_verify_poll_interval_s
        self._stuck_count = 0
        self.state = RuntimeState()

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
        selection = self.selector.select(derived)
        pre_action_state = self.state.model_dump(mode="json")

        execution: ExecutionResult | None = None
        post_action_verification: dict[str, Any] | None = None
        input_trace: list[dict] = []
        sleep_s = IDLE_SLEEP_S
        if selection.selected_action is not None:
            if self.kill_switch is not None and self.kill_switch.is_triggered():
                logger.warning(
                    "tick %d: kill switch active — blocking action=%s",
                    iteration,
                    selection.selected_action.action_type.value,
                )
                execution = ExecutionResult(
                    action_id=selection.selected_action.action_id,
                    status="blocked",
                    verification_status="not_applicable",
                    failure_reason="manual kill switch is active",
                    recovery_required=False,
                    summary={
                        "action_type": selection.selected_action.action_type.value,
                        "blocked_by": "kill_switch",
                    },
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
            sleep_s = WAIT_SLEEP_S.get(selection.selected_action.action_type, DEFAULT_SLEEP_S)
        else:
            logger.info("tick %d: no selected action — idle", iteration)

        state_after = self.state.model_dump(mode="json")
        recovery_strategy: str | None = None
        if self._is_stuck(vision_summary, selection, execution):
            self._stuck_count += 1
            if self._stuck_count >= self.stuck_threshold and not self.dry_run:
                logger.warning(
                    "tick %d: stuck for %d ticks — sending ESC to recover",
                    iteration, self._stuck_count,
                )
                try:
                    self.ui_actions.close_popup()
                    recovery_strategy = "esc_close_popup"
                except Exception:  # noqa: BLE001
                    logger.exception("ESC recovery failed")
                    recovery_strategy = "esc_close_popup_failed"
                self._stuck_count = 0
                sleep_s = DEFAULT_SLEEP_S
        else:
            self._stuck_count = 0

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
                )
            )
            self.trace_store.append(trace)

        return TickResult(iteration=iteration, summary=vision_summary, selection=selection,
                          execution=execution, sleep_s=sleep_s)

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
        metadata={"loop_contract": [phase.value for phase in LOOP_PHASE_ORDER]},
    )


def _post_action_verifier_spec(runner: Any, action_type: ActionType) -> VerifierSpec | None:
    registry = getattr(runner, "verifier_registry", None)
    if not isinstance(registry, VerifierRegistry):
        return None
    return registry.get(action_type)


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
