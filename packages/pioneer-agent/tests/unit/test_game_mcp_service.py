from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from pioneer_agent.adapters.capture import CaptureFrame
from pioneer_agent.core.device import (
    CapabilityFlags,
    DevicePlatform,
    DeviceProfile,
    DeviceSession,
    ObservationSource,
    ObservationSourceType,
)
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ObservationSnapshot, RuntimeState, SelectionResult
from pioneer_agent.mcp_server.service import (
    MAX_TRACE_ACTIONS,
    MAX_TRACE_FRAMES,
    GameMCPService,
    ObservedAdvisorCycle,
)
from pioneer_agent.perception.vision_sync import VisionSyncSummary
from pioneer_agent.runtime.advisor_loop import build_advisor_report
from pioneer_agent.storage.trace_store import (
    TickTrace,
    TraceFrameReference,
    TraceFrameRole,
    TraceStore,
)


class _CountingProvider:
    def __init__(self, cycle: ObservedAdvisorCycle) -> None:
        self.cycle = cycle
        self.calls = 0

    def observe(self) -> ObservedAdvisorCycle:
        self.calls += 1
        return self.cycle


class _RecordingFixtureEvaluator:
    def __init__(self) -> None:
        self.paths: list[Path] = []

    def evaluate(self, fixture_path: Path) -> dict:
        self.paths.append(fixture_path)
        return {"fixture": fixture_path.name, "execution_authority": "none"}


def _cycle() -> ObservedAdvisorCycle:
    captured_at = datetime(2026, 8, 26, 12, 0, 0, tzinfo=UTC)
    session = DeviceSession(
        session_id="session-1",
        profile=DeviceProfile(
            profile_id="profile-1",
            platform=DevicePlatform.PC_CLIENT,
            resolution=(1286, 666),
        ),
        source=ObservationSource(
            source_id="source-1",
            source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
            capabilities=CapabilityFlags(
                observe_only=True,
                live_capture=True,
                reliable_window_info=True,
            ),
        ),
    )
    state = RuntimeState(progress={"chapter_claimable": True})
    action = CandidateAction(
        action_id="claim-1",
        action_type=ActionType.CLAIM_CHAPTER_REWARD,
        source_state_refs=["progress.chapter_claimable"],
    ).model_copy(update={"score_total": 100.0})
    report = build_advisor_report(
        frame=CaptureFrame(
            png=b"frame",
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
            domains_run=["resource_bar", "chapter_panel"],
            unknown_domains=[],
            notes=[],
        ),
    )
    observation = ObservationSnapshot(
        observation_id="observation-1",
        captured_at=captured_at,
        frame_sha256="a" * 64,
        frame_size=(1286, 666),
        page_type="chapter",
        domains_run=["resource_bar", "chapter_panel"],
        observed_state=state,
        source="vision_sync",
    )
    return ObservedAdvisorCycle(observation=observation, report=report)


class GameMCPServiceTests(unittest.TestCase):
    def test_empty_service_is_explicit_and_does_not_observe(self) -> None:
        service = GameMCPService()

        self.assertEqual(service.session_status().status, "ok")
        self.assertIsNone(service.session_status().session)
        self.assertEqual(service.observe_game().status, "not_configured")
        self.assertEqual(service.get_runtime_state().status, "not_observed")
        self.assertEqual(service.get_advisor_report().status, "not_observed")
        self.assertEqual(service.list_action_candidates().status, "not_observed")

    def test_only_observe_game_refreshes_provider_and_cached_tools_have_parity(self) -> None:
        provider = _CountingProvider(_cycle())
        service = GameMCPService(observation_provider=provider)

        observed = service.observe_game()
        state = service.get_runtime_state()
        report = service.get_advisor_report()
        candidates = service.list_action_candidates()
        status = service.session_status()

        self.assertEqual(provider.calls, 1)
        self.assertEqual(observed.status, "ok")
        self.assertEqual(observed.observation, state.observation)
        self.assertEqual(observed.observation, report.observation)
        self.assertEqual(observed.observation, candidates.observation)
        self.assertEqual(observed.observation, status.latest_observation)
        self.assertEqual(state.runtime_state, report.advisor_report["current_state"])
        self.assertEqual(candidates.candidates[0].action_id, "claim-1")
        self.assertFalse(candidates.candidates[0].executable)
        self.assertEqual(candidates.candidates[0].execution_authority, "none")
        self.assertEqual(candidates.candidates[0].blockers, ["advisor_mode"])

    def test_failed_refresh_preserves_previous_cache(self) -> None:
        cycle = _cycle()

        class _FailsAfterOne:
            calls = 0

            def observe(self) -> ObservedAdvisorCycle:
                self.calls += 1
                if self.calls > 1:
                    raise RuntimeError("capture unavailable")
                return cycle

        provider = _FailsAfterOne()
        service = GameMCPService(observation_provider=provider)
        first = service.observe_game()
        failed = service.observe_game()

        self.assertEqual(first.status, "ok")
        self.assertEqual(failed.status, "error")
        self.assertEqual(service.get_runtime_state().observation, first.observation)

    def test_refresh_rejects_reused_observation_id(self) -> None:
        provider = _CountingProvider(_cycle())
        service = GameMCPService(observation_provider=provider)

        first = service.observe_game()
        repeated = service.observe_game()

        self.assertEqual(first.status, "ok")
        self.assertEqual(repeated.status, "error")
        self.assertEqual(repeated.error.code, "observation_not_fresh")  # type: ignore[union-attr]
        self.assertEqual(service.get_runtime_state().observation, first.observation)

    def test_last_trace_is_bounded_and_does_not_expose_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = TraceStore(Path(tmp) / "trace.jsonl")
            frames = [
                TraceFrameReference(
                    role=TraceFrameRole.PRE_ACTION,
                    path=f"/private/raw/frame-{index}.png",
                    sha256=f"{index:064x}",
                    observation={
                        "observation_id": f"observation-{index}",
                        "captured_at": datetime(2026, 8, 26, 12, 0, index, tzinfo=UTC).isoformat(),
                        "frame_sha256": f"{index:064x}",
                    },
                )
                for index in range(MAX_TRACE_FRAMES + 3)
            ]
            store.append(
                TickTrace(
                    trace_id="trace-1",
                    session_id="session-1",
                    iteration=3,
                    frames=frames,
                    ranked_actions=[
                        {
                            "action_id": f"action-{index}",
                            "action_type": "wait_for_resource",
                            "score_total": float(index),
                            "private_debug": "drop-me",
                        }
                        for index in range(MAX_TRACE_ACTIONS + 4)
                    ],
                    verification={
                        "status": "verified",
                        "raw_image_path": "/private/raw/post.png",
                    },
                )
            )

            response = GameMCPService(trace_store=store).get_last_trace()

            self.assertEqual(response.status, "ok")
            assert response.trace is not None
            self.assertEqual(len(response.trace.frames), MAX_TRACE_FRAMES)
            self.assertEqual(len(response.trace.ranked_actions), MAX_TRACE_ACTIONS)
            serialized = response.model_dump_json()
            self.assertNotIn("/private/raw", serialized)
            self.assertNotIn("private_debug", serialized)
            self.assertNotIn("raw_image_path", serialized)
            self.assertIn("frame-sha256:", serialized)

    def test_fixture_evaluation_is_closed_root_and_never_uses_live_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            root.mkdir()
            fixture = root / "state.json"
            fixture.write_text(json.dumps({"progress": {}}), encoding="utf-8")
            outside = Path(tmp) / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            escaping_link = root / "escaping.json"
            escaping_link.symlink_to(outside)
            evaluator = _RecordingFixtureEvaluator()
            provider = _CountingProvider(_cycle())
            service = GameMCPService(
                fixture_root=root,
                fixture_evaluator=evaluator,
                observation_provider=provider,
            )

            accepted = service.evaluate_fixture("state.json")
            traversal = service.evaluate_fixture("../outside.json")
            absolute = service.evaluate_fixture(str(outside))
            symlink_escape = service.evaluate_fixture("escaping.json")

            self.assertEqual(accepted.status, "ok")
            self.assertEqual(accepted.fixture_id, "state.json")
            self.assertFalse(accepted.live_source_used)
            self.assertEqual(evaluator.paths, [fixture.resolve()])
            self.assertEqual(provider.calls, 0)
            self.assertEqual(traversal.status, "invalid_request")
            self.assertEqual(absolute.status, "invalid_request")
            self.assertEqual(symlink_escape.status, "invalid_request")

    def test_real_fixture_evaluator_returns_advisory_projection(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        service = GameMCPService(fixture_root=project_root / "tests" / "fixtures")

        response = service.evaluate_fixture("chapter_claimable_state.json")

        self.assertEqual(response.status, "ok")
        assert response.evaluation is not None
        self.assertEqual(response.evaluation["execution_authority"], "none")
        self.assertNotIn("runtime_dispatch", response.evaluation)
        self.assertFalse(response.evaluation["selected_action"]["executable"])
        self.assertEqual(
            response.evaluation["selected_action"]["execution_blocked_reason"],
            "offline_fixture",
        )


if __name__ == "__main__":
    unittest.main()
