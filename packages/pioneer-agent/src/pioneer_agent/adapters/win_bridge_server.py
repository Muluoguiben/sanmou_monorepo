"""Windows-side bridge server for game screenshot capture and input injection.

This script runs on the Windows host and exposes a localhost-only TCP interface
for the WSL2-side agent to capture screenshots and send clicks to the game
window. The server requires a per-user token handshake, binds an exclusive
loopback listener, and refuses to run elevated. It is not a remote-control API.

Usage (from Windows or WSL):
    python win_bridge_server.py [--port 9877] [--window "三国：谋定天下"]
        [--auth-token-file "%LOCALAPPDATA%\\SanmouBridge\\bridge.token"]
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import hmac
import importlib.util
import json
import math
import os
import socket
import stat
import struct
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from io import BytesIO


def _load_capture_primitives() -> Any:
    """Load the sibling capture module when this file runs as a script."""
    module_path = Path(__file__).with_name("win_capture.py")
    spec = importlib.util.spec_from_file_location(
        "_sanmou_win_capture_for_bridge", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load Windows capture primitives")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_capture = _load_capture_primitives()

try:
    import win32con
    from PIL import Image
except ImportError as exc:
    print(f"Missing dependency: {exc}", file=sys.stderr)
    print("Install with: pip install dxcam opencv-python pyautogui pywin32 Pillow windows-capture", file=sys.stderr)
    sys.exit(1)

dxcam = _capture.dxcam
win32gui = _capture.win32gui
win32process = _capture.win32process
WindowsCapture = _capture.WindowsCapture

pyautogui = None


MIN_WINDOW_DIM = _capture.MIN_WINDOW_DIM
MIN_SCREENSHOT_DIM = _capture.MIN_SCREENSHOT_DIM
MAX_UNIFORM_PIXEL_RATIO = _capture.MAX_UNIFORM_PIXEL_RATIO
MIN_SCREENSHOT_MEAN = _capture.MIN_SCREENSHOT_MEAN
MIN_SCREENSHOT_STD = _capture.MIN_SCREENSHOT_STD
ATOMIC_FRAME_CLICK_GUARD_VERSION = 1
CAPTURE_GEOMETRY_VERSION = _capture.CAPTURE_GEOMETRY_VERSION
BRIDGE_LISTEN_HOST = "127.0.0.1"
MAX_PROTOCOL_MESSAGE_BYTES = 1_048_576
AUTH_TOKEN_HEX_LENGTH = 64
AUTHENTICATION_TIMEOUT_SECONDS = 10.0
ATOMIC_CLICK_AUTHORIZATION_SCOPES = frozenset(
    {
        "operator_confirmed_final_mutating_click",
        "observation_bound_intermediate_click",
    }
)

CaptureSanityError = _capture.CaptureSanityError
_rect_payload = _capture._rect_payload
_window_geometry_identity = _capture._window_geometry_identity
_screen_rect_payload = _capture._screen_rect_payload
_dwm_extended_frame_bounds = _capture._dwm_extended_frame_bounds
_build_capture_geometry = _capture._build_capture_geometry
_wgc_capture_geometry = _capture._wgc_capture_geometry
_dxgi_clamped_capture_rect = _capture._dxgi_clamped_capture_rect
_validate_capture_geometry = _capture._validate_capture_geometry
_validate_outer_window_identity = _capture._validate_outer_window_identity
_validate_screen_rect = _capture._validate_screen_rect
_plain_int = _capture._plain_int
_plain_positive_int = _capture._plain_positive_int
_enable_physical_pixel_coordinates = _capture._enable_physical_pixel_coordinates


def _normalize_title(title: str) -> str:
    return title.strip().lower()


def _usable_rect(rect: tuple[int, int, int, int], hwnd: int | None = None) -> bool:
    return _usable_rect_reason(rect, hwnd) == "ok"


def _usable_rect_reason(rect: tuple[int, int, int, int], hwnd: int | None = None) -> str:
    left, top, right, bottom = rect
    width = right - left
    height = bottom - top
    if width <= MIN_WINDOW_DIM or height <= MIN_WINDOW_DIM:
        return "too_small"
    if left <= -10000 or top <= -10000:
        return "offscreen"
    if hwnd is not None and win32gui.IsIconic(hwnd):
        return "iconic"
    return "ok"


def list_windows(title_substring: str | None = None, *, include_offscreen: bool = False) -> list[dict[str, Any]]:
    """List visible candidate windows by partial title match."""
    result: list[dict[str, Any]] = []
    needle = _normalize_title(title_substring or "")

    def callback(hwnd: int, _: Any) -> bool:
        try:
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if needle and needle not in _normalize_title(title):
                    return True
                item = _rect_payload(hwnd)
                if include_offscreen or not item["offscreen"]:
                    result.append(item)
        except Exception:
            return True
        return True

    win32gui.EnumWindows(callback, None)
    return result


def _best_window(candidates: list[dict[str, Any]]) -> int | None:
    usable = [item for item in candidates if item["usable"]]
    if not usable:
        return None
    usable.sort(key=lambda item: item["width"] * item["height"], reverse=True)
    return int(usable[0]["hwnd"])


def find_window(title_substring: str) -> int:
    """Find the largest usable visible window by partial title match."""
    result = list_windows(title_substring)
    if not result:
        raise RuntimeError(f"Window not found: {title_substring}")
    hwnd = _best_window(result)
    if hwnd is not None:
        return hwnd

    for item in result:
        _restore_window(int(item["hwnd"]))
    time.sleep(0.5)
    result = list_windows(title_substring)
    hwnd = _best_window(result)
    if hwnd is None:
        compact = [
            {key: item[key] for key in ("hwnd", "title", "left", "top", "width", "height", "iconic", "offscreen")}
            for item in result
        ]
        raise RuntimeError(f"No usable target window for {title_substring}: {compact}")
    return hwnd


def _restore_window(hwnd: int) -> None:
    if win32gui.IsIconic(hwnd):
        win32gui.SendMessage(hwnd, 0x0112, 0xF120, 0)  # WM_SYSCOMMAND + SC_RESTORE
        time.sleep(0.2)


def _ensure_window_onscreen(hwnd: int) -> None:
    """Un-minimize the window if needed so dxcam can capture it.

    dxcam uses DXGI Desktop Duplication — it can grab any visible window
    regardless of foreground status, but a minimized window lives at
    (-32000, -32000) and has no capturable pixels.

    SC_RESTORE via SendMessage has no foreground-lock restriction, so this
    works from a long-running server process (SetForegroundWindow does not).
    """
    for _ in range(10):
        if not win32gui.IsWindow(hwnd):
            raise RuntimeError(f"Invalid window handle: {hwnd}")
        if win32gui.IsIconic(hwnd):
            _restore_window(hwnd)
            time.sleep(0.2)
            continue
        rect = win32gui.GetWindowRect(hwnd)
        if not _usable_rect(rect, hwnd):
            _restore_window(hwnd)
            time.sleep(0.2)
            continue
        return
    rect = win32gui.GetWindowRect(hwnd)
    raise RuntimeError(f"Window is not capturable: hwnd={hwnd} rect={rect} iconic={win32gui.IsIconic(hwnd)}")


def capture_window_dxgi(hwnd: int) -> tuple[bytes, dict[str, Any]]:
    """Preserve bridge restore behavior, then delegate read-only capture."""
    _ensure_window_onscreen(hwnd)
    return _capture.capture_window_dxgi(hwnd)


def capture_window_wgc(
    hwnd: int,
    timeout_seconds: float = 5.0,
) -> tuple[bytes, dict[str, Any]]:
    """Preserve bridge restore behavior, then delegate read-only capture."""
    _ensure_window_onscreen(hwnd)
    return _capture.capture_window_wgc(hwnd, timeout_seconds=timeout_seconds)


_validate_capture_sanity = _capture._validate_capture_sanity


def _resolve_window(window_title: str, hwnd: int | None) -> int:
    if hwnd is not None and win32gui.IsWindow(hwnd):
        current = _rect_payload(hwnd)
        if current["usable"] and _normalize_title(current["title"]).find(_normalize_title(window_title)) >= 0:
            return hwnd
    return find_window(window_title)


def capture_window_with_backend(
    hwnd: int,
    backend: str = "auto",
) -> tuple[bytes, dict[str, Any]]:
    """Capture and return the exact concrete capture geometry."""
    normalized = backend.lower()
    if normalized not in {"auto", "wgc", "dxgi"}:
        raise RuntimeError(f"Unknown capture backend: {backend}")

    errors: list[str] = []
    if normalized in {"auto", "wgc"}:
        try:
            return capture_window_wgc(hwnd)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"wgc: {exc}")
            if normalized == "wgc":
                raise

    if normalized in {"auto", "dxgi"}:
        try:
            return capture_window_dxgi(hwnd)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"dxgi: {exc}")
            if normalized == "dxgi":
                raise

    raise RuntimeError("No capture backend succeeded: " + " | ".join(errors))


def capture_window(hwnd: int, backend: str = "auto") -> bytes:
    png_bytes, _ = capture_window_with_backend(hwnd, backend=backend)
    return png_bytes


def _pyautogui() -> Any:
    global pyautogui
    if pyautogui is None:
        import pyautogui as loaded_pyautogui

        pyautogui = loaded_pyautogui
    return pyautogui


def click_at(x: int, y: int, button: str = "left") -> None:
    """Click at absolute screen coordinates."""
    _pyautogui().click(x, y, button=button)


def _require_foreground_window(hwnd: int, *, action: str) -> None:
    """Focus the target or fail before emitting any global input."""
    _ensure_window_onscreen(hwnd)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        raise RuntimeError(f"failed to foreground {action} target") from exc
    time.sleep(0.05)
    if win32gui.GetForegroundWindow() != hwnd:
        raise RuntimeError(f"{action} target is not the foreground window")


def click_window_relative(
    hwnd: int,
    rx: int,
    ry: int,
    button: str = "left",
    *,
    expected_window: dict[str, Any] | None = None,
    expected_capture_geometry: dict[str, Any] | None = None,
    expected_frame_sha256: str | None = None,
    guard_expires_at: str | None = None,
    authorization_scope: str | None = None,
    kill_switch_path: str | None = None,
    semantic_frame_guard: dict[str, Any] | None = None,
    capture_backend: str = "auto",
    atomic_frame_click_guard_version: int | None = None,
) -> dict[str, Any]:
    """Click at screenshot-relative coordinates.

    Guarded absolute coordinates are resolved from the attested capture origin,
    never from the outer window rectangle.
    """
    expiry: datetime | None = None
    if expected_window is None:
        if (
            expected_frame_sha256 is not None
            or guard_expires_at is not None
            or authorization_scope is not None
            or kill_switch_path is not None
            or semantic_frame_guard is not None
            or expected_capture_geometry is not None
            or atomic_frame_click_guard_version is not None
        ):
            raise RuntimeError("atomic frame guard requires expected_window")
        _ensure_window_onscreen(hwnd)
    else:
        expiry = _validate_atomic_frame_guard(
            expected_frame_sha256=expected_frame_sha256,
            guard_expires_at=guard_expires_at,
            authorization_scope=authorization_scope,
            kill_switch_path=kill_switch_path,
            version=atomic_frame_click_guard_version,
        )
        expected_capture_geometry = _validate_capture_geometry(
            expected_capture_geometry
        )
        if capture_backend != expected_capture_geometry["capture_backend"]:
            raise RuntimeError(
                "atomic recapture backend does not match the observed screenshot"
            )
        if expected_capture_geometry["outer_window"] != expected_window:
            raise RuntimeError(
                "capture geometry outer window does not match guarded identity"
            )
        if semantic_frame_guard is not None:
            _validate_semantic_frame_guard_contract(
                semantic_frame_guard,
                expected_capture_geometry=expected_capture_geometry,
                click_point=(rx, ry),
                authorization_scope=authorization_scope,
            )
        if datetime.now(UTC) >= expiry:
            raise RuntimeError("atomic click guard expired before guarded click")
        _assert_expected_window(hwnd, expected_window)
        _assert_guarded_relative_point(rx, ry, expected_capture_geometry)
    _require_foreground_window(hwnd, action="click")
    if expected_window is not None:
        _assert_expected_window(hwnd, expected_window)
    if expected_capture_geometry is None:
        rect = win32gui.GetWindowRect(hwnd)
        abs_x = rect[0] + rx
        abs_y = rect[1] + ry
    else:
        origin = expected_capture_geometry["capture_origin"]
        abs_x = origin["x"] + rx
        abs_y = origin["y"] + ry
    if expected_window is not None:
        point_window = win32gui.WindowFromPoint((abs_x, abs_y))
        point_root = (
            win32gui.GetAncestor(point_window, win32con.GA_ROOT)
            if point_window
            else None
        )
        if point_root != hwnd:
            raise RuntimeError("guarded click point is covered by another window")

    atomic_guard: dict[str, Any] | None = None
    kill_switch_checks: list[dict[str, Any]] = []
    if expected_window is not None:
        assert expected_frame_sha256 is not None
        assert guard_expires_at is not None
        assert authorization_scope is not None
        assert kill_switch_path is not None
        assert expiry is not None
        kill_switch_checks.append(
            _assert_kill_switch_clear(
                kill_switch_path,
                stage="before_capture",
            )
        )
        png_bytes, recapture_geometry = capture_window_with_backend(
            hwnd,
            backend=capture_backend,
        )
        _validate_capture_sanity(png_bytes, hwnd=hwnd)
        kill_switch_checks.append(
            _assert_kill_switch_clear(
                kill_switch_path,
                stage="after_capture",
            )
        )
        captured_frame_sha256 = hashlib.sha256(png_bytes).hexdigest()
        if recapture_geometry != expected_capture_geometry:
            raise RuntimeError(
                "atomic recapture backend or capture geometry changed before click"
            )
        expected_roi_sha256: str | None = None
        captured_roi_sha256: str | None = None
        if semantic_frame_guard is None:
            if captured_frame_sha256 != expected_frame_sha256:
                raise RuntimeError("window frame changed after operator confirmation")
        else:
            expected_roi_sha256 = str(semantic_frame_guard["roi_sha256"])
            captured_roi_sha256 = _semantic_roi_sha256(
                png_bytes,
                semantic_frame_guard,
            )
            if captured_roi_sha256 != expected_roi_sha256:
                raise RuntimeError(
                    "terminal semantic ROI changed after operator confirmation"
                )

        # Capture can take seconds. Recheck every non-pixel precondition after it
        # and evaluate expiry at the last possible instant before input injection.
        _assert_expected_window(hwnd, expected_window)
        if win32gui.GetForegroundWindow() != hwnd:
            raise RuntimeError("guarded click target lost foreground during frame validation")
        origin = expected_capture_geometry["capture_origin"]
        abs_x = origin["x"] + rx
        abs_y = origin["y"] + ry
        point_window = win32gui.WindowFromPoint((abs_x, abs_y))
        point_root = (
            win32gui.GetAncestor(point_window, win32con.GA_ROOT)
            if point_window
            else None
        )
        if point_root != hwnd:
            raise RuntimeError("guarded click point became covered during frame validation")
        if datetime.now(UTC) >= expiry:
            raise RuntimeError("atomic click guard expired during frame validation")
        kill_switch_checks.append(
            _assert_kill_switch_clear(
                kill_switch_path,
                stage="before_input_injection",
            )
        )
        # The UNC stop-file check can itself block briefly. Re-evaluate every
        # window-bound precondition after it so an Alt-Tab or geometry change
        # during that check cannot redirect the pending absolute-coordinate
        # click into another window.
        _assert_expected_window(hwnd, expected_window)
        if win32gui.GetForegroundWindow() != hwnd:
            raise RuntimeError(
                "guarded click target lost foreground during final kill-switch check"
            )
        origin = expected_capture_geometry["capture_origin"]
        abs_x = origin["x"] + rx
        abs_y = origin["y"] + ry
        point_window = win32gui.WindowFromPoint((abs_x, abs_y))
        point_root = (
            win32gui.GetAncestor(point_window, win32con.GA_ROOT)
            if point_window
            else None
        )
        if point_root != hwnd:
            raise RuntimeError(
                "guarded click point became covered during final kill-switch check"
            )
        # Re-evaluate the deadline at the last possible instant before input.
        verified_at = datetime.now(UTC)
        if verified_at >= expiry:
            raise RuntimeError("atomic click guard expired before input injection")
    _pyautogui().click(abs_x, abs_y, button=button)
    if expected_window is not None:
        atomic_guard = {
            "verified": True,
            "version": ATOMIC_FRAME_CLICK_GUARD_VERSION,
            "mode": (
                "semantic_roi_rgb24_sha256"
                if semantic_frame_guard is not None
                else "full_frame_png_sha256"
            ),
            "source_frame_sha256": expected_frame_sha256,
            "captured_frame_sha256": captured_frame_sha256,
            "guard_expires_at": guard_expires_at,
            "authorization_scope": authorization_scope,
            "verified_at": verified_at.isoformat(),
            "capture_backend": capture_backend,
            "source_capture_geometry": dict(expected_capture_geometry),
            "recapture_geometry": dict(recapture_geometry),
            "absolute_click_point": {"x": abs_x, "y": abs_y},
            "kill_switch_guard": {
                "checked": True,
                "path": kill_switch_path,
                "checks": kill_switch_checks,
            },
        }
        if semantic_frame_guard is None:
            atomic_guard["expected_frame_sha256"] = expected_frame_sha256
        else:
            atomic_guard["semantic_frame_guard"] = dict(semantic_frame_guard)
            atomic_guard["expected_roi_sha256"] = expected_roi_sha256
            atomic_guard["captured_roi_sha256"] = captured_roi_sha256
    return {"atomic_frame_guard": atomic_guard} if atomic_guard is not None else {}


def _validate_atomic_frame_guard(
    *,
    expected_frame_sha256: str | None,
    guard_expires_at: str | None,
    authorization_scope: str | None,
    kill_switch_path: str | None,
    version: int | None,
) -> datetime:
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version != ATOMIC_FRAME_CLICK_GUARD_VERSION
    ):
        raise RuntimeError("guarded click requires atomic frame guard v1")
    if (
        not isinstance(expected_frame_sha256, str)
        or len(expected_frame_sha256) != 64
        or any(char not in "0123456789abcdef" for char in expected_frame_sha256)
    ):
        raise RuntimeError("guarded click requires a lowercase SHA256 frame hash")
    if not isinstance(guard_expires_at, str):
        raise RuntimeError("guarded click requires an aware guard expiry")
    try:
        expiry = datetime.fromisoformat(
            guard_expires_at.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise RuntimeError("guarded click expiry is invalid") from exc
    if expiry.tzinfo is None or expiry.utcoffset() is None:
        raise RuntimeError("guarded click expiry must be timezone-aware")
    if authorization_scope not in ATOMIC_CLICK_AUTHORIZATION_SCOPES:
        raise RuntimeError("guarded click authorization scope is invalid")
    if not isinstance(kill_switch_path, str) or not kill_switch_path:
        raise RuntimeError("guarded click requires a kill-switch path")
    return expiry.astimezone(UTC)


def _assert_kill_switch_clear(path_value: str, *, stage: str) -> dict[str, Any]:
    if not (
        os.path.isabs(path_value)
        or path_value.startswith("\\\\")
    ):
        raise RuntimeError("kill-switch path must be absolute")
    stop_path = Path(path_value)
    parent = stop_path.parent
    try:
        parent_stat = os.stat(parent)
    except OSError as exc:
        raise RuntimeError(
            f"kill-switch parent is not accessible at {stage}"
        ) from exc
    if not stat.S_ISDIR(parent_stat.st_mode):
        raise RuntimeError(f"kill-switch parent is not a directory at {stage}")
    try:
        os.stat(stop_path)
    except FileNotFoundError:
        present = False
    except OSError as exc:
        raise RuntimeError(f"kill-switch state is not checkable at {stage}") from exc
    else:
        present = True
    if present:
        raise RuntimeError(f"kill switch is triggered at {stage}")
    return {
        "stage": stage,
        "checked_at": datetime.now(UTC).isoformat(),
        "parent_accessible": True,
        "stop_file_present": False,
    }


def _validate_semantic_frame_guard_contract(
    guard: dict[str, Any],
    *,
    expected_capture_geometry: dict[str, Any],
    click_point: tuple[int, int],
    authorization_scope: str | None,
) -> None:
    if guard.get("schema_version") != 1:
        raise RuntimeError("semantic frame guard schema is unsupported")
    if guard.get("algorithm") != "semantic-roi-rgb24-sha256-v1":
        raise RuntimeError("semantic frame guard algorithm is unsupported")
    if not isinstance(guard.get("semantic_target_key"), str) or not guard[
        "semantic_target_key"
    ].strip():
        raise RuntimeError("semantic frame guard target key is invalid")
    if _scope_for_semantic_target(guard["semantic_target_key"]) != authorization_scope:
        raise RuntimeError(
            "semantic frame guard authorization scope does not match its target"
        )
    guard_capture_geometry = _validate_capture_geometry(
        guard.get("capture_geometry")
    )
    if guard_capture_geometry != expected_capture_geometry:
        raise RuntimeError(
            "semantic frame guard capture geometry does not match its screenshot"
        )
    frame_size = guard.get("frame_size")
    if (
        not isinstance(frame_size, (list, tuple))
        or len(frame_size) != 2
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
            for value in frame_size
        )
        or tuple(frame_size) != tuple(expected_capture_geometry["frame_size"])
    ):
        raise RuntimeError("semantic frame guard size does not match the captured frame")
    normalized = _normalized_guard_bbox(guard.get("normalized_bbox"))
    expected_roi, expected_click = _semantic_guard_geometry(tuple(frame_size), normalized)
    if expected_roi["width"] <= 0 or expected_roi["height"] <= 0:
        raise RuntimeError("semantic frame guard ROI has no decoded pixel area")
    if (
        expected_roi["x"] < 0
        or expected_roi["y"] < 0
        or expected_roi["x"] + expected_roi["width"] > frame_size[0]
        or expected_roi["y"] + expected_roi["height"] > frame_size[1]
    ):
        raise RuntimeError("semantic frame guard ROI is outside the observed frame")
    if guard.get("roi_bbox") != expected_roi:
        raise RuntimeError("semantic frame guard ROI does not match its target bbox")
    if guard.get("click_point") != expected_click or click_point != (
        expected_click["x"],
        expected_click["y"],
    ):
        raise RuntimeError("semantic frame guard click point does not match dispatch")
    if not (
        expected_roi["x"] <= expected_click["x"]
        < expected_roi["x"] + expected_roi["width"]
        and expected_roi["y"] <= expected_click["y"]
        < expected_roi["y"] + expected_roi["height"]
    ):
        raise RuntimeError("semantic frame guard click point is outside its ROI")
    roi_sha256 = guard.get("roi_sha256")
    if (
        not isinstance(roi_sha256, str)
        or len(roi_sha256) != 64
        or any(char not in "0123456789abcdef" for char in roi_sha256)
    ):
        raise RuntimeError("semantic frame guard ROI hash is invalid")


def _normalized_guard_bbox(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise RuntimeError("semantic frame guard normalized bbox is invalid")
    parsed: dict[str, float] = {}
    for key in ("x_min", "y_min", "x_max", "y_max"):
        raw = value.get(key)
        if (
            isinstance(raw, bool)
            or not isinstance(raw, (int, float))
            or not math.isfinite(float(raw))
        ):
            raise RuntimeError("semantic frame guard normalized bbox is invalid")
        parsed[key] = float(raw)
    if not (
        0 <= parsed["x_min"] < parsed["x_max"] <= 1000
        and 0 <= parsed["y_min"] < parsed["y_max"] <= 1000
    ):
        raise RuntimeError("semantic frame guard normalized bbox is out of range")
    return parsed


def _semantic_guard_geometry(
    frame_size: tuple[int, int],
    bbox: dict[str, float],
) -> tuple[dict[str, int], dict[str, int]]:
    width, height = frame_size
    left = round(bbox["x_min"] / 1000 * width)
    top = round(bbox["y_min"] / 1000 * height)
    right = round(bbox["x_max"] / 1000 * width)
    bottom = round(bbox["y_max"] / 1000 * height)
    return (
        {"x": left, "y": top, "width": right - left, "height": bottom - top},
        {
            "x": min(
                max(
                    round((bbox["x_min"] + bbox["x_max"]) / 2000 * width),
                    left,
                ),
                right - 1,
            ),
            "y": min(
                max(
                    round((bbox["y_min"] + bbox["y_max"]) / 2000 * height),
                    top,
                ),
                bottom - 1,
            ),
        },
    )


def _semantic_roi_sha256(png_bytes: bytes, guard: dict[str, Any]) -> str:
    frame_size = tuple(guard["frame_size"])
    roi = guard["roi_bbox"]
    with Image.open(BytesIO(png_bytes)) as image:
        rgb = image.convert("RGB")
        rgb.load()
    if rgb.size != frame_size:
        raise RuntimeError("atomic recapture size changed before click")
    crop = rgb.crop(
        (
            roi["x"],
            roi["y"],
            roi["x"] + roi["width"],
            roi["y"] + roi["height"],
        )
    )
    return hashlib.sha256(crop.tobytes()).hexdigest()


def _scope_for_semantic_target(target_key: Any) -> str | None:
    if target_key in {
        "chapter_claim_button",
        "recruit_button",
        "upgrade_confirm_button",
    }:
        return "operator_confirmed_final_mutating_click"
    if target_key == "building_upgrade_button":
        return "observation_bound_intermediate_click"
    return None


def _assert_expected_window(hwnd: int, expected: dict[str, Any]) -> None:
    required = (
        "hwnd",
        "pid",
        "left",
        "top",
        "right",
        "bottom",
        "width",
        "height",
    )
    _validate_outer_window_identity(expected)
    info = _rect_payload(hwnd)
    mismatches = [key for key in required if info.get(key) != expected[key]]
    if mismatches:
        raise RuntimeError(
            "window identity/geometry changed before click: " + ", ".join(mismatches)
        )
    if (
        info.get("usable") is not True
        or info.get("visible") is not True
        or info.get("iconic") is not False
        or info.get("offscreen") is not False
    ):
        raise RuntimeError("window is no longer visible and usable before click")


def _assert_guarded_relative_point(
    rx: int,
    ry: int,
    capture_geometry: dict[str, Any],
) -> None:
    frame_size = capture_geometry["frame_size"]
    if (
        isinstance(rx, bool)
        or not isinstance(rx, int)
        or isinstance(ry, bool)
        or not isinstance(ry, int)
        or rx < 0
        or ry < 0
        or rx >= frame_size[0]
        or ry >= frame_size[1]
    ):
        raise RuntimeError("guarded click point is outside the observed frame")


def move_window_relative(hwnd: int, rx: int, ry: int, duration: float = 0.0) -> None:
    """Move mouse to window-relative coords. Useful for hover."""
    _require_foreground_window(hwnd, action="move")
    rect = win32gui.GetWindowRect(hwnd)
    _pyautogui().moveTo(rect[0] + rx, rect[1] + ry, duration=duration)


def drag_window_relative(
    hwnd: int,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    duration: float = 0.4,
    button: str = "left",
) -> None:
    """Drag from (x1,y1) to (x2,y2) in window coordinates — for map panning."""
    _require_foreground_window(hwnd, action="drag")
    rect = win32gui.GetWindowRect(hwnd)
    start = (rect[0] + x1, rect[1] + y1)
    end = (rect[0] + x2, rect[1] + y2)
    ui = _pyautogui()
    ui.moveTo(start[0], start[1], duration=0.0)
    ui.dragTo(end[0], end[1], duration=duration, button=button)


def key_press(key: str, modifiers: list[str] | None = None) -> None:
    """Press a keyboard key. modifiers = ['ctrl','shift','alt'] optional."""
    mods = [m for m in (modifiers or []) if m]
    ui = _pyautogui()
    if mods:
        ui.hotkey(*mods, key)
    else:
        ui.press(key)


def key_press_window_guarded(
    hwnd: int,
    key: str,
    modifiers: list[str] | None = None,
) -> None:
    """Focus the resolved window or fail before emitting a global key event."""
    info = _rect_payload(hwnd)
    if (
        info.get("usable") is not True
        or info.get("visible") is not True
        or info.get("iconic") is not False
        or info.get("offscreen") is not False
    ):
        raise RuntimeError("key target window is not visible and usable")
    _require_foreground_window(hwnd, action="key")
    key_press(key, modifiers=modifiers)


def get_window_info(hwnd: int) -> dict[str, Any]:
    """Return basic window geometry info."""
    info = _rect_payload(hwnd)
    info["wgc_available"] = WindowsCapture is not None
    info["dxcam_available"] = dxcam is not None
    return info


# --- Protocol helpers ---

def recv_msg(conn: socket.socket) -> dict[str, Any]:
    """Receive a length-prefixed JSON message."""
    raw_len = _recv_exact(conn, 4)
    if not raw_len:
        raise ConnectionError("Client disconnected")
    msg_len = struct.unpack(">I", raw_len)[0]
    if msg_len < 2 or msg_len > MAX_PROTOCOL_MESSAGE_BYTES:
        raise ConnectionError("invalid bridge protocol message length")
    data = _recv_exact(conn, msg_len)
    if len(data) != msg_len:
        raise ConnectionError("client disconnected during bridge protocol message")
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError("bridge protocol message must be a JSON object")
    return payload


def send_json(conn: socket.socket, payload: dict[str, Any]) -> None:
    """Send a JSON response with a length prefix."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    conn.sendall(struct.pack(">I", len(body)) + body)


def send_binary(conn: socket.socket, data: bytes) -> None:
    """Send a binary response with a length prefix."""
    conn.sendall(struct.pack(">I", len(data)) + data)


def _recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            return bytes(buf) if buf else b""
        buf.extend(chunk)
    return bytes(buf)


# --- Main server ---


def _load_auth_token(path: Path) -> str:
    try:
        token = path.read_text(encoding="utf-8-sig").strip().lower()
    except OSError as exc:
        raise RuntimeError(f"unable to read bridge auth token: {path}") from exc
    if len(token) != AUTH_TOKEN_HEX_LENGTH or any(
        char not in "0123456789abcdef" for char in token
    ):
        raise RuntimeError("bridge auth token must be exactly 32 random bytes encoded as hex")
    return token


def _authenticate_client(conn: socket.socket, auth_token: str) -> bool:
    try:
        message = recv_msg(conn)
    except (ConnectionError, ValueError, json.JSONDecodeError):
        return False
    supplied = message.get("token")
    authenticated = (
        message.get("cmd") == "authenticate"
        and isinstance(supplied, str)
        and hmac.compare_digest(supplied.lower(), auth_token)
    )
    send_json(
        conn,
        {"status": "ok", "authenticated": True}
        if authenticated
        else {"status": "error", "message": "bridge authentication failed"},
    )
    return authenticated


def handle_client(
    conn: socket.socket,
    window_title: str,
    capture_backend: str,
    *,
    auth_token: str,
) -> None:
    conn.settimeout(AUTHENTICATION_TIMEOUT_SECONDS)
    try:
        authenticated = _authenticate_client(conn, auth_token)
    except (TimeoutError, socket.timeout):
        return
    finally:
        conn.settimeout(None)
    if not authenticated:
        return
    hwnd = None
    last_screenshot_binding: dict[str, Any] | None = None

    while True:
        try:
            msg = recv_msg(conn)
        except ConnectionError:
            break

        cmd = msg.get("cmd", "")

        try:
            if cmd == "ping":
                send_json(conn, {"status": "ok"})

            elif cmd == "capabilities":
                send_json(
                    conn,
                    {
                        "status": "ok",
                        "atomic_frame_click_guard_version": (
                            ATOMIC_FRAME_CLICK_GUARD_VERSION
                        ),
                        "capture_geometry_version": CAPTURE_GEOMETRY_VERSION,
                        "atomic_frame_click_guard_modes": [
                            "semantic_roi_rgb24_sha256",
                            "full_frame_png_sha256",
                        ],
                        "atomic_frame_click_authorization_scopes": sorted(
                            ATOMIC_CLICK_AUTHORIZATION_SCOPES
                        ),
                    },
                )

            elif cmd == "screenshot":
                # A failed replacement capture must not leave a stale frame
                # authorized for a later guarded dispatch.
                last_screenshot_binding = None
                hwnd = _resolve_window(window_title, hwnd)
                png_bytes, capture_geometry = capture_window_with_backend(
                    hwnd,
                    backend=str(msg.get("backend") or capture_backend),
                )
                _validate_capture_sanity(png_bytes, hwnd=hwnd)
                frame_sha256 = hashlib.sha256(png_bytes).hexdigest()
                last_screenshot_binding = {
                    "hwnd": hwnd,
                    "frame_sha256": frame_sha256,
                    "capture_geometry": capture_geometry,
                }
                send_json(
                    conn,
                    {
                        "status": "ok",
                        "data_b64": base64.b64encode(png_bytes).decode("ascii"),
                        "size": len(png_bytes),
                        "frame_sha256": frame_sha256,
                        "capture_geometry": capture_geometry,
                    },
                )

            elif cmd == "click":
                hwnd = _resolve_window(window_title, hwnd)
                button = msg.get("button", "left")
                expected_window = msg.get("expected_window")
                expected_capture_geometry = msg.get("expected_capture_geometry")
                guarded_capture_backend: str | None = None
                if expected_window is not None and not isinstance(expected_window, dict):
                    raise RuntimeError("expected_window must be an object")
                if expected_window is not None:
                    if last_screenshot_binding is None:
                        raise RuntimeError(
                            "guarded click requires a screenshot from this bridge session"
                        )
                    screenshot_binding = last_screenshot_binding
                    # Every guarded dispatch attempt consumes the session-local
                    # screenshot binding, including malformed/mismatched ones.
                    last_screenshot_binding = None
                    if not _plain_int(msg.get("x")) or not _plain_int(msg.get("y")):
                        raise RuntimeError("guarded click coordinates must be integers")
                    rx, ry = msg["x"], msg["y"]
                    expected_capture_geometry = _validate_capture_geometry(
                        expected_capture_geometry
                    )
                    if screenshot_binding.get("hwnd") != hwnd:
                        raise RuntimeError(
                            "guarded click target differs from the observed screenshot window"
                        )
                    if (
                        screenshot_binding.get("frame_sha256")
                        != msg.get("expected_frame_sha256")
                    ):
                        raise RuntimeError(
                            "guarded click frame is not the last bridge screenshot"
                        )
                    if (
                        screenshot_binding.get("capture_geometry")
                        != expected_capture_geometry
                    ):
                        raise RuntimeError(
                            "guarded click capture geometry is not the last bridge screenshot"
                        )
                    guarded_capture_backend = str(
                        expected_capture_geometry["capture_backend"]
                    )
                else:
                    last_screenshot_binding = None
                    rx, ry = int(msg["x"]), int(msg["y"])
                click_result = click_window_relative(
                    hwnd,
                    rx,
                    ry,
                    button,
                    expected_window=expected_window,
                    expected_capture_geometry=expected_capture_geometry,
                    expected_frame_sha256=msg.get("expected_frame_sha256"),
                    guard_expires_at=msg.get("guard_expires_at"),
                    authorization_scope=msg.get("authorization_scope"),
                    kill_switch_path=msg.get("kill_switch_path"),
                    semantic_frame_guard=msg.get("semantic_frame_guard"),
                    capture_backend=(
                        guarded_capture_backend
                        if guarded_capture_backend is not None
                        else str(msg.get("backend") or capture_backend)
                    ),
                    atomic_frame_click_guard_version=msg.get(
                        "atomic_frame_click_guard_version"
                    ),
                )
                send_json(conn, {"status": "ok", **click_result})

            elif cmd == "move":
                last_screenshot_binding = None
                hwnd = _resolve_window(window_title, hwnd)
                rx, ry = int(msg["x"]), int(msg["y"])
                duration = float(msg.get("duration", 0.0))
                move_window_relative(hwnd, rx, ry, duration=duration)
                send_json(conn, {"status": "ok"})

            elif cmd == "drag":
                last_screenshot_binding = None
                hwnd = _resolve_window(window_title, hwnd)
                drag_window_relative(
                    hwnd,
                    int(msg["x1"]),
                    int(msg["y1"]),
                    int(msg["x2"]),
                    int(msg["y2"]),
                    duration=float(msg.get("duration", 0.4)),
                    button=msg.get("button", "left"),
                )
                send_json(conn, {"status": "ok"})

            elif cmd == "key":
                last_screenshot_binding = None
                hwnd = _resolve_window(window_title, hwnd)
                key_press_window_guarded(
                    hwnd,
                    msg["key"],
                    modifiers=msg.get("modifiers"),
                )
                send_json(conn, {"status": "ok"})

            elif cmd == "window_info":
                hwnd = _resolve_window(window_title, hwnd)
                send_json(conn, get_window_info(hwnd))

            elif cmd == "list_windows":
                title_filter = msg.get("title") if isinstance(msg.get("title"), str) else window_title
                send_json(conn, {"status": "ok", "windows": list_windows(title_filter, include_offscreen=True)})

            elif cmd == "quit":
                send_json(conn, {"status": "bye"})
                break

            else:
                send_json(conn, {"status": "error", "message": f"Unknown command: {cmd}"})

        except Exception as exc:
            payload = {"status": "error", "message": str(exc)}
            if isinstance(exc, CaptureSanityError):
                payload["sanity_reason"] = exc.reason
                payload["mean"] = exc.mean
                payload["std"] = exc.std
                if exc.density is not None:
                    payload["density"] = exc.density
                payload["hwnd"] = hwnd
            send_json(conn, payload)


def _default_auth_token_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is required to locate the bridge auth token")
    return Path(local_app_data) / "SanmouBridge" / "bridge.token"


def _create_listen_socket(port: int) -> socket.socket:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
    if exclusive is None:
        server_socket.close()
        raise RuntimeError("Windows SO_EXCLUSIVEADDRUSE is required for the bridge listener")
    try:
        server_socket.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        server_socket.bind((BRIDGE_LISTEN_HOST, port))
        server_socket.listen(1)
    except BaseException:
        server_socket.close()
        raise
    return server_socket


def main() -> None:
    _enable_physical_pixel_coordinates()
    parser = argparse.ArgumentParser(description="Windows bridge server for game automation.")
    parser.add_argument("--port", type=int, default=9877, help="TCP port to listen on.")
    parser.add_argument("--window", default="三国：谋定天下", help="Game window title substring.")
    parser.add_argument(
        "--capture-backend",
        choices=("auto", "wgc", "dxgi"),
        default="auto",
        help="Window capture backend. auto tries WGC first, then DXGI desktop duplication.",
    )
    parser.add_argument(
        "--auth-token-file",
        help="Path to a 32-byte hex token file. Defaults to %LOCALAPPDATA%\\SanmouBridge\\bridge.token.",
    )
    args = parser.parse_args()

    if bool(ctypes.windll.shell32.IsUserAnAdmin()):
        parser.error(
            "the Python bridge must run without elevation; use the allowlisted controller for high-integrity input"
        )
    token_path = (
        Path(args.auth_token_file).expanduser().resolve()
        if args.auth_token_file
        else _default_auth_token_path()
    )
    auth_token = _load_auth_token(token_path)
    sock = _create_listen_socket(args.port)

    print(f"Bridge server listening on {BRIDGE_LISTEN_HOST}:{args.port}")
    print(f"Target window: {args.window}")
    print(f"Capture backend: {args.capture_backend}")

    try:
        while True:
            print("Waiting for agent connection...")
            conn, addr = sock.accept()
            print(f"Agent connected from {addr}")
            try:
                handle_client(
                    conn,
                    args.window,
                    args.capture_backend,
                    auth_token=auth_token,
                )
            except Exception as exc:
                print(f"Session error: {exc}", file=sys.stderr)
            finally:
                conn.close()
                print("Agent disconnected.")
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
