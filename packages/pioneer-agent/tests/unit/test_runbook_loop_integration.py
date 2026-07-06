"""Integration tests: RunbookEngine inside AutonomousLoop + state persistence."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import (
    CandidateAction,
    ExecutionResult,
    RuntimeState,
    SelectionResult,
)
from pioneer_agent.perception.vision_sync import VisionSyncSummary
from pioneer_agent.runbook.engine import RunbookEngine
from pioneer_agent.runbook.models import OpeningRunbook
from pioneer_agent.runbook.state_store import (
    RunbookStateStore,
    build_engine_from_store,
)
from pioneer_agent.runtime.autonomous_loop import (
    IDLE_SLEEP_S,
    WAIT_SLEEP_S,
    AutonomousLoop,
)
from pioneer_agent.storage.loop_logger import LoopLogger
from pioneer_agent.storage.trace_store import TraceStore


def _png() -> bytes:
    img = Image.new("RGB", (64, 64), (0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _StubBridge:
    def screenshot(self, save_path=None):  # noqa: ANN001
        return _png()


class _StubVisionSync:
    """Returns a fixed RuntimeState so runbook metrics are test-controlled."""

    def __init__(self, state_payload: dict[str, Any]) -> None:
        self.state_payload = state_payload

    def sync(self, png, *, state, captured_at):  # noqa: ANN001
        return (
            RuntimeState.model_validate(self.state_payload),
            VisionSyncSummary(page_type="city", domains_run=[], notes=[]),
        )


class _RecordingSelector:
    def __init__(self, action: CandidateAction | None) -> None:
        self.action = action
        self.seen_states: list[RuntimeState] = []

    def select(self, state):  # noqa: ANN001
        self.seen_states.append(state)
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
        return ExecutionResult(
            action_id=action.action_id,
            status="ok",
            verification_status="verified",
            summary={"action_type": action.action_type.value},
        )


def _runbook() -> OpeningRunbook:
    return OpeningRunbook.model_validate(
        {
            "season": "S15 测试",
            "generated_at": "2026-07-06",
            "phases": [
                {
                    "phase_id": "p1",
                    "title": "收菜",
                    "exit_when": {"progress.step1_done": "== true"},
                    "selector_hints": {
                        "lineup_preset": "junk_team",
                        "allowed_action_types": ["claim_chapter_reward"],
                    },
                },
                {
                    "phase_id": "p2",
                    "title": "二拖一",
                    "human_gate": True,
                    "exit_when": {"progress.step2_done": "== true"},
                    "selector_hints": {"routine": "er_tuo_yi"},
                },
                {
                    "phase_id": "p3",
                    "title": "开地",
                    "exit_when": {"progress.step3_done": "== true"},
                    "abort_when": {"global_state.battle_loss_rate": "> 0.35"},
                    "selector_hints": {"lineup_preset": "main_team"},
                },
            ],
        }
    )


def _action(action_type: ActionType) -> CandidateAction:
    return CandidateAction(action_id=f"a-{action_type.value}", action_type=action_type)


def _loop(
    *,
    state_payload: dict[str, Any],
    action: CandidateAction | None,
    engine: RunbookEngine,
    store: RunbookStateStore | None = None,
    loop_logger: LoopLogger | None = None,
    trace_store: TraceStore | None = None,
) -> tuple[AutonomousLoop, _RecordingSelector, _StubRunner]:
    selector = _RecordingSelector(action)
    runner = _StubRunner()
    loop = AutonomousLoop(
        bridge=_StubBridge(),
        vision_sync=_StubVisionSync(state_payload),  # type: ignore[arg-type]
        ui_actions=object(),  # type: ignore[arg-type]
        selector=selector,  # type: ignore[arg-type]
        deriver=_StubDeriver(),  # type: ignore[arg-type]
        runner=runner,  # type: ignore[arg-type]
        sleeper=lambda _s: None,
        loop_logger=loop_logger,
        trace_store=trace_store,
        runbook_engine=engine,
        runbook_state_store=store,
    )
    return loop, selector, runner


class RunbookLoopIntegrationTests(unittest.TestCase):
    def test_hints_injected_logged_and_traced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            trace_store = TraceStore(Path(tmp) / "trace.jsonl")
            loop, selector, runner = _loop(
                state_payload={"progress": {"step1_done": False}},
                action=_action(ActionType.CLAIM_CHAPTER_REWARD),
                engine=RunbookEngine(_runbook()),
                loop_logger=loop_logger,
                trace_store=trace_store,
            )
            result = loop.tick(0)

            runbook_ctx = selector.seen_states[0].global_state["runbook"]
            self.assertEqual(runbook_ctx["phase_id"], "p1")
            self.assertEqual(runbook_ctx["selector_hints"]["lineup_preset"], "junk_team")

            self.assertEqual(result.execution.status, "ok")
            self.assertEqual(runner.actions[0].action_type, ActionType.CLAIM_CHAPTER_REWARD)

            record = json.loads((Path(tmp) / "loop.jsonl").read_text().splitlines()[0])
            self.assertEqual(record["runbook_phase"], "p1")
            self.assertIsNone(record["runbook_hold_reason"])

            trace = json.loads((Path(tmp) / "trace.jsonl").read_text().splitlines()[0])
            self.assertEqual(trace["metadata"]["runbook"]["phase_id"], "p1")

    def test_action_filter_blocks_disallowed_action(self) -> None:
        loop, _selector, runner = _loop(
            state_payload={"progress": {"step1_done": False}},
            action=_action(ActionType.ATTACK_LAND),
            engine=RunbookEngine(_runbook()),
        )
        result = loop.tick(0)
        self.assertEqual(result.execution.status, "blocked")
        self.assertEqual(result.execution.summary["blocked_by"], "runbook_action_filter")
        self.assertEqual(runner.actions, [])
        self.assertEqual(result.sleep_s, IDLE_SLEEP_S)

    def test_wait_actions_exempt_from_action_filter(self) -> None:
        loop, _selector, runner = _loop(
            state_payload={"progress": {"step1_done": False}},
            action=_action(ActionType.WAIT_FOR_STAMINA),
            engine=RunbookEngine(_runbook()),
        )
        result = loop.tick(0)
        self.assertEqual(result.execution.status, "ok")
        self.assertEqual(len(runner.actions), 1)
        self.assertEqual(result.sleep_s, WAIT_SLEEP_S[ActionType.WAIT_FOR_STAMINA])

    def test_human_gate_hold_blocks_dispatch(self) -> None:
        loop, selector, runner = _loop(
            state_payload={"progress": {}},
            action=_action(ActionType.ATTACK_LAND),
            engine=RunbookEngine(_runbook(), start_phase_id="p2"),
        )
        result = loop.tick(0)
        self.assertEqual(result.execution.status, "blocked")
        self.assertEqual(
            result.execution.summary["blocked_by"], "runbook_hold:human_gate_pending"
        )
        self.assertEqual(runner.actions, [])
        self.assertEqual(
            selector.seen_states[0].global_state["runbook"]["human_gate_pending"], "p2"
        )

    def test_abort_hold_blocks_dispatch_and_logs_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            loop, _selector, runner = _loop(
                state_payload={
                    "progress": {"step3_done": False},
                    "global_state": {"battle_loss_rate": 0.5},
                },
                action=_action(ActionType.ATTACK_LAND),
                engine=RunbookEngine(_runbook(), start_phase_id="p3"),
                loop_logger=loop_logger,
            )
            result = loop.tick(0)
            self.assertEqual(result.execution.status, "blocked")
            self.assertEqual(
                result.execution.summary["blocked_by"], "runbook_hold:abort_triggered"
            )
            self.assertEqual(runner.actions, [])
            record = json.loads((Path(tmp) / "loop.jsonl").read_text().splitlines()[0])
            self.assertIn("abort_triggered", record["runbook_escalations"])

    def test_transition_persists_and_resumes_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.confirm_gate("p2")

            engine = build_engine_from_store(_runbook(), store)
            loop, _selector, _runner = _loop(
                state_payload={"progress": {"step1_done": True}},
                action=None,
                engine=engine,
                store=store,
            )
            loop.tick(0)
            self.assertEqual(engine.current_phase.phase_id, "p2")

            record = store.load()
            self.assertEqual(record.current_phase_id, "p2")
            self.assertIn("p2", record.confirmed_gates)

            resumed = build_engine_from_store(_runbook(), store)
            self.assertEqual(resumed.current_phase.phase_id, "p2")
            self.assertIn("p2", resumed.confirmed_gates)

    def test_mid_run_gate_confirmation_via_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            engine = build_engine_from_store(_runbook(), store)
            loop, _selector, _runner = _loop(
                state_payload={"progress": {"step1_done": True}},
                action=None,
                engine=engine,
                store=store,
            )
            loop.tick(0)
            self.assertEqual(engine.current_phase.phase_id, "p1")

            store.confirm_gate("p2")
            loop.tick(1)
            self.assertEqual(engine.current_phase.phase_id, "p2")


class RunbookStateStoreTests(unittest.TestCase):
    def test_load_missing_file_returns_empty_record(self) -> None:
        store = RunbookStateStore(Path("/nonexistent/runbook_state.json"))
        record = store.load()
        self.assertIsNone(record.current_phase_id)
        self.assertEqual(record.confirmed_gates, set())

    def test_load_corrupt_file_returns_empty_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runbook_state.json"
            path.write_text("{not json", encoding="utf-8")
            record = RunbookStateStore(path).load()
            self.assertIsNone(record.current_phase_id)

    def test_save_and_confirm_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.save(current_phase_id="p2", confirmed_gates={"p2"})
            store.confirm_gate("p3")
            record = store.load()
            self.assertEqual(record.current_phase_id, "p2")
            self.assertEqual(record.confirmed_gates, {"p2", "p3"})

    def test_resume_with_unknown_phase_starts_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.save(current_phase_id="from_last_season", confirmed_gates={"ghost_gate", "p2"})
            engine = build_engine_from_store(_runbook(), store)
            self.assertEqual(engine.current_phase.phase_id, "p1")
            self.assertEqual(engine.confirmed_gates, frozenset({"p2"}))


if __name__ == "__main__":
    unittest.main()
