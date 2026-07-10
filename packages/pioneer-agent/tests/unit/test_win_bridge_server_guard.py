from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


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


def _load_server(*, foreground_error: bool = False, point_root: int = 101):
    gui = types.ModuleType("win32gui")
    gui.GetWindowRect = lambda _hwnd: (0, 0, 1286, 666)
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
    expected = {"hwnd": 101, "pid": 202, "width": 1286, "height": 666}

    def test_foreground_failure_sends_no_click(self) -> None:
        server = _load_server(foreground_error=True)

        with self.assertRaisesRegex(RuntimeError, "foreground"):
            server.click_window_relative(
                101,
                800,
                500,
                expected_window=self.expected,
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
            )

        self.assertEqual(server.pyautogui.clicks, [])

    def test_foreground_failure_sends_no_key(self) -> None:
        server = _load_server(foreground_error=True)

        with self.assertRaisesRegex(RuntimeError, "foreground"):
            server.key_press_window_guarded(101, "escape")

        self.assertEqual(server.pyautogui.presses, [])


if __name__ == "__main__":
    unittest.main()
