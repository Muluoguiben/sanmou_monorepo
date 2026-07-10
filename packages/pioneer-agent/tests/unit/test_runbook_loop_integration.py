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
from pioneer_agent.runbook.lineup_binding import (
    OPERATOR_LINEUP_BINDING_SOURCE,
    apply_operator_lineup_bindings,
)
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
from pioneer_agent.safety.kill_switch import KillSwitch
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


def _with_attack_facts(
    payload: dict[str, Any],
    *,
    lineup_preset: str = "main_team",
) -> dict[str, Any]:
    result = dict(payload)
    result.setdefault(
        "team_containers",
        [{"team_id": "team-1", "lineup_preset": lineup_preset}],
    )
    result.setdefault("main_lineup", {"current_host_team_id": "team-1"})
    result.setdefault(
        "teams",
        [
            {
                "team_id": team.get("team_id"),
                "page_type": "team_panel",
                "heroes": [
                    {
                        "hero_id": f"hero-{team.get('team_id')}-{slot}",
                        "position": slot,
                    }
                    for slot in (1, 2, 3)
                ],
            }
            for team in result["team_containers"]
            if isinstance(team, dict) and team.get("team_id") is not None
        ],
    )
    map_state = dict(result.get("map_state") or {})
    map_state.setdefault(
        "candidate_lands",
        [{"land_id": "L-6", "level": 6, "land_scope": "inner_city"}],
    )
    result["map_state"] = map_state
    state = RuntimeState.model_validate(result)
    bindings = {
        str(team.get("team_id")): team["lineup_preset"]
        for team in state.team_containers
        if isinstance(team.get("lineup_preset"), str)
        and team.get("lineup_preset")
    }
    apply_operator_lineup_bindings(
        state,
        bindings,
        bound_at=datetime.now().astimezone(),
    )
    return state.model_dump(mode="python")


class _StubVisionSync:
    """Returns a fixed RuntimeState so runbook metrics are test-controlled."""

    def __init__(
        self,
        state_payload: dict[str, Any],
        *,
        lineup_preset: str = "main_team",
    ) -> None:
        self.state_payload = _with_attack_facts(
            state_payload,
            lineup_preset=lineup_preset,
        )

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

    def input_authority_failure_reason(self) -> None:
        return None


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


def _action(action_type: ActionType, **params: Any) -> CandidateAction:
    if action_type == ActionType.ATTACK_LAND:
        params = {
            "land_id": "L-6",
            "team_id": "team-1",
            "level": 6,
            "land_scope": "inner_city",
            "lineup_preset": "main_team",
            **params,
        }
    return CandidateAction(
        action_id=f"a-{action_type.value}",
        action_type=action_type,
        params=params,
    )


class _SpyUIActions:
    def __init__(self) -> None:
        self.close_popup_calls = 0

    def close_popup(self):  # noqa: ANN201
        self.close_popup_calls += 1
        return type("_Outcome", (), {"success": True})()


def _loop(
    *,
    state_payload: dict[str, Any],
    action: CandidateAction | None,
    engine: RunbookEngine,
    store: RunbookStateStore | None = None,
    loop_logger: LoopLogger | None = None,
    trace_store: TraceStore | None = None,
    ui_actions: Any = None,
    kill_switch: KillSwitch | None = None,
    lineup_preset_bindings: dict[str, str] | None = None,
    dry_run: bool = False,
) -> tuple[AutonomousLoop, _RecordingSelector, _StubRunner]:
    selector = _RecordingSelector(action)
    runner = _StubRunner()
    loop = AutonomousLoop(
        bridge=_StubBridge(),
        vision_sync=_StubVisionSync(state_payload),  # type: ignore[arg-type]
        ui_actions=ui_actions if ui_actions is not None else object(),  # type: ignore[arg-type]
        selector=selector,  # type: ignore[arg-type]
        deriver=_StubDeriver(),  # type: ignore[arg-type]
        runner=runner,  # type: ignore[arg-type]
        sleeper=lambda _s: None,
        loop_logger=loop_logger,
        trace_store=trace_store,
        kill_switch=kill_switch,
        runbook_engine=engine,
        runbook_state_store=store,
        lineup_preset_bindings=lineup_preset_bindings,
        dry_run=dry_run,
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

    def test_target_mismatch_dispatch_backstop_blocks_custom_selector(self) -> None:
        loop, _selector, runner = _loop(
            state_payload={
                "progress": {"step3_done": False},
                "global_state": {"battle_loss_rate": 0.1},
                "team_containers": [
                    {"team_id": "team-1", "lineup_preset": "wrong_team"}
                ],
            },
            # The selector forges params that match policy; the final guard
            # must bind the identity to current state and still block it.
            action=_action(ActionType.ATTACK_LAND, lineup_preset="main_team"),
            engine=RunbookEngine(_runbook(), start_phase_id="p3"),
        )

        result = loop.tick(0)

        self.assertEqual(result.execution.status, "blocked")
        self.assertEqual(
            result.execution.summary["blocked_by"],
            "runbook_lineup_preset_mismatch",
        )
        self.assertEqual(runner.actions, [])
        self.assertEqual(result.sleep_s, IDLE_SLEEP_S)

    def test_operator_binding_produces_trusted_current_lineup_fact(self) -> None:
        loop, selector, runner = _loop(
            state_payload={
                "progress": {"step3_done": False},
                "global_state": {"battle_loss_rate": 0.1},
                "main_lineup": {"current_host_team_id": "team-1"},
                "team_containers": [
                    {"team_id": "team-1", "container_stamina": 20}
                ],
                "teams": [
                    {
                        "team_id": "team-1",
                        "page_type": "team_panel",
                        "heroes": [
                            {"hero_id": "hero-1"},
                            {"hero_id": "hero-2"},
                            {"hero_id": "hero-3"},
                        ],
                    }
                ],
            },
            action=_action(ActionType.ATTACK_LAND),
            engine=RunbookEngine(_runbook(), start_phase_id="p3"),
            lineup_preset_bindings={"team-1": "main_team"},
        )
        result = loop.tick(0)
        bound_team = selector.seen_states[0].team_containers[0]
        self.assertEqual(bound_team["lineup_preset"], "main_team")
        self.assertEqual(
            bound_team["lineup_preset_source"],
            OPERATOR_LINEUP_BINDING_SOURCE,
        )
        self.assertEqual(result.execution.status, "ok")
        self.assertEqual(len(runner.actions), 1)

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

    def test_attack_report_loss_metric_triggers_abort_without_global_injection(self) -> None:
        runbook = OpeningRunbook.model_validate(
            {
                "season": "S15 ledger integration",
                "generated_at": "2026-07-10",
                "phases": [
                    {
                        "phase_id": "attack_phase",
                        "title": "Attack phase",
                        "exit_when": {"progress.done": "== true"},
                        "abort_when": {"battle_loss_rate": "> 0.35"},
                    }
                ],
            }
        )
        report = {
            "report_id": "br-loss-50",
            "report_id_source": "explicit",
            "report_identity_confidence": "high",
            "captured_at": "2026-07-10T12:00:00",
            "result": "loss",
            "occupation_result": "failed",
            "attacker_loss_ratio": 0.5,
            "verification": {
                "parse_status": "complete",
                "checks": {"loss_consistency": "not_conflicted"},
                "action_verification_ready": False,
                "verifier_status": "unverified",
            },
        }
        loop, selector, runner = _loop(
            state_payload={
                "progress": {"done": False},
                "map_state": {"battle_reports": [report]},
            },
            action=_action(ActionType.ATTACK_LAND),
            engine=RunbookEngine(runbook),
        )

        result = loop.tick(0)

        self.assertNotIn("battle_loss_rate", selector.seen_states[0].global_state)
        self.assertEqual(result.execution.status, "blocked")
        self.assertEqual(
            result.execution.summary["blocked_by"], "runbook_hold:abort_triggered"
        )
        self.assertEqual(runner.actions, [])

    def test_transition_persists_and_resumes_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.confirm_gate("p2", season="S15 测试")

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

            store.confirm_gate("p2", season="S15 测试")
            loop.tick(1)
            self.assertEqual(engine.current_phase.phase_id, "p2")


class RunbookFixRegressionTests(unittest.TestCase):
    """Regressions for the 2026-07-06 code-review findings."""

    def test_empty_allowlist_blocks_all_non_wait_actions(self) -> None:
        runbook = OpeningRunbook.model_validate(
            {
                "season": "S15 测试",
                "generated_at": "2026-07-06",
                "phases": [
                    {
                        "phase_id": "lockdown",
                        "title": "观察",
                        "exit_when": {"done": "== true"},
                        "selector_hints": {"allowed_action_types": []},
                    }
                ],
            }
        )
        loop, _selector, runner = _loop(
            state_payload={"progress": {}},
            action=_action(ActionType.ATTACK_LAND),
            engine=RunbookEngine(runbook),
        )
        result = loop.tick(0)
        self.assertEqual(result.execution.status, "blocked")
        self.assertEqual(result.execution.summary["blocked_by"], "runbook_action_filter")
        self.assertEqual(runner.actions, [])

        loop2, _selector2, runner2 = _loop(
            state_payload={"progress": {}},
            action=_action(ActionType.WAIT_FOR_STAMINA),
            engine=RunbookEngine(runbook),
        )
        result2 = loop2.tick(0)
        self.assertEqual(result2.execution.status, "ok")
        self.assertEqual(len(runner2.actions), 1)

    def test_enum_members_in_allowlist_are_normalized(self) -> None:
        runbook = OpeningRunbook.model_validate(
            {
                "season": "S15 测试",
                "generated_at": "2026-07-06",
                "phases": [
                    {
                        "phase_id": "p1",
                        "title": "收菜",
                        "exit_when": {"done": "== true"},
                        "selector_hints": {
                            "allowed_action_types": [ActionType.CLAIM_CHAPTER_REWARD]
                        },
                    }
                ],
            }
        )
        loop, _selector, runner = _loop(
            state_payload={"progress": {}},
            action=_action(ActionType.CLAIM_CHAPTER_REWARD),
            engine=RunbookEngine(runbook),
        )
        result = loop.tick(0)
        self.assertEqual(result.execution.status, "ok")
        self.assertEqual(len(runner.actions), 1)

    def test_kill_switch_freezes_runbook_cursor_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            switch = KillSwitch(Path(tmp) / "KILL_SWITCH")
            switch.trigger()
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.confirm_gate("p2", season="S15 测试")
            engine = build_engine_from_store(_runbook(), store)
            loop, _selector, _runner = _loop(
                state_payload={"progress": {"step1_done": True}},
                action=None,
                engine=engine,
                store=store,
                kill_switch=switch,
            )
            loop.tick(0)
            self.assertEqual(engine.current_phase.phase_id, "p1")
            self.assertFalse(store.path.exists())

            switch.clear()
            loop.tick(1)
            self.assertEqual(engine.current_phase.phase_id, "p2")
            self.assertTrue(store.path.exists())

    def test_dry_run_does_not_persist_runbook_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.confirm_gate("p2", season="S15 测试")
            engine = build_engine_from_store(_runbook(), store)
            loop, _selector, _runner = _loop(
                state_payload={"progress": {"step1_done": True}},
                action=None,
                engine=engine,
                store=store,
                dry_run=True,
            )
            loop.tick(0)
            self.assertEqual(engine.current_phase.phase_id, "p2")
            self.assertFalse(store.path.exists())

    def test_esc_recovery_suppressed_during_runbook_hold(self) -> None:
        spy = _SpyUIActions()
        loop, _selector, _runner = _loop(
            state_payload={"progress": {}},
            action=None,
            engine=RunbookEngine(_runbook(), start_phase_id="p2"),
            ui_actions=spy,
        )
        for i in range(4):
            loop.tick(i)
        self.assertEqual(spy.close_popup_calls, 0)

        spy2 = _SpyUIActions()
        loop2, _selector2, _runner2 = _loop(
            state_payload={"progress": {}},
            action=None,
            engine=RunbookEngine(_runbook()),
            ui_actions=spy2,
        )
        for i in range(4):
            loop2.tick(i)
        self.assertGreater(spy2.close_popup_calls, 0)

    def test_repeated_filter_blocks_escalate_to_planner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            loop, _selector, _runner = _loop(
                state_payload={"progress": {"step1_done": False}},
                action=_action(ActionType.ATTACK_LAND),
                engine=RunbookEngine(_runbook()),
                loop_logger=loop_logger,
            )
            for i in range(3):
                loop.tick(i)
            records = [
                json.loads(line)
                for line in (Path(tmp) / "loop.jsonl").read_text().splitlines()
            ]
            self.assertEqual(records[0]["runbook_escalations"], [])
            self.assertIn("action_filter_stuck", records[2]["runbook_escalations"])

    def test_escalations_are_edge_triggered_not_per_tick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            trace_store = TraceStore(Path(tmp) / "trace.jsonl")
            loop, _selector, _runner = _loop(
                state_payload={"progress": {}},
                action=None,
                engine=RunbookEngine(_runbook(), start_phase_id="p2"),
                loop_logger=loop_logger,
                trace_store=trace_store,
            )
            loop.tick(0)
            loop.tick(1)
            records = [
                json.loads(line)
                for line in (Path(tmp) / "loop.jsonl").read_text().splitlines()
            ]
            self.assertEqual(records[0]["runbook_escalations"], ["human_gate"])
            self.assertEqual(records[1]["runbook_escalations"], [])
            traces = [
                json.loads(line)
                for line in (Path(tmp) / "trace.jsonl").read_text().splitlines()
            ]
            self.assertIn(
                "human_gate", traces[1]["metadata"]["runbook"]["active_escalations"]
            )


class _StarvedSelector:
    """Models a real selector whose candidates were all runbook-rejected."""

    def __init__(self, reason: str = "runbook_action_filter") -> None:
        self.reason = reason

    def select(self, state):  # noqa: ANN001
        return SelectionResult(
            selected_action=None,
            ranked_actions=[],
            selection_reason={
                "pipeline": {"rejected_by_reason": {self.reason: 3}},
                "rejected_candidates": [
                    {
                        "action_type": "attack_land",
                        "reason": self.reason,
                        "params": {
                            "land_id": "L-6",
                            "team_id": "team-1",
                            "level": 6,
                            "land_scope": "inner_city",
                            "lineup_preset": None,
                        },
                    }
                ],
            },
        )


class GuardSeamRegressionTests(unittest.TestCase):
    """Regressions for the 2026-07-07 review findings."""

    def test_esc_recovery_suppressed_under_kill_switch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            switch = KillSwitch(Path(tmp) / "STOP")
            switch.trigger()
            spy = _SpyUIActions()
            loop, _selector, _runner = _loop(
                state_payload={"progress": {}},
                action=None,
                engine=RunbookEngine(_runbook()),
                ui_actions=spy,
                kill_switch=switch,
            )
            for i in range(5):
                loop.tick(i)
            self.assertEqual(spy.close_popup_calls, 0)

            switch.clear()
            for i in range(5, 10):
                loop.tick(i)
            self.assertGreater(spy.close_popup_calls, 0)

    def test_completed_runbook_blocks_dispatch_and_escalates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            loop, _selector, runner = _loop(
                state_payload={"progress": {}},
                action=_action(ActionType.ATTACK_LAND),
                engine=RunbookEngine(_runbook(), start_phase_id="p3", completed=True),
                loop_logger=loop_logger,
            )
            result = loop.tick(0)
            self.assertEqual(result.execution.status, "blocked")
            self.assertEqual(
                result.execution.summary["blocked_by"], "runbook_hold:runbook_completed"
            )
            self.assertEqual(runner.actions, [])
            record = json.loads((Path(tmp) / "loop.jsonl").read_text().splitlines()[0])
            self.assertIn("runbook_completed", record["runbook_escalations"])

    def test_allowlist_starvation_escalates_to_planner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            runner = _StubRunner()
            spy = _SpyUIActions()
            loop = AutonomousLoop(
                bridge=_StubBridge(),
                vision_sync=_StubVisionSync({"progress": {"step1_done": False}}),  # type: ignore[arg-type]
                ui_actions=spy,  # type: ignore[arg-type]
                selector=_StarvedSelector(),  # type: ignore[arg-type]
                deriver=_StubDeriver(),  # type: ignore[arg-type]
                runner=runner,  # type: ignore[arg-type]
                sleeper=lambda _s: None,
                loop_logger=loop_logger,
                runbook_engine=RunbookEngine(_runbook()),
            )
            for i in range(3):
                loop.tick(i)
            records = [
                json.loads(line)
                for line in (Path(tmp) / "loop.jsonl").read_text().splitlines()
            ]
            self.assertIn("action_filter_stuck", records[2]["runbook_escalations"])
            self.assertEqual(spy.close_popup_calls, 0)

    def test_target_fact_starvation_escalates_with_specific_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            trace_store = TraceStore(Path(tmp) / "trace.jsonl")
            spy = _SpyUIActions()
            loop = AutonomousLoop(
                bridge=_StubBridge(),
                vision_sync=_StubVisionSync(
                    {
                        "progress": {"step3_done": False},
                        "global_state": {"battle_loss_rate": 0.1},
                    }
                ),  # type: ignore[arg-type]
                ui_actions=spy,  # type: ignore[arg-type]
                selector=_StarvedSelector("runbook_lineup_preset_unknown"),  # type: ignore[arg-type]
                deriver=_StubDeriver(),  # type: ignore[arg-type]
                runner=_StubRunner(),  # type: ignore[arg-type]
                sleeper=lambda _s: None,
                loop_logger=loop_logger,
                trace_store=trace_store,
                runbook_engine=RunbookEngine(_runbook(), start_phase_id="p3"),
            )
            for i in range(3):
                loop.tick(i)
            record = json.loads(
                (Path(tmp) / "loop.jsonl").read_text().splitlines()[2]
            )
            self.assertIn("action_filter_stuck", record["runbook_escalations"])
            self.assertEqual(spy.close_popup_calls, 0)
            trace = json.loads(
                (Path(tmp) / "trace.jsonl").read_text().splitlines()[2]
            )
            escalation = trace["metadata"]["runbook"]["escalations"][0]
            observed = escalation["details"]["observed_action_facts"]
            self.assertEqual(observed["source"], "rejected_candidates")
            self.assertEqual(observed["candidates"][0]["facts"]["land_id"], "L-6")

    def test_unknown_confirmation_warns_once_not_per_tick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.confirm_gate("ghost_phase", season="S15 测试")
            engine = build_engine_from_store(_runbook(), store)
            loop, _selector, _runner = _loop(
                state_payload={"progress": {}},
                action=None,
                engine=engine,
                store=store,
            )
            with self.assertLogs("pioneer_agent.runtime.autonomous_loop", level="WARNING") as captured:
                for i in range(4):
                    loop.tick(i)
            unknown_warnings = [
                line for line in captured.output if "unknown gates" in line
            ]
            self.assertEqual(len(unknown_warnings), 1)

    def test_post_action_abort_suppresses_esc_recovery(self) -> None:
        # A verifier-style observation after the action surfaces an abort, so
        # the refreshed decision must block the recovery ESC even though the
        # tick-start decision allowed the action; a clean post-state still ESCs.
        class _RecoveryRunner:
            """Mutates loop.state to `post` (like a verifier re-observe) then
            fails with recovery_required."""

            def __init__(self, post: dict) -> None:
                self.loop: AutonomousLoop | None = None
                self.post = post

            def run(self, action):  # noqa: ANN001
                if self.loop is not None:
                    self.loop.state = RuntimeState.model_validate(self.post)
                return ExecutionResult(
                    action_id=action.action_id, status="failed",
                    recovery_required=True, summary={},
                )

            def input_authority_failure_reason(self) -> None:
                return None

        for post_loss, expect_esc in ((0.5, False), (0.1, True)):
            spy = _SpyUIActions()
            runner = _RecoveryRunner(
                {"progress": {"step3_done": False},
                 "global_state": {"battle_loss_rate": post_loss}}
            )
            loop = AutonomousLoop(
                bridge=_StubBridge(),
                vision_sync=_StubVisionSync(
                    {"progress": {"step3_done": False},
                     "global_state": {"battle_loss_rate": 0.1}}
                ),  # type: ignore[arg-type]
                ui_actions=spy,  # type: ignore[arg-type]
                selector=_RecordingSelector(_action(ActionType.ATTACK_LAND)),  # type: ignore[arg-type]
                deriver=_StubDeriver(),  # type: ignore[arg-type]
                runner=runner,  # type: ignore[arg-type]
                sleeper=lambda _s: None,
                runbook_engine=RunbookEngine(_runbook(), start_phase_id="p3"),
            )
            runner.loop = loop
            loop.tick(0)
            if expect_esc:
                self.assertGreater(spy.close_popup_calls, 0, f"loss={post_loss}")
            else:
                self.assertEqual(spy.close_popup_calls, 0, f"loss={post_loss}")

    def test_distinct_unknown_metrics_in_same_phase_both_reported(self) -> None:
        runbook = OpeningRunbook.model_validate(
            {
                "season": "S15 测试",
                "generated_at": "2026-07-07",
                "phases": [
                    {
                        "phase_id": "solo",
                        "title": "唯一阶段",
                        "exit_when": {"progress.done": "== true"},
                        "abort_when": {"global_state.risk": "> 0.5"},
                    }
                ],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            vision = _SequencedVisionSync(
                [
                    {"progress": {"done": False}},                          # abort metric dark
                    {"progress": {}, "global_state": {"risk": 0.1}},        # exit metric dark
                ]
            )
            loop = AutonomousLoop(
                bridge=_StubBridge(),
                vision_sync=vision,  # type: ignore[arg-type]
                ui_actions=object(),  # type: ignore[arg-type]
                selector=_RecordingSelector(None),  # type: ignore[arg-type]
                deriver=_StubDeriver(),  # type: ignore[arg-type]
                runner=_StubRunner(),  # type: ignore[arg-type]
                sleeper=lambda _s: None,
                loop_logger=loop_logger,
                runbook_engine=RunbookEngine(runbook),
            )
            loop.tick(0)
            loop.tick(1)
            records = [
                json.loads(line)
                for line in (Path(tmp) / "loop.jsonl").read_text().splitlines()
            ]
            # Same kind (unknown_metrics) same phase but different missing
            # metric — the second must NOT be deduped away.
            self.assertIn("unknown_metrics", records[0]["runbook_escalations"])
            self.assertIn("unknown_metrics", records[1]["runbook_escalations"])

    def test_persistent_abort_with_flickering_sibling_not_reflooded(self) -> None:
        # open_lv-style phase: two abort conditions. One stays triggered (abort
        # holds); the other's metric flickers dark/readable. The abort must be
        # reported ONCE, not re-fired each tick the sibling status churns.
        runbook = OpeningRunbook.model_validate(
            {
                "season": "S15 测试",
                "generated_at": "2026-07-07",
                "phases": [
                    {
                        "phase_id": "open",
                        "title": "开地",
                        "exit_when": {"progress.cleared": "== true"},
                        "abort_when": {
                            "global_state.loss_rate": "> 0.35",
                            "global_state.defeats": ">= 2",
                        },
                    },
                    {"phase_id": "next", "title": "下一阶段",
                     "exit_when": {"progress.done": "== true"}},
                ],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            vision = _SequencedVisionSync(
                [
                    {"progress": {}, "global_state": {"loss_rate": 0.5, "defeats": 1}},   # sibling readable
                    {"progress": {}, "global_state": {"loss_rate": 0.5}},                 # sibling dark
                    {"progress": {}, "global_state": {"loss_rate": 0.5, "defeats": 1}},   # readable again
                ]
            )
            loop = AutonomousLoop(
                bridge=_StubBridge(),
                vision_sync=vision,  # type: ignore[arg-type]
                ui_actions=_SpyUIActions(),  # type: ignore[arg-type]
                selector=_RecordingSelector(None),  # type: ignore[arg-type]
                deriver=_StubDeriver(),  # type: ignore[arg-type]
                runner=_StubRunner(),  # type: ignore[arg-type]
                sleeper=lambda _s: None,
                loop_logger=loop_logger,
                runbook_engine=RunbookEngine(runbook, start_phase_id="open"),
            )
            for i in range(3):
                loop.tick(i)
            records = [
                json.loads(line)
                for line in (Path(tmp) / "loop.jsonl").read_text().splitlines()
            ]
            abort_ticks = [r for r in records if "abort_triggered" in r["runbook_escalations"]]
            # Reported once (tick 0), not re-fired when the sibling flickers.
            self.assertEqual(len(abort_ticks), 1)
            self.assertEqual(records[0]["runbook_escalations"].count("abort_triggered"), 1)

    def test_refresh_frozen_under_kill_switch(self) -> None:
        # An action dispatches, then the kill switch trips before the post-action
        # refresh; a gate confirmation is pending. The refresh must not apply the
        # gate or persist state during the emergency stop.
        class _KillSwitchTrippingRunner:
            def __init__(self, switch: KillSwitch, store: RunbookStateStore) -> None:
                self.switch = switch
                self.store = store

            def run(self, action):  # noqa: ANN001
                self.store.confirm_gate("p2", season="S15 测试")
                self.switch.trigger()
                return ExecutionResult(
                    action_id=action.action_id, status="failed",
                    recovery_required=True, summary={},
                )

            def input_authority_failure_reason(self) -> None:
                return None

        with tempfile.TemporaryDirectory() as tmp:
            switch = KillSwitch(Path(tmp) / "STOP")
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            engine = build_engine_from_store(_runbook(), store)
            runner = _KillSwitchTrippingRunner(switch, store)
            loop = AutonomousLoop(
                bridge=_StubBridge(),
                vision_sync=_StubVisionSync({"progress": {}}),  # type: ignore[arg-type]
                ui_actions=_SpyUIActions(),  # type: ignore[arg-type]
                selector=_RecordingSelector(_action(ActionType.ATTACK_LAND)),  # type: ignore[arg-type]
                deriver=_StubDeriver(),  # type: ignore[arg-type]
                runner=runner,  # type: ignore[arg-type]
                sleeper=lambda _s: None,
                kill_switch=switch,
                runbook_engine=engine,
                runbook_state_store=store,
            )
            loop.tick(0)
            # Gate confirmation was pending, but the kill switch tripped mid-tick
            # (after the tick-start persist): the post-action refresh must not
            # apply the gate to the engine, nor persist it into the state file.
            self.assertNotIn("p2", engine.confirmed_gates)
            self.assertNotIn("p2", store._load_state_file().confirmed_gates)

    def test_deleted_state_file_is_recreated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            engine = build_engine_from_store(_runbook(), store)
            loop, _selector, _runner = _loop(
                state_payload={"progress": {}},
                action=None,
                engine=engine,
                store=store,
            )
            loop.tick(0)
            self.assertTrue(store.path.exists())
            store.path.unlink()
            loop.tick(1)
            self.assertTrue(store.path.exists())


class _SequencedVisionSync:
    """Different RuntimeState per sync call — models the world changing
    between the first click and the intermediate flow observation."""

    def __init__(
        self,
        payloads: list[dict[str, Any]],
        *,
        lineup_preset: str = "main_team",
    ) -> None:
        self.payloads = [
            _with_attack_facts(payload, lineup_preset=lineup_preset)
            for payload in payloads
        ]
        self.calls = 0

    def sync(self, png, *, state, captured_at):  # noqa: ANN001
        payload = self.payloads[min(self.calls, len(self.payloads) - 1)]
        self.calls += 1
        return (
            RuntimeState.model_validate(payload),
            VisionSyncSummary(page_type="city", domains_run=[], notes=[]),
        )


class _FlowRunner:
    """First dispatch is a non-terminal flow step (e.g. opening the upgrade
    dialog); subsequent dispatches are terminal."""

    def __init__(self) -> None:
        self.calls = 0

    def run(self, action):  # noqa: ANN001
        self.calls += 1
        if self.calls == 1:
            return ExecutionResult(
                action_id=action.action_id,
                status="ok",
                verification_status="unknown",
                summary={
                    "action_type": action.action_type.value,
                    "terminal_for_verifier": False,
                },
            )
        return ExecutionResult(
            action_id=action.action_id,
            status="ok",
            verification_status="verified",
            summary={"action_type": action.action_type.value},
        )


class RunbookFlowContinuationTests(unittest.TestCase):
    def _flow_loop(
        self, payloads: list[dict[str, Any]]
    ) -> tuple[AutonomousLoop, _FlowRunner, _SpyUIActions]:
        runner = _FlowRunner()
        spy = _SpyUIActions()
        loop = AutonomousLoop(
            bridge=_StubBridge(),
            vision_sync=_SequencedVisionSync(payloads),  # type: ignore[arg-type]
            ui_actions=spy,  # type: ignore[arg-type]
            selector=_RecordingSelector(_action(ActionType.ATTACK_LAND)),  # type: ignore[arg-type]
            deriver=_StubDeriver(),  # type: ignore[arg-type]
            runner=runner,  # type: ignore[arg-type]
            sleeper=lambda _s: None,
            runbook_engine=RunbookEngine(_runbook(), start_phase_id="p3"),
        )
        return loop, runner, spy

    def test_abort_mid_flow_blocks_terminal_click(self) -> None:
        loop, runner, spy = self._flow_loop(
            [
                {"progress": {"step3_done": False}, "global_state": {"battle_loss_rate": 0.1}},
                {"progress": {"step3_done": False}, "global_state": {"battle_loss_rate": 0.5}},
            ]
        )
        result = loop.tick(0)
        self.assertEqual(runner.calls, 1)
        self.assertEqual(result.execution.status, "failed")
        self.assertIn(
            "runbook blocks action flow continuation: runbook_hold:abort_triggered",
            result.execution.failure_reason,
        )
        # Blocking hold also suppresses the dangling-dialog ESC recovery.
        self.assertEqual(spy.close_popup_calls, 0)

    def test_flow_continues_when_runbook_still_allows(self) -> None:
        loop, runner, _spy = self._flow_loop(
            [
                {"progress": {"step3_done": False}, "global_state": {"battle_loss_rate": 0.1}},
                {"progress": {"step3_done": False}, "global_state": {"battle_loss_rate": 0.1}},
            ]
        )
        result = loop.tick(0)
        self.assertEqual(runner.calls, 2)
        self.assertEqual(result.execution.status, "ok")

    def test_current_state_target_change_blocks_terminal_click(self) -> None:
        loop, runner, _spy = self._flow_loop(
            [
                {
                    "progress": {"step3_done": False},
                    "global_state": {"battle_loss_rate": 0.1},
                },
                {
                    "progress": {"step3_done": False},
                    "global_state": {"battle_loss_rate": 0.1},
                    "team_containers": [
                        {"team_id": "team-1", "lineup_preset": "wrong_team"}
                    ],
                },
            ]
        )
        result = loop.tick(0)
        self.assertEqual(runner.calls, 1)
        self.assertEqual(result.execution.status, "failed")
        self.assertIn("runbook_lineup_preset_mismatch", result.execution.failure_reason)

    def _two_phase_flow_runbook(self, abort_metric: str | None = None) -> OpeningRunbook:
        f1: dict[str, Any] = {
            "phase_id": "f1",
            "title": "流内阶段",
            "exit_when": {"progress.step_done": "== true"},
            "selector_hints": {"lineup_preset": "flow_team"},
        }
        if abort_metric:
            f1["abort_when"] = {abort_metric: "> 0.5"}
        return OpeningRunbook.model_validate(
            {
                "season": "S15 测试",
                "generated_at": "2026-07-07",
                "phases": [f1, {"phase_id": "f2", "title": "下一阶段",
                                "exit_when": {"progress.step2_done": "== true"}}],
            }
        )

    def _flow_loop_with(
        self, runbook: OpeningRunbook, payloads: list[dict[str, Any]],
        loop_logger: LoopLogger | None = None,
    ) -> tuple[AutonomousLoop, _FlowRunner, RunbookEngine]:
        runner = _FlowRunner()
        engine = RunbookEngine(runbook)
        loop = AutonomousLoop(
            bridge=_StubBridge(),
            vision_sync=_SequencedVisionSync(
                payloads,
                lineup_preset="flow_team",
            ),  # type: ignore[arg-type]
            ui_actions=_SpyUIActions(),  # type: ignore[arg-type]
            selector=_RecordingSelector(
                _action(ActionType.ATTACK_LAND, lineup_preset="flow_team")
            ),  # type: ignore[arg-type]
            deriver=_StubDeriver(),  # type: ignore[arg-type]
            runner=runner,  # type: ignore[arg-type]
            sleeper=lambda _s: None,
            loop_logger=loop_logger,
            runbook_engine=engine,
        )
        return loop, runner, engine

    def test_mid_flow_transition_deferred_until_next_tick(self) -> None:
        loop, runner, engine = self._flow_loop_with(
            self._two_phase_flow_runbook(),
            [
                {"progress": {"step_done": False}},
                {"progress": {"step_done": True}},
            ],
        )
        result = loop.tick(0)
        # Exit became satisfied mid-flow, but the phase must not swap under
        # the in-flight action: terminal click dispatches under f1.
        self.assertEqual(runner.calls, 2)
        self.assertEqual(result.execution.status, "ok")
        self.assertEqual(engine.current_phase.phase_id, "f1")

        loop.tick(1)
        self.assertEqual(engine.current_phase.phase_id, "f2")

    def test_productive_tick_not_relabeled_transition_deferred(self) -> None:
        # The post-action frozen refresh emits hold_reason="transition_deferred"
        # when exit becomes satisfied but the transition is deferred; that
        # synthetic label must not leak into the recorded payload of a tick that
        # actually made forward progress (the tick-start hold is kept instead).
        runbook = OpeningRunbook.model_validate(
            {
                "season": "S15 测试",
                "generated_at": "2026-07-07",
                "phases": [
                    {
                        "phase_id": "f1",
                        "title": "阶段",
                        "exit_when": {"progress.step_done": "== true"},
                        "abort_when": {"global_state.risk": "> 0.5"},
                    },
                    {"phase_id": "f2", "title": "下一阶段",
                     "exit_when": {"progress.step2_done": "== true"}},
                ],
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            # tick-start: exit not satisfied, risk dark -> abort_metrics_unknown
            # (non-blocking). runner mutates state to exit-satisfied (still no
            # abort) so the post-action refresh sees a satisfied-but-frozen exit.
            class _ProgressRunner:
                def __init__(self) -> None:
                    self.loop: AutonomousLoop | None = None

                def run(self, action):  # noqa: ANN001
                    if self.loop is not None:
                        self.loop.state = RuntimeState.model_validate(
                            {"progress": {"step_done": True}, "global_state": {"risk": 0.1}}
                        )
                    return ExecutionResult(
                        action_id=action.action_id, status="ok",
                        verification_status="verified", summary={},
                    )

            runner = _ProgressRunner()
            loop = AutonomousLoop(
                bridge=_StubBridge(),
                vision_sync=_StubVisionSync({"progress": {"step_done": False}}),  # type: ignore[arg-type]
                ui_actions=_SpyUIActions(),  # type: ignore[arg-type]
                selector=_RecordingSelector(
                    _action(ActionType.ATTACK_LAND, lineup_preset="flow_team")
                ),  # type: ignore[arg-type]
                deriver=_StubDeriver(),  # type: ignore[arg-type]
                runner=runner,  # type: ignore[arg-type]
                sleeper=lambda _s: None,
                loop_logger=loop_logger,
                runbook_engine=RunbookEngine(runbook),
            )
            runner.loop = loop
            loop.tick(0)
            record = json.loads((Path(tmp) / "loop.jsonl").read_text().splitlines()[0])
            # Pre-fix the refresh's frozen re-eval relabeled this to
            # "transition_deferred"; now the tick-start hold (None here) is kept.
            self.assertNotEqual(record["runbook_hold_reason"], "transition_deferred")
            self.assertIsNone(record["runbook_hold_reason"])

    def test_evaluate1_escalations_survive_flow_merge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loop_logger = LoopLogger(Path(tmp), archive_screenshots=False)
            loop, runner, _engine = self._flow_loop_with(
                self._two_phase_flow_runbook(abort_metric="global_state.risk"),
                [
                    {"progress": {"step_done": False}},
                    {"progress": {"step_done": False}, "global_state": {"risk": 0.1}},
                ],
                loop_logger=loop_logger,
            )
            loop.tick(0)
            # evaluate#1 saw the abort metric dark (unknown_metrics); the flow
            # evaluation resolved it — the escalation must still be recorded.
            self.assertEqual(runner.calls, 2)
            record = json.loads((Path(tmp) / "loop.jsonl").read_text().splitlines()[0])
            self.assertIn("unknown_metrics", record["runbook_escalations"])


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
            store.save(current_phase_id="from_last_season", confirmed_gates={"ghost_gate", "p2"}, season="S15 测试")
            engine = build_engine_from_store(_runbook(), store)
            self.assertEqual(engine.current_phase.phase_id, "p1")
            self.assertEqual(engine.confirmed_gates, frozenset({"p2"}))

    def test_confirm_gate_never_touches_loop_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.save(current_phase_id="p2", confirmed_gates=set())
            state_before = store.path.read_text(encoding="utf-8")

            cli_store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            cli_store.confirm_gate("er_tuo_yi")

            self.assertEqual(store.path.read_text(encoding="utf-8"), state_before)
            self.assertTrue(cli_store.confirmations_path.exists())

    def test_loop_save_cannot_clobber_operator_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            loop_store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            cli_store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            # CLI confirms between the loop's read and its save — the old
            # read-modify-write design lost this permanently.
            cli_store.confirm_gate("p2")
            loop_store.save(current_phase_id="p1", confirmed_gates=set())
            self.assertIn("p2", loop_store.load().confirmed_gates)

    def test_atomic_save_leaves_no_tmp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.save(current_phase_id="p1", confirmed_gates={"a"}, completed=True)
            leftovers = [p.name for p in Path(tmp).iterdir()]
            self.assertEqual(leftovers, ["runbook_state.json"])

    def test_completed_persists_and_restores_into_engine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.save(current_phase_id="p3", confirmed_gates=set(), completed=True, season="S15 测试")
            record = store.load()
            self.assertTrue(record.completed)
            engine = build_engine_from_store(_runbook(), store)
            self.assertTrue(engine.completed)
            decision = engine.evaluate({})
            self.assertTrue(decision.completed)
            self.assertEqual(decision.hold_reason, "runbook_completed")

    def test_state_from_another_season_is_discarded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.save(
                current_phase_id="p3",
                confirmed_gates={"p2"},
                completed=True,
                season="S15 旧赛季",
            )
            record = store.load(expected_season="S16 新赛季")
            self.assertIsNone(record.current_phase_id)
            self.assertFalse(record.completed)
            self.assertEqual(record.confirmed_gates, set())

            same_season = store.load(expected_season="S15 旧赛季")
            self.assertEqual(same_season.current_phase_id, "p3")
            self.assertTrue(same_season.completed)

    def test_confirmations_from_another_season_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.confirm_gate("p2", season="S15 旧赛季")
            self.assertEqual(store.read_confirmations(expected_season="S16 新赛季"), set())
            self.assertEqual(store.read_confirmations(expected_season="S15 旧赛季"), {"p2"})
            self.assertEqual(store.read_confirmations(), {"p2"})

    def test_unstamped_records_rejected_when_season_expected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.save(current_phase_id="p2", confirmed_gates=set())
            store.confirm_gate("p2")

            record = store.load(expected_season="S15 测试")
            self.assertIsNone(record.current_phase_id)
            self.assertEqual(record.confirmed_gates, set())

            unfiltered = store.load()
            self.assertEqual(unfiltered.current_phase_id, "p2")
            self.assertIn("p2", unfiltered.confirmed_gates)

    def test_build_engine_ignores_state_from_another_season(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.save(
                current_phase_id="p3",
                confirmed_gates={"p2"},
                completed=True,
                season="S14 上赛季",
            )
            store.confirm_gate("p2", season="S14 上赛季")
            engine = build_engine_from_store(_runbook(), store)
            self.assertEqual(engine.current_phase.phase_id, "p1")
            self.assertFalse(engine.completed)
            self.assertEqual(engine.confirmed_gates, frozenset())

    def test_single_instance_lock_excludes_second_holder(self) -> None:
        from pioneer_agent.runbook.state_store import acquire_single_instance_lock

        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "runbook_state.json.lock"
            first = acquire_single_instance_lock(lock_path)
            self.assertIsNotNone(first)
            second = acquire_single_instance_lock(lock_path)
            self.assertIsNone(second)
            first.close()
            third = acquire_single_instance_lock(lock_path)
            self.assertIsNotNone(third)
            third.close()

    def test_malformed_confirmation_lines_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RunbookStateStore(Path(tmp) / "runbook_state.json")
            store.confirmations_path.write_text(
                '{"phase_id": "p2"}\n{not json\n{"no_phase": true}\n',
                encoding="utf-8",
            )
            self.assertEqual(store.read_confirmations(), {"p2"})


if __name__ == "__main__":
    unittest.main()
