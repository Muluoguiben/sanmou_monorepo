"""Tests for the ActionType → handler dispatch table."""
from __future__ import annotations

import hashlib
import io
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

from PIL import Image

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
    FieldMeta,
    ObservationSnapshot,
    RuntimeState,
)
from pioneer_agent.executor.action_handlers import dispatch
from pioneer_agent.executor.operator_confirmation import (
    OperatorConfirmation,
    OperatorConfirmationReceipt,
)
from pioneer_agent.executor.ui_actions import ClickOutcome, UIActions
from pioneer_agent.executor.ui_runner import UIActionRunner
from pioneer_agent.executor.semantic_frame_guard import build_semantic_frame_guard
from pioneer_agent.perception.ui_registry import UIRegistry
from pioneer_agent.runtime.architecture_gates import (
    LOW_RISK_AUTOMATION_ACTIONS,
    AutomationMode,
    AutomationReadiness,
    AutomationReadinessGate,
)
from pioneer_agent.safety.guard import SessionMode
from pioneer_agent.verifier import ExpectedStateDelta, VerifierRegistry, VerifierSpec
from tests.unit.capture_geometry_fixtures import capture_geometry


class _NullUI:
    """All handlers take a UIActions, but wait + pending paths never call it."""


class _SemanticUI:
    def __init__(self, *, click_ok: bool = True) -> None:
        self.click_ok = click_ok
        self.clicks: list[dict] = []

    def click_bbox(self, target_key, bbox, *, label=None):  # noqa: ANN001
        self.clicks.append({"target_key": target_key, "bbox": bbox, "label": label})
        return ClickOutcome(
            success=self.click_ok,
            px=(800, 850),
            reason=None if self.click_ok else "bridge click failed",
            matched_label=label,
        )


def _mk_action(t: ActionType, **params) -> CandidateAction:
    if t == ActionType.CLAIM_CHAPTER_REWARD:
        params.setdefault("chapter_id", 17)
    elif t == ActionType.RECRUIT_SOLDIERS:
        params.setdefault("team_id", "team-1")
    elif t == ActionType.UPGRADE_BUILDING:
        params.setdefault("current_level", 10)
        params.setdefault("target_level", 11)
    return CandidateAction(action_id=f"a-{t.value}", action_type=t, params=params)


def _device_session(
    *,
    active: bool = True,
    source_capabilities: CapabilityFlags | None = None,
    session_capabilities: CapabilityFlags | None = None,
    source_type: ObservationSourceType = ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
) -> DeviceSession:
    source_flags = source_capabilities or CapabilityFlags(input_control=True)
    session_flags = session_capabilities or source_flags
    return DeviceSession(
        profile=DeviceProfile(
            platform=DevicePlatform.PC_CLIENT,
            resolution=(1286, 666),
        ),
        source=ObservationSource(
            source_type=source_type,
            capabilities=source_flags,
        ),
        capabilities=session_flags,
        active=active,
    )


def _ready_automation_gate(
    *,
    accepted_actions: frozenset[ActionType] = LOW_RISK_AUTOMATION_ACTIONS,
    high_risk_verifiers_ready: bool = False,
) -> AutomationReadinessGate:
    return AutomationReadinessGate(
        AutomationReadiness(
            golden_replay_baseline_ready=True,
            low_risk_verifier_false_positive_covered=True,
            map_land_verifier_ready=high_risk_verifiers_ready,
            battle_result_verifier_ready=high_risk_verifiers_ready,
            team_state_verifier_ready=high_risk_verifiers_ready,
            closure_gate_ready=True,
            accepted_actions=accepted_actions,
        )
    )


def _authorized_runner(ui: object, **kwargs: object) -> UIActionRunner:
    session = _device_session(source_type=ObservationSourceType.SCREENSHOT_FILE)
    kwargs.setdefault("automation_gate", _ready_automation_gate())
    return UIActionRunner(
        ui,  # type: ignore[arg-type]
        device_session=session,
        capabilities=session.capabilities,
        session_mode=SessionMode.AUTOMATION_TEST,
        allow_offline_fixture_observations=True,
        **kwargs,
    )


def _frame_observation(
    action: CandidateAction,
    *,
    captured_at: datetime | None = None,
) -> ObservationSnapshot:
    captured_at = captured_at or datetime.now(UTC)
    if action.action_type == ActionType.CLAIM_CHAPTER_REWARD:
        state = RuntimeState(
            progress={
                "current_chapter_id": action.params["chapter_id"],
                "chapter_claimable": True,
                "chapter_claim_button": action.params["claim_button"],
            },
            field_meta={
                "progress.chapter_panel": FieldMeta(
                    value="loaded",
                    source="vision.chapter_panel",
                    updated_at=captured_at,
                    observation_id="obs-current",
                )
            },
        )
        page_type, domains = "chapter", ["resource_bar", "chapter_panel"]
    elif action.action_type == ActionType.RECRUIT_SOLDIERS:
        state = RuntimeState(
            teams=[
                {
                    "team_id": action.params["team_id"],
                    "soldiers": 22000,
                    "recruit_button": action.params["recruit_button"],
                }
            ],
            field_meta={
                "teams.recruit_panel": FieldMeta(
                    value="loaded",
                    source="vision.recruit_panel",
                    updated_at=captured_at,
                    observation_id="obs-current",
                )
            },
        )
        page_type, domains = "recruit", ["resource_bar", "recruit_panel"]
    else:
        dialog = action.params["upgrade_dialog"]
        state = RuntimeState(
            city={"upgrade_dialog": dialog},
            field_meta={
                "city.upgrade_dialog": FieldMeta(
                    value="loaded",
                    source="vision.upgrade_dialog",
                    updated_at=captured_at,
                    observation_id="obs-current",
                )
            },
        )
        page_type, domains = "upgrade_dialog", ["resource_bar", "upgrade_dialog"]
    return ObservationSnapshot(
        observation_id="obs-current",
        captured_at=captured_at,
        frame_sha256=hashlib.sha256(_frame_bytes()).hexdigest(),
        frame_size=(1920, 1080),
        capture_geometry=capture_geometry((1920, 1080)),
        page_type=page_type,
        domains_run=domains,
        observed_state=state,
        source="vision_sync",
    )


def _frame_bytes() -> bytes:
    image = Image.new("RGB", (1920, 1080), (20, 40, 60))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class DispatchTests(unittest.TestCase):
    def test_wait_for_stamina_returns_ok(self) -> None:
        res = dispatch(_mk_action(ActionType.WAIT_FOR_STAMINA), _NullUI())  # type: ignore[arg-type]
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.verification_status, "not_applicable")

    def test_wait_for_resource_returns_ok(self) -> None:
        res = dispatch(_mk_action(ActionType.WAIT_FOR_RESOURCE), _NullUI())  # type: ignore[arg-type]
        self.assertEqual(res.status, "ok")

    def test_upgrade_without_building_name_fails(self) -> None:
        res = dispatch(_mk_action(ActionType.UPGRADE_BUILDING), _NullUI())  # type: ignore[arg-type]
        self.assertEqual(res.status, "failed")
        self.assertTrue(res.recovery_required)
        self.assertIn("building_name", (res.failure_reason or ""))

    def test_upgrade_with_building_name_pending(self) -> None:
        res = dispatch(
            _mk_action(ActionType.UPGRADE_BUILDING, building_name="征兵所"),
            _NullUI(),  # type: ignore[arg-type]
        )
        self.assertEqual(res.status, "pending")
        self.assertIn("征兵所", (res.failure_reason or ""))

    def test_claim_chapter_reward_clicks_observed_claim_button(self) -> None:
        ui = _SemanticUI()
        res = dispatch(
            _mk_action(
                ActionType.CLAIM_CHAPTER_REWARD,
                claim_button={
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            ),
            ui,  # type: ignore[arg-type]
        )

        self.assertEqual(res.status, "ok")
        self.assertEqual(res.verification_status, "unverified")
        self.assertEqual(ui.clicks[0]["target_key"], "chapter_claim_button")
        self.assertEqual(res.summary["target_key"], "chapter_claim_button")

    def test_claim_chapter_reward_without_bbox_stays_pending(self) -> None:
        res = dispatch(_mk_action(ActionType.CLAIM_CHAPTER_REWARD), _NullUI())  # type: ignore[arg-type]

        self.assertEqual(res.status, "pending")
        self.assertIn("bbox not observed", res.failure_reason or "")

    def test_recruit_soldiers_clicks_observed_recruit_button(self) -> None:
        ui = _SemanticUI()
        res = dispatch(
            _mk_action(
                ActionType.RECRUIT_SOLDIERS,
                team_id="team-1",
                recruit_button={
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            ),
            ui,  # type: ignore[arg-type]
        )

        self.assertEqual(res.status, "ok")
        self.assertEqual(ui.clicks[0]["target_key"], "recruit_button")

    def test_upgrade_building_clicks_observed_confirm_button(self) -> None:
        ui = _SemanticUI()
        res = dispatch(
            _mk_action(
                ActionType.UPGRADE_BUILDING,
                building_name="君王殿",
                upgrade_dialog={
                    "visible": True,
                    "building_name": "君王殿",
                    "current_level": 10,
                    "next_level": 11,
                    "can_upgrade": True,
                    "confirm_button": {
                        "visible": True,
                        "enabled": True,
                        "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                    },
                },
            ),
            ui,  # type: ignore[arg-type]
        )

        self.assertEqual(res.status, "ok")
        self.assertEqual(ui.clicks[0]["target_key"], "upgrade_confirm_button")
        self.assertTrue(res.summary["terminal_for_verifier"])
        self.assertEqual(res.summary["flow_step"], "confirm_upgrade")

    def test_upgrade_building_clicks_observed_upgrade_entry_as_intermediate_step(self) -> None:
        ui = _SemanticUI()
        res = dispatch(
            _mk_action(
                ActionType.UPGRADE_BUILDING,
                building_name="君王殿",
                upgrade_button={
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 100, "y_min": 700, "x_max": 240, "y_max": 900},
                },
            ),
            ui,  # type: ignore[arg-type]
        )

        self.assertEqual(res.status, "ok")
        self.assertEqual(res.verification_status, "not_applicable")
        self.assertFalse(res.summary["terminal_for_verifier"])
        self.assertEqual(res.summary["flow_step"], "open_upgrade_dialog")
        self.assertEqual(ui.clicks[0]["target_key"], "building_upgrade_button")

    def test_upgrade_building_blocks_disabled_confirm_button(self) -> None:
        res = dispatch(
            _mk_action(
                ActionType.UPGRADE_BUILDING,
                building_name="君王殿",
                upgrade_dialog={
                    "visible": True,
                    "building_name": "君王殿",
                    "current_level": 10,
                    "next_level": 11,
                    "can_upgrade": True,
                    "confirm_button": {
                        "visible": True,
                        "enabled": False,
                        "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                    },
                },
            ),
            _NullUI(),  # type: ignore[arg-type]
        )

        self.assertEqual(res.status, "failed")
        self.assertIn("disabled", res.failure_reason or "")

    def test_attack_is_pending(self) -> None:
        res = dispatch(_mk_action(ActionType.ATTACK_LAND), _NullUI())  # type: ignore[arg-type]
        self.assertEqual(res.status, "pending")

    def test_every_action_type_has_a_handler(self) -> None:
        for t in ActionType:
            res = dispatch(_mk_action(t, building_name="x"), _NullUI())  # type: ignore[arg-type]
            self.assertIn(res.status, {"ok", "pending", "failed"})
            self.assertNotIn("no handler", res.failure_reason or "")


class UIActionRunnerTests(unittest.TestCase):
    def test_live_input_cannot_bypass_guard_with_non_live_capture_capabilities(self) -> None:
        action = _mk_action(
            ActionType.CLAIM_CHAPTER_REWARD,
            claim_button={
                "visible": True,
                "enabled": True,
                "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
            },
        )
        cases = (
            _device_session(),
            _device_session(source_type=ObservationSourceType.SCREENSHOT_FILE),
        )
        for session in cases:
            with self.subTest(source_type=session.source.source_type.value):
                ui = _SemanticUI()
                runner = UIActionRunner(
                    ui,  # type: ignore[arg-type]
                    device_session=session,
                    capabilities=session.capabilities,
                    session_mode=SessionMode.LIVE,
                    automation_gate=_ready_automation_gate(),
                )

                result = runner.run(action, observation=_frame_observation(action))

                self.assertEqual(result.status, "blocked")
                self.assertEqual(result.summary["blocked_by"], "window_identity_gate")
                self.assertEqual(ui.clicks, [])

    def test_live_dispatch_forwards_atomic_window_identity_guard(self) -> None:
        class _GuardedBridge:
            atomic_frame_click_guard_version = 1
            capture_geometry_version = 1
            atomic_frame_click_guard_modes = frozenset(
                {"semantic_roi_rgb24_sha256"}
            )
            atomic_frame_click_authorization_scopes = frozenset(
                {"operator_confirmed_final_mutating_click"}
            )

            def __init__(self) -> None:
                self.clicks: list[dict[str, Any]] = []

            def click(
                self,
                x: int,
                y: int,
                button: str = "left",
                *,
                expected_window: dict[str, int] | None = None,
                expected_capture_geometry: dict[str, Any] | None = None,
                expected_frame_sha256: str | None = None,
                guard_expires_at: str | None = None,
                authorization_scope: str | None = None,
                kill_switch_path: str | None = None,
                semantic_frame_guard: dict[str, Any] | None = None,
            ) -> dict[str, Any]:
                self.clicks.append(
                    {
                        "x": x,
                        "y": y,
                        "button": button,
                        "expected_window": expected_window,
                        "expected_capture_geometry": expected_capture_geometry,
                        "expected_frame_sha256": expected_frame_sha256,
                        "guard_expires_at": guard_expires_at,
                        "authorization_scope": authorization_scope,
                        "kill_switch_path": kill_switch_path,
                        "semantic_frame_guard": semantic_frame_guard,
                        "capture_backend": expected_capture_geometry["capture_backend"],
                        "source_capture_geometry": expected_capture_geometry,
                        "recapture_geometry": expected_capture_geometry,
                        "absolute_click_point": {
                            "x": expected_capture_geometry["capture_origin"]["x"] + x,
                            "y": expected_capture_geometry["capture_origin"]["y"] + y,
                        },
                    }
                )
                assert semantic_frame_guard is not None
                return {
                    "status": "ok",
                    "atomic_frame_guard": {
                        "verified": True,
                        "version": 1,
                        "mode": "semantic_roi_rgb24_sha256",
                        "expected_roi_sha256": semantic_frame_guard["roi_sha256"],
                        "captured_roi_sha256": semantic_frame_guard["roi_sha256"],
                        "guard_expires_at": guard_expires_at,
                        "authorization_scope": authorization_scope,
                        "semantic_frame_guard": semantic_frame_guard,
                        "capture_backend": expected_capture_geometry["capture_backend"],
                        "source_capture_geometry": expected_capture_geometry,
                        "recapture_geometry": expected_capture_geometry,
                        "absolute_click_point": {
                            "x": expected_capture_geometry["capture_origin"]["x"] + x,
                            "y": expected_capture_geometry["capture_origin"]["y"] + y,
                        },
                        "kill_switch_guard": {
                            "checked": True,
                            "path": kill_switch_path,
                            "checks": [
                                {
                                    "stage": stage,
                                    "checked_at": datetime.now(UTC).isoformat(),
                                    "parent_accessible": True,
                                    "stop_file_present": False,
                                }
                                for stage in (
                                    "before_capture",
                                    "after_capture",
                                    "before_input_injection",
                                )
                            ],
                        },
                    },
                }

        action = _mk_action(
            ActionType.CLAIM_CHAPTER_REWARD,
            claim_button={
                "visible": True,
                "enabled": True,
                "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
            },
        )
        capabilities = CapabilityFlags(
            live_capture=True,
            input_control=True,
            reliable_window_info=True,
        )
        session = DeviceSession(
            profile=DeviceProfile(
                platform=DevicePlatform.PC_CLIENT,
                resolution=(1920, 1080),
            ),
            source=ObservationSource(
                source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
                capabilities=capabilities,
                metadata={"hwnd": 101, "pid": 202},
            ),
            capabilities=capabilities,
        )
        bridge = _GuardedBridge()
        ui = UIActions(bridge, UIRegistry({}))  # type: ignore[arg-type]
        observation = _frame_observation(action)
        semantic_guard = build_semantic_frame_guard(
            _frame_bytes(),
            frame_size=observation.frame_size or (0, 0),
            capture_geometry=observation.capture_geometry,
            semantic_target_key="chapter_claim_button",
            bbox=action.params["claim_button"]["bbox"],
        )
        confirmed_at = observation.captured_at + timedelta(microseconds=1)
        confirmation_receipt = OperatorConfirmationReceipt(
            confirmation=OperatorConfirmation(
                confirmation_id="atomic-window-guard-test",
                action_id=action.action_id,
                action_type=action.action_type,
                target_key="chapter_claim_button",
                target_identity={"chapter_id": 17},
                observation_id=observation.observation_id,
                frame_sha256=observation.frame_sha256,
                semantic_frame_guard=semantic_guard,
                observation_captured_at=observation.captured_at,
                confirmed_at=confirmed_at,
                expires_at=confirmed_at + timedelta(seconds=10),
            ),
            consumed_at=confirmed_at + timedelta(microseconds=1),
            dispatch_at=confirmed_at + timedelta(microseconds=1),
        )
        confirmation_provider = MagicMock()
        confirmation_provider.consume_for_dispatch.return_value = confirmation_receipt
        runner = UIActionRunner(
            ui,
            device_session=session,
            capabilities=capabilities,
            session_mode=SessionMode.LIVE,
            automation_gate=_ready_automation_gate(),
            operator_confirmation_provider=confirmation_provider,
            kill_switch_path=Path(__file__).resolve().parent / "KILL_SWITCH_TEST",
        )

        result = runner.run(
            action,
            observation=observation,
            frame_bytes=_frame_bytes(),
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(bridge.clicks), 1)
        self.assertEqual(
            bridge.clicks[0]["expected_window"],
            observation.capture_geometry.outer_window.model_dump(mode="json"),
        )
        self.assertEqual(
            bridge.clicks[0]["semantic_frame_guard"]["roi_sha256"],
            semantic_guard.roi_sha256,
        )

    def test_live_dispatch_rejects_ui_without_atomic_window_guard(self) -> None:
        action = _mk_action(
            ActionType.CLAIM_CHAPTER_REWARD,
            claim_button={
                "visible": True,
                "enabled": True,
                "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
            },
        )
        capabilities = CapabilityFlags(
            live_capture=True,
            input_control=True,
            reliable_window_info=True,
        )
        session = DeviceSession(
            profile=DeviceProfile(
                platform=DevicePlatform.PC_CLIENT,
                resolution=(1920, 1080),
            ),
            source=ObservationSource(
                source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
                capabilities=capabilities,
                metadata={"hwnd": 101, "pid": 202},
            ),
            capabilities=capabilities,
        )
        ui = _SemanticUI()
        runner = UIActionRunner(
            ui,  # type: ignore[arg-type]
            device_session=session,
            capabilities=capabilities,
            session_mode=SessionMode.LIVE,
            automation_gate=_ready_automation_gate(),
        )

        result = runner.run(action, observation=_frame_observation(action))

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.summary["blocked_by"], "window_identity_gate")
        self.assertEqual(ui.clicks, [])

    def test_live_window_cannot_enable_offline_fixture_observations(self) -> None:
        action = _mk_action(
            ActionType.CLAIM_CHAPTER_REWARD,
            claim_button={
                "visible": True,
                "enabled": True,
                "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
            },
        )
        observation = _frame_observation(action).model_copy(
            update={"source": "runtime_fixture"}
        )
        ui = _SemanticUI()
        session = _device_session()
        runner = UIActionRunner(
            ui,  # type: ignore[arg-type]
            device_session=session,
            capabilities=session.capabilities,
            session_mode=SessionMode.AUTOMATION_TEST,
            allow_offline_fixture_observations=True,
            automation_gate=_ready_automation_gate(),
        )

        result = runner.run(action, observation=observation)

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.summary["blocked_by"], "observation_gate")
        self.assertIn("vision_sync", result.failure_reason or "")
        self.assertEqual(ui.clicks, [])

    def test_runner_delegates_to_dispatch(self) -> None:
        runner = _authorized_runner(_NullUI())
        res = runner.run(_mk_action(ActionType.WAIT_FOR_STAMINA))
        self.assertEqual(res.status, "ok")

    def test_runner_without_device_session_cannot_click(self) -> None:
        ui = _SemanticUI()
        runner = UIActionRunner(
            ui,  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
            session_mode=SessionMode.LIVE,
        )
        res = runner.run(
            _mk_action(
                ActionType.CLAIM_CHAPTER_REWARD,
                claim_button={
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            )
        )
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "device_session")
        self.assertEqual(ui.clicks, [])

    def test_runner_without_explicit_capabilities_cannot_click(self) -> None:
        ui = _SemanticUI()
        session = _device_session()
        runner = UIActionRunner(
            ui,  # type: ignore[arg-type]
            device_session=session,
            session_mode=SessionMode.LIVE,
        )
        res = runner.run(
            _mk_action(
                ActionType.CLAIM_CHAPTER_REWARD,
                claim_button={
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            )
        )
        self.assertEqual(res.status, "blocked")
        self.assertIn("explicit capabilities", res.failure_reason or "")
        self.assertEqual(ui.clicks, [])

    def test_runner_blocks_missing_action_bound_verifier_identity_before_click(self) -> None:
        button = {
            "visible": True,
            "enabled": True,
            "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
        }
        cases = (
            CandidateAction(
                action_id="claim-missing-chapter",
                action_type=ActionType.CLAIM_CHAPTER_REWARD,
                params={"claim_button": button},
            ),
            CandidateAction(
                action_id="recruit-missing-team",
                action_type=ActionType.RECRUIT_SOLDIERS,
                params={"recruit_button": button},
            ),
            CandidateAction(
                action_id="upgrade-missing-level",
                action_type=ActionType.UPGRADE_BUILDING,
                params={
                    "building_name": "仓库",
                    "upgrade_dialog": {
                        "visible": True,
                        "building_name": "仓库",
                        "can_upgrade": True,
                        "confirm_button": button,
                    },
                },
            ),
        )
        for action in cases:
            with self.subTest(action_type=action.action_type.value):
                ui = _SemanticUI()
                result = _authorized_runner(ui).run(action)
                self.assertEqual(result.status, "blocked")
                self.assertEqual(result.summary["blocked_by"], "verifier_registry")
                self.assertIn("missing required action param", result.failure_reason or "")
                self.assertEqual(ui.clicks, [])

    def test_runner_blocks_observe_only_sources(self) -> None:
        capabilities = CapabilityFlags(observe_only=True)
        session = _device_session(source_capabilities=capabilities)
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            device_session=session,
            capabilities=capabilities,
            session_mode=SessionMode.AUTOMATION_TEST,
        )
        res = runner.run(_mk_action(ActionType.CLAIM_CHAPTER_REWARD))
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.verification_status, "not_applicable")
        self.assertIn("input_control", res.failure_reason or "")

    def test_runner_blocks_advisor_session_mode(self) -> None:
        session = _device_session()
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            device_session=session,
            capabilities=session.capabilities,
            session_mode="advisor",
        )
        res = runner.run(_mk_action(ActionType.CLAIM_CHAPTER_REWARD))
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "safety_guard")
        self.assertEqual(res.summary["guard_decision"], "block")
        self.assertIn("session mode advisor", res.failure_reason or "")

    def test_runner_allows_explicit_control_session(self) -> None:
        runner = _authorized_runner(_NullUI())
        res = runner.run(_mk_action(ActionType.WAIT_FOR_STAMINA))
        self.assertEqual(res.status, "ok")

    def test_runner_blocks_inactive_or_capability_mismatched_session(self) -> None:
        cases = (
            (
                _device_session(active=False),
                CapabilityFlags(input_control=True),
            ),
            (
                _device_session(
                    source_capabilities=CapabilityFlags(observe_only=True),
                    session_capabilities=CapabilityFlags(input_control=True),
                ),
                CapabilityFlags(input_control=True),
            ),
        )
        for session, capabilities in cases:
            with self.subTest(session_id=session.session_id):
                runner = UIActionRunner(
                    _NullUI(),  # type: ignore[arg-type]
                    device_session=session,
                    capabilities=capabilities,
                    session_mode=SessionMode.LIVE,
                )
                res = runner.run(_mk_action(ActionType.WAIT_FOR_STAMINA))
                self.assertEqual(res.status, "blocked")
                self.assertEqual(res.summary["blocked_by"], "device_session")

    def test_runner_requires_confirmation_for_sensitive_action(self) -> None:
        runner = _authorized_runner(_NullUI())
        res = runner.run(_mk_action(ActionType.ATTACK_LAND))
        self.assertEqual(res.status, "requires_confirmation")
        self.assertEqual(res.summary["blocked_by"], "safety_guard")
        self.assertEqual(res.summary["guard_decision"], "require_confirmation")

    def test_runner_blocks_low_risk_action_without_semantic_bbox(self) -> None:
        runner = _authorized_runner(_NullUI())
        res = runner.run(_mk_action(ActionType.CLAIM_CHAPTER_REWARD))
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "semantic_target_gate")
        self.assertIn("semantic bbox target", res.failure_reason or "")

    def test_runner_dispatches_low_risk_action_when_semantic_bbox_is_present(self) -> None:
        runner = _authorized_runner(_SemanticUI())
        action = _mk_action(
            ActionType.CLAIM_CHAPTER_REWARD,
            claim_button={
                "visible": True,
                "enabled": True,
                "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
            },
        )
        res = runner.run(action, observation=_frame_observation(action))
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.summary["target_key"], "chapter_claim_button")
        self.assertEqual(res.summary["semantic_target_gate"]["decision"], "allow")
        self.assertEqual(res.summary["observation_gate"]["decision"], "allow")
        self.assertEqual(res.summary["semantic_target_gate"]["details"]["target"], "claim_button")

    def test_runner_blocks_low_risk_action_with_disabled_semantic_bbox(self) -> None:
        runner = _authorized_runner(_SemanticUI())
        res = runner.run(
            _mk_action(
                ActionType.RECRUIT_SOLDIERS,
                recruit_button={
                    "visible": True,
                    "enabled": False,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            )
        )
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "semantic_target_gate")

    def test_runner_dispatches_upgrade_confirm_when_semantic_bbox_is_present(self) -> None:
        runner = _authorized_runner(_SemanticUI())
        action = _mk_action(
            ActionType.UPGRADE_BUILDING,
            building_name="君王殿",
            upgrade_dialog={
                "visible": True,
                "building_name": "君王殿",
                "current_level": 10,
                "next_level": 11,
                "can_upgrade": True,
                "confirm_button": {
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            },
        )
        res = runner.run(action, observation=_frame_observation(action))
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.summary["target_key"], "upgrade_confirm_button")
        self.assertEqual(res.summary["semantic_target_gate"]["decision"], "allow")
        self.assertEqual(
            res.summary["semantic_target_gate"]["details"]["target"],
            "upgrade_dialog.confirm_button",
        )

    def test_runner_blocks_missing_stale_or_wrong_target_observation(self) -> None:
        button = {
            "visible": True,
            "enabled": True,
            "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
        }
        action = _mk_action(
            ActionType.CLAIM_CHAPTER_REWARD,
            claim_button=button,
        )

        for label, observation in (
            ("missing", None),
            (
                "stale",
                _frame_observation(
                    action,
                    captured_at=datetime.now(UTC) - timedelta(minutes=2),
                ),
            ),
            (
                "wrong_target",
                _frame_observation(
                    action.model_copy(
                        update={"params": {**action.params, "chapter_id": 18}}
                    )
                ),
            ),
        ):
            with self.subTest(label=label):
                ui = _SemanticUI()
                result = _authorized_runner(ui).run(action, observation=observation)
                self.assertEqual(result.status, "blocked")
                self.assertEqual(result.summary["blocked_by"], "observation_gate")
                self.assertEqual(ui.clicks, [])

        nan_ui = _SemanticUI()
        nan_ttl_result = _authorized_runner(
            nan_ui,
            observation_max_age_seconds=float("nan"),
        ).run(
            action,
            observation=_frame_observation(
                action,
                captured_at=datetime.now(UTC) - timedelta(days=7),
            ),
        )
        self.assertEqual(nan_ttl_result.status, "blocked")
        self.assertIn("finite and positive", nan_ttl_result.failure_reason or "")
        self.assertEqual(nan_ui.clicks, [])

    def test_runner_blocks_low_risk_action_when_architecture_gate_is_not_ready(self) -> None:
        runner = _authorized_runner(
            _NullUI(),
            automation_gate=AutomationReadinessGate(
                AutomationReadiness(low_risk_verifier_false_positive_covered=False)
            ),
        )
        res = runner.run(_mk_action(ActionType.CLAIM_CHAPTER_REWARD))
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "architecture_gate")
        self.assertIn("committed closure artifact", res.failure_reason or "")

    def test_runner_blocks_confirmed_action_without_verifier_spec(self) -> None:
        runner = _authorized_runner(_NullUI())
        res = runner.run(
            _mk_action(
                ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM,
                confirmation_token="manual-ok",
            )
        )
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "verifier_registry")
        self.assertIn("requires a verifier", res.failure_reason or "")

    def test_runner_dispatches_confirmed_sensitive_action_with_verifier_spec(self) -> None:
        registry = VerifierRegistry(
            {
                ActionType.ATTACK_LAND: VerifierSpec(
                    action_type=ActionType.ATTACK_LAND,
                    expected_deltas=(
                        ExpectedStateDelta(
                            path="map_state.last_attack_id",
                            expected_after="attack-1",
                        ),
                    ),
                    timeout_seconds=10.0,
                )
            }
        )
        runner = _authorized_runner(
            _NullUI(),
            verifier_registry=registry,
            automation_gate=_ready_automation_gate(
                accepted_actions=frozenset({ActionType.ATTACK_LAND}),
                high_risk_verifiers_ready=True,
            ),
        )
        res = runner.run(_mk_action(ActionType.ATTACK_LAND, confirmation_token="manual-ok"))
        self.assertEqual(res.status, "pending")
        self.assertIn("attack flow", res.failure_reason or "")

    def test_runner_blocks_high_risk_full_auto_even_with_confirmation_token(self) -> None:
        registry = VerifierRegistry(
            {
                ActionType.ATTACK_LAND: VerifierSpec(
                    action_type=ActionType.ATTACK_LAND,
                    expected_deltas=(
                        ExpectedStateDelta(
                            path="map_state.last_attack_id",
                            expected_after="attack-1",
                        ),
                    ),
                    timeout_seconds=10.0,
                )
            }
        )
        runner = _authorized_runner(
            _NullUI(),
            verifier_registry=registry,
            automation_mode=AutomationMode.FULL_AUTO,
            automation_gate=_ready_automation_gate(
                accepted_actions=frozenset({ActionType.ATTACK_LAND}),
            ),
        )
        res = runner.run(_mk_action(ActionType.ATTACK_LAND, confirmation_token="manual-ok"))
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "architecture_gate")
        self.assertIn("high-risk full-auto", res.failure_reason or "")


if __name__ == "__main__":
    unittest.main()
