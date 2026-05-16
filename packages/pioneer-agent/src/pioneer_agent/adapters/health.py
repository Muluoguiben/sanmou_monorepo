from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class BridgeHealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True)
class BridgeHealthReport:
    status: BridgeHealthStatus
    checked_at: datetime
    ping_ok: bool | None = None
    screenshot_ok: bool = False
    screenshot_bytes: int = 0
    screenshot_is_png: bool = False
    window_info_ok: bool = False
    window_info: dict[str, Any] = field(default_factory=dict)
    input_capability_ok: bool = False
    failures: tuple[str, ...] = ()

    @property
    def healthy(self) -> bool:
        return self.status == BridgeHealthStatus.OK


class BridgeHealthChecker:
    def check(self, bridge: Any) -> BridgeHealthReport:
        failures: list[str] = []
        ping_ok = self._check_ping(bridge, failures)
        screenshot_bytes, screenshot_is_png = self._check_screenshot(bridge, failures)
        window_info = self._check_window_info(bridge, failures)
        input_capability_ok = _has_input_capability(bridge)
        if not input_capability_ok:
            failures.append("input capability methods are missing")

        required_failed = (
            ping_ok is False
            or screenshot_bytes == 0
            or not screenshot_is_png
            or not _window_info_ok(window_info)
        )
        if required_failed:
            status = BridgeHealthStatus.FAILED
        elif not input_capability_ok:
            status = BridgeHealthStatus.DEGRADED
        else:
            status = BridgeHealthStatus.OK

        return BridgeHealthReport(
            status=status,
            checked_at=datetime.now(UTC),
            ping_ok=ping_ok,
            screenshot_ok=screenshot_bytes > 0 and screenshot_is_png,
            screenshot_bytes=screenshot_bytes,
            screenshot_is_png=screenshot_is_png,
            window_info_ok=_window_info_ok(window_info),
            window_info=window_info,
            input_capability_ok=input_capability_ok,
            failures=tuple(failures),
        )

    def _check_ping(self, bridge: Any, failures: list[str]) -> bool | None:
        ping = getattr(bridge, "ping", None)
        if ping is None:
            return None
        try:
            ok = bool(ping())
        except Exception as exc:  # noqa: BLE001
            failures.append(f"ping failed: {exc}")
            return False
        if not ok:
            failures.append("ping returned false")
        return ok

    def _check_screenshot(self, bridge: Any, failures: list[str]) -> tuple[int, bool]:
        try:
            png = bridge.screenshot()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"screenshot failed: {exc}")
            return 0, False
        screenshot_is_png = png.startswith(PNG_MAGIC)
        if not screenshot_is_png:
            failures.append("screenshot is not a PNG payload")
        return len(png), screenshot_is_png

    def _check_window_info(self, bridge: Any, failures: list[str]) -> dict[str, Any]:
        window_info = getattr(bridge, "window_info", None)
        if window_info is None:
            failures.append("window_info method is missing")
            return {}
        try:
            info = dict(window_info())
        except Exception as exc:  # noqa: BLE001
            failures.append(f"window_info failed: {exc}")
            return {}
        if not _window_info_ok(info):
            failures.append("window_info missing positive width/height")
        return info


def _window_info_ok(info: dict[str, Any]) -> bool:
    return _positive_int(info.get("width")) and _positive_int(info.get("height"))


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and value > 0


def _has_input_capability(bridge: Any) -> bool:
    return all(
        callable(getattr(bridge, name, None))
        for name in ("click", "drag", "key_press")
    )
