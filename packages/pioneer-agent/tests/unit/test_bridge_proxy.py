from __future__ import annotations

import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pioneer_agent.adapters import bridge_proxy


class _FakeSocket:
    def __init__(self, response: dict[str, object]) -> None:
        body = json.dumps(response).encode("utf-8")
        self._response = bytearray(struct.pack(">I", len(body)) + body)
        self.sent = bytearray()
        self.connected_to: tuple[str, int] | None = None
        self.closed = False

    def settimeout(self, _value: int) -> None:
        return None

    def connect(self, address: tuple[str, int]) -> None:
        self.connected_to = address

    def sendall(self, data: bytes) -> None:
        self.sent.extend(data)

    def recv(self, count: int) -> bytes:
        chunk = bytes(self._response[:count])
        del self._response[:count]
        return chunk

    def close(self) -> None:
        self.closed = True


class _RawResponseSocket:
    def __init__(self, body: bytes) -> None:
        self._response = bytearray(struct.pack(">I", len(body)) + body)

    def recv(self, count: int) -> bytes:
        chunk = bytes(self._response[:count])
        del self._response[:count]
        return chunk


class _DeclaredLengthSocket(_RawResponseSocket):
    def __init__(self, length: int) -> None:
        self._response = bytearray(struct.pack(">I", length))


class BridgeProxyAuthenticationTests(unittest.TestCase):
    def test_proxy_accepts_screenshot_envelopes_larger_than_request_limit(self) -> None:
        body = b"x" * 17_000_000

        self.assertEqual(bridge_proxy.recv_frame(_RawResponseSocket(body)), body)

    def test_proxy_rejects_response_above_screenshot_limit_before_reading_body(self) -> None:
        with self.assertRaisesRegex(ConnectionError, "response length"):
            bridge_proxy.recv_frame(
                _DeclaredLengthSocket(bridge_proxy._MAX_PROTOCOL_RESPONSE_BYTES + 1)
            )

    def test_proxy_authenticates_before_reporting_ready(self) -> None:
        token = "a" * 64
        fake_socket = _FakeSocket({"status": "ok", "authenticated": True})

        with tempfile.TemporaryDirectory() as temp_dir:
            token_path = Path(temp_dir) / "bridge.token"
            token_path.write_text(token, encoding="utf-8")
            stdout = io.StringIO()
            with (
                patch.object(
                    sys,
                    "argv",
                    ["bridge_proxy.py", "9877", str(token_path)],
                ),
                patch.object(sys, "stdin", io.StringIO("")),
                patch.object(sys, "stdout", stdout),
                patch.object(
                    bridge_proxy.socket,
                    "socket",
                    return_value=fake_socket,
                ),
            ):
                bridge_proxy.main()

        self.assertEqual(fake_socket.connected_to, ("127.0.0.1", 9877))
        message_length = struct.unpack(">I", fake_socket.sent[:4])[0]
        message = json.loads(fake_socket.sent[4 : 4 + message_length])
        self.assertEqual(message, {"cmd": "authenticate", "token": token})
        self.assertEqual(json.loads(stdout.getvalue()), {"status": "proxy_ready"})
        self.assertTrue(fake_socket.closed)

    def test_proxy_rejects_invalid_token_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            token_path = Path(temp_dir) / "bridge.token"
            token_path.write_text("short", encoding="utf-8")
            with patch.object(
                sys,
                "argv",
                ["bridge_proxy.py", "9877", str(token_path)],
            ):
                with self.assertRaisesRegex(RuntimeError, "32 random bytes"):
                    bridge_proxy._load_auth_token()


if __name__ == "__main__":
    unittest.main()
