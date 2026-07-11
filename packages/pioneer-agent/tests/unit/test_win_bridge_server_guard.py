from __future__ import annotations

import importlib.util
import hashlib
import io
import sys
import types
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from tests.unit.capture_geometry_fixtures import capture_geometry_payload


class _FakePyAutoGui:
    def __init__(self) -> None:
        self.clicks: list[tuple[int, int, str]] = []
        self.presses: list[str] = []

    def click(self, x: int, y: int, *, button: str) -> None:
        self.clicks.append((x, y, button))

    def press(self, key: str) -> None:
        self.presses.append(key)

    def hotkey(self, *keys: str) -> None:
        self.presses.append("+".join(keys))


def _load_server(
    *,
    foreground_error: bool = False,
    point_root: int = 101,
    window_rect: tuple[int, int, int, int] = (0, 0, 1286, 666),
):
    gui = types.ModuleType("win32gui")
    gui.GetWindowRect = lambda _hwnd: window_rect
    gui.IsWindowVisible = lambda _hwnd: True
    gui.IsIconic = lambda _hwnd: False
    gui.GetWindowText = lambda _hwnd: "三国：谋定天下"
    gui.GetForegroundWindow = lambda: 101
    gui.WindowFromPoint = lambda _point: 303
    gui.GetAncestor = lambda _hwnd, _flag: point_root

    def _foreground(_hwnd: int) -> None:
        if foreground_error:
            raise RuntimeError("foreground lock")

    gui.SetForegroundWindow = _foreground

    process = types.ModuleType("win32process")
    process.GetWindowThreadProcessId = lambda _hwnd: (1, 202)
    constants = types.ModuleType("win32con")
    constants.GA_ROOT = 2
    capture = types.ModuleType("windows_capture")
    capture.WindowsCapture = object

    module_name = "_pioneer_win_bridge_server_guard_test"
    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "pioneer_agent"
        / "adapters"
        / "win_bridge_server.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    fake_modules = {
        "dxcam": types.ModuleType("dxcam"),
        "win32con": constants,
        "win32gui": gui,
        "win32process": process,
        "windows_capture": capture,
        module_name: module,
    }
    with patch.dict(sys.modules, fake_modules):
        spec.loader.exec_module(module)
    module.pyautogui = _FakePyAutoGui()
    return module


class GuardedWindowClickTests(unittest.TestCase):
    geometry = capture_geometry_payload((1286, 666))
    expected = geometry["outer_window"]

    def setUp(self) -> None:
        self._temp = TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.kill_switch_path = str(Path(self._temp.name) / "KILL_SWITCH")

    def _guard_kwargs(self) -> dict[str, object]:
        return {
            "expected_frame_sha256": "a" * 64,
            "guard_expires_at": (
                datetime.now(UTC) + timedelta(seconds=10)
            ).isoformat(),
            "authorization_scope": "operator_confirmed_final_mutating_click",
            "kill_switch_path": self.kill_switch_path,
            "expected_capture_geometry": self.geometry,
            "capture_backend": "wgc",
            "atomic_frame_click_guard_version": 1,
        }

    def test_foreground_failure_sends_no_click(self) -> None:
        server = _load_server(foreground_error=True)

        with self.assertRaisesRegex(RuntimeError, "foreground"):
            server.click_window_relative(
                101,
                800,
                500,
                expected_window=self.expected,
                **self._guard_kwargs(),
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_covered_point_sends_no_click(self) -> None:
        server = _load_server(point_root=999)

        with self.assertRaisesRegex(RuntimeError, "covered"):
            server.click_window_relative(
                101,
                800,
                500,
                expected_window=self.expected,
                **self._guard_kwargs(),
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_out_of_bounds_point_sends_no_click(self) -> None:
        server = _load_server()

        with self.assertRaisesRegex(RuntimeError, "outside"):
            server.click_window_relative(
                101,
                1286,
                500,
                expected_window=self.expected,
                **self._guard_kwargs(),
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_foreground_failure_sends_no_key(self) -> None:
        server = _load_server(foreground_error=True)

        with self.assertRaisesRegex(RuntimeError, "foreground"):
            server.key_press_window_guarded(101, "escape")

        self.assertEqual(server.pyautogui.presses, [])

    def test_semantic_roi_mismatch_sends_no_click(self) -> None:
        server = _load_server()
        initial = _make_png((20, 40, 60))
        changed = _make_png((60, 40, 20))
        guard = _semantic_guard(initial)
        server.capture_window_with_backend = lambda _hwnd, backend: (
            changed,
            self.geometry,
        )
        server._validate_capture_sanity = lambda _png, hwnd: None

        with self.assertRaisesRegex(RuntimeError, "semantic ROI changed"):
            server.click_window_relative(
                101,
                800,
                500,
                expected_window=self.expected,
                expected_capture_geometry=self.geometry,
                expected_frame_sha256=hashlib.sha256(initial).hexdigest(),
                guard_expires_at=(
                    datetime.now(UTC) + timedelta(seconds=10)
                ).isoformat(),
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path=self.kill_switch_path,
                semantic_frame_guard=guard,
                capture_backend="wgc",
                atomic_frame_click_guard_version=1,
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_zero_area_semantic_roi_sends_no_click(self) -> None:
        server = _load_server()
        png = _make_png((20, 40, 60))
        server.capture_window = lambda _hwnd, backend: png
        server._validate_capture_sanity = lambda _png, hwnd: None
        guard = {
            "schema_version": 1,
            "algorithm": "semantic-roi-rgb24-sha256-v1",
            "semantic_target_key": "chapter_claim_button",
            "frame_size": [1286, 666],
            "capture_geometry": self.geometry,
            "normalized_bbox": {
                "x_min": 0.0,
                "y_min": 0.0,
                "x_max": 0.1,
                "y_max": 0.1,
            },
            "roi_bbox": {"x": 0, "y": 0, "width": 0, "height": 0},
            "click_point": {"x": 0, "y": 0},
            "roi_sha256": hashlib.sha256(b"").hexdigest(),
        }

        with self.assertRaisesRegex(RuntimeError, "no decoded pixel area"):
            server.click_window_relative(
                101,
                0,
                0,
                expected_window=self.expected,
                expected_capture_geometry=self.geometry,
                expected_frame_sha256=hashlib.sha256(png).hexdigest(),
                guard_expires_at=(
                    datetime.now(UTC) + timedelta(seconds=10)
                ).isoformat(),
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path=self.kill_switch_path,
                semantic_frame_guard=guard,
                capture_backend="wgc",
                atomic_frame_click_guard_version=1,
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_semantic_click_outside_half_open_roi_sends_no_click(self) -> None:
        server = _load_server()
        guard = {
            "schema_version": 1,
            "algorithm": "semantic-roi-rgb24-sha256-v1",
            "semantic_target_key": "chapter_claim_button",
            "frame_size": [1286, 666],
            "capture_geometry": self.geometry,
            "normalized_bbox": {
                "x_min": 14.0,
                "y_min": 27.0,
                "x_max": 15.0,
                "y_max": 29.0,
            },
            "roi_bbox": {"x": 18, "y": 18, "width": 1, "height": 1},
            "click_point": {"x": 19, "y": 18},
            "roi_sha256": "b" * 64,
        }

        with self.assertRaisesRegex(RuntimeError, "click point"):
            server.click_window_relative(
                101,
                19,
                18,
                expected_window=self.expected,
                expected_capture_geometry=self.geometry,
                expected_frame_sha256="a" * 64,
                guard_expires_at=(
                    datetime.now(UTC) + timedelta(seconds=10)
                ).isoformat(),
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path=self.kill_switch_path,
                semantic_frame_guard=guard,
                capture_backend="wgc",
                atomic_frame_click_guard_version=1,
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_kill_switch_triggered_during_capture_sends_no_click(self) -> None:
        server = _load_server()
        png = _make_png((20, 40, 60))
        guard = _semantic_guard(png)

        def capture_and_trigger(_hwnd, backend):  # noqa: ANN001
            Path(self.kill_switch_path).write_text("stop\n", encoding="utf-8")
            return png, self.geometry

        server.capture_window_with_backend = capture_and_trigger
        server._validate_capture_sanity = lambda _png, hwnd: None

        with self.assertRaisesRegex(RuntimeError, "kill switch is triggered at after_capture"):
            server.click_window_relative(
                101,
                800,
                500,
                expected_window=self.expected,
                expected_capture_geometry=self.geometry,
                expected_frame_sha256=hashlib.sha256(png).hexdigest(),
                guard_expires_at=(
                    datetime.now(UTC) + timedelta(seconds=10)
                ).isoformat(),
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path=self.kill_switch_path,
                semantic_frame_guard=guard,
                capture_backend="wgc",
                atomic_frame_click_guard_version=1,
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_alt_tab_during_final_kill_switch_check_sends_no_click(self) -> None:
        server = _load_server()
        png = _make_png((20, 40, 60))
        guard = _semantic_guard(png)
        server.capture_window_with_backend = lambda _hwnd, backend: (
            png,
            self.geometry,
        )
        server._validate_capture_sanity = lambda _png, hwnd: None
        original_check = server._assert_kill_switch_clear

        def check_and_alt_tab(path, *, stage):  # noqa: ANN001
            result = original_check(path, stage=stage)
            if stage == "before_input_injection":
                server.win32gui.GetForegroundWindow = lambda: 999
            return result

        server._assert_kill_switch_clear = check_and_alt_tab

        with self.assertRaisesRegex(RuntimeError, "lost foreground"):
            server.click_window_relative(
                101,
                800,
                500,
                expected_window=self.expected,
                expected_capture_geometry=self.geometry,
                expected_frame_sha256=hashlib.sha256(png).hexdigest(),
                guard_expires_at=(
                    datetime.now(UTC) + timedelta(seconds=10)
                ).isoformat(),
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path=self.kill_switch_path,
                semantic_frame_guard=guard,
                capture_backend="wgc",
                atomic_frame_click_guard_version=1,
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_inaccessible_kill_switch_parent_sends_no_click(self) -> None:
        server = _load_server()
        missing = str(Path(self._temp.name) / "missing" / "KILL_SWITCH")

        with self.assertRaisesRegex(RuntimeError, "parent is not accessible"):
            server.click_window_relative(
                101,
                800,
                500,
                expected_window=self.expected,
                expected_capture_geometry=self.geometry,
                expected_frame_sha256="a" * 64,
                guard_expires_at=(
                    datetime.now(UTC) + timedelta(seconds=10)
                ).isoformat(),
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path=missing,
                capture_backend="wgc",
                atomic_frame_click_guard_version=1,
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_expired_confirmation_sends_no_click(self) -> None:
        server = _load_server()

        with self.assertRaisesRegex(RuntimeError, "expired"):
            server.click_window_relative(
                101,
                800,
                500,
                expected_window=self.expected,
                expected_capture_geometry=self.geometry,
                expected_frame_sha256="a" * 64,
                guard_expires_at=(
                    datetime.now(UTC) - timedelta(seconds=1)
                ).isoformat(),
                authorization_scope="operator_confirmed_final_mutating_click",
                kill_switch_path=self.kill_switch_path,
                capture_backend="wgc",
                atomic_frame_click_guard_version=1,
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_matching_semantic_roi_clicks_once_and_attests(self) -> None:
        server = _load_server()
        initial = _make_png((20, 40, 60))
        guard = _semantic_guard(initial)
        server.capture_window_with_backend = lambda _hwnd, backend: (
            initial,
            self.geometry,
        )
        server._validate_capture_sanity = lambda _png, hwnd: None
        expiry = (datetime.now(UTC) + timedelta(seconds=10)).isoformat()

        result = server.click_window_relative(
            101,
            800,
            500,
            expected_window=self.expected,
            expected_capture_geometry=self.geometry,
            expected_frame_sha256=hashlib.sha256(initial).hexdigest(),
            guard_expires_at=expiry,
            authorization_scope="operator_confirmed_final_mutating_click",
            kill_switch_path=self.kill_switch_path,
            semantic_frame_guard=guard,
            capture_backend="wgc",
            atomic_frame_click_guard_version=1,
        )

        self.assertEqual(server.pyautogui.clicks, [(800, 500, "left")])
        proof = result["atomic_frame_guard"]
        self.assertTrue(proof["verified"])
        self.assertEqual(proof["mode"], "semantic_roi_rgb24_sha256")
        self.assertEqual(proof["captured_roi_sha256"], guard["roi_sha256"])
        self.assertEqual(
            [item["stage"] for item in proof["kill_switch_guard"]["checks"]],
            ["before_capture", "after_capture", "before_input_injection"],
        )

    def test_wgc_border_geometry_maps_screenshot_point_from_capture_origin(self) -> None:
        server = _load_server(window_rect=(0, 0, 2582, 1336))
        geometry = server._wgc_capture_geometry(
            outer_window={
                "hwnd": 101,
                "pid": 202,
                "left": 0,
                "top": 0,
                "right": 2582,
                "bottom": 1336,
                "width": 2582,
                "height": 1336,
            },
            dwm_bounds=(9, 0, 2573, 1327),
            frame_size=(2564, 1327),
        )
        png = _make_png_size((2564, 1327), (20, 40, 60))
        server.capture_window_with_backend = lambda _hwnd, backend: (
            png,
            geometry,
        )
        server._validate_capture_sanity = lambda _png, hwnd: None

        result = server.click_window_relative(
            101,
            800,
            500,
            expected_window=geometry["outer_window"],
            expected_capture_geometry=geometry,
            expected_frame_sha256=hashlib.sha256(png).hexdigest(),
            guard_expires_at=(datetime.now(UTC) + timedelta(seconds=10)).isoformat(),
            authorization_scope="operator_confirmed_final_mutating_click",
            kill_switch_path=self.kill_switch_path,
            capture_backend="wgc",
            atomic_frame_click_guard_version=1,
        )

        self.assertEqual(server.pyautogui.clicks, [(809, 500, "left")])
        self.assertEqual(
            result["atomic_frame_guard"]["absolute_click_point"],
            {"x": 809, "y": 500},
        )

    def test_wgc_rejects_frame_not_matching_dwm_bounds(self) -> None:
        server = _load_server(window_rect=(0, 0, 2582, 1336))
        outer = {
            "hwnd": 101,
            "pid": 202,
            "left": 0,
            "top": 0,
            "right": 2582,
            "bottom": 1336,
            "width": 2582,
            "height": 1336,
        }

        with self.assertRaisesRegex(RuntimeError, "uniquely bound"):
            server._wgc_capture_geometry(
                outer_window=outer,
                dwm_bounds=(9, 0, 2573, 1327),
                frame_size=(2565, 1327),
            )

    def test_dxgi_geometry_uses_actual_clamped_region(self) -> None:
        server = _load_server()
        outer = {
            "hwnd": 101,
            "pid": 202,
            "left": -100,
            "top": -50,
            "right": 800,
            "bottom": 600,
            "width": 900,
            "height": 650,
        }

        rect = server._dxgi_clamped_capture_rect(
            outer,
            output_width=1920,
            output_height=1080,
        )
        geometry = server._build_capture_geometry(
            backend="dxgi",
            outer_window=outer,
            capture_rect=rect,
            frame_size=(800, 600),
        )

        self.assertEqual(rect, (0, 0, 800, 600))
        self.assertEqual(geometry["capture_origin"], {"x": 0, "y": 0})
        self.assertEqual(geometry["frame_size"], [800, 600])

    def test_atomic_recapture_geometry_or_backend_drift_sends_no_click(self) -> None:
        png = _make_png((20, 40, 60))
        expected = capture_geometry_payload(
            (1286, 666),
            outer_rect=(0, 0, 1290, 666),
        )
        drifts = (
            capture_geometry_payload(
                (1286, 666),
                capture_origin=(1, 0),
                outer_rect=(0, 0, 1290, 666),
            ),
            capture_geometry_payload(
                (1286, 666),
                backend="dxgi",
                outer_rect=(0, 0, 1290, 666),
            ),
        )
        for drift in drifts:
            with self.subTest(drift=drift["capture_backend"]):
                server = _load_server(window_rect=(0, 0, 1290, 666))
                server.capture_window_with_backend = lambda _hwnd, backend: (
                    png,
                    drift,
                )
                server._validate_capture_sanity = lambda _png, hwnd: None

                with self.assertRaisesRegex(RuntimeError, "geometry changed"):
                    server.click_window_relative(
                        101,
                        800,
                        500,
                        expected_window=expected["outer_window"],
                        expected_capture_geometry=expected,
                        expected_frame_sha256=hashlib.sha256(png).hexdigest(),
                        guard_expires_at=(
                            datetime.now(UTC) + timedelta(seconds=10)
                        ).isoformat(),
                        authorization_scope="operator_confirmed_final_mutating_click",
                        kill_switch_path=self.kill_switch_path,
                        capture_backend="wgc",
                        atomic_frame_click_guard_version=1,
                    )
                self.assertEqual(server.pyautogui.clicks, [])

    def test_invalid_capture_rect_is_rejected(self) -> None:
        server = _load_server()
        geometry = capture_geometry_payload((1286, 666))
        geometry["capture_rect"]["right"] -= 1

        with self.assertRaisesRegex(RuntimeError, "capture rectangle is invalid"):
            server._validate_capture_geometry(geometry)

    def test_protocol_reuses_concrete_backend_from_observed_screenshot(self) -> None:
        server = _load_server()
        png = _make_png((20, 40, 60))
        digest = hashlib.sha256(png).hexdigest()
        messages = iter(
            [
                {"cmd": "screenshot", "backend": "auto"},
                {
                    "cmd": "click",
                    "x": 800,
                    "y": 500,
                    "expected_window": self.expected,
                    "expected_capture_geometry": self.geometry,
                    "expected_frame_sha256": digest,
                    "guard_expires_at": (
                        datetime.now(UTC) + timedelta(seconds=10)
                    ).isoformat(),
                    "authorization_scope": "operator_confirmed_final_mutating_click",
                    "kill_switch_path": self.kill_switch_path,
                    "atomic_frame_click_guard_version": 1,
                },
                {"cmd": "quit"},
            ]
        )
        clicks: list[dict[str, object]] = []
        server.recv_msg = lambda _conn: next(messages)
        server.send_json = lambda _conn, _payload: None
        server.send_binary = lambda _conn, _payload: None
        server._resolve_window = lambda _title, _hwnd: 101
        server.capture_window_with_backend = lambda _hwnd, backend: (
            png,
            self.geometry,
        )
        server._validate_capture_sanity = lambda _png, hwnd: None

        def record_click(_hwnd, _x, _y, _button, **kwargs):  # noqa: ANN001
            clicks.append(kwargs)
            return {}

        server.click_window_relative = record_click

        server.handle_client(object(), "game", "auto")

        self.assertEqual(len(clicks), 1)
        self.assertEqual(clicks[0]["capture_backend"], "wgc")


def _make_png(color: tuple[int, int, int]) -> bytes:
    return _make_png_size((1286, 666), color)


def _make_png_size(
    size: tuple[int, int],
    color: tuple[int, int, int],
) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _semantic_guard(png: bytes) -> dict[str, object]:
    roi = {"x": 772, "y": 466, "width": 56, "height": 68}
    with Image.open(io.BytesIO(png)) as image:
        rgb = image.convert("RGB")
        crop = rgb.crop((772, 466, 828, 534))
    return {
        "schema_version": 1,
        "algorithm": "semantic-roi-rgb24-sha256-v1",
        "semantic_target_key": "chapter_claim_button",
        "frame_size": [1286, 666],
        "capture_geometry": capture_geometry_payload((1286, 666)),
        "normalized_bbox": {
            "x_min": 600.0,
            "y_min": 700.0,
            "x_max": 644.0,
            "y_max": 802.0,
        },
        "roi_bbox": roi,
        "click_point": {"x": 800, "y": 500},
        "roi_sha256": hashlib.sha256(crop.tobytes()).hexdigest(),
    }


if __name__ == "__main__":
    unittest.main()
