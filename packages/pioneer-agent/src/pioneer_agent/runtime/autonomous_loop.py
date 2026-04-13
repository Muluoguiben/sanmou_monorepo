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
from typing import Protocol

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import ExecutionResult, RuntimeState, SelectionResult
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.executor.ui_runner import UIActionRunner
from pioneer_agent.perception.vision_sync import VisionSync, VisionSyncSummary
from pioneer_agent.selector.action_selector import ActionSelector
from pioneer_agent.storage.loop_logger import LoopLogger

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
    ) -> None:
        self.bridge = bridge
        self.vision_sync = vision_sync
        self.ui_actions = ui_actions
        self.selector = selector or ActionSelector()
        self.deriver = deriver or StateDeriver()
        self.runner = runner or UIActionRunner(ui_actions)
        self.sleeper = sleeper
        self.loop_logger = loop_logger
        self.state = RuntimeState()

    def tick(self, iteration: int) -> TickResult:
        started_at = datetime.now()
        t0 = time.monotonic()
        png = self.bridge.screenshot()
        logger.info("tick %d: captured %d bytes", iteration, len(png))

        self.state, vision_summary = self.vision_sync.sync(
            png, state=self.state, captured_at=started_at
        )
        logger.info("tick %d: page=%s domains=%s", iteration, vision_summary.page_type, vision_summary.domains_run)

        derived = self.deriver.derive(self.state)
        selection = self.selector.select(derived)

        execution: ExecutionResult | None = None
        sleep_s = IDLE_SLEEP_S
        if selection.selected_action is not None:
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

        if self.loop_logger is not None:
            self.loop_logger.log_tick(
                iteration=iteration,
                started_at=started_at,
                elapsed_s=time.monotonic() - t0,
                png=png,
                vision_summary=vision_summary,
                selection=selection,
                execution=execution,
                sleep_s=sleep_s,
            )

        return TickResult(iteration=iteration, summary=vision_summary, selection=selection,
                          execution=execution, sleep_s=sleep_s)

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
