from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import unittest

from pydantic import ValidationError

from pioneer_agent.agent_harness.contracts import GAME_READ_ONLY_TOOLS
from pioneer_agent.agent_harness.journal import (
    AgentInference,
    DecisionJournal,
    InMemoryJournalStore,
    JsonJournalStore,
    ObservedFact,
)
from pioneer_agent.agent_harness.loop import DecisionWindowStatus, RecommendationHarness
from pioneer_agent.agent_harness.policy import StopPolicy, StopReason
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog, JsonlToolLog, summarize_arguments


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "agent_harness"
NOW = datetime.fromisoformat("2026-08-26T10:00:10+08:00")


class ScriptedMcpClient:
    def __init__(self, responses: Mapping[str, Any]) -> None:
        self.responses = dict(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append((name, dict(arguments)))
        response = self.responses[name]
        if isinstance(response, Exception):
            raise response
        return response


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class JournalTests(unittest.TestCase):
    def test_observed_and_inferred_entries_require_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            ObservedFact(fact="chapter is claimable", observed_at=NOW, evidence_refs=[])
        with self.assertRaises(ValidationError):
            AgentInference(inference="claim next", inferred_at=NOW, based_on_evidence_refs=[])

    def test_json_store_round_trip_preserves_sections(self) -> None:
        with TemporaryDirectory() as tmp:
            store = JsonJournalStore(Path(tmp) / "journal.json")
            journal = DecisionJournal(agent_session_id="agent-1")
            journal.tactical.observed.append(
                ObservedFact(
                    fact="chapter is claimable",
                    observed_at=NOW,
                    observation_id="obs-1",
                    evidence_refs=["observation:obs-1"],
                )
            )
            journal.hypothesis.inferred.append(
                AgentInference(
                    inference="claiming may unlock the next chapter",
                    inferred_at=NOW,
                    based_on_evidence_refs=["observation:obs-1"],
                )
            )
            store.save(journal)
            loaded = store.load("agent-1")
            self.assertEqual(loaded.tactical.observed[0].fact, "chapter is claimable")
            self.assertEqual(loaded.hypothesis.inferred[0].inference, "claiming may unlock the next chapter")


class ToolLogTests(unittest.TestCase):
    def test_argument_summary_redacts_secrets_and_hashes_text(self) -> None:
        summary = summarize_arguments(
            {
                "question": "private printable question",
                "access_token": "secret-value",
                "screenshot_bytes": b"raw-png",
            }
        )
        serialized = json.dumps(summary, sort_keys=True)
        self.assertNotIn("private printable question", serialized)
        self.assertNotIn("secret-value", serialized)
        self.assertNotIn("raw-png", serialized)
        self.assertEqual(summary["access_token"], "<redacted>")
        self.assertTrue(summary["screenshot_bytes"]["omitted"])

    def test_jsonl_log_round_trip(self) -> None:
        fixture = load_fixture("recommendation_ready.json")
        with TemporaryDirectory() as tmp:
            log = JsonlToolLog(Path(tmp) / "tools.jsonl")
            harness = RecommendationHarness(
                game_client=ScriptedMcpClient(fixture["game"]),
                qa_client=ScriptedMcpClient(fixture["qa"]),
                journal_store=InMemoryJournalStore(),
                tool_log=log,
                agent_session_id="agent-log",
                model_id="fixture-model",
                clock=lambda: NOW,
            )
            result = _run(harness.run_decision_window(qa_questions=["章节奖励先领吗？"]))
            self.assertEqual(result.status, DecisionWindowStatus.RECOMMENDED)
            records = log.read()
            self.assertEqual(
                [item.tool_name for item in records],
                ["session_status", "observe_game", "get_runtime_state", "answer_rule_question", "list_action_candidates"],
            )
            self.assertTrue(all(item.success for item in records))
            self.assertEqual(records[1].observation_refs[0], "observation_id:observation-1")
            raw_log = (Path(tmp) / "tools.jsonl").read_text(encoding="utf-8")
            self.assertNotIn("章节奖励先领吗", raw_log)


class RecommendationHarnessTests(unittest.TestCase):
    def test_harness_package_has_no_server_handler_or_control_import(self) -> None:
        package_root = Path(__file__).resolve().parents[2] / "src" / "pioneer_agent" / "agent_harness"
        source = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py"))
        self.assertNotIn("pioneer_agent.mcp_server", source)
        self.assertNotIn("pioneer_agent.executor", source)
        self.assertNotIn("pioneer_agent.adapters.control", source)

    def test_ready_fixture_runs_fixed_read_only_order_and_recommends(self) -> None:
        fixture = load_fixture("recommendation_ready.json")
        game = ScriptedMcpClient(fixture["game"])
        qa = ScriptedMcpClient(fixture["qa"])
        journal_store = InMemoryJournalStore()
        tool_log = InMemoryToolLog()
        harness = RecommendationHarness(
            game_client=game,
            qa_client=qa,
            journal_store=journal_store,
            tool_log=tool_log,
            agent_session_id="agent-ready",
            model_id="fixture-model",
            clock=lambda: NOW,
        )

        result = _run(harness.run_decision_window(qa_questions=["章节奖励先领吗？"]))

        self.assertEqual(result.status, DecisionWindowStatus.RECOMMENDED)
        self.assertEqual(result.recommendation.action_type, "claim_chapter_reward")  # type: ignore[union-attr]
        self.assertFalse(result.recommendation.executable)  # type: ignore[union-attr]
        self.assertIsNone(result.journal.last_verified_action)
        self.assertEqual(len(result.journal.pending_timers), 1)
        self.assertEqual(
            [name for name, _ in game.calls],
            ["session_status", "observe_game", "get_runtime_state", "list_action_candidates"],
        )
        self.assertEqual([name for name, _ in qa.calls], ["answer_rule_question"])
        self.assertTrue(all(name in GAME_READ_ONLY_TOOLS for name, _ in game.calls))
        self.assertTrue(result.journal.tactical.observed)
        self.assertTrue(result.journal.planning.inferred)
        self.assertTrue(result.journal.strategic.observed)

    def test_unknown_critical_domain_stops_before_state_or_proposals(self) -> None:
        fixture = load_fixture("recommendation_ready.json")
        fixture["game"]["observe_game"]["structuredContent"]["unknown_domains"] = ["map_land"]
        game = ScriptedMcpClient(fixture["game"])
        harness = _harness(game)

        result = _run(harness.run_decision_window())

        self.assertEqual(result.status, DecisionWindowStatus.STOPPED)
        self.assertEqual(result.stop.reason, StopReason.CRITICAL_DOMAIN_UNKNOWN)
        self.assertEqual([name for name, _ in game.calls], ["session_status", "observe_game"])

    def test_stale_observation_stops(self) -> None:
        fixture = load_fixture("recommendation_ready.json")
        fixture["game"]["observe_game"]["structuredContent"]["captured_at"] = "2026-08-26T09:00:00+08:00"
        result = _run(_harness(ScriptedMcpClient(fixture["game"])).run_decision_window())
        self.assertEqual(result.stop.reason, StopReason.OBSERVATION_STALE)

    def test_all_blocked_fixture_stops_without_recommendation(self) -> None:
        fixture = load_fixture("all_blocked.json")
        result = _run(_harness(ScriptedMcpClient(fixture["game"])).run_decision_window())
        self.assertEqual(result.stop.reason, StopReason.ALL_CANDIDATES_BLOCKED)
        self.assertIsNone(result.recommendation)

    def test_human_confirmation_candidate_is_reported_then_stops(self) -> None:
        fixture = load_fixture("recommendation_ready.json")
        candidates = fixture["game"]["list_action_candidates"]["structuredContent"]["candidates"]
        candidates[0] = {
            "action_id": "attack-land-5-1",
            "action_type": "attack_land",
            "risk": {"level": "high", "confirmation_required": True},
            "evidence": ["state.map.candidate_lands.5-1"],
            "confidence": 0.91,
            "blockers": [],
            "executable": False,
        }
        result = _run(_harness(ScriptedMcpClient(fixture["game"])).run_decision_window())
        self.assertEqual(result.stop.reason, StopReason.HUMAN_CONFIRMATION_REQUIRED)
        self.assertEqual(result.recommendation.action_type, "attack_land")  # type: ignore[union-attr]
        self.assertFalse(result.recommendation.executable)  # type: ignore[union-attr]

    def test_window_identity_change_from_journal_stops_before_observe(self) -> None:
        fixture = load_fixture("recommendation_ready.json")
        store = InMemoryJournalStore()
        journal = store.load("agent-window")
        journal.tooling.observed.append(
            ObservedFact(
                fact="window_identity",
                observed_at=NOW - timedelta(seconds=5),
                observation_id="old-observation",
                evidence_refs=["observation:old-observation"],
                metadata={"window_identity": {"hwnd": 999, "pid": 202, "title": "Sanmou"}},
            )
        )
        store.save(journal)
        game = ScriptedMcpClient(fixture["game"])
        harness = RecommendationHarness(
            game_client=game,
            journal_store=store,
            tool_log=InMemoryToolLog(),
            agent_session_id="agent-window",
            model_id="fixture-model",
            clock=lambda: NOW,
        )
        result = _run(harness.run_decision_window())
        self.assertEqual(result.stop.reason, StopReason.WINDOW_IDENTITY_CHANGED)
        self.assertEqual([name for name, _ in game.calls], ["session_status"])

    def test_checkpoint_staleness_stops_when_fresh_observation_misses_domain(self) -> None:
        fixture = load_fixture("recommendation_ready.json")
        fixture["game"]["observe_game"]["structuredContent"]["domains_run"].remove("resource_bar")
        store = InMemoryJournalStore()
        journal = store.load("agent-stale")
        journal.tooling.observed.append(
            ObservedFact(
                fact="checkpoint:resources",
                observed_at=NOW - timedelta(seconds=181),
                observation_id="old-observation",
                evidence_refs=["observation:old-observation"],
            )
        )
        store.save(journal)
        game = ScriptedMcpClient(fixture["game"])
        harness = RecommendationHarness(
            game_client=game,
            journal_store=store,
            tool_log=InMemoryToolLog(),
            agent_session_id="agent-stale",
            model_id="fixture-model",
            clock=lambda: NOW,
        )
        result = _run(harness.run_decision_window())
        self.assertEqual(result.stop.reason, StopReason.CHECKPOINT_STALE)
        self.assertEqual([name for name, _ in game.calls], ["session_status", "observe_game"])

    def test_two_consecutive_qa_failures_stop_without_proposals(self) -> None:
        fixture = load_fixture("recommendation_ready.json")
        game = ScriptedMcpClient(fixture["game"])
        qa = ScriptedMcpClient({"answer_rule_question": RuntimeError("offline")})
        harness = RecommendationHarness(
            game_client=game,
            qa_client=qa,
            journal_store=InMemoryJournalStore(),
            tool_log=InMemoryToolLog(),
            agent_session_id="agent-tool-failure",
            model_id="fixture-model",
            stop_policy=StopPolicy(max_consecutive_tool_failures=2),
            clock=lambda: NOW,
        )
        result = _run(harness.run_decision_window(qa_questions=["q1", "q2"]))
        self.assertEqual(result.stop.reason, StopReason.CONSECUTIVE_TOOL_FAILURES)
        self.assertEqual([name for name, _ in game.calls], ["session_status", "observe_game", "get_runtime_state"])
        self.assertEqual(len(qa.calls), 2)

    def test_non_none_execution_authority_fails_closed(self) -> None:
        fixture = load_fixture("recommendation_ready.json")
        fixture["game"]["session_status"]["structuredContent"]["execution_authority"] = "control"
        result = _run(_harness(ScriptedMcpClient(fixture["game"])).run_decision_window())
        self.assertEqual(result.stop.reason, StopReason.EXECUTION_AUTHORITY_VIOLATION)


def _harness(game: ScriptedMcpClient) -> RecommendationHarness:
    return RecommendationHarness(
        game_client=game,
        journal_store=InMemoryJournalStore(),
        tool_log=InMemoryToolLog(),
        agent_session_id="agent-test",
        model_id="fixture-model",
        clock=lambda: NOW,
    )


def _run(awaitable):  # noqa: ANN001
    import asyncio

    return asyncio.run(awaitable)
