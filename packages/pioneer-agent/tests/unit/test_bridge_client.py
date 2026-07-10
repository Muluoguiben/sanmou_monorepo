from __future__ import annotations

import base64
import unittest

from pioneer_agent.adapters.bridge_client import BridgeClient


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
    def test_screenshot_sends_capture_backend_when_configured(self) -> None:
        client = StubBridgeClient(capture_backend="wgc")
        client.responses.append({
            "status": "ok",
            "data_b64": base64.b64encode(b"png-bytes").decode("ascii"),
        })

        self.assertEqual(client.screenshot(), b"png-bytes")
        self.assertEqual(client.sent, [{"cmd": "screenshot", "backend": "wgc"}])

    def test_list_windows_accepts_optional_title_filter(self) -> None:
        client = StubBridgeClient()
        client.responses.append({"status": "ok", "windows": []})

        self.assertEqual(client.list_windows("三国"), {"status": "ok", "windows": []})
        self.assertEqual(client.sent, [{"cmd": "list_windows", "title": "三国"}])

    def test_click_forwards_expected_window_guard(self) -> None:
        client = StubBridgeClient()
        expected = {"hwnd": 101, "pid": 202, "width": 1286, "height": 666}
        semantic_guard = {
            "schema_version": 1,
            "algorithm": "semantic-roi-rgb24-sha256-v1",
            "semantic_target_key": "chapter_claim_button",
            "frame_size": [1286, 666],
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
                expected_frame_sha256="a" * 64,
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
                    "atomic_frame_click_guard_version": 1,
                    "expected_frame_sha256": "a" * 64,
                    "guard_expires_at": expiry,
                    "authorization_scope": "operator_confirmed_final_mutating_click",
                    "kill_switch_path": "\\\\wsl$\\Ubuntu\\tmp\\KILL_SWITCH_TEST",
                    "semantic_frame_guard": semantic_guard,
                }
            ],
        )

    def test_guarded_click_without_frame_binding_sends_nothing(self) -> None:
        client = StubBridgeClient()

        with self.assertRaisesRegex(ValueError, "SHA256"):
            client.click(
                10,
                10,
                expected_window={"hwnd": 1, "pid": 2, "width": 3, "height": 4},
            )

        self.assertEqual(client.sent, [])

    def test_guarded_click_rejects_zero_area_semantic_roi_before_sending(self) -> None:
        client = StubBridgeClient()
        guard = {
            "schema_version": 1,
            "algorithm": "semantic-roi-rgb24-sha256-v1",
            "semantic_target_key": "chapter_claim_button",
            "frame_size": [1286, 666],
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
                expected_window={"hwnd": 101, "pid": 202, "width": 1286, "height": 666},
                expected_frame_sha256="a" * 64,
                guard_expires_at="2099-01-01T00:00:00+00:00",
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path="/tmp/KILL_SWITCH_TEST",
                semantic_frame_guard=guard,
            )

        self.assertEqual(client.sent, [])

    def test_guarded_click_rejects_dispatch_outside_semantic_roi_before_sending(self) -> None:
        client = StubBridgeClient()
        guard = {
            "schema_version": 1,
            "algorithm": "semantic-roi-rgb24-sha256-v1",
            "semantic_target_key": "chapter_claim_button",
            "frame_size": [1286, 666],
            "normalized_bbox": {"x_min": 600, "y_min": 700, "x_max": 644, "y_max": 802},
            "roi_bbox": {"x": 772, "y": 466, "width": 56, "height": 68},
            "click_point": {"x": 800, "y": 500},
            "roi_sha256": "b" * 64,
        }

        with self.assertRaisesRegex(ValueError, "click point"):
            client.click(
                801,
                500,
                expected_window={"hwnd": 101, "pid": 202, "width": 1286, "height": 666},
                expected_frame_sha256="a" * 64,
                guard_expires_at="2099-01-01T00:00:00+00:00",
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path="/tmp/KILL_SWITCH_TEST",
                semantic_frame_guard=guard,
            )

        self.assertEqual(client.sent, [])

    def test_final_target_cannot_downgrade_to_intermediate_scope(self) -> None:
        client = StubBridgeClient()
        guard = {
            "schema_version": 1,
            "algorithm": "semantic-roi-rgb24-sha256-v1",
            "semantic_target_key": "chapter_claim_button",
            "frame_size": [1286, 666],
            "normalized_bbox": {"x_min": 600, "y_min": 700, "x_max": 644, "y_max": 802},
            "roi_bbox": {"x": 772, "y": 466, "width": 56, "height": 68},
            "click_point": {"x": 800, "y": 500},
            "roi_sha256": "b" * 64,
        }

        with self.assertRaisesRegex(ValueError, "scope does not match"):
            client.click(
                800,
                500,
                expected_window={"hwnd": 101, "pid": 202, "width": 1286, "height": 666},
                expected_frame_sha256="a" * 64,
                guard_expires_at="2099-01-01T00:00:00+00:00",
                authorization_scope="observation_bound_intermediate_click",
                kill_switch_path="/tmp/KILL_SWITCH_TEST",
                semantic_frame_guard=guard,
            )

        self.assertEqual(client.sent, [])


if __name__ == "__main__":
    unittest.main()
