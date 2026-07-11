from __future__ import annotations

import ast
from pathlib import Path
import unittest


ADAPTERS = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "pioneer_agent"
    / "adapters"
)


class WindowsCaptureBoundaryTests(unittest.TestCase):
    def test_capture_module_has_no_transport_or_input_dispatch_surface(self) -> None:
        source = (ADAPTERS / "win_capture.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported_roots: set[str] = set()
        function_names: set[str] = set()
        attribute_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_names.add(node.name)
            elif isinstance(node, ast.Attribute):
                attribute_names.add(node.attr)

        self.assertTrue({"dxcam", "windows_capture"} <= imported_roots)
        self.assertTrue(
            {"socket", "pyautogui", "pynput"}.isdisjoint(imported_roots)
        )
        self.assertTrue(
            {
                "click_at",
                "click_window_relative",
                "drag_window_relative",
                "handle_client",
                "key_press",
                "main",
                "recv_msg",
                "send_binary",
                "send_json",
            }.isdisjoint(function_names)
        )
        self.assertTrue(
            {
                "SendInput",
                "SendMessage",
                "PostMessage",
                "SetCursorPos",
                "SetForegroundWindow",
                "mouse_event",
                "keybd_event",
            }.isdisjoint(attribute_names)
        )

    def test_recorder_loads_capture_only_module(self) -> None:
        source = (ADAPTERS / "win_record_replay.py").read_text(encoding="utf-8")

        self.assertIn('with_name("win_capture.py")', source)
        self.assertNotIn('with_name("win_bridge_server.py")', source)

    def test_bridge_delegates_capture_but_retains_legacy_restore_wrapper(self) -> None:
        source = (ADAPTERS / "win_bridge_server.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name: ast.get_source_segment(source, node) or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
        }

        self.assertIn("_capture.capture_window_dxgi", functions["capture_window_dxgi"])
        self.assertIn("_capture.capture_window_wgc", functions["capture_window_wgc"])
        self.assertIn("_ensure_window_onscreen", functions["capture_window_dxgi"])
        self.assertIn("_ensure_window_onscreen", functions["capture_window_wgc"])


if __name__ == "__main__":
    unittest.main()
