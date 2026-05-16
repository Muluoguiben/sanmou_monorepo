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


if __name__ == "__main__":
    unittest.main()
