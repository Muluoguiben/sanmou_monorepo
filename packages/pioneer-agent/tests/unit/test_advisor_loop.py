from __future__ import annotations

import io
import unittest
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from pioneer_agent.adapters.capture import CaptureFrame
from pioneer_agent.core.device import (
    AccountSession,
    CapabilityFlags,
    DevicePlatform,
    DeviceProfile,
    DeviceSession,
    ObservationSource,
    ObservationSourceType,
)
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState, SelectionResult
from pioneer_agent.core.runtime_state_io import load_runtime_state_record
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.perception.screenshot_interpreter import ScreenshotInterpretation
from pioneer_agent.perception.vision_sync import VisionSyncSummary
from pioneer_agent.runtime.evidence import EvidenceValidationError
from pioneer_agent.runtime.advisor_loop import AdvisorLoop, build_advisor_report
from pioneer_agent.selector.action_selector import ActionSelector


def _png(size: tuple[int, int]) -> bytes:
    image = Image.new("RGB", size, (0, 0, 0))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class _Capture:
    session: DeviceSession
    size: tuple[int, int]

    @property
    def device_session(self) -> DeviceSession:
        return self.session

    @property
    def capabilities(self) -> CapabilityFlags:
        return self.session.capabilities

    def capture(self) -> CaptureFrame:
        return CaptureFrame(
            png=_png(self.size),
            captured_at=datetime(2026, 1, 1, 0, 0, 0),
            device_session=self.session,
            source_type=self.session.source.source_type,
        )

    def screenshot(self, save_path=None):  # noqa: ANN001
        return self.capture().png


class _FixedVisionSync:
    def sync(self, image, state=None, *, captured_at=None):  # noqa: ANN001
        runtime_state = RuntimeState(
            progress={"chapter_claimable": True, "current_chapter_id": 3},
            economy={"resources": {"wood": 1000}},
        )
        return runtime_state, VisionSyncSummary(
            page_type="chapter",
            domains_run=["resource_bar", "chapter_panel"],
            notes=[],
        )


class _FixedSelector:
    def __init__(self, action: CandidateAction) -> None:
        self.action = action

    def select(self, state):  # noqa: ANN001
        ranked = [self.action.model_copy(update={"score_total": 10000.0})]
        return SelectionResult(
            selected_action=ranked[0],
            ranked_actions=ranked,
            selection_reason={"triggered_rules": ["chapter_reward_first"]},
        )


class _IdentityDeriver:
    def derive(self, state):  # noqa: ANN001
        return state


def _session(platform: DevicePlatform, source_type: ObservationSourceType, size: tuple[int, int]) -> DeviceSession:
    source = ObservationSource(
        source_type=source_type,
        capabilities=CapabilityFlags(observe_only=True),
    )
    return DeviceSession(
        profile=DeviceProfile(platform=platform, resolution=size, screenshot_size=size),
        source=source,
    )


class AdvisorLoopTests(unittest.TestCase):
    def test_ios_advisor_report_never_marks_actions_executable(self) -> None:
        action = CandidateAction(
            action_id="claim-3",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
            params={"chapter_id": 3},
            source_state_refs=["progress.chapter_claimable"],
        )
        loop = AdvisorLoop(
            _Capture(
                _session(DevicePlatform.IOS, ObservationSourceType.SCREENSHOT_FILE, (1170, 2532)),
                (1170, 2532),
            ),
            _FixedVisionSync(),  # type: ignore[arg-type]
            selector=_FixedSelector(action),  # type: ignore[arg-type]
            deriver=_IdentityDeriver(),  # type: ignore[arg-type]
            account_session=AccountSession(server_id="s1"),
        )

        report = loop.tick()

        self.assertEqual(report.mode, "advisor")
        self.assertEqual(report.device_session.profile.platform, DevicePlatform.IOS)
        self.assertIsNotNone(report.recommended_action)
        self.assertFalse(report.recommended_action.executable)  # type: ignore[union-attr]
        self.assertEqual(report.recommended_action.execution_blocked_reason, "advisor_mode")  # type: ignore[union-attr]

    def test_same_game_state_from_different_devices_yields_same_recommendation_type(self) -> None:
        action = CandidateAction(
            action_id="claim-3",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
            params={"chapter_id": 3},
        )
        selector = _FixedSelector(action)
        reports = []
        for session, size in [
            (_session(DevicePlatform.PC_CLIENT, ObservationSourceType.WINDOWS_WINDOW_CAPTURE, (1920, 1080)), (1920, 1080)),
            (_session(DevicePlatform.ANDROID_EMULATOR, ObservationSourceType.SCREENSHOT_FILE, (2560, 1440)), (2560, 1440)),
        ]:
            reports.append(
                AdvisorLoop(
                    _Capture(session, size),
                    _FixedVisionSync(),  # type: ignore[arg-type]
                    selector=selector,  # type: ignore[arg-type]
                    deriver=_IdentityDeriver(),  # type: ignore[arg-type]
                ).tick()
            )

        self.assertEqual(
            reports[0].recommended_action.action_type,  # type: ignore[union-attr]
            reports[1].recommended_action.action_type,  # type: ignore[union-attr]
        )

    def test_build_report_contains_required_advisor_fields(self) -> None:
        action = CandidateAction(
            action_id="wait",
            action_type=ActionType.WAIT_FOR_RESOURCE,
            params={"target_resource": "wood"},
            source_state_refs=["economy.resources"],
        ).model_copy(update={"score_total": 12.0})
        selection = SelectionResult(
            selected_action=action,
            ranked_actions=[action],
            selection_reason={"triggered_rules": ["resource_gate"]},
        )
        frame = CaptureFrame(
            png=b"not-used",
            captured_at=datetime(2026, 1, 1, 0, 0, 0),
            device_session=_session(DevicePlatform.ANDROID, ObservationSourceType.SCREENSHOT_FILE, (2400, 1080)),
            source_type=ObservationSourceType.SCREENSHOT_FILE,
        )

        report = build_advisor_report(
            frame=frame,
            state=RuntimeState(economy={"resources": {"wood": 1}}),
            selection=selection,
            vision_summary=VisionSyncSummary(page_type="city", domains_run=["resource_bar"], notes=[]),
        )

        self.assertEqual(report.current_state_summary["page_type"], "city")
        self.assertEqual(len(report.available_actions), 1)
        self.assertEqual(report.recommended_action.score, 12.0)  # type: ignore[union-attr]
        self.assertIn("vision.domain:resource_bar", report.evidence)
        self.assertIn("selector.rule:resource_gate", report.evidence)
        self.assertIn("vision.domain:resource_bar", [item.ref for item in report.structured_evidence])
        self.assertIn("selector.rule:resource_gate", [item.ref for item in report.structured_evidence])

    def test_build_report_serializes_unknown_domain_as_untrusted_evidence(self) -> None:
        frame = CaptureFrame(
            png=b"not-used",
            captured_at=datetime(2026, 7, 21, 12, 0, 0),
            device_session=_session(
                DevicePlatform.PC_CLIENT,
                ObservationSourceType.SCREENSHOT_FILE,
                (1920, 1080),
            ),
            source_type=ObservationSourceType.SCREENSHOT_FILE,
        )
        report = build_advisor_report(
            frame=frame,
            state=RuntimeState(),
            selection=SelectionResult(),
            vision_summary=VisionSyncSummary(
                page_type="main_map",
                domains_run=["resource_bar"],
                unknown_domains=["map_land"],
                notes=["secondary map parser was uncertain"],
            ),
        )

        serialized = report.model_dump(mode="json")
        self.assertEqual(serialized["vision_summary"]["unknown_domains"], ["map_land"])
        refs = [item.ref for item in report.structured_evidence]
        self.assertIn("vision.domain_unknown:map_land", refs)
        self.assertNotIn("vision.domain:map_land", refs)
        unknown = next(
            item
            for item in report.structured_evidence
            if item.ref == "vision.domain_unknown:map_land"
        )
        self.assertEqual(unknown.confidence, 0.0)
        self.assertEqual(report.confidence, 0.0)
        self.assertEqual(
            unknown.metadata,
            {
                "domain": "map_land",
                "status": "unknown",
                "trusted_for_state": False,
            },
        )

    def test_build_report_includes_strategy_snapshot_structured_evidence(self) -> None:
        action = CandidateAction(
            action_id="upgrade-main-hall",
            action_type=ActionType.UPGRADE_BUILDING,
            params={
                "building_id": "main_hall",
                "building_name": "君王殿",
                "strategy_key": "building-main-city",
                "strategy_entry_ids": ["building-main-city"],
                "strategy_topic": "君王殿",
                "strategy_rationale": "君王殿是多数城建解锁和章节推进的核心建筑之一。",
                "strategy_source_ref": "KB-RULE-BUILDING-001",
            },
            source_state_refs=["city.upgradeable_buildings"],
        ).model_copy(update={"score_total": 88.0})
        selection = SelectionResult(
            selected_action=action,
            ranked_actions=[action],
            selection_reason={"triggered_rules": ["chapter_progress"]},
        )
        frame = CaptureFrame(
            png=b"not-used",
            captured_at=datetime(2026, 1, 1, 0, 0, 0),
            device_session=_session(DevicePlatform.ANDROID, ObservationSourceType.SCREENSHOT_FILE, (2400, 1080)),
            source_type=ObservationSourceType.SCREENSHOT_FILE,
        )

        report = build_advisor_report(
            frame=frame,
            state=RuntimeState(city={"upgradeable_buildings": []}),
            selection=selection,
            vision_summary=VisionSyncSummary(page_type="city", domains_run=["city_buildings"], notes=[]),
        )

        assert report.recommended_action is not None
        structured = report.recommended_action.structured_evidence
        self.assertIn("strategy_snapshot:building-main-city", report.recommended_action.evidence)
        self.assertEqual(structured[-1].entry_id, "building-main-city")
        self.assertEqual(structured[-1].topic, "君王殿")
        self.assertEqual(structured[-1].source_ref, "KB-RULE-BUILDING-001")

    def test_build_report_rejects_strategy_key_without_entry_ids(self) -> None:
        action = CandidateAction(
            action_id="upgrade-main-hall",
            action_type=ActionType.UPGRADE_BUILDING,
            params={
                "building_id": "main_hall",
                "strategy_key": "building-main-city",
            },
        ).model_copy(update={"score_total": 88.0})
        selection = SelectionResult(
            selected_action=action,
            ranked_actions=[action],
            selection_reason={"triggered_rules": []},
        )
        frame = CaptureFrame(
            png=b"not-used",
            captured_at=datetime(2026, 1, 1, 0, 0, 0),
            device_session=_session(DevicePlatform.ANDROID, ObservationSourceType.SCREENSHOT_FILE, (2400, 1080)),
            source_type=ObservationSourceType.SCREENSHOT_FILE,
        )

        with self.assertRaisesRegex(EvidenceValidationError, "strategy_key requires strategy_entry_ids"):
            build_advisor_report(
                frame=frame,
                state=RuntimeState(),
                selection=selection,
                vision_summary=VisionSyncSummary(page_type="city", domains_run=[], notes=[]),
            )

    def test_build_report_rejects_forged_strategy_entry_ids(self) -> None:
        action = CandidateAction(
            action_id="upgrade-main-hall",
            action_type=ActionType.UPGRADE_BUILDING,
            params={
                "building_id": "main_hall",
                "strategy_key": "made-up-entry",
                "strategy_entry_ids": ["made-up-entry"],
            },
        ).model_copy(update={"score_total": 88.0})
        selection = SelectionResult(
            selected_action=action,
            ranked_actions=[action],
            selection_reason={"triggered_rules": []},
        )
        frame = CaptureFrame(
            png=b"not-used",
            captured_at=datetime(2026, 1, 1, 0, 0, 0),
            device_session=_session(DevicePlatform.ANDROID, ObservationSourceType.SCREENSHOT_FILE, (2400, 1080)),
            source_type=ObservationSourceType.SCREENSHOT_FILE,
        )

        with self.assertRaisesRegex(EvidenceValidationError, "not present in allowed"):
            build_advisor_report(
                frame=frame,
                state=RuntimeState(),
                selection=selection,
                vision_summary=VisionSyncSummary(page_type="city", domains_run=[], notes=[]),
            )

    def test_build_report_includes_screenshot_interpretation(self) -> None:
        action = CandidateAction(
            action_id="wait",
            action_type=ActionType.WAIT_FOR_RESOURCE,
            source_state_refs=[],
        ).model_copy(update={"score_total": 1.0})
        selection = SelectionResult(
            selected_action=action,
            ranked_actions=[action],
            selection_reason={"triggered_rules": ["advisor_review"]},
        )
        frame = CaptureFrame(
            png=b"not-used",
            captured_at=datetime(2026, 1, 1, 0, 0, 0),
            device_session=_session(DevicePlatform.PC_CLIENT, ObservationSourceType.SCREENSHOT_FILE, (1920, 1080)),
            source_type=ObservationSourceType.SCREENSHOT_FILE,
        )
        interpretation = ScreenshotInterpretation(
            page_type="chapter",
            summary="截图显示章节任务页面。",
            visible_text=["章节"],
            key_facts=["章节页可见"],
            suggested_next_steps=["确认是否可领取奖励"],
            risks=["只看到当前页面"],
            confidence=0.73,
        )

        report = build_advisor_report(
            frame=frame,
            state=RuntimeState(),
            selection=selection,
            vision_summary=VisionSyncSummary(page_type="unknown", domains_run=[], notes=[]),
            screenshot_interpretation=interpretation,
        )

        self.assertEqual(report.screenshot_interpretation, interpretation)
        self.assertEqual(report.current_state_summary["interpreted_page_type"], "chapter")
        self.assertEqual(report.current_state_summary["interpretation_summary"], "截图显示章节任务页面。")
        self.assertEqual(report.vision_summary["interpretation"]["page_type"], "chapter")
        self.assertIn("vision.interpretation", report.evidence)
        self.assertEqual(report.confidence, 0.73)

    def test_fixture_replay_builds_advisor_reports_for_desktop_contract(self) -> None:
        expectations = [
            ("chapter_claimable_state.json", ActionType.CLAIM_CHAPTER_REWARD),
            ("transfer_priority_state.json", ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM),
            ("sample_state.json", ActionType.ATTACK_LAND),
            ("recruit_priority_state.json", ActionType.RECRUIT_SOLDIERS),
            ("recruit_rule_state.json", ActionType.RECRUIT_SOLDIERS),
            ("wait_resource_state.json", ActionType.WAIT_FOR_RESOURCE),
            ("wait_stamina_state.json", ActionType.WAIT_FOR_STAMINA),
            ("team_panel_state.json", ActionType.INSPECT_TEAM_READINESS),
        ]
        project_root = Path(__file__).resolve().parents[2]
        deriver = StateDeriver()
        selector = ActionSelector()
        frame = CaptureFrame(
            png=b"not-used",
            captured_at=datetime(2026, 1, 1, 0, 0, 0),
            device_session=_session(
                DevicePlatform.ANDROID_EMULATOR,
                ObservationSourceType.SCREENSHOT_FILE,
                (1080, 2400),
            ),
            source_type=ObservationSourceType.SCREENSHOT_FILE,
        )

        for fixture_name, expected_action_type in expectations:
            with self.subTest(fixture_name=fixture_name):
                state = load_runtime_state_record(
                    project_root / "tests" / "fixtures" / fixture_name
                ).state
                derived = deriver.derive(state)
                selection = selector.select(derived)
                report = build_advisor_report(
                    frame=frame,
                    state=derived,
                    selection=selection,
                    vision_summary=VisionSyncSummary(
                        page_type="fixture_replay",
                        domains_run=["runtime_fixture"],
                        notes=[fixture_name],
                    ),
                )

                self.assertIsNotNone(report.recommended_action)
                self.assertEqual(report.recommended_action.action_type, expected_action_type)  # type: ignore[union-attr]
                self.assertFalse(report.recommended_action.executable)  # type: ignore[union-attr]
                self.assertEqual(report.recommended_action.execution_blocked_reason, "advisor_mode")  # type: ignore[union-attr]
                self.assertGreater(len(report.available_actions), 0)
                self.assertEqual(report.current_state_summary["page_type"], "fixture_replay")
                self.assertIn("vision.domain:runtime_fixture", report.evidence)
                self.assertIn("pipeline", report.selection_reason)
                self.assertGreaterEqual(
                    report.selection_reason["pipeline"]["generated"],
                    report.selection_reason["pipeline"]["viable"],
                )


if __name__ == "__main__":
    unittest.main()
