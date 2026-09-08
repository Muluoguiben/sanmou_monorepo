from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pioneer_agent.agent_harness.journal import JsonJournalStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.policy import StopReason
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
if __package__:
    from .test_agent_harness import NOW, ScriptedMcpClient, load_fixture
else:
    from test_agent_harness import NOW, ScriptedMcpClient, load_fixture


class HarnessLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = JsonJournalStore(Path(self.tmp.name) / "journal.json")
        self.log = InMemoryToolLog()
        self.now = NOW
        self.fixture = load_fixture("recommendation_ready.json")
        self.refresh()

    def refresh(self, domains=None):
        for response in self.fixture["game"].values():
            observation = response["structuredContent"].get("observation")
            if observation:
                observation["domains_run"] = domains or [
                    "resource_bar", "chapter_panel", "team_panel", "map_land", "battle_report"
                ]
                observation["captured_at"] = self.now.isoformat()

    def harness(self, game=None, qa=None):
        return RecommendationHarness(
            game_client=game or ScriptedMcpClient(self.fixture["game"]), qa_client=qa,
            journal_store=self.store, tool_log=self.log, agent_session_id="restart-test",
            model_id="synthetic", clock=lambda: self.now,
        )

    async def test_r17_repeated_real_domains_refresh_timer_checkpoint(self):
        for _ in range(3):
            self.refresh()
            result = await self.harness().run_decision_window()
            self.assertEqual(result.status, "recommended")
            checkpoint = result.journal.latest_tooling_fact("checkpoint:map_timers")
            self.assertEqual(checkpoint.observed_at, self.now)
            self.assertEqual(checkpoint.metadata["domains"], ["map_land"])
            self.assertIn("frame_sha256:" + "a" * 64, checkpoint.evidence_refs)
            self.assertNotIn("recruit_timers", [i.metadata.get("checkpoint_name") for i in result.journal.tooling.inferred])
            self.now += timedelta(seconds=121)

    async def test_r17_map_refresh_does_not_refresh_recruit_timer(self):
        self.refresh(["resource_bar", "chapter_panel", "team_panel", "map_land", "battle_report", "recruit_panel"])
        first = await self.harness().run_decision_window()
        self.assertEqual(first.status, "recommended")
        self.now += timedelta(seconds=121)
        self.refresh()
        stopped = await self.harness().run_decision_window()
        self.assertEqual(stopped.stop.reason, StopReason.CHECKPOINT_STALE)
        self.assertEqual(stopped.stop.details, ["recruit_timers:121.000s"])

    async def test_r17_unknown_source_never_refreshes_checkpoint(self):
        await self.harness().run_decision_window()
        self.now += timedelta(seconds=121)
        self.refresh()
        obs = self.fixture["game"]["observe_game"]["structuredContent"]["observation"]
        obs["domains_run"].remove("map_land")
        obs["unknown_domains"] = ["map_land"]
        result = await self.harness().run_decision_window()
        self.assertEqual(result.stop.reason, StopReason.CRITICAL_DOMAIN_UNKNOWN)
        self.assertEqual(result.journal.latest_tooling_fact("checkpoint:map_timers").observed_at, NOW)

    async def test_r18_restart_reobserves_before_comparing_persisted_identity(self):
        self.assertEqual((await self.harness().run_decision_window()).status, "recommended")
        self.fixture["game"]["session_status"]["structuredContent"]["session"]["window_identity"] = None
        game = ScriptedMcpClient(self.fixture["game"])
        result = await self.harness(game).run_decision_window()
        self.assertEqual(result.status, "recommended")
        self.assertEqual([name for name, _ in game.calls][:2], ["session_status", "observe_game"])

    async def test_r18_restart_changed_or_missing_identity_preserves_baseline(self):
        await self.harness().run_decision_window()
        original = deepcopy(self.fixture)
        for missing in (False, True):
            with self.subTest(missing=missing):
                self.fixture = deepcopy(original)
                self.fixture["game"]["session_status"]["structuredContent"]["session"]["window_identity"] = None
                obs = self.fixture["game"]["observe_game"]["structuredContent"]["observation"]
                obs["capture_geometry"] = None
                if missing:
                    obs["window_identity"] = None
                else:
                    obs["window_identity"]["hwnd"] = 999
                game = ScriptedMcpClient(self.fixture["game"])
                result = await self.harness(game).run_decision_window()
                self.assertEqual(result.stop.reason, StopReason.CAPTURE_UNHEALTHY if missing else StopReason.WINDOW_IDENTITY_CHANGED)
                self.assertEqual(len(game.calls), 2)
                self.assertEqual(result.journal.latest_tooling_fact("window_identity").metadata["window_identity"]["hwnd"], 101)
        self.fixture = original
        self.assertEqual((await self.harness().run_decision_window()).status, "recommended")

    async def test_r19_slow_qa_and_candidate_calls_cannot_return_stale_advice(self):
        for slow_tool in ("answer_rule_question", "list_action_candidates", "get_runtime_state"):
            with self.subTest(slow_tool=slow_tool):
                self.now = NOW
                owner = self

                class SlowClient(ScriptedMcpClient):
                    async def call_tool(self, name, arguments):
                        if name == slow_tool:
                            owner.now += timedelta(seconds=300)
                        return await super().call_tool(name, arguments)

                result = await self.harness(SlowClient(self.fixture["game"]), SlowClient(self.fixture["qa"])).run_decision_window(qa_questions=["synthetic"])
                self.assertEqual(result.stop.reason, StopReason.OBSERVATION_STALE)
                self.assertIsNone(result.recommendation)
                self.assertFalse(any(i.inference.startswith("recommend ") for i in result.journal.planning.inferred))

    async def test_r19_downstream_binding_cannot_change_provenance(self):
        original = deepcopy(self.fixture)
        for tool in ("get_runtime_state", "list_action_candidates"):
            for field, value in (("session_id", "different"), ("captured_at", (NOW + timedelta(seconds=1)).isoformat()),
                                 ("window_identity", None), ("capture_geometry", None),
                                 ("domains_run", []), ("unknown_domains", ["recruit_panel"])):
                with self.subTest(tool=tool, field=field):
                    self.fixture = deepcopy(original)
                    self.fixture["game"][tool]["structuredContent"]["observation"][field] = value
                    result = await self.harness().run_decision_window()
                    self.assertEqual(result.stop.reason, StopReason.CONTRACT_VIOLATION)
                    self.assertIsNone(result.recommendation)

    async def test_r20_cancelled_call_is_logged_and_journaled(self):
        class CancelledClient:
            async def call_tool(self, name, arguments):
                raise asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            await self.harness(CancelledClient()).run_decision_window()
        self.assertFalse(self.log.records[-1].success)
        self.assertEqual(self.log.records[-1].error_type, "CancelledError")
        self.assertEqual(self.store.load("restart-test").tooling.inferred[-1].inference, "stop:tool_failure")
