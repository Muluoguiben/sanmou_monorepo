from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from PIL import Image

from pioneer_agent.adapters import bridge_proxy
from pioneer_agent.adapters.capture import WindowsBridgeCaptureAdapter
from pioneer_agent.adapters.capture_bridge_client import CaptureBridgeClient
from tests.unit.capture_geometry_fixtures import capture_geometry_payload
from tests.unit.test_win_bridge_server_guard import _load_server


ROOT = Path(__file__).resolve().parents[4]
TOKEN = "synthetic-token-for-offline-security-tests"


def request(cmd="screenshot", **fields):
    return {"cmd": cmd, "protocol_version": 2, "request_id": uuid4().hex, **fields}


def screenshot_response(req, **fields):
    buffer = io.BytesIO()
    Image.new("RGB", (80, 60), (1, 2, 3)).save(buffer, format="PNG")
    png = buffer.getvalue()
    return {
        "status": "ok", "request_id": req["request_id"], "protocol_version": 2,
        "data_b64": base64.b64encode(png).decode("ascii"), "size": len(png),
        "frame_sha256": hashlib.sha256(png).hexdigest(),
        "capture_geometry": capture_geometry_payload((80, 60)),
        "captured_at": datetime.now(UTC).isoformat(), **fields,
    }


class FakeSocket:
    def __init__(self, chunks):
        self.chunks = iter(chunks)
        self.sent = []
        self.closed = False

    def settimeout(self, _value):
        pass

    def sendall(self, data):
        if self.closed:
            raise OSError("closed")
        self.sent.append(data)

    def recv(self, _size):
        if self.closed:
            raise OSError("closed")
        chunk = next(self.chunks, b"")
        if isinstance(chunk, Exception):
            raise chunk
        return chunk

    def close(self):
        self.closed = True


class CaptureSecurityTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "native Windows proxy launch integration")
    def test_native_client_proxy_server_end_to_end_with_synthetic_capture(self):
        server = _load_server()
        template = screenshot_response(request())
        server._resolve_window = lambda *args: 101
        server.capture_window_with_backend = lambda *args, **kwargs: (
            base64.b64decode(template["data_b64"]), template["capture_geometry"])
        server._validate_capture_sanity = lambda *args, **kwargs: None
        errors = []
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(5)
            def serve():
                try:
                    conn, _ = listener.accept()
                    with conn:
                        conn.settimeout(5)
                        server.handle_client(conn, "synthetic", "wgc", auth_token=TOKEN)
                except Exception as exc:
                    errors.append(exc)
            worker = threading.Thread(target=serve)
            worker.start()
            client = CaptureBridgeClient(port=listener.getsockname()[1], capture_backend="wgc")
            try:
                with patch.dict(os.environ, {"SANMOU_CAPTURE_TOKEN": TOKEN}):
                    frame = WindowsBridgeCaptureAdapter(client).capture()
                    self.assertEqual(frame.png, base64.b64decode(template["data_b64"]))
                    self.assertIsNotNone(frame.captured_at.tzinfo)
                    self.assertTrue(client.ping())
            finally:
                client.close()
                worker.join(6)
            self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [])
            self.assertIsNone(client._proc)
            self.assertIsNone(client.last_screenshot)

    def test_fresh_process_game_mcp_import_has_no_control_graph(self):
        code = """
import json, os, sys
try:
    import pioneer_agent.app.game_mcp
except RuntimeError as exc:
    # Native Windows deliberately lacks the fixture root's POSIX safeguards.
    # This is not successful MCP startup; Linux exercises the complete import.
    assert os.name == 'nt' and 'secure fixture reads require' in str(exc), str(exc)
from pioneer_agent.adapters.capture import WindowsBridgeCaptureAdapter
adapter = WindowsBridgeCaptureAdapter()
blocked = [n for n in sys.modules if n.startswith((
    'pioneer_agent.adapters.control', 'pioneer_agent.adapters.bridge_client',
    'pioneer_agent.adapters.win_bridge_server', 'pioneer_agent.executor'))]
print(json.dumps(blocked))
assert not blocked, blocked
assert not any(hasattr(adapter.bridge, n) for n in ('click', 'move', 'drag', 'key_press'))
"""
        run = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.assertEqual(json.loads(run.stdout), [])

    def test_minimized_wgc_dxgi_and_discovery_never_restore_or_focus(self):
        for backend in ("wgc", "dxgi"):
            with self.subTest(backend=backend):
                server = _load_server()
                server.win32gui.IsIconic = lambda _hwnd: True
                mutation = Mock(side_effect=AssertionError("window mutation"))
                server.win32gui.SendMessage = mutation
                server.win32gui.ShowWindow = mutation
                server.win32gui.SetForegroundWindow = mutation
                with self.assertRaisesRegex(RuntimeError, "visible and usable"):
                    server.capture_window_with_backend(101, backend)
                item = server._rect_payload(101)
                server.list_windows = lambda *args, **kwargs: [item]
                with self.assertRaisesRegex(RuntimeError, "No usable target"):
                    server.find_window("game")
                mutation.assert_not_called()
                self.assertEqual(server.pyautogui.clicks, [])
                self.assertEqual(server.pyautogui.presses, [])

    def test_actual_loopback_commands_never_reach_input(self):
        # Real framing/socket exchange; every Windows surface is synthetic.
        for command in ("click", "move", "drag", "key", "restore", "foreground", "start-game"):
            with self.subTest(command=command):
                server = _load_server()
                observer = Mock(side_effect=AssertionError("must reject before lookup"))
                server._resolve_window = observer
                server.click_window_relative = observer
                server.move_window_relative = observer
                server.drag_window_relative = observer
                server.key_press_window_guarded = observer
                with socket.socket() as listener:
                    listener.bind(("127.0.0.1", 0))
                    listener.listen(1)
                    errors = []
                    def serve():
                        try:
                            conn, _ = listener.accept()
                            with conn:
                                conn.settimeout(2)
                                server.handle_client(conn, "synthetic", "wgc", auth_token=TOKEN)
                        except Exception as exc:
                            errors.append(exc)
                    worker = threading.Thread(target=serve)
                    worker.start()
                    with socket.create_connection(listener.getsockname(), timeout=2) as client:
                        req = request(command, x=800, y=500, auth_token=TOKEN)
                        bridge_proxy.send_cmd(client, req)
                        reply = json.loads(bridge_proxy.recv_frame(client))
                    worker.join(3)
                    self.assertFalse(worker.is_alive())
                    self.assertEqual(errors, [])
                self.assertEqual(reply["status"], "error")
                self.assertIn("capture_only", reply["message"])
                self.assertEqual(reply["request_id"], req["request_id"])
                observer.assert_not_called()

    def test_authentication_and_old_peer_rejected_before_observation(self):
        for fields in ({"auth_token": "wrong"}, {"protocol_version": 1, "auth_token": TOKEN}, {"request_id": "old", "auth_token": TOKEN}):
            with self.subTest(fields=fields):
                server = _load_server()
                server._resolve_window = Mock(side_effect=AssertionError("observation"))
                server.recv_msg = Mock(return_value=request(**fields))
                server.send_json = Mock()
                server.handle_client(object(), "game", "wgc", auth_token=TOKEN)
                server._resolve_window.assert_not_called()
                self.assertEqual(server.send_json.call_args.args[1]["status"], "error")
        with self.assertRaisesRegex(RuntimeError, "authentication"):
            server.handle_client(object(), "game", "auto")

    def test_server_binds_capture_time_and_refuses_repeated_request(self):
        server = _load_server()
        req = request(auth_token=TOKEN)
        response = screenshot_response(req)
        server._resolve_window = lambda *args: 101
        server.capture_window_with_backend = lambda *args, **kwargs: (
            base64.b64decode(response["data_b64"]), response["capture_geometry"])
        server._validate_capture_sanity = lambda *args, **kwargs: None
        server.recv_msg = Mock(side_effect=[req, req])
        server.send_json = Mock()
        before = datetime.now(UTC)
        server.handle_client(object(), "game", "wgc", auth_token=TOKEN)
        shot, rejected = [c.args[1] for c in server.send_json.call_args_list]
        self.assertEqual(shot["request_id"], req["request_id"])
        self.assertLessEqual(before, datetime.fromisoformat(shot["captured_at"]))
        self.assertLessEqual(datetime.fromisoformat(shot["captured_at"]), datetime.now(UTC))
        self.assertEqual(rejected["status"], "error")

    def test_server_main_missing_auth_never_listens_and_valid_auth_is_loopback(self):
        server = _load_server()
        server._enable_physical_pixel_coordinates = Mock()
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, "argv", ["server"]), patch.object(server.socket, "socket") as factory:
            with self.assertRaises(SystemExit):
                server.main()
            factory.assert_not_called()
        sock = Mock()
        sock.accept.side_effect = KeyboardInterrupt
        with patch.dict(os.environ, {"SANMOU_CAPTURE_TOKEN": TOKEN}), patch.object(sys, "argv", ["server"]), patch.object(server.socket, "socket", return_value=sock):
            server.main()
        sock.bind.assert_called_once_with(("127.0.0.1", 9877))

    def test_proxy_timeout_partial_frame_and_old_response_close_stream(self):
        req = request()
        old_body = json.dumps(screenshot_response(req, request_id="0" * 32)).encode()
        cases = [
            [socket.timeout(), struct.pack(">I", len(old_body)), old_body],
            [b"\x00\x00", socket.timeout()],
            [struct.pack(">I", 100), b"partial", socket.timeout()],
            [struct.pack(">I", len(old_body)), old_body],
            [struct.pack(">I", 100_000_000)],
            [struct.pack(">I", 4), b"null"],
        ]
        for chunks in cases:
            with self.subTest(chunks=repr(chunks)[:60]):
                sock = FakeSocket(chunks)
                with self.assertRaises((OSError, ValueError, TimeoutError)):
                    bridge_proxy.exchange(sock, req, TOKEN)
                self.assertTrue(sock.closed)
                with self.assertRaises(OSError):
                    bridge_proxy.exchange(sock, request(), TOKEN)
                self.assertEqual(len(sock.sent), 1)

    def test_proxy_refuses_input_without_sending_any_bytes(self):
        for cmd in ("click", "move", "drag", "key"):
            sock = FakeSocket([])
            with self.assertRaises(ValueError):
                bridge_proxy.exchange(sock, request(cmd), TOKEN)
            self.assertEqual(sock.sent, [])
            self.assertTrue(sock.closed)

    def test_client_invalid_response_invalidates_cached_frame_and_connection(self):
        for fields in (
            {"request_id": "0" * 32}, {"protocol_version": 1},
            {"captured_at": None}, {"captured_at": "2026-01-01T00:00:00"},
            {"captured_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
            {"captured_at": (datetime.now(UTC) + timedelta(minutes=1)).isoformat()},
            {"frame_sha256": "0" * 64}, {"size": False}, {"capture_geometry": {}},
        ):
            with self.subTest(fields=fields):
                client = CaptureBridgeClient()
                client.connect = Mock()
                sent = []
                client._send = sent.append
                client._read_line = lambda: screenshot_response(sent[-1], **fields)
                client.close = Mock(wraps=client.close)
                client._last_screenshot = object()
                with self.assertRaises(RuntimeError):
                    client.screenshot_capture()
                client.close.assert_called()
                self.assertIsNone(client.last_screenshot)

    def test_adapter_uses_server_timestamp_and_same_frame_geometry(self):
        client = CaptureBridgeClient()
        client.connect = Mock()
        sent = []
        responses = []
        client._send = sent.append
        def read():
            value = screenshot_response(sent[-1])
            responses.append(value)
            return value
        client._read_line = read
        client.window_info = Mock(side_effect=AssertionError("second observation"))
        adapter = WindowsBridgeCaptureAdapter(client)
        frame = adapter.capture()
        self.assertEqual(frame.captured_at, datetime.fromisoformat(responses[0]["captured_at"]))
        self.assertEqual(frame.device_session.last_observed_at, frame.captured_at)
        self.assertEqual(frame.capture_geometry.model_dump(mode="json"), responses[0]["capture_geometry"])
        self.assertTrue(adapter.capabilities.observe_only)
        self.assertFalse(adapter.capabilities.input_control)
        client.window_info.assert_not_called()


class RetiredControllerTests(unittest.TestCase):
    def test_repository_scripts_contain_no_install_or_input_implementation(self):
        base = ROOT / ".agent/skills/sanmou-client-control"
        for name in ("sanmou_client_control.ps1", "install_sanmou_controller_task.bat"):
            source = (base / "scripts" / name).read_text(encoding="utf-8")
            self.assertIn("SANMOU_LEGACY_CONTROLLER_DISABLED", source)
            for forbidden in ("Register-ScheduledTask", "Start-ScheduledTask", "-Verb RunAs", "SendInput", "Add-Type", "Start-Process", "Copy-Item"):
                self.assertNotIn(forbidden, source)
        skill = (base / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("The user-writable Highest scheduled controller is disabled", skill)

    @unittest.skipUnless(os.name == "nt", "Windows tombstone execution requires PowerShell/cmd")
    def test_retired_entry_points_exit_without_writing_requested_paths(self):
        script = ROOT / ".agent/skills/sanmou-client-control/scripts/sanmou_client_control.ps1"
        with TemporaryDirectory() as tmp:
            sentinel = Path(tmp) / "status.json"
            for action in ("install-controller-task", "register-task", "controller", "send", "start-controller", "start-game-via-task", "capture-window", "click-relative"):
                run = subprocess.run([shutil.which("powershell"), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), action, "-StatusPath", str(sentinel)], capture_output=True, text=True, timeout=10)
                self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
                self.assertIn("SANMOU_LEGACY_CONTROLLER_DISABLED", run.stderr)
                self.assertFalse(sentinel.exists())
            bat = script.with_name("install_sanmou_controller_task.bat")
            run = subprocess.run([os.environ["COMSPEC"], "/c", str(bat)], capture_output=True, text=True, timeout=10)
            self.assertEqual(run.returncode, 1)
            self.assertIn("SANMOU_LEGACY_CONTROLLER_DISABLED", run.stderr)


if __name__ == "__main__":
    unittest.main()
