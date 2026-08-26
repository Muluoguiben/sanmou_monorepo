from __future__ import annotations

import ast
import asyncio
import json
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pioneer_agent.adapters.capture import CaptureFrame
from pioneer_agent.agent_harness.contracts import InProcessMcpClient
from pioneer_agent.agent_harness.journal import InMemoryJournalStore
from pioneer_agent.agent_harness.loop import DecisionWindowStatus, RecommendationHarness
from pioneer_agent.agent_harness.policy import StopReason
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
from pioneer_agent.core.device import (
    CapabilityFlags,
    DevicePlatform,
    DeviceProfile,
    DeviceSession,
    ObservationSource,
    ObservationSourceType,
)
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import (
    CandidateAction,
    CaptureGeometry,
    CapturePoint,
    CaptureRect,
    CaptureWindowIdentity,
    ObservationSnapshot,
    RuntimeState,
    SelectionResult,
)
from pioneer_agent.mcp_server.contracts import (
    CONTRACT_VERSION,
    GAME_TOOL_ARGUMENTS,
    GET_RUNTIME_STATE_TOOL,
    LIST_ACTION_CANDIDATES_TOOL,
    OBSERVE_GAME_TOOL,
    SESSION_STATUS_TOOL,
)
from pioneer_agent.mcp_server.server import build_live_service, create_server
from pioneer_agent.mcp_server.service import ObservedAdvisorCycle
from pioneer_agent.perception.vision_sync import VisionSyncSummary
from pioneer_agent.runtime.advisor_loop import build_advisor_report


NOW = datetime(2026, 8, 27, 10, 0, 10, tzinfo=UTC)
PRIVATE_PATH = "/private/account/frame.png"
PRIVATE_SECRET = "do-not-expose"


class _FakeObservationProvider:
    def __init__(self, cycle: ObservedAdvisorCycle) -> None:
        self.cycle = cycle
        self.calls = 0

    def observe(self) -> ObservedAdvisorCycle:
        self.calls += 1
        return self.cycle


class AgentHarnessGameMCPIntegrationTests(unittest.TestCase):
    def test_live_server_order_privacy_and_recommendation_only_authority(self) -> None:
        cycle = _cycle(captured_at=NOW - timedelta(seconds=10))
        provider = _FakeObservationProvider(cycle)
        service = build_live_service(
            observation_provider=provider,
            device_session=cycle.report.device_session,
        )
        client = InProcessMcpClient(create_server(service))
        tool_log = InMemoryToolLog()
        harness = RecommendationHarness(
            game_client=client,
            journal_store=InMemoryJournalStore(),
            tool_log=tool_log,
            agent_session_id="agent-in-process",
            model_id="integration-fixture",
            clock=lambda: NOW,
        )

        result = asyncio.run(harness.run_decision_window())

        self.assertEqual(result.status, DecisionWindowStatus.RECOMMENDED)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(
            [name for name, _ in client.calls],
            [
                SESSION_STATUS_TOOL,
                OBSERVE_GAME_TOOL,
                GET_RUNTIME_STATE_TOOL,
                LIST_ACTION_CANDIDATES_TOOL,
            ],
        )
        assert result.recommendation is not None
        self.assertFalse(result.recommendation.executable)
        self.assertEqual(result.recommendation.execution_authority, "none")
        self.assertEqual(result.recommendation.execution_blocked_reason, "advisor_mode")
        self.assertIsNone(result.journal.last_verified_action)
        self.assertTrue(all(record.result_summary["execution_authority"] == "none" for record in tool_log.records))
        serialized = result.model_dump_json() + json.dumps(
            [record.model_dump(mode="json") for record in tool_log.records],
            ensure_ascii=False,
        )
        self.assertNotIn(PRIVATE_PATH, serialized)
        self.assertNotIn(PRIVATE_SECRET, serialized)
        self.assertEqual(CONTRACT_VERSION, "sanmou-game/v1")
        self.assertTrue(
            all("contract_version" in record.result_summary["keys"] for record in tool_log.records)
        )

    def test_unknown_stale_and_blocked_cycles_stop_fail_closed(self) -> None:
        scenarios = (
            (
                "unknown",
                _cycle(
                    captured_at=NOW - timedelta(seconds=10),
                    domains_run=["resource_bar", "chapter_panel"],
                    unknown_domains=["map_land"],
                ),
                StopReason.CRITICAL_DOMAIN_UNKNOWN,
                [SESSION_STATUS_TOOL, OBSERVE_GAME_TOOL],
            ),
            (
                "stale",
                _cycle(captured_at=NOW - timedelta(minutes=10)),
                StopReason.OBSERVATION_STALE,
                [SESSION_STATUS_TOOL, OBSERVE_GAME_TOOL],
            ),
            (
                "blocked",
                _cycle(
                    captured_at=NOW - timedelta(seconds=10),
                    execution_blocked_reason="resource_threshold_unknown",
                ),
                StopReason.ALL_CANDIDATES_BLOCKED,
                [
                    SESSION_STATUS_TOOL,
                    OBSERVE_GAME_TOOL,
                    GET_RUNTIME_STATE_TOOL,
                    LIST_ACTION_CANDIDATES_TOOL,
                ],
            ),
        )
        for name, cycle, expected_reason, expected_calls in scenarios:
            with self.subTest(name=name):
                provider = _FakeObservationProvider(cycle)
                client = InProcessMcpClient(
                    create_server(
                        build_live_service(
                            observation_provider=provider,
                            device_session=cycle.report.device_session,
                        )
                    )
                )
                result = asyncio.run(
                    RecommendationHarness(
                        game_client=client,
                        journal_store=InMemoryJournalStore(),
                        tool_log=InMemoryToolLog(),
                        agent_session_id=f"agent-{name}",
                        model_id="integration-fixture",
                        clock=lambda: NOW,
                    ).run_decision_window()
                )
                self.assertEqual(result.status, DecisionWindowStatus.STOPPED)
                self.assertEqual(result.stop.reason, expected_reason)
                self.assertEqual([tool_name for tool_name, _ in client.calls], expected_calls)
                self.assertIsNone(result.journal.last_verified_action)

    def test_composed_surface_has_no_mutating_tool_or_control_import(self) -> None:
        tools = asyncio.run(create_server(build_live_service(
            observation_provider=_FakeObservationProvider(_cycle(captured_at=NOW)),
        )).list_tools())
        tool_names = [tool.name for tool in tools]
        self.assertEqual(tool_names, list(GAME_TOOL_ARGUMENTS))
        self.assertFalse(
            set(tool_names).intersection(
                {"click", "press_key", "prepare_action", "execute_prepared_action"}
            )
        )

        src_root = Path(__file__).resolve().parents[2] / "src" / "pioneer_agent"
        imported: set[str] = set()
        for package in (src_root / "agent_harness", src_root / "mcp_server"):
            for path in package.glob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imported.update(alias.name for alias in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported.add(node.module)
        forbidden = (
            "pioneer_agent.executor",
            "pioneer_agent.adapters.control",
            "pioneer_agent.adapters.bridge_client",
            "pioneer_agent.adapters.win_bridge_server",
            "pioneer_agent.runtime.replay_runtime",
            "pioneer_agent.verifier",
        )
        self.assertFalse(
            {
                name
                for name in imported
                if any(name == item or name.startswith(f"{item}.") for item in forbidden)
            }
        )


def _cycle(
    *,
    captured_at: datetime,
    domains_run: list[str] | None = None,
    unknown_domains: list[str] | None = None,
    execution_blocked_reason: str = "advisor_mode",
) -> ObservedAdvisorCycle:
    domains = domains_run or [
        "resource_bar",
        "chapter_panel",
        "team_panel",
        "map_land",
        "battle_report",
        "timing",
    ]
    unknown = unknown_domains or []
    capabilities = CapabilityFlags(
        observe_only=True,
        live_capture=True,
        reliable_window_info=True,
    )
    session = DeviceSession(
        session_id="game-session-integration",
        profile=DeviceProfile(
            profile_id="profile-integration",
            platform=DevicePlatform.PC_CLIENT,
            resolution=(1280, 720),
        ),
        source=ObservationSource(
            source_id="source-integration",
            source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
            uri=PRIVATE_PATH,
            capabilities=capabilities,
            metadata={"secret": PRIVATE_SECRET},
        ),
        capabilities=capabilities,
        started_at=NOW - timedelta(minutes=5),
    )
    window = CaptureWindowIdentity(
        left=10,
        top=20,
        right=1290,
        bottom=740,
        width=1280,
        height=720,
        hwnd=101,
        pid=202,
    )
    geometry = CaptureGeometry(
        capture_backend="wgc",
        outer_window=window,
        capture_rect=CaptureRect(
            left=10,
            top=20,
            right=1290,
            bottom=740,
            width=1280,
            height=720,
        ),
        capture_origin=CapturePoint(x=10, y=20),
        frame_size=(1280, 720),
    )
    state = RuntimeState(
        progress={"chapter_claimable": True, "current_chapter_id": 8},
        city={
            "notes": [PRIVATE_PATH],
            "metadata": {"secret": PRIVATE_SECRET},
        },
        timing={"next_action_ready_time": (NOW + timedelta(minutes=5)).isoformat()},
    )
    action = CandidateAction(
        action_id="claim-chapter-8",
        action_type=ActionType.CLAIM_CHAPTER_REWARD,
        risk={"level": "low", "confirmation_required": False},
        source_state_refs=["progress.chapter_claimable", PRIVATE_PATH],
        score_total=100.0,
    )
    report = build_advisor_report(
        frame=CaptureFrame(
            png=b"private-frame-bytes",
            captured_at=captured_at,
            device_session=session,
            source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
        ),
        state=state,
        selection=SelectionResult(
            selected_action=action,
            ranked_actions=[action],
            selection_reason={"triggered_rules": ["chapter_reward_first"]},
        ),
        vision_summary=VisionSyncSummary(
            page_type="chapter",
            domains_run=domains,
            unknown_domains=unknown,
            notes=[],
        ),
    )
    if execution_blocked_reason != "advisor_mode":
        blocked = report.available_actions[0].model_copy(
            update={"execution_blocked_reason": execution_blocked_reason}
        )
        report = report.model_copy(
            update={"available_actions": [blocked], "recommended_action": blocked}
        )
    observation = ObservationSnapshot(
        observation_id="observation-integration",
        captured_at=captured_at,
        frame_sha256="c" * 64,
        frame_size=(1280, 720),
        capture_geometry=geometry,
        page_type="chapter",
        domains_run=domains,
        unknown_domains=unknown,
        observed_state=state,
        source="vision_sync",
    )
    return ObservedAdvisorCycle(observation=observation, report=report)


if __name__ == "__main__":
    unittest.main()
