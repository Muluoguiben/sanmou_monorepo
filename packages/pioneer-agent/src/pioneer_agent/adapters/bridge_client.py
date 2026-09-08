"""WSL2-side client for the Windows bridge server.

Communicates with the bridge server via a python.exe subprocess proxy,
bypassing WSL2 network routing issues (e.g. WireGuard, NAT).
"""

from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pioneer_agent.core.models import CaptureGeometry


_ATOMIC_FRAME_CLICK_GUARD_VERSION = 1
_CAPTURE_GEOMETRY_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ATOMIC_AUTHORIZATION_SCOPES = frozenset(
    {
        "operator_confirmed_final_mutating_click",
        "observation_bound_intermediate_click",
    }
)


from pioneer_agent.adapters.capture_bridge_client import (
    CaptureBridgeClient, BridgeScreenshot, _to_windows_path,
)


def _to_windows_kill_switch_path(value: Path | str) -> str:
    """Convert an absolute WSL path to the Windows UNC seen by the server."""
    raw = str(value)
    if raw.startswith("/"):
        return "\\\\wsl$\\Ubuntu" + raw.replace("/", "\\")
    if raw.startswith("\\\\") or re.match(r"^[A-Za-z]:[\\/]", raw):
        return raw.replace("/", "\\")
    raise ValueError("kill-switch path must be absolute and Windows-accessible")


class BridgeClient(CaptureBridgeClient):
    """Legacy guarded control API; capture transport never authorizes input."""

    atomic_frame_click_guard_version = _ATOMIC_FRAME_CLICK_GUARD_VERSION
    capture_geometry_version = _CAPTURE_GEOMETRY_VERSION
    atomic_frame_click_guard_modes = frozenset(
        {"semantic_roi_rgb24_sha256", "full_frame_png_sha256"}
    )
    atomic_frame_click_authorization_scopes = _ATOMIC_AUTHORIZATION_SCOPES

    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        *,
        expected_window: dict[str, int] | None = None,
        expected_capture_geometry: dict[str, Any] | CaptureGeometry | None = None,
        expected_frame_sha256: str | None = None,
        guard_expires_at: str | None = None,
        authorization_scope: str | None = None,
        kill_switch_path: Path | str | None = None,
        semantic_frame_guard: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a click at screenshot-relative coordinates when guarded."""
        atomic_guard = expected_window is not None
        capture_geometry_payload: dict[str, Any] | None = None
        if atomic_guard:
            capture_geometry_payload = _capture_geometry_payload(
                expected_capture_geometry
            )
            _validate_atomic_click_request(
                expected_window=expected_window,
                expected_capture_geometry=capture_geometry_payload,
                expected_frame_sha256=expected_frame_sha256,
                guard_expires_at=guard_expires_at,
                authorization_scope=authorization_scope,
                kill_switch_path=kill_switch_path,
                semantic_frame_guard=semantic_frame_guard,
                click_point=(x, y),
            )
            last = self._last_screenshot
            if (
                last is None
                or hashlib.sha256(last.png).hexdigest() != expected_frame_sha256
                or last.frame_sha256 != expected_frame_sha256
                or last.capture_geometry.model_dump(mode="json")
                != capture_geometry_payload
            ):
                raise RuntimeError(
                    "guarded click is not bound to the last BridgeClient screenshot"
                )
            # A dispatch attempt is one-shot locally as well as on the server.
            self._last_screenshot = None
        elif (
            expected_frame_sha256 is not None
            or guard_expires_at is not None
            or authorization_scope is not None
            or kill_switch_path is not None
            or semantic_frame_guard is not None
            or expected_capture_geometry is not None
        ):
            raise ValueError("atomic frame guard requires expected_window")
        else:
            self._last_screenshot = None

        self.connect()
        if atomic_guard:
            self._send({"cmd": "capabilities"})
            capabilities = self._read_line()
            if (
                capabilities.get("status") != "ok"
                or capabilities.get("atomic_frame_click_guard_version")
                != _ATOMIC_FRAME_CLICK_GUARD_VERSION
            ):
                raise RuntimeError(
                    "bridge does not advertise atomic frame click guard v1"
                )
            if (
                capabilities.get("capture_geometry_version")
                != _CAPTURE_GEOMETRY_VERSION
            ):
                raise RuntimeError(
                    "bridge does not advertise capture geometry v1; update and restart the Windows bridge server"
                )
            supported_modes = capabilities.get("atomic_frame_click_guard_modes")
            required_mode = (
                "semantic_roi_rgb24_sha256"
                if semantic_frame_guard is not None
                else "full_frame_png_sha256"
            )
            if not isinstance(supported_modes, list) or required_mode not in supported_modes:
                raise RuntimeError(
                    f"bridge does not advertise atomic click mode {required_mode}"
                )
            supported_scopes = capabilities.get(
                "atomic_frame_click_authorization_scopes"
            )
            if (
                not isinstance(supported_scopes, list)
                or authorization_scope not in supported_scopes
            ):
                raise RuntimeError(
                    f"bridge does not advertise atomic authorization scope {authorization_scope}"
                )
        payload: dict[str, Any] = {
            "cmd": "click",
            "x": x,
            "y": y,
            "button": button,
        }
        if expected_window is not None:
            payload["expected_window"] = dict(expected_window)
            assert capture_geometry_payload is not None
            payload["expected_capture_geometry"] = capture_geometry_payload
            payload["atomic_frame_click_guard_version"] = (
                _ATOMIC_FRAME_CLICK_GUARD_VERSION
            )
            payload["expected_frame_sha256"] = expected_frame_sha256
            payload["guard_expires_at"] = guard_expires_at
            payload["authorization_scope"] = authorization_scope
            assert kill_switch_path is not None
            payload["kill_switch_path"] = _to_windows_kill_switch_path(
                kill_switch_path
            )
            if semantic_frame_guard is not None:
                payload["semantic_frame_guard"] = dict(semantic_frame_guard)
            if self.capture_backend:
                payload["backend"] = self.capture_backend
        self._send(payload)
        response = self._read_line()
        if atomic_guard and response.get("status") == "ok":
            _validate_atomic_click_response(
                response,
                expected_frame_sha256=expected_frame_sha256,
                guard_expires_at=guard_expires_at,
                authorization_scope=authorization_scope,
                kill_switch_path=_to_windows_kill_switch_path(kill_switch_path),
                capture_backend=self.capture_backend,
                semantic_frame_guard=semantic_frame_guard,
                expected_capture_geometry=capture_geometry_payload,
            )
        return response

    def move(self, x: int, y: int, duration: float = 0.0) -> dict[str, Any]:
        """Move the cursor to window-relative coordinates (hover)."""
        self._last_screenshot = None
        self.connect()
        self._send({"cmd": "move", "x": x, "y": y, "duration": duration})
        return self._read_line()

    def drag(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: float = 0.4,
        button: str = "left",
    ) -> dict[str, Any]:
        """Drag from (x1,y1) to (x2,y2) in window coords. Used to pan the map."""
        self._last_screenshot = None
        self.connect()
        self._send({
            "cmd": "drag",
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "duration": duration, "button": button,
        })
        return self._read_line()

    def key_press(self, key: str, modifiers: list[str] | None = None) -> dict[str, Any]:
        """Press a keyboard key — e.g. 'escape', 'enter', 'tab'."""
        self._last_screenshot = None
        self.connect()
        payload: dict[str, Any] = {"cmd": "key", "key": key}
        if modifiers:
            payload["modifiers"] = modifiers
        self._send(payload)
        return self._read_line()



def _validate_atomic_click_request(
    *,
    expected_window: dict[str, int],
    expected_capture_geometry: dict[str, Any],
    expected_frame_sha256: str | None,
    guard_expires_at: str | None,
    authorization_scope: str | None,
    kill_switch_path: Path | str | None,
    semantic_frame_guard: dict[str, Any] | None,
    click_point: tuple[int, int],
) -> None:
    geometry = CaptureGeometry.model_validate(expected_capture_geometry)
    if geometry.outer_window.model_dump(mode="json") != expected_window:
        raise ValueError(
            "guarded click window identity does not match capture geometry"
        )
    if not isinstance(expected_frame_sha256, str) or not _SHA256_RE.fullmatch(
        expected_frame_sha256
    ):
        raise ValueError("guarded click requires a lowercase SHA256 frame hash")
    if not isinstance(guard_expires_at, str):
        raise ValueError("guarded click requires an aware guard expiry")
    try:
        expiry = datetime.fromisoformat(guard_expires_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("guarded click expiry is invalid") from exc
    if expiry.tzinfo is None or expiry.utcoffset() is None:
        raise ValueError("guarded click expiry must be timezone-aware")
    if authorization_scope not in _ATOMIC_AUTHORIZATION_SCOPES:
        raise ValueError("guarded click authorization scope is invalid")
    if kill_switch_path is None:
        raise ValueError("guarded click requires a kill-switch path")
    _to_windows_kill_switch_path(kill_switch_path)
    if semantic_frame_guard is not None:
        if (
            not isinstance(semantic_frame_guard, dict)
            or semantic_frame_guard.get("algorithm")
            != "semantic-roi-rgb24-sha256-v1"
            or not isinstance(semantic_frame_guard.get("semantic_target_key"), str)
            or not _SHA256_RE.fullmatch(
                str(semantic_frame_guard.get("roi_sha256", ""))
            )
        ):
            raise ValueError("guarded click semantic ROI binding is invalid")
        if semantic_frame_guard.get("capture_geometry") != expected_capture_geometry:
            raise ValueError(
                "guarded click semantic ROI does not bind the capture geometry"
            )
        _validate_semantic_guard_geometry(
            semantic_frame_guard,
            click_point=click_point,
        )
        if _scope_for_target(semantic_frame_guard["semantic_target_key"]) != authorization_scope:
            raise ValueError(
                "guarded click authorization scope does not match its semantic target"
            )


def _validate_atomic_click_response(
    response: dict[str, Any],
    *,
    expected_frame_sha256: str | None,
    guard_expires_at: str | None,
    authorization_scope: str | None,
    kill_switch_path: str,
    capture_backend: str | None,
    semantic_frame_guard: dict[str, Any] | None,
    expected_capture_geometry: dict[str, Any] | None,
) -> None:
    proof = response.get("atomic_frame_guard")
    if not isinstance(proof, dict):
        raise RuntimeError("bridge omitted atomic frame guard attestation")
    if proof.get("verified") is not True or proof.get("version") != _ATOMIC_FRAME_CLICK_GUARD_VERSION:
        raise RuntimeError("bridge returned an invalid atomic frame guard attestation")
    if proof.get("guard_expires_at") != guard_expires_at:
        raise RuntimeError("bridge returned an invalid guard expiry attestation")
    if proof.get("authorization_scope") != authorization_scope:
        raise RuntimeError("bridge returned an invalid authorization scope attestation")
    if semantic_frame_guard is None:
        if (
            proof.get("mode") != "full_frame_png_sha256"
            or proof.get("expected_frame_sha256") != expected_frame_sha256
            or proof.get("captured_frame_sha256") != expected_frame_sha256
        ):
            raise RuntimeError("bridge returned an invalid full-frame attestation")
    elif (
        proof.get("mode") != "semantic_roi_rgb24_sha256"
        or proof.get("expected_roi_sha256")
        != semantic_frame_guard.get("roi_sha256")
        or proof.get("captured_roi_sha256")
        != semantic_frame_guard.get("roi_sha256")
        or proof.get("semantic_frame_guard") != semantic_frame_guard
    ):
        raise RuntimeError("bridge returned an invalid semantic ROI attestation")
    if (
        capture_backend in {"wgc", "dxgi"}
        and proof.get("capture_backend") != capture_backend
    ):
        raise RuntimeError("bridge used a different backend for atomic frame validation")
    if proof.get("capture_backend") not in {"wgc", "dxgi"}:
        raise RuntimeError("bridge did not attest a concrete atomic capture backend")
    if (
        expected_capture_geometry is None
        or proof.get("source_capture_geometry") != expected_capture_geometry
        or proof.get("recapture_geometry") != expected_capture_geometry
        or proof.get("capture_backend")
        != expected_capture_geometry.get("capture_backend")
    ):
        raise RuntimeError("bridge returned an invalid capture geometry attestation")
    expected_click = (
        semantic_frame_guard.get("click_point")
        if isinstance(semantic_frame_guard, dict)
        else None
    )
    if isinstance(expected_click, dict):
        origin = expected_capture_geometry["capture_origin"]
        absolute = {
            "x": origin["x"] + expected_click["x"],
            "y": origin["y"] + expected_click["y"],
        }
        if proof.get("absolute_click_point") != absolute:
            raise RuntimeError("bridge returned an invalid absolute click attestation")
    _validate_kill_switch_attestation(
        proof.get("kill_switch_guard"),
        expected_path=kill_switch_path,
    )


def _validate_semantic_guard_geometry(
    guard: dict[str, Any],
    *,
    click_point: tuple[int, int],
) -> None:
    frame_size = guard.get("frame_size")
    if (
        not isinstance(frame_size, (list, tuple))
        or len(frame_size) != 2
        or any(not _plain_positive_int(value) for value in frame_size)
    ):
        raise ValueError("semantic guard frame size is invalid")
    normalized = guard.get("normalized_bbox")
    if not isinstance(normalized, dict):
        raise ValueError("semantic guard normalized bbox is invalid")
    values: dict[str, float] = {}
    for key in ("x_min", "y_min", "x_max", "y_max"):
        raw = normalized.get(key)
        if not _finite_number(raw):
            raise ValueError("semantic guard normalized bbox is invalid")
        values[key] = float(raw)
    if not (
        0 <= values["x_min"] < values["x_max"] <= 1000
        and 0 <= values["y_min"] < values["y_max"] <= 1000
    ):
        raise ValueError("semantic guard normalized bbox is out of range")

    width, height = int(frame_size[0]), int(frame_size[1])
    left = round(values["x_min"] / 1000 * width)
    top = round(values["y_min"] / 1000 * height)
    right = round(values["x_max"] / 1000 * width)
    bottom = round(values["y_max"] / 1000 * height)
    if right <= left or bottom <= top:
        raise ValueError("semantic guard ROI has no decoded pixel area")
    expected_roi = {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }
    expected_click = {
        "x": min(
            max(round((values["x_min"] + values["x_max"]) / 2000 * width), left),
            right - 1,
        ),
        "y": min(
            max(round((values["y_min"] + values["y_max"]) / 2000 * height), top),
            bottom - 1,
        ),
    }
    if guard.get("roi_bbox") != expected_roi:
        raise ValueError("semantic guard ROI geometry is inconsistent")
    if guard.get("click_point") != expected_click or click_point != (
        expected_click["x"],
        expected_click["y"],
    ):
        raise ValueError("semantic guard click point is inconsistent")
    if not (
        left <= expected_click["x"] < right
        and top <= expected_click["y"] < bottom
        and right <= width
        and bottom <= height
    ):
        raise ValueError("semantic guard click must be inside its half-open ROI")


def _capture_geometry_payload(
    value: dict[str, Any] | CaptureGeometry | None,
) -> dict[str, Any]:
    try:
        geometry = (
            value
            if isinstance(value, CaptureGeometry)
            else CaptureGeometry.model_validate(value)
        )
    except (ValidationError, TypeError, ValueError) as exc:
        raise ValueError("guarded click requires valid capture geometry v1") from exc
    return geometry.model_dump(mode="json")


def _validate_kill_switch_attestation(value: Any, *, expected_path: str) -> None:
    if (
        not isinstance(value, dict)
        or value.get("checked") is not True
        or value.get("path") != expected_path
    ):
        raise RuntimeError("bridge omitted the kill-switch attestation")
    checks = value.get("checks")
    expected_stages = (
        "before_capture",
        "after_capture",
        "before_input_injection",
    )
    if not isinstance(checks, list) or tuple(
        item.get("stage") if isinstance(item, dict) else None
        for item in checks
    ) != expected_stages:
        raise RuntimeError("bridge returned incomplete kill-switch checks")
    if any(
        not isinstance(item, dict)
        or item.get("parent_accessible") is not True
        or item.get("stop_file_present") is not False
        or not isinstance(item.get("checked_at"), str)
        for item in checks
    ):
        raise RuntimeError("bridge returned an invalid kill-switch check")


def _finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _plain_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _scope_for_target(target_key: Any) -> str | None:
    if target_key in {
        "chapter_claim_button",
        "recruit_button",
        "upgrade_confirm_button",
    }:
        return "operator_confirmed_final_mutating_click"
    if target_key == "building_upgrade_button":
        return "observation_bound_intermediate_click"
    return None
