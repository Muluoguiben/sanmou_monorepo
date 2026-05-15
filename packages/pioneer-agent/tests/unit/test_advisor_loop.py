from __future__ import annotations

import io
import unittest
from dataclasses import dataclass
from datetime import datetime
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
from pioneer_agent.perception.screenshot_interpreter import ScreenshotInterpretation
from pioneer_agent.perception.vision_sync import VisionSyncSummary
from pioneer_agent.runtime.advisor_loop import AdvisorLoop, build_advisor_report


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


if __name__ == "__main__":
    unittest.main()
