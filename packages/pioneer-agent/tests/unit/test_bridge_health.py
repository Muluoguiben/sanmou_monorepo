from __future__ import annotations

import io
import unittest
from typing import Any

from PIL import Image

from pioneer_agent.adapters.health import BridgeHealthChecker, BridgeHealthStatus


def _png() -> bytes:
    image = Image.new("RGB", (32, 18), "black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class _HealthyBridge:
    def ping(self) -> bool:
        return True

    def screenshot(self) -> bytes:
        return _png()

    def window_info(self) -> dict[str, Any]:
        return {"width": 1920, "height": 1080, "title": "三谋"}

    def click(self, x: int, y: int, button: str = "left") -> dict[str, Any]:
        return {"status": "ok"}

    def drag(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"status": "ok"}

    def key_press(self, key: str, modifiers: list[str] | None = None) -> dict[str, Any]:
        return {"status": "ok"}


class _BadScreenshotBridge(_HealthyBridge):
    def screenshot(self) -> bytes:
        return b"not-png"


class _ScreenshotOnlyBridge:
    def screenshot(self) -> bytes:
        return _png()

    def window_info(self) -> dict[str, Any]:
        return {"width": 800, "height": 600}


class BridgeHealthTests(unittest.TestCase):
    def test_healthy_bridge_passes_all_checks(self) -> None:
        report = BridgeHealthChecker().check(_HealthyBridge())

        self.assertEqual(report.status, BridgeHealthStatus.OK)
        self.assertTrue(report.healthy)
        self.assertTrue(report.ping_ok)
        self.assertTrue(report.screenshot_ok)
        self.assertTrue(report.screenshot_is_png)
        self.assertEqual(report.window_info["width"], 1920)
        self.assertTrue(report.input_capability_ok)
        self.assertEqual(report.failures, ())

    def test_bad_screenshot_fails_health(self) -> None:
        report = BridgeHealthChecker().check(_BadScreenshotBridge())

        self.assertEqual(report.status, BridgeHealthStatus.FAILED)
        self.assertFalse(report.screenshot_ok)
        self.assertIn("screenshot is not a PNG payload", report.failures)

    def test_missing_input_capability_is_degraded(self) -> None:
        report = BridgeHealthChecker().check(_ScreenshotOnlyBridge())

        self.assertEqual(report.status, BridgeHealthStatus.DEGRADED)
        self.assertFalse(report.input_capability_ok)
        self.assertIn("input capability methods are missing", report.failures)


if __name__ == "__main__":
    unittest.main()
