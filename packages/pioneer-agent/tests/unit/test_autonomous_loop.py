"""Tests for the autonomous observe → plan → act loop."""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ExecutionResult, SelectionResult
from pioneer_agent.runtime.autonomous_loop import (
    DEFAULT_SLEEP_S,
    IDLE_SLEEP_S,
    WAIT_SLEEP_S,
    AutonomousLoop,
)


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "stub"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _ScriptedVision:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = payloads
        self.calls = 0

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        p = self._payloads[self.calls]
        self.calls += 1
        return _StubResult(data=p)


class _StubBridge:
    def __init__(self) -> None:
        self.shots = 0

    def screenshot(self, save_path=None):  # noqa: ANN001
        import io

        from PIL import Image

        self.shots += 1
        img = Image.new("RGB", (1920, 1080), (0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def click(self, x, y, button="left"):  # noqa: ANN001
        return {"status": "ok"}

    def drag(self, *a, **kw):  # noqa: ANN001
        return {"status": "ok"}

    def key_press(self, key, modifiers=None):  # noqa: ANN001
        return {"status": "ok"}


class _StubSelector:
    def __init__(self, action: CandidateAction | None) -> None:
        self.action = action

    def select(self, _state):  # noqa: ANN001
        return SelectionResult(
            selected_action=self.action,
            ranked_actions=[self.action] if self.action else [],
        )


class _StubDeriver:
    def derive(self, state):  # noqa: ANN001
        return state


class _StubRunner:
    def __init__(self) -> None:
        self.actions: list[CandidateAction] = []

    def run(self, action):  # noqa: ANN001
        self.actions.append(action)
        return ExecutionResult(action_id=action.action_id, status="ok")


class AutonomousLoopTests(unittest.TestCase):
    def _loop(self, *, action: CandidateAction | None, vision_payloads: list[dict[str, Any]]):
        from pioneer_agent.executor.ui_actions import UIActions
        from pioneer_agent.perception.ui_registry import UIButton, UIRegistry
        from pioneer_agent.perception.vision_sync import VisionSync

        bridge = _StubBridge()
        vision = _ScriptedVision(vision_payloads)
        registry = UIRegistry({"esc_close": UIButton("esc_close", "关闭", 0.5, 0.5)})
        ui = UIActions(bridge, registry, vision=vision)  # type: ignore[arg-type]
        sleeper_calls: list[float] = []
        loop = AutonomousLoop(
            bridge=bridge,
            vision_sync=VisionSync(vision),  # type: ignore[arg-type]
            ui_actions=ui,
            selector=_StubSelector(action),
            deriver=_StubDeriver(),  # type: ignore[arg-type]
            runner=_StubRunner(),  # type: ignore[arg-type]
            sleeper=sleeper_calls.append,
        )
        return loop, bridge, sleeper_calls

    def test_tick_no_action_returns_idle_sleep(self) -> None:
        loop, bridge, _ = self._loop(
            action=None,
            vision_payloads=[{"page_type": "main_map", "resources": {}}],
        )
        result = loop.tick(0)
        self.assertEqual(bridge.shots, 1)
        self.assertEqual(result.summary.page_type, "main_map")
        self.assertIsNone(result.execution)
        self.assertEqual(result.sleep_s, IDLE_SLEEP_S)

    def test_tick_wait_action_uses_long_sleep(self) -> None:
        action = CandidateAction(
            action_id="w1", action_type=ActionType.WAIT_FOR_STAMINA,
        )
        loop, _bridge, _ = self._loop(
            action=action,
            vision_payloads=[{"page_type": "main_map", "resources": {}}],
        )
        result = loop.tick(0)
        self.assertEqual(result.execution.status, "ok")
        self.assertEqual(result.sleep_s, WAIT_SLEEP_S[ActionType.WAIT_FOR_STAMINA])

    def test_tick_default_sleep_for_other_actions(self) -> None:
        action = CandidateAction(
            action_id="u1", action_type=ActionType.UPGRADE_BUILDING,
            params={"building_name": "征兵所"},
        )
        loop, _bridge, _ = self._loop(
            action=action,
            vision_payloads=[{"page_type": "main_map", "resources": {}}],
        )
        result = loop.tick(0)
        self.assertEqual(result.sleep_s, DEFAULT_SLEEP_S)

    def test_run_forever_respects_max_iterations(self) -> None:
        loop, bridge, sleeps = self._loop(
            action=None,
            vision_payloads=[{"page_type": "main_map", "resources": {}}] * 3,
        )
        loop.run_forever(max_iterations=3)
        self.assertEqual(bridge.shots, 3)
        self.assertEqual(len(sleeps), 3)

    def test_tick_writes_loop_logger_when_provided(self) -> None:
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from pioneer_agent.storage.loop_logger import LoopLogger

        with TemporaryDirectory() as tmp:
            loop, _bridge, _ = self._loop(
                action=None,
                vision_payloads=[{"page_type": "main_map", "resources": {}}],
            )
            loop.loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            loop.tick(7)
            payload = json.loads((Path(tmp) / "loop.jsonl").read_text().strip())
            self.assertEqual(payload["iteration"], 7)
            self.assertEqual(payload["page_type"], "main_map")
            self.assertIsNone(payload["selected_action_type"])

    def test_run_forever_swallows_tick_errors(self) -> None:
        class _ExplodingVision:
            def extract(self, *a, **kw):  # noqa: ANN001
                raise RuntimeError("vision down")

        from pioneer_agent.executor.ui_actions import UIActions
        from pioneer_agent.perception.ui_registry import UIButton, UIRegistry
        from pioneer_agent.perception.vision_sync import VisionSync

        bridge = _StubBridge()
        ui = UIActions(bridge, UIRegistry({"k": UIButton("k", "k", 0.5, 0.5)}))  # type: ignore[arg-type]
        sleeps: list[float] = []
        loop = AutonomousLoop(
            bridge=bridge,
            vision_sync=VisionSync(_ExplodingVision()),  # type: ignore[arg-type]
            ui_actions=ui,
            selector=_StubSelector(None),
            deriver=_StubDeriver(),  # type: ignore[arg-type]
            runner=_StubRunner(),  # type: ignore[arg-type]
            sleeper=sleeps.append,
        )
        loop.run_forever(max_iterations=2)
        self.assertEqual(sleeps, [IDLE_SLEEP_S, IDLE_SLEEP_S])


if __name__ == "__main__":
    unittest.main()
