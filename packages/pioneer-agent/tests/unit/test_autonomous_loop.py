"""Tests for the autonomous observe → plan → act loop."""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from pioneer_agent.core.device import CapabilityFlags
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ExecutionResult, SelectionResult
from pioneer_agent.executor.ui_runner import UIActionRunner
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
        self._trace_events: list[dict[str, Any]] = []

    def reset_trace_events(self) -> None:
        self._trace_events.clear()

    def consume_trace_events(self) -> list[dict[str, Any]]:
        events = list(self._trace_events)
        self._trace_events.clear()
        return events

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        p = self._payloads[self.calls]
        self.calls += 1
        self._trace_events.append(
            {
                "model": "stub",
                "raw_size": {"width": 1920, "height": 1080},
                "prepared_size": {"width": 1280, "height": 720},
                "resized": True,
            }
        )
        return _StubResult(data=p)


class _StubBridge:
    def __init__(self) -> None:
        self.shots = 0
        self.keys: list[str] = []

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
        self.keys.append(key)
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


def _chapter_resource_payload() -> dict[str, Any]:
    return {"page_type": "chapter", "resources": {}}


def _chapter_panel_payload(*, claimable: bool) -> dict[str, Any]:
    payload = {
        "current_chapter_id": 17,
        "chapter_claimable": claimable,
        "claim_button_visible": claimable,
        "claim_button_enabled": claimable,
        "tasks": [],
    }
    if claimable:
        payload.update(
            {
                "claim_x_min": 700,
                "claim_y_min": 800,
                "claim_x_max": 900,
                "claim_y_max": 900,
            }
        )
    return payload


def _claim_button_param() -> dict[str, Any]:
    return {
        "visible": True,
        "enabled": True,
        "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
    }


class AutonomousLoopTests(unittest.TestCase):
    def _loop(self, *, action: CandidateAction | None, vision_payloads: list[dict[str, Any]],
              dry_run: bool = False, stuck_threshold: int = 3,
              runner: Any = None, ui_actions: Any = None):
        from pioneer_agent.executor.ui_actions import UIActions
        from pioneer_agent.perception.ui_registry import UIButton, UIRegistry
        from pioneer_agent.perception.vision_sync import VisionSync

        bridge = _StubBridge()
        vision = _ScriptedVision(vision_payloads)
        registry = UIRegistry({"esc_close": UIButton("esc_close", "关闭", 0.5, 0.5)})
        ui = ui_actions if ui_actions is not None else UIActions(bridge, registry, vision=vision)  # type: ignore[arg-type]
        sleeper_calls: list[float] = []
        loop = AutonomousLoop(
            bridge=bridge,
            vision_sync=VisionSync(vision),  # type: ignore[arg-type]
            ui_actions=ui,
            selector=_StubSelector(action),
            deriver=_StubDeriver(),  # type: ignore[arg-type]
            runner=runner if runner is not None else _StubRunner(),  # type: ignore[arg-type]
            sleeper=sleeper_calls.append,
            dry_run=dry_run,
            stuck_threshold=stuck_threshold,
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

    def test_tick_writes_trace_store_when_provided(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from pioneer_agent.storage.trace_store import TracePhase, TraceStore

        with TemporaryDirectory() as tmp:
            loop, _bridge, _ = self._loop(
                action=None,
                vision_payloads=[{"page_type": "main_map", "resources": {}}],
            )
            loop.trace_store = TraceStore(Path(tmp) / "trace.jsonl")
            loop.tick(3)

            records = loop.trace_store.read()
            self.assertEqual(len(records), 1)
            trace = records[0]
            self.assertEqual(trace.iteration, 3)
            self.assertEqual(trace.current_phase, TracePhase.TRACE)
            self.assertEqual(trace.observe.outputs["page_type"], "main_map")
            self.assertEqual(trace.decide.outputs["selected_action_id"], None)
            self.assertEqual(trace.act.outputs["status"], "idle")
            self.assertEqual(trace.screenshot.raw_size.width, 1920)
            self.assertEqual(trace.screenshot.raw_size.height, 1080)
            self.assertEqual(trace.screenshot.prepared_size.width, 1280)
            self.assertEqual(trace.screenshot.metadata["vision"][0]["prepared_size"]["height"], 720)
            self.assertIsNotNone(trace.recover)
            self.assertEqual(trace.recover.outputs["status"], "not_required")
            self.assertEqual(trace.next_recovery_strategy, "none")
            self.assertEqual(
                trace.metadata["loop_contract"],
                ["observe", "decide", "act", "verify", "trace", "recover"],
            )

    def test_tick_trace_includes_ui_input_coordinates(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from pioneer_agent.executor.ui_actions import UIActions
        from pioneer_agent.perception.ui_registry import UIButton, UIRegistry
        from pioneer_agent.perception.vision_sync import VisionSync
        from pioneer_agent.storage.trace_store import TraceStore

        class _ClickingRunner:
            def __init__(self, ui: UIActions) -> None:
                self.ui = ui

            def run(self, action):  # noqa: ANN001
                out = self.ui.click_button("wu_jiang")
                return ExecutionResult(
                    action_id=action.action_id,
                    status="ok" if out.success else "failed",
                    summary={"click": out.trace},
                )

        with TemporaryDirectory() as tmp:
            action = CandidateAction(
                action_id="u1",
                action_type=ActionType.UPGRADE_BUILDING,
                params={"building_name": "征兵所"},
            )
            bridge = _StubBridge()
            vision = _ScriptedVision([{"page_type": "main_map", "resources": {}}])
            registry = UIRegistry({"wu_jiang": UIButton("wu_jiang", "武将", 0.5, 0.9)})
            ui = UIActions(bridge, registry, vision=vision)  # type: ignore[arg-type]
            loop = AutonomousLoop(
                bridge=bridge,
                vision_sync=VisionSync(vision),  # type: ignore[arg-type]
                ui_actions=ui,
                selector=_StubSelector(action),
                deriver=_StubDeriver(),  # type: ignore[arg-type]
                runner=_ClickingRunner(ui),  # type: ignore[arg-type]
                sleeper=lambda _seconds: None,
                trace_store=TraceStore(Path(tmp) / "trace.jsonl"),
            )

            loop.tick(0)

            trace = loop.trace_store.read()[0]
            self.assertEqual(trace.screenshot.coordinates[0].click_point.x, 960)
            self.assertEqual(trace.screenshot.coordinates[0].coordinate_space, "window:relative")
            self.assertEqual(trace.screenshot.metadata["input_events"][0]["target"]["key"], "wu_jiang")

    def test_tick_runs_post_action_verifier_after_low_risk_click(self) -> None:
        from pioneer_agent.executor.ui_actions import UIActions
        from pioneer_agent.perception.ui_registry import UIButton, UIRegistry
        from pioneer_agent.perception.vision_sync import VisionSync

        action = CandidateAction(
            action_id="claim-17",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
            params={"chapter_id": 17, "claim_button": _claim_button_param()},
        )
        bridge = _StubBridge()
        vision = _ScriptedVision(
            [
                _chapter_resource_payload(),
                _chapter_panel_payload(claimable=True),
                _chapter_resource_payload(),
                _chapter_panel_payload(claimable=False),
            ]
        )
        ui = UIActions(  # type: ignore[arg-type]
            bridge,
            UIRegistry({"esc_close": UIButton("esc_close", "close", 0.5, 0.5)}),
            vision=vision,
        )
        runner = UIActionRunner(ui, capabilities=CapabilityFlags(input_control=True))
        loop = AutonomousLoop(
            bridge=bridge,
            vision_sync=VisionSync(vision),  # type: ignore[arg-type]
            ui_actions=ui,
            selector=_StubSelector(action),
            deriver=_StubDeriver(),  # type: ignore[arg-type]
            runner=runner,
            sleeper=lambda _seconds: None,
            post_action_verify_poll_interval_s=0,
        )

        result = loop.tick(0)

        self.assertEqual(result.execution.status, "ok")
        self.assertEqual(result.execution.verification_status, "verified")
        verifier = result.execution.summary["post_action_verifier"]
        self.assertEqual(verifier["status"], "verified")
        self.assertEqual(verifier["checked"], ["progress.chapter_claimable"])
        self.assertEqual(verifier["post_observe"]["domains_run"], ["resource_bar", "chapter_panel"])
        self.assertFalse(loop.state.progress["chapter_claimable"])

    def test_tick_fails_action_when_post_action_verifier_does_not_match(self) -> None:
        from pioneer_agent.executor.ui_actions import UIActions
        from pioneer_agent.perception.ui_registry import UIButton, UIRegistry
        from pioneer_agent.perception.vision_sync import VisionSync

        action = CandidateAction(
            action_id="claim-17",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
            params={"chapter_id": 17, "claim_button": _claim_button_param()},
        )
        bridge = _StubBridge()
        vision = _ScriptedVision(
            [
                _chapter_resource_payload(),
                _chapter_panel_payload(claimable=True),
                _chapter_resource_payload(),
                _chapter_panel_payload(claimable=True),
            ]
        )
        ui = UIActions(  # type: ignore[arg-type]
            bridge,
            UIRegistry({"esc_close": UIButton("esc_close", "close", 0.5, 0.5)}),
            vision=vision,
        )
        runner = UIActionRunner(ui, capabilities=CapabilityFlags(input_control=True))
        loop = AutonomousLoop(
            bridge=bridge,
            vision_sync=VisionSync(vision),  # type: ignore[arg-type]
            ui_actions=ui,
            selector=_StubSelector(action),
            deriver=_StubDeriver(),  # type: ignore[arg-type]
            runner=runner,
            sleeper=lambda _seconds: None,
            post_action_verify_poll_interval_s=0,
        )

        result = loop.tick(0)

        self.assertEqual(result.execution.status, "failed")
        self.assertEqual(result.execution.verification_status, "failed")
        self.assertTrue(result.execution.recovery_required)
        self.assertIn("post-action verifier failed", result.execution.failure_reason or "")
        self.assertEqual(result.execution.summary["post_action_verifier"]["status"], "failed")
        self.assertEqual(bridge.keys, ["escape"])
        self.assertEqual(loop._stuck_count, 0)

    def test_tick_trace_records_immediate_recovery_after_verifier_failure(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from pioneer_agent.executor.ui_actions import UIActions
        from pioneer_agent.perception.ui_registry import UIButton, UIRegistry
        from pioneer_agent.perception.vision_sync import VisionSync
        from pioneer_agent.storage.trace_store import TraceStore

        with TemporaryDirectory() as tmp:
            action = CandidateAction(
                action_id="claim-17",
                action_type=ActionType.CLAIM_CHAPTER_REWARD,
                params={"chapter_id": 17, "claim_button": _claim_button_param()},
            )
            bridge = _StubBridge()
            vision = _ScriptedVision(
                [
                    _chapter_resource_payload(),
                    _chapter_panel_payload(claimable=True),
                    _chapter_resource_payload(),
                    _chapter_panel_payload(claimable=True),
                ]
            )
            ui = UIActions(  # type: ignore[arg-type]
                bridge,
                UIRegistry({"esc_close": UIButton("esc_close", "close", 0.5, 0.5)}),
                vision=vision,
            )
            runner = UIActionRunner(ui, capabilities=CapabilityFlags(input_control=True))
            loop = AutonomousLoop(
                bridge=bridge,
                vision_sync=VisionSync(vision),  # type: ignore[arg-type]
                ui_actions=ui,
                selector=_StubSelector(action),
                deriver=_StubDeriver(),  # type: ignore[arg-type]
                runner=runner,
                sleeper=lambda _seconds: None,
                trace_store=TraceStore(Path(tmp) / "trace.jsonl"),
                post_action_verify_poll_interval_s=0,
            )

            loop.tick(0)

            trace = loop.trace_store.read()[0]
            self.assertEqual(trace.recover.outputs["status"], "attempted")
            self.assertEqual(trace.recover.recovery_strategy, "esc_after_action_failure")
            self.assertEqual(trace.next_recovery_strategy, "esc_after_action_failure")
            self.assertEqual(trace.screenshot.metadata["input_events"][-1]["action"], "key_press")
            self.assertEqual(trace.screenshot.metadata["input_events"][-1]["key"], "escape")

    def test_trace_records_post_action_verifier_payload(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from pioneer_agent.executor.ui_actions import UIActions
        from pioneer_agent.perception.ui_registry import UIButton, UIRegistry
        from pioneer_agent.perception.vision_sync import VisionSync
        from pioneer_agent.storage.trace_store import TraceStore

        with TemporaryDirectory() as tmp:
            action = CandidateAction(
                action_id="claim-17",
                action_type=ActionType.CLAIM_CHAPTER_REWARD,
                params={"chapter_id": 17, "claim_button": _claim_button_param()},
            )
            bridge = _StubBridge()
            vision = _ScriptedVision(
                [
                    _chapter_resource_payload(),
                    _chapter_panel_payload(claimable=True),
                    _chapter_resource_payload(),
                    _chapter_panel_payload(claimable=False),
                ]
            )
            ui = UIActions(  # type: ignore[arg-type]
                bridge,
                UIRegistry({"esc_close": UIButton("esc_close", "close", 0.5, 0.5)}),
                vision=vision,
            )
            runner = UIActionRunner(ui, capabilities=CapabilityFlags(input_control=True))
            loop = AutonomousLoop(
                bridge=bridge,
                vision_sync=VisionSync(vision),  # type: ignore[arg-type]
                ui_actions=ui,
                selector=_StubSelector(action),
                deriver=_StubDeriver(),  # type: ignore[arg-type]
                runner=runner,
                sleeper=lambda _seconds: None,
                trace_store=TraceStore(Path(tmp) / "trace.jsonl"),
                post_action_verify_poll_interval_s=0,
            )

            loop.tick(0)

            trace = loop.trace_store.read()[0]
            self.assertEqual(trace.verify.outputs["status"], "verified")
            self.assertEqual(trace.verification["status"], "verified")
            self.assertEqual(
                trace.verify.outputs["post_action_verifier"]["checked"],
                ["progress.chapter_claimable"],
            )

    def test_dry_run_skips_runner_and_marks_execution(self) -> None:
        action = CandidateAction(
            action_id="u1", action_type=ActionType.UPGRADE_BUILDING,
            params={"building_name": "征兵所"},
        )
        runner = _StubRunner()
        loop, _bridge, _ = self._loop(
            action=action,
            vision_payloads=[
                {"page_type": "city", "resources": {}},
                {"page_type": "city", "buildings": []},
            ],
            dry_run=True,
            runner=runner,
        )
        result = loop.tick(0)
        self.assertEqual(runner.actions, [])
        self.assertIsNotNone(result.execution)
        self.assertEqual(result.execution.status, "dry_run")
        self.assertEqual(result.execution.verification_status, "not_applicable")
        self.assertEqual(result.sleep_s, DEFAULT_SLEEP_S)

    def test_kill_switch_blocks_runner_dispatch(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from pioneer_agent.safety.kill_switch import KillSwitch

        action = CandidateAction(
            action_id="u1",
            action_type=ActionType.UPGRADE_BUILDING,
            params={"building_name": "征兵所"},
        )
        runner = _StubRunner()

        with TemporaryDirectory() as tmp:
            kill_switch = KillSwitch(Path(tmp) / "STOP")
            kill_switch.trigger()
            loop, _bridge, _ = self._loop(
                action=action,
                vision_payloads=[
                    {"page_type": "city", "resources": {}},
                    {"page_type": "city", "buildings": []},
                ],
                runner=runner,
            )
            loop.kill_switch = kill_switch

            result = loop.tick(0)

        self.assertEqual(runner.actions, [])
        self.assertIsNotNone(result.execution)
        self.assertEqual(result.execution.status, "blocked")
        self.assertEqual(result.execution.summary["blocked_by"], "kill_switch")
        self.assertIn("kill switch", result.execution.failure_reason or "")

    def test_is_stuck_conditions(self) -> None:
        from pioneer_agent.perception.vision_sync import VisionSyncSummary

        action = CandidateAction(action_id="a", action_type=ActionType.WAIT_FOR_STAMINA)
        ok = SelectionResult(selected_action=action, ranked_actions=[action])
        no_act = SelectionResult(selected_action=None, ranked_actions=[])
        good_summary = VisionSyncSummary(page_type="city", domains_run=["resource_bar"], notes=[])
        bad_summary = VisionSyncSummary(page_type="unknown", domains_run=[], notes=[])
        none_summary = VisionSyncSummary(page_type=None, domains_run=[], notes=[])

        self.assertTrue(AutonomousLoop._is_stuck(bad_summary, ok, None))
        self.assertTrue(AutonomousLoop._is_stuck(none_summary, ok, None))
        self.assertTrue(AutonomousLoop._is_stuck(good_summary, no_act, None))
        self.assertTrue(AutonomousLoop._is_stuck(
            good_summary, ok, ExecutionResult(action_id="a", status="failed")))
        self.assertTrue(AutonomousLoop._is_stuck(
            good_summary, ok, ExecutionResult(action_id="a", status="pending")))
        self.assertFalse(AutonomousLoop._is_stuck(
            good_summary, ok, ExecutionResult(action_id="a", status="ok")))

    def test_stuck_threshold_triggers_esc_recovery(self) -> None:
        class _RecordingUI:
            def __init__(self) -> None:
                self.esc_calls = 0

            def close_popup(self):
                self.esc_calls += 1
                return object()

        ui = _RecordingUI()
        loop, _bridge, _ = self._loop(
            action=None,
            vision_payloads=[{"page_type": "unknown", "resources": {}}] * 4,
            stuck_threshold=3,
            ui_actions=ui,
        )
        loop.tick(0)
        loop.tick(1)
        self.assertEqual(ui.esc_calls, 0)
        loop.tick(2)
        self.assertEqual(ui.esc_calls, 1)
        self.assertEqual(loop._stuck_count, 0)

    def test_productive_tick_resets_stuck_counter(self) -> None:
        loop, _bridge, _ = self._loop(
            action=None,
            vision_payloads=[
                {"page_type": "unknown", "resources": {}},
                {"page_type": "unknown", "resources": {}},
                {"page_type": "city", "resources": {}},
                {"page_type": "city", "buildings": []},
            ],
            stuck_threshold=3,
        )
        action = CandidateAction(action_id="w", action_type=ActionType.WAIT_FOR_STAMINA)
        loop.tick(0)
        loop.tick(1)
        self.assertEqual(loop._stuck_count, 2)
        loop.selector = _StubSelector(action)
        loop.tick(2)
        self.assertEqual(loop._stuck_count, 0)

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
