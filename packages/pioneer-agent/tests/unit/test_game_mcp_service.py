from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import types
import unittest
from unittest import mock
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
    MAX_FIXTURE_BYTES,
    MAX_TRACE_ACTIONS,
    MAX_TRACE_FRAMES,
    GameMCPService,
    ObservedAdvisorCycle,
)
from pioneer_agent.runtime.evidence import AdvisorEvidence
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
        self.fixtures: list[tuple[str, bytes]] = []

    def evaluate(self, fixture_bytes: bytes, *, fixture_id: str) -> dict:
        self.fixtures.append((fixture_id, fixture_bytes))
        return {"fixture": fixture_id, "execution_authority": "none"}


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

    def test_observe_game_is_single_flight(self) -> None:
        started = threading.Event()
        release = threading.Event()

        class _BlockingProvider:
            calls = 0

            def observe(self) -> ObservedAdvisorCycle:
                self.calls += 1
                started.set()
                self.assert_released = release.wait(timeout=5)
                return _cycle()

        provider = _BlockingProvider()
        service = GameMCPService(observation_provider=provider)
        results = []
        worker = threading.Thread(target=lambda: results.append(service.observe_game()))
        worker.start()
        self.assertTrue(started.wait(timeout=5))

        overlapping = service.observe_game()

        self.assertEqual(overlapping.status, "error")
        self.assertEqual(overlapping.error.code, "observation_in_progress")  # type: ignore[union-attr]
        self.assertEqual(provider.calls, 1)
        release.set()
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0].status, "ok")

    def test_live_outputs_use_explicit_privacy_projection(self) -> None:
        cycle = _cycle()
        private_path = "/private/account/frame.png"
        private_uri = "file:///private/account/frame.png"
        private_base64 = "A" * 256
        long_text = "敏感" * 1_000
        cycle.report.current_state.city["notes"] = [
            private_path,
            private_uri,
            private_base64,
            long_text,
        ]
        cycle.report.current_state.city["metadata"] = {"secret": "do-not-expose"}
        cycle.report.current_state.map_state["uri"] = private_uri
        action = cycle.report.available_actions[0].model_copy(
            update={
                "params": {
                    **cycle.report.available_actions[0].params,
                    "notes": [private_path, private_base64, long_text],
                    "metadata": {"secret": "do-not-expose"},
                },
                "risk": {"summary": private_uri, "metadata": {"secret": "x"}},
                "evidence": [private_path, "progress.chapter_claimable"],
                "structured_evidence": [
                    AdvisorEvidence(
                        evidence_id="state:progress.chapter_claimable",
                        source_type="state",
                        ref="progress.chapter_claimable",
                        summary=private_path,
                        source_ref=private_uri,
                        metadata={"uri": private_uri, "secret": "do-not-expose"},
                    )
                ],
            }
        )
        cycle = ObservedAdvisorCycle(
            observation=cycle.observation,
            report=cycle.report.model_copy(
                update={
                    "available_actions": [action],
                    "recommended_action": action,
                    "evidence": [private_path, "progress.chapter_claimable"],
                    "structured_evidence": action.structured_evidence,
                    "selection_reason": {
                        **cycle.report.selection_reason,
                        "metadata": {"uri": private_uri},
                    },
                }
            ),
        )
        service = GameMCPService(observation_provider=_CountingProvider(cycle))

        self.assertEqual(service.observe_game().status, "ok")
        responses = [
            service.get_runtime_state(),
            service.get_advisor_report(),
            service.list_action_candidates(),
        ]
        serialized = "\n".join(response.model_dump_json() for response in responses)

        self.assertNotIn(private_path, serialized)
        self.assertNotIn(private_uri, serialized)
        self.assertNotIn(private_base64, serialized)
        self.assertNotIn("do-not-expose", serialized)
        self.assertNotIn('"uri"', serialized)
        self.assertNotIn('"metadata"', serialized)
        self.assertNotIn('"device_session"', serialized)
        self.assertNotIn('"account_session"', serialized)
        self.assertLessEqual(_longest_string(json.loads(responses[1].model_dump_json())), 500)

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
                            "params": {
                                "notes": [
                                    "/private/raw/action.png",
                                    "data:image/png;base64," + "A" * 256,
                                ],
                                "uri": "file:///private/raw/action.png",
                            },
                            "private_debug": "drop-me",
                        }
                        for index in range(MAX_TRACE_ACTIONS + 4)
                    ],
                    verification={
                        "status": "verified",
                        "raw_image_path": "/private/raw/post.png",
                        "metadata": {"uri": "file:///private/raw/post.png"},
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
            self.assertNotIn("data:image", serialized)
            self.assertNotIn('"metadata"', serialized)
            self.assertNotIn('"uri"', serialized)
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
            self.assertEqual(
                evaluator.fixtures,
                [("state.json", fixture.read_bytes())],
            )
            self.assertEqual(provider.calls, 0)
            self.assertEqual(traversal.status, "invalid_request")
            self.assertEqual(absolute.status, "invalid_request")
            self.assertEqual(symlink_escape.status, "invalid_request")

    def test_fixture_read_is_bounded_no_follow_and_hardlink_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            root.mkdir()
            valid = root / "valid.json"
            valid.write_text(json.dumps({"progress": {}}), encoding="utf-8")
            (root / "inside-link.json").symlink_to(valid)
            nested_target = root / "nested-target"
            nested_target.mkdir()
            (nested_target / "state.json").write_text("{}", encoding="utf-8")
            (root / "nested-link").symlink_to(nested_target, target_is_directory=True)
            oversized = root / "oversized.json"
            oversized.write_bytes(b"{" + b" " * MAX_FIXTURE_BYTES + b"}")
            hardlink = root / "hardlink.json"
            os.link(valid, hardlink)
            service = GameMCPService(
                fixture_root=root,
                fixture_evaluator=_RecordingFixtureEvaluator(),
            )

            self.assertEqual(service.evaluate_fixture("inside-link.json").status, "invalid_request")
            self.assertEqual(
                service.evaluate_fixture("nested-link/state.json").status,
                "invalid_request",
            )
            self.assertEqual(service.evaluate_fixture("oversized.json").status, "invalid_request")
            self.assertEqual(service.evaluate_fixture("hardlink.json").status, "invalid_request")

    def test_fixture_evaluator_receives_pinned_bytes_not_a_reopenable_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "fixtures"
            root.mkdir()
            fixture = root / "state.json"
            original = json.dumps({"progress": {"current_chapter_id": 1}}).encode()
            replacement = json.dumps({"progress": {"current_chapter_id": 99}}).encode()
            fixture.write_bytes(original)

            class _ReplacingEvaluator:
                received = b""

                def evaluate(self, fixture_bytes: bytes, *, fixture_id: str) -> dict:
                    self.received = fixture_bytes
                    fixture.unlink()
                    fixture.write_bytes(replacement)
                    return {"fixture": fixture_id, "execution_authority": "none"}

            evaluator = _ReplacingEvaluator()
            response = GameMCPService(
                fixture_root=root,
                fixture_evaluator=evaluator,
            ).evaluate_fixture("state.json")

            self.assertEqual(response.status, "ok")
            self.assertEqual(evaluator.received, original)
            self.assertEqual(fixture.read_bytes(), replacement)

    def test_real_fixture_evaluator_returns_advisory_projection(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        service = GameMCPService(fixture_root=project_root / "tests" / "fixtures")

        response = service.evaluate_fixture("chapter_claimable_state.json")

        self.assertEqual(response.status, "ok")
        assert response.evaluation is not None
        self.assertEqual(response.evaluation["execution_authority"], "none")
        self.assertNotIn("runtime_dispatch", response.evaluation)
        self.assertNotIn("semantic_target_gate", response.evaluation)
        self.assertNotIn("verifier_gate", response.evaluation)
        self.assertFalse(response.evaluation["selected_action"]["executable"])
        self.assertEqual(
            response.evaluation["selected_action"]["execution_blocked_reason"],
            "offline_fixture",
        )

    def test_fixture_evaluator_never_imports_or_calls_runner_modules(self) -> None:
        project_root = Path(__file__).resolve().parents[2]

        class _RunnerTrap:
            calls = 0

            def __init__(self, *args, **kwargs) -> None:
                type(self).calls += 1

            def run(self, *args, **kwargs):
                type(self).calls += 1
                raise AssertionError("runner must not be called")

            def run_fixture(self, *args, **kwargs):
                type(self).calls += 1
                raise AssertionError("ReplayRuntime must not be called")

        fake_replay = types.ModuleType("pioneer_agent.runtime.replay_runtime")
        fake_replay.ReplayRuntime = _RunnerTrap
        fake_runner = types.ModuleType("pioneer_agent.executor.ui_runner")
        fake_runner.UIActionRunner = _RunnerTrap
        with mock.patch.dict(
            sys.modules,
            {
                "pioneer_agent.runtime.replay_runtime": fake_replay,
                "pioneer_agent.executor.ui_runner": fake_runner,
            },
        ):
            response = GameMCPService(
                fixture_root=project_root / "tests" / "fixtures"
            ).evaluate_fixture("chapter_claimable_state.json")
            self.assertIs(sys.modules["pioneer_agent.runtime.replay_runtime"], fake_replay)
            self.assertIs(sys.modules["pioneer_agent.executor.ui_runner"], fake_runner)

        self.assertEqual(response.status, "ok")
        self.assertEqual(_RunnerTrap.calls, 0)


def _longest_string(value) -> int:  # noqa: ANN001
    if isinstance(value, str):
        return len(value)
    if isinstance(value, dict):
        return max((_longest_string(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return max((_longest_string(item) for item in value), default=0)
    return 0


if __name__ == "__main__":
    unittest.main()
