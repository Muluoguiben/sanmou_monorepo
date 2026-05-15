from __future__ import annotations

from typing import Any, Protocol

from pioneer_agent.adapters.bridge_client import BridgeClient
from pioneer_agent.core.device import CapabilityFlags, DeviceSession


class ControlAdapter(Protocol):
    @property
    def capabilities(self) -> CapabilityFlags: ...

    def click(self, x: int, y: int, button: str = "left") -> dict[str, Any]: ...

    def drag(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: float = 0.4,
        button: str = "left",
    ) -> dict[str, Any]: ...

    def key_press(self, key: str, modifiers: list[str] | None = None) -> dict[str, Any]: ...


class UnsupportedControlAdapter:
    """Control adapter for Advisor-only sources; every input attempt is rejected."""

    def __init__(self, device_session: DeviceSession | None = None) -> None:
        self.device_session = device_session
        self._capabilities = CapabilityFlags(observe_only=True)

    @property
    def capabilities(self) -> CapabilityFlags:
        return self._capabilities

    def click(self, x: int, y: int, button: str = "left") -> dict[str, Any]:
        return self._blocked("click")

    def drag(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: float = 0.4,
        button: str = "left",
    ) -> dict[str, Any]:
        return self._blocked("drag")

    def key_press(self, key: str, modifiers: list[str] | None = None) -> dict[str, Any]:
        return self._blocked("key_press")

    def _blocked(self, command: str) -> dict[str, Any]:
        session_id = self.device_session.session_id if self.device_session else None
        return {
            "status": "blocked",
            "command": command,
            "device_session_id": session_id,
            "message": "input control is disabled for observe-only sources",
        }


class WindowsBridgeControlAdapter:
    """Explicit opt-in control adapter over the existing Windows bridge."""

    def __init__(self, bridge: BridgeClient | None = None) -> None:
        self.bridge = bridge or BridgeClient()
        self._capabilities = CapabilityFlags(
            observe_only=False,
            live_capture=True,
            input_control=True,
            reliable_window_info=True,
        )

    @property
    def capabilities(self) -> CapabilityFlags:
        return self._capabilities

    def click(self, x: int, y: int, button: str = "left") -> dict[str, Any]:
        return self.bridge.click(x, y, button=button)

    def drag(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: float = 0.4,
        button: str = "left",
    ) -> dict[str, Any]:
        return self.bridge.drag(x1, y1, x2, y2, duration=duration, button=button)

    def key_press(self, key: str, modifiers: list[str] | None = None) -> dict[str, Any]:
        return self.bridge.key_press(key, modifiers=modifiers)
