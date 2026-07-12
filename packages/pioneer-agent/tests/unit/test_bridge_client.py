from __future__ import annotations

import base64
import hashlib
import io
import unittest
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from PIL import Image

from pioneer_agent.adapters import bridge_client
from pioneer_agent.adapters.bridge_client import BridgeClient, BridgeScreenshot
from tests.unit.capture_geometry_fixtures import (
    capture_geometry,
    capture_geometry_payload,
)


class StubBridgeClient(BridgeClient):
    def __init__(self, *, capture_backend: str | None = None) -> None:
        super().__init__(capture_backend=capture_backend)
        self.sent: list[dict[str, object]] = []
        self.responses: list[dict[str, object]] = []

    def connect(self) -> None:
        return None

    def _send(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)

    def _read_line(self) -> dict[str, object]:
        if not self.responses:
            return {"status": "ok"}
        return self.responses.pop(0)


class BridgeClientTests(unittest.TestCase):
    def test_wsl_distro_can_be_overridden_without_path_injection(self) -> None:
        with patch.dict(
            bridge_client.os.environ,
            {"SANMOU_WSL_DISTRO": "Ubuntu-24.04"},
        ):
            self.assertEqual(
                bridge_client._to_windows_kill_switch_path("/tmp/KILL_SWITCH"),
                "\\\\wsl$\\Ubuntu-24.04\\tmp\\KILL_SWITCH",
            )

        with patch.dict(
            bridge_client.os.environ,
            {"SANMOU_WSL_DISTRO": "Ubuntu\\..\\C$"},
        ):
            with self.assertRaisesRegex(ValueError, "unsupported"):
                bridge_client._to_windows_path(Path("/tmp/proxy.py"))

    def test_wsl_standard_distro_environment_is_used(self) -> None:
        with patch.dict(
            bridge_client.os.environ,
            {"WSL_DISTRO_NAME": "Debian"},
            clear=True,
        ):
            self.assertEqual(
                bridge_client._to_windows_path(Path("/tmp/proxy.py")),
                "\\\\wsl$\\Debian\\tmp\\proxy.py",
            )

    def test_connect_forwards_custom_windows_token_path_to_proxy(self) -> None:
        client = BridgeClient(auth_token_file=r"D:\secrets\bridge.token")
        process = MagicMock()
        process.poll.return_value = None
        process.stdout.readline.return_value = '{"status":"proxy_ready"}\n'

        with (
            patch.dict(
                bridge_client.os.environ,
                {"WSL_DISTRO_NAME": "Debian"},
                clear=True,
            ),
            patch.object(bridge_client.subprocess, "Popen", return_value=process) as popen,
        ):
            client.connect()

        self.assertEqual(
            popen.call_args.args[0],
            [
                "python.exe",
                ANY,
                "9877",
                r"D:\secrets\bridge.token",
            ],
        )

    def test_screenshot_sends_capture_backend_when_configured(self) -> None:
        client = StubBridgeClient(capture_backend="wgc")
        png = _make_png()
        geometry = capture_geometry_payload((1286, 666))
        client.responses.append({
            "status": "ok",
            "data_b64": base64.b64encode(png).decode("ascii"),
            "size": len(png),
            "frame_sha256": hashlib.sha256(png).hexdigest(),
            "capture_geometry": geometry,
        })

        self.assertEqual(client.screenshot(), png)
        self.assertEqual(
            client.last_screenshot.capture_geometry.model_dump(mode="json"),
            geometry,
        )
        self.assertEqual(client.sent, [{"cmd": "screenshot", "backend": "wgc"}])

    def test_screenshot_from_old_server_without_geometry_fails_closed(self) -> None:
        client = StubBridgeClient()
        png = _make_png()
        client.responses.append(
            {
                "status": "ok",
                "data_b64": base64.b64encode(png).decode("ascii"),
                "size": len(png),
                "frame_sha256": hashlib.sha256(png).hexdigest(),
            }
        )

        with self.assertRaisesRegex(RuntimeError, "update and restart"):
            client.screenshot()

    def test_failed_archive_write_does_not_retain_click_binding(self) -> None:
        client = StubBridgeClient(capture_backend="wgc")
        png = _make_png()
        client.responses.append(
            {
                "status": "ok",
                "data_b64": base64.b64encode(png).decode("ascii"),
                "size": len(png),
                "frame_sha256": hashlib.sha256(png).hexdigest(),
                "capture_geometry": capture_geometry_payload((1286, 666)),
            }
        )

        with patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                client.screenshot_capture("capture.png")

        self.assertIsNone(client.last_screenshot)

    def test_list_windows_accepts_optional_title_filter(self) -> None:
        client = StubBridgeClient()
        client.responses.append({"status": "ok", "windows": []})

        self.assertEqual(client.list_windows("三国"), {"status": "ok", "windows": []})
        self.assertEqual(client.sent, [{"cmd": "list_windows", "title": "三国"}])

    def test_old_atomic_server_without_geometry_capability_fails_closed(self) -> None:
        client = StubBridgeClient()
        png = _make_png()
        digest = hashlib.sha256(png).hexdigest()
        geometry_model = capture_geometry((1286, 666))
        geometry = geometry_model.model_dump(mode="json")
        client._last_screenshot = BridgeScreenshot(
            png=png,
            frame_sha256=digest,
            capture_geometry=geometry_model,
        )
        client.responses.append(
            {
                "status": "ok",
                "atomic_frame_click_guard_version": 1,
                "atomic_frame_click_guard_modes": ["full_frame_png_sha256"],
                "atomic_frame_click_authorization_scopes": [
                    "operator_confirmed_final_mutating_click"
                ],
            }
        )

        with self.assertRaisesRegex(RuntimeError, "update and restart"):
            client.click(
                800,
                500,
                expected_window=geometry["outer_window"],
                expected_capture_geometry=geometry,
                expected_frame_sha256=digest,
                guard_expires_at="2099-01-01T00:00:00+00:00",
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path="/tmp/KILL_SWITCH_TEST",
            )

        self.assertEqual(client.sent, [{"cmd": "capabilities"}])

    def test_guarded_click_without_last_client_screenshot_sends_nothing(self) -> None:
        client = StubBridgeClient()
        geometry = capture_geometry_payload((1286, 666))

        with self.assertRaisesRegex(RuntimeError, "last BridgeClient screenshot"):
            client.click(
                800,
                500,
                expected_window=geometry["outer_window"],
                expected_capture_geometry=geometry,
                expected_frame_sha256="a" * 64,
                guard_expires_at="2099-01-01T00:00:00+00:00",
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path="/tmp/KILL_SWITCH_TEST",
            )

        self.assertEqual(client.sent, [])

    def test_click_forwards_expected_window_guard(self) -> None:
        client = StubBridgeClient()
        geometry = capture_geometry_payload((1286, 666))
        expected = geometry["outer_window"]
        png = _make_png()
        digest = hashlib.sha256(png).hexdigest()
        client._last_screenshot = BridgeScreenshot(
            png=png,
            frame_sha256=digest,
            capture_geometry=capture_geometry((1286, 666)),
        )
        semantic_guard = {
            "schema_version": 1,
            "algorithm": "semantic-roi-rgb24-sha256-v1",
            "semantic_target_key": "chapter_claim_button",
            "frame_size": [1286, 666],
            "capture_geometry": geometry,
            "normalized_bbox": {"x_min": 600, "y_min": 700, "x_max": 644, "y_max": 802},
            "roi_bbox": {"x": 772, "y": 466, "width": 56, "height": 68},
            "click_point": {"x": 800, "y": 500},
            "roi_sha256": "b" * 64,
        }
        expiry = "2099-01-01T00:00:00+00:00"
        client.responses.extend(
            [
                {
                    "status": "ok",
                    "atomic_frame_click_guard_version": 1,
                    "capture_geometry_version": 1,
                    "atomic_frame_click_guard_modes": [
                        "semantic_roi_rgb24_sha256",
                        "full_frame_png_sha256",
                    ],
                    "atomic_frame_click_authorization_scopes": [
                        "operator_confirmed_final_mutating_click",
                        "observation_bound_intermediate_click",
                    ],
                },
                {
                    "status": "ok",
                    "atomic_frame_guard": {
                        "verified": True,
                        "version": 1,
                        "mode": "semantic_roi_rgb24_sha256",
                        "semantic_frame_guard": semantic_guard,
                        "expected_roi_sha256": "b" * 64,
                        "captured_roi_sha256": "b" * 64,
                        "guard_expires_at": expiry,
                        "authorization_scope": "operator_confirmed_final_mutating_click",
                        "capture_backend": "wgc",
                        "source_capture_geometry": geometry,
                        "recapture_geometry": geometry,
                        "absolute_click_point": {"x": 800, "y": 500},
                        "kill_switch_guard": {
                            "checked": True,
                            "path": "\\\\wsl$\\Ubuntu\\tmp\\KILL_SWITCH_TEST",
                            "checks": [
                                {
                                    "stage": stage,
                                    "checked_at": "2099-01-01T00:00:00+00:00",
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
                },
            ]
        )

        self.assertEqual(
            client.click(
                800,
                500,
                expected_window=expected,
                expected_capture_geometry=geometry,
                expected_frame_sha256=digest,
                guard_expires_at=expiry,
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path="/tmp/KILL_SWITCH_TEST",
                semantic_frame_guard=semantic_guard,
            )["status"],
            "ok",
        )
        self.assertEqual(
            client.sent,
            [
                {"cmd": "capabilities"},
                {
                    "cmd": "click",
                    "x": 800,
                    "y": 500,
                    "button": "left",
                    "expected_window": expected,
                    "expected_capture_geometry": geometry,
                    "atomic_frame_click_guard_version": 1,
                    "expected_frame_sha256": digest,
                    "guard_expires_at": expiry,
                    "authorization_scope": "operator_confirmed_final_mutating_click",
                    "kill_switch_path": "\\\\wsl$\\Ubuntu\\tmp\\KILL_SWITCH_TEST",
                    "semantic_frame_guard": semantic_guard,
                }
            ],
        )

    def test_guarded_click_without_frame_binding_sends_nothing(self) -> None:
        client = StubBridgeClient()
        geometry = capture_geometry_payload((3, 4), hwnd=1, pid=2)

        with self.assertRaisesRegex(ValueError, "SHA256"):
            client.click(
                10,
                10,
                expected_window=geometry["outer_window"],
                expected_capture_geometry=geometry,
            )

        self.assertEqual(client.sent, [])

    def test_guarded_click_rejects_zero_area_semantic_roi_before_sending(self) -> None:
        client = StubBridgeClient()
        geometry = capture_geometry_payload((1286, 666))
        guard = {
            "schema_version": 1,
            "algorithm": "semantic-roi-rgb24-sha256-v1",
            "semantic_target_key": "chapter_claim_button",
            "frame_size": [1286, 666],
            "capture_geometry": geometry,
            "normalized_bbox": {
                "x_min": 0.0,
                "y_min": 0.0,
                "x_max": 0.1,
                "y_max": 0.1,
            },
            "roi_bbox": {"x": 0, "y": 0, "width": 0, "height": 0},
            "click_point": {"x": 0, "y": 0},
            "roi_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        }

        with self.assertRaisesRegex(ValueError, "no decoded pixel area"):
            client.click(
                0,
                0,
                expected_window=geometry["outer_window"],
                expected_capture_geometry=geometry,
                expected_frame_sha256="a" * 64,
                guard_expires_at="2099-01-01T00:00:00+00:00",
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path="/tmp/KILL_SWITCH_TEST",
                semantic_frame_guard=guard,
            )

        self.assertEqual(client.sent, [])

    def test_guarded_click_rejects_dispatch_outside_semantic_roi_before_sending(self) -> None:
        client = StubBridgeClient()
        geometry = capture_geometry_payload((1286, 666))
        guard = {
            "schema_version": 1,
            "algorithm": "semantic-roi-rgb24-sha256-v1",
            "semantic_target_key": "chapter_claim_button",
            "frame_size": [1286, 666],
            "capture_geometry": geometry,
            "normalized_bbox": {"x_min": 600, "y_min": 700, "x_max": 644, "y_max": 802},
            "roi_bbox": {"x": 772, "y": 466, "width": 56, "height": 68},
            "click_point": {"x": 800, "y": 500},
            "roi_sha256": "b" * 64,
        }

        with self.assertRaisesRegex(ValueError, "click point"):
            client.click(
                801,
                500,
                expected_window=geometry["outer_window"],
                expected_capture_geometry=geometry,
                expected_frame_sha256="a" * 64,
                guard_expires_at="2099-01-01T00:00:00+00:00",
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path="/tmp/KILL_SWITCH_TEST",
                semantic_frame_guard=guard,
            )

        self.assertEqual(client.sent, [])

    def test_final_target_cannot_downgrade_to_intermediate_scope(self) -> None:
        client = StubBridgeClient()
        geometry = capture_geometry_payload((1286, 666))
        guard = {
            "schema_version": 1,
            "algorithm": "semantic-roi-rgb24-sha256-v1",
            "semantic_target_key": "chapter_claim_button",
            "frame_size": [1286, 666],
            "capture_geometry": geometry,
            "normalized_bbox": {"x_min": 600, "y_min": 700, "x_max": 644, "y_max": 802},
            "roi_bbox": {"x": 772, "y": 466, "width": 56, "height": 68},
            "click_point": {"x": 800, "y": 500},
            "roi_sha256": "b" * 64,
        }

        with self.assertRaisesRegex(ValueError, "scope does not match"):
            client.click(
                800,
                500,
                expected_window=geometry["outer_window"],
                expected_capture_geometry=geometry,
                expected_frame_sha256="a" * 64,
                guard_expires_at="2099-01-01T00:00:00+00:00",
                authorization_scope="observation_bound_intermediate_click",
                kill_switch_path="/tmp/KILL_SWITCH_TEST",
                semantic_frame_guard=guard,
            )

        self.assertEqual(client.sent, [])


def _make_png() -> bytes:
    image = Image.new("RGB", (1286, 666), (20, 40, 60))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    unittest.main()
