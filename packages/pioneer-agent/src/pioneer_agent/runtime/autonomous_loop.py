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
from typing import Protocol

from PIL import Image, UnidentifiedImageError

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import ExecutionResult, RuntimeState, SelectionResult
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.executor.ui_runner import UIActionRunner
from pioneer_agent.perception.vision_sync import VisionSync, VisionSyncSummary
from pioneer_agent.selector.action_selector import ActionSelector
from pioneer_agent.storage.loop_logger import LoopLogger
from pioneer_agent.storage.trace_store import (
    ImageSize,
    ScreenshotTraceMetadata,
    TickTrace,
    TracePhase,
    TraceStep,
    TraceStore,
)

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
        dry_run: bool = False,
        stuck_threshold: int = STUCK_ESC_THRESHOLD,
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
        self.dry_run = dry_run
        self.stuck_threshold = stuck_threshold
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
        state_after = self.state.model_dump(mode="json")

        execution: ExecutionResult | None = None
        sleep_s = IDLE_SLEEP_S
        if selection.selected_action is not None:
            if self.dry_run:
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
                execution = self.runner.run(selection.selected_action)
                logger.info(
                    "tick %d: action=%s status=%s",
                    iteration,
                    selection.selected_action.action_type.value,
                    execution.status,
                )
            sleep_s = WAIT_SLEEP_S.get(selection.selected_action.action_type, DEFAULT_SLEEP_S)
        else:
            logger.info("tick %d: no selected action — idle", iteration)

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
            self.trace_store.append(
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
                )
            )

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
) -> TickTrace:
    action = selection.selected_action
    screenshot_size = _image_size_from_png(png)
    return TickTrace(
        iteration=iteration,
        created_at=started_at,
        current_phase=TracePhase.TRACE,
        screenshot=ScreenshotTraceMetadata(
            path=screenshot_path,
            raw_size=screenshot_size,
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
            outputs={"status": execution.verification_status if execution else "not_applicable"},
        ),
        trace=TraceStep(
            phase=TracePhase.TRACE,
            outputs={"sleep_s": sleep_s, "elapsed_s": round(elapsed_s, 3)},
        ),
        recover=TraceStep(
            phase=TracePhase.RECOVER,
            recovery_strategy=recovery_strategy,
        ) if recovery_strategy else None,
        state_before=state_before,
        vision={
            "page_type": vision_summary.page_type,
            "domains_run": list(vision_summary.domains_run),
            "notes": list(vision_summary.notes),
        },
        state_after=state_after,
        selected_action=action.model_dump(mode="json") if action else None,
        ranked_actions=[item.model_dump(mode="json") for item in selection.ranked_actions],
        execution=execution.model_dump(mode="json") if execution else None,
        verification={"status": execution.verification_status} if execution else None,
        recovery={"strategy": recovery_strategy} if recovery_strategy else None,
        failure_reason=execution.failure_reason if execution else None,
        next_recovery_strategy=recovery_strategy,
    )


def _image_size_from_png(png: bytes) -> ImageSize | None:
    try:
        with Image.open(BytesIO(png)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError):
        return None
    return ImageSize(width=width, height=height)
