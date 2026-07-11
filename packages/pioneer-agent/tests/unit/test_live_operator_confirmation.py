from __future__ import annotations

import hashlib
import io
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

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
from pioneer_agent.executor.operator_confirmation import (
    JsonlOperatorConfirmationStore,
    OperatorConfirmation,
    WaitingOperatorConfirmationProvider,
)
from pioneer_agent.executor.ui_actions import UIActions
from pioneer_agent.executor.ui_runner import UIActionRunner
from pioneer_agent.executor.semantic_frame_guard import build_semantic_frame_guard
from pioneer_agent.perception.ui_registry import UIRegistry
from pioneer_agent.runtime.architecture_gates import (
    AutomationReadiness,
    AutomationReadinessGate,
)
from tests.unit.capture_geometry_fixtures import capture_geometry
from pioneer_agent.safety.guard import SessionMode


class _Bridge:
    atomic_frame_click_guard_version = 1
    capture_geometry_version = 1
    atomic_frame_click_guard_modes = frozenset({"semantic_roi_rgb24_sha256"})
    atomic_frame_click_authorization_scopes = frozenset(
        {
            "operator_confirmed_final_mutating_click",
            "observation_bound_intermediate_click",
        }
    )

    def __init__(self) -> None:
        self.clicks: list[dict] = []

    def click(  # noqa: ANN001
        self,
        x,
        y,
        button="left",
        *,
        expected_window=None,
        expected_capture_geometry=None,
        expected_frame_sha256=None,
        guard_expires_at=None,
        authorization_scope=None,
        kill_switch_path=None,
        semantic_frame_guard=None,
    ):
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
                "kill_switch_guard": _kill_switch_attestation(kill_switch_path),
            },
        }


class LiveOperatorConfirmationTests(unittest.TestCase):
    def test_live_final_click_blocks_without_terminal_frame_bytes(self) -> None:
        action, observation = _action_and_observation()
        bridge = _Bridge()

        result = _runner(UIActions(bridge, UIRegistry({}))).run(
            action,
            observation=observation,
        )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.summary["blocked_by"], "atomic_frame_guard")
        self.assertIn("frame bytes", result.failure_reason)
        self.assertEqual(bridge.clicks, [])

    def test_live_final_click_blocks_mismatched_terminal_frame_bytes(self) -> None:
        action, observation = _action_and_observation()
        bridge = _Bridge()

        result = _runner(UIActions(bridge, UIRegistry({}))).run(
            action,
            observation=observation,
            frame_bytes=b"not-the-observed-frame",
        )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.summary["blocked_by"], "atomic_frame_guard")
        self.assertIn("frame_sha256", result.failure_reason)
        self.assertEqual(bridge.clicks, [])

    def test_live_final_click_defaults_to_blocked_without_confirmation(self) -> None:
        action, observation = _action_and_observation()
        bridge = _Bridge()
        result = _runner(UIActions(bridge, UIRegistry({}))).run(
            action,
            observation=observation,
            frame_bytes=_frame_bytes(),
        )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.summary["blocked_by"], "operator_confirmation")
        self.assertEqual(bridge.clicks, [])

    def test_live_final_click_consumes_bound_confirmation_and_traces_timestamps(self) -> None:
        action, observation = _action_and_observation()
        with TemporaryDirectory() as tmp:
            store = JsonlOperatorConfirmationStore(Path(tmp) / "confirmations.jsonl")
            confirmed_at = datetime.now(UTC) - timedelta(milliseconds=100)
            semantic_guard = _semantic_guard(observation)
            store.append_grant(
                OperatorConfirmation(
                    confirmation_id="confirm-claim-17",
                    action_id=action.action_id,
                    action_type=action.action_type,
                    target_key="chapter_claim_button",
                    target_identity={"chapter_id": 17},
                    observation_id=observation.observation_id,
                    frame_sha256=observation.frame_sha256,
                    semantic_frame_guard=semantic_guard,
                    observation_captured_at=observation.captured_at,
                    confirmed_at=confirmed_at,
                    expires_at=datetime.now(UTC) + timedelta(seconds=10),
                )
            )
            bridge = _Bridge()
            ui = UIActions(bridge, UIRegistry({}))
            runner = _runner(ui, provider=store)

            result = runner.run(
                action,
                observation=observation,
                frame_bytes=_frame_bytes(),
            )

            self.assertEqual(result.status, "ok")
            dispatch_at = datetime.fromisoformat(result.summary["dispatch_at"])
            self.assertGreater(dispatch_at, confirmed_at)
            confirmation = result.summary["operator_confirmation"]
            self.assertEqual(confirmation["confirmation_id"], "confirm-claim-17")
            self.assertEqual(confirmation["target_identity"], {"chapter_id": 17})
            self.assertEqual(
                confirmation["runtime_dispatch"],
                {
                    "status": "ok",
                    "target_key": "chapter_claim_button",
                    "terminal_for_verifier": True,
                },
            )
            event = ui.consume_input_trace()[0]
            self.assertEqual(event["confirmation_id"], "confirm-claim-17")
            self.assertEqual(event["confirmed_at"], confirmation["confirmed_at"])
            self.assertEqual(event["dispatch_at"], result.summary["dispatch_at"])
            self.assertTrue(event["atomic_frame_guard"]["bridge_verified"])
            self.assertEqual(
                event["atomic_frame_guard"]["binding"]["roi_sha256"],
                semantic_guard.roi_sha256,
            )
            self.assertEqual(len(bridge.clicks), 1)
            self.assertEqual(
                bridge.clicks[0]["semantic_frame_guard"]["roi_sha256"],
                semantic_guard.roi_sha256,
            )

            second = runner.run(
                action,
                observation=observation,
                frame_bytes=_frame_bytes(),
            )
            self.assertEqual(second.status, "blocked")
            self.assertEqual(second.summary["blocked_by"], "operator_confirmation")
            self.assertEqual(len(bridge.clicks), 1)

    def test_kill_switch_aborts_wait_without_clicking(self) -> None:
        action, observation = _action_and_observation()
        with TemporaryDirectory() as tmp:
            store = JsonlOperatorConfirmationStore(Path(tmp) / "confirmations.jsonl")
            provider = WaitingOperatorConfirmationProvider(
                store,
                Path(tmp) / "request.json",
                abort_if=lambda: True,
            )
            bridge = _Bridge()

            result = _runner(
                UIActions(bridge, UIRegistry({})),
                provider=provider,
            ).run(
                action,
                observation=observation,
                frame_bytes=_frame_bytes(),
            )

            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.summary["blocked_by"], "operator_confirmation")
            self.assertIn("kill switch", result.failure_reason)
            self.assertEqual(bridge.clicks, [])
            self.assertFalse((Path(tmp) / "request.json").exists())

    def test_truthy_non_boolean_upgrade_dialog_cannot_bypass_confirmation(self) -> None:
        action, observation = _upgrade_action_and_observation(dialog_visible=1)
        bridge = _Bridge()

        result = _runner(
            UIActions(bridge, UIRegistry({})),
            accepted_action=ActionType.UPGRADE_BUILDING,
        ).run(action, observation=observation)

        self.assertEqual(result.status, "failed")
        self.assertIn("must be an observed boolean", result.failure_reason)
        self.assertEqual(bridge.clicks, [])

    def test_upgrade_entry_uses_observation_bound_guard_without_confirmation(self) -> None:
        action, observation = _upgrade_entry_action_and_observation()
        bridge = _Bridge()

        result = _runner(
            UIActions(bridge, UIRegistry({})),
            accepted_action=ActionType.UPGRADE_BUILDING,
        ).run(action, observation=observation, frame_bytes=_frame_bytes())

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(bridge.clicks), 1)
        self.assertEqual(
            bridge.clicks[0]["authorization_scope"],
            "observation_bound_intermediate_click",
        )
        self.assertEqual(
            datetime.fromisoformat(bridge.clicks[0]["guard_expires_at"]),
            observation.captured_at + timedelta(seconds=30),
        )
        self.assertIsNone(bridge.clicks[0].get("confirmation"))


def _runner(
    ui: UIActions,
    *,
    provider: JsonlOperatorConfirmationStore | WaitingOperatorConfirmationProvider | None = None,
    accepted_action: ActionType = ActionType.CLAIM_CHAPTER_REWARD,
) -> UIActionRunner:
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
    readiness = AutomationReadiness(
        golden_replay_baseline_ready=True,
        low_risk_verifier_false_positive_covered=True,
        closure_gate_ready=True,
        accepted_actions=frozenset({accepted_action}),
    )
    return UIActionRunner(
        ui,
        device_session=session,
        capabilities=capabilities,
        session_mode=SessionMode.LIVE,
        automation_gate=AutomationReadinessGate(readiness),
        operator_confirmation_provider=provider,
        kill_switch_path=Path(__file__).resolve().parent / "KILL_SWITCH_TEST",
    )


def _action_and_observation() -> tuple[CandidateAction, ObservationSnapshot]:
    button = {
        "visible": True,
        "enabled": True,
        "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
    }
    action = CandidateAction(
        action_id="claim-17",
        action_type=ActionType.CLAIM_CHAPTER_REWARD,
        params={"chapter_id": 17, "claim_button": button},
    )
    captured_at = datetime.now(UTC) - timedelta(seconds=1)
    state = RuntimeState(
        progress={
            "current_chapter_id": 17,
            "chapter_claimable": True,
            "chapter_claim_button": button,
        },
        field_meta={
            "progress.chapter_panel": FieldMeta(
                value="loaded",
                source="vision.chapter_panel",
                updated_at=captured_at,
                observation_id="obs-claim-17",
            )
        },
    )
    return action, ObservationSnapshot(
        observation_id="obs-claim-17",
        captured_at=captured_at,
        frame_sha256=hashlib.sha256(_frame_bytes()).hexdigest(),
        frame_size=(1920, 1080),
        capture_geometry=capture_geometry((1920, 1080)),
        page_type="chapter",
        domains_run=["resource_bar", "chapter_panel"],
        observed_state=state,
        source="vision_sync",
    )


def _frame_bytes() -> bytes:
    image = Image.new("RGB", (1920, 1080), (20, 40, 60))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _semantic_guard(observation: ObservationSnapshot):  # noqa: ANN201
    return build_semantic_frame_guard(
        _frame_bytes(),
        frame_size=observation.frame_size or (0, 0),
        capture_geometry=observation.capture_geometry,
        semantic_target_key="chapter_claim_button",
        bbox={"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
    )


def _upgrade_action_and_observation(
    *,
    dialog_visible: object,
) -> tuple[CandidateAction, ObservationSnapshot]:
    button = {
        "visible": True,
        "enabled": True,
        "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
    }
    action = CandidateAction(
        action_id="upgrade-main-hall-4",
        action_type=ActionType.UPGRADE_BUILDING,
        params={
            "building_name": "主城",
            "current_level": 3,
            "target_level": 4,
            "upgrade_dialog": {
                "visible": dialog_visible,
                "building_name": "主城",
                "current_level": 3,
                "next_level": 4,
                "can_upgrade": True,
                "confirm_button": button,
            },
        },
    )
    captured_at = datetime.now(UTC) - timedelta(seconds=1)
    state = RuntimeState(
        city={
            "buildings": [{"name": "主城", "level": 3}],
            "upgrade_dialog": {
                "visible": True,
                "building_name": "主城",
                "current_level": 3,
                "next_level": 4,
                "can_upgrade": True,
                "confirm_button": button,
            },
        },
        field_meta={
            "city.upgrade_dialog": FieldMeta(
                value="loaded",
                source="vision.upgrade_dialog",
                updated_at=captured_at,
                observation_id="obs-upgrade-main-hall-4",
            )
        },
    )
    return action, ObservationSnapshot(
        observation_id="obs-upgrade-main-hall-4",
        captured_at=captured_at,
        frame_sha256="b" * 64,
        frame_size=(1920, 1080),
        capture_geometry=capture_geometry((1920, 1080)),
        page_type="upgrade_dialog",
        domains_run=["resource_bar", "city_buildings", "upgrade_dialog"],
        observed_state=state,
        source="vision_sync",
    )


def _upgrade_entry_action_and_observation() -> tuple[CandidateAction, ObservationSnapshot]:
    button = {
        "visible": True,
        "enabled": True,
        "bbox": {"x_min": 100, "y_min": 700, "x_max": 240, "y_max": 900},
    }
    action = CandidateAction(
        action_id="upgrade-main-hall-4",
        action_type=ActionType.UPGRADE_BUILDING,
        params={
            "building_name": "涓诲煄",
            "current_level": 3,
            "target_level": 4,
            "upgrade_button": button,
        },
    )
    captured_at = datetime.now(UTC) - timedelta(seconds=1)
    state = RuntimeState(
        city={
            "buildings": [
                {"name": "涓诲煄", "level": 3, "upgrade_button": button}
            ]
        },
        field_meta={
            "city": FieldMeta(
                value="loaded",
                source="vision.city_buildings",
                updated_at=captured_at,
                observation_id="obs-upgrade-entry",
            )
        },
    )
    return action, ObservationSnapshot(
        observation_id="obs-upgrade-entry",
        captured_at=captured_at,
        frame_sha256=hashlib.sha256(_frame_bytes()).hexdigest(),
        frame_size=(1920, 1080),
        capture_geometry=capture_geometry((1920, 1080)),
        page_type="city",
        domains_run=["resource_bar", "city_buildings"],
        observed_state=state,
        source="vision_sync",
    )


def _kill_switch_attestation(path: str | None) -> dict[str, object]:
    return {
        "checked": True,
        "path": path,
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
    }


if __name__ == "__main__":
    unittest.main()
