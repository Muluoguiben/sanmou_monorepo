"""Read-only Windows window capture primitives.

This module binds WGC or DXGI pixels to an exact HWND geometry and validates
the resulting frame.  It intentionally has no transport server and no input
control path.  Callers must present a visible, non-minimized window; capture
never restores, foregrounds, moves, or otherwise mutates the target window.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from io import BytesIO
import sys
import time
from typing import Any

try:
    import dxcam
    import win32gui
    import win32process
    from PIL import Image, ImageStat
except ImportError as exc:
    print(f"Missing dependency: {exc}", file=sys.stderr)
    print(
        "Install with: pip install dxcam opencv-python pywin32 Pillow windows-capture",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from windows_capture import WindowsCapture
except ImportError:
    WindowsCapture = None  # type: ignore[assignment]


MIN_WINDOW_DIM = 20
MIN_SCREENSHOT_DIM = 48
MAX_UNIFORM_PIXEL_RATIO = 0.985
MIN_SCREENSHOT_MEAN = 1.0
MIN_SCREENSHOT_STD = 1.0
CAPTURE_GEOMETRY_VERSION = 1


class CaptureSanityError(RuntimeError):
    """Raised when a captured image is considered unusable."""

    reason: str
    mean: float
    std: float
    density: float | None

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        mean: float = 0.0,
        std: float = 0.0,
        density: float | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.mean = mean
        self.std = std
        self.density = density


def _rect_payload(hwnd: int) -> dict[str, Any]:
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    usable_reason = _usable_rect_reason((left, top, right, bottom), hwnd)
    return {
        "hwnd": hwnd,
        "title": win32gui.GetWindowText(hwnd),
        "pid": pid,
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": width,
        "height": height,
        "visible": bool(win32gui.IsWindowVisible(hwnd)),
        "iconic": bool(win32gui.IsIconic(hwnd)),
        "offscreen": left <= -10000 or top <= -10000,
        "usable": usable_reason == "ok",
        "usable_reason": usable_reason,
    }


def _window_geometry_identity(hwnd: int) -> dict[str, int]:
    """Return the exact outer physical-pixel window identity."""
    info = _rect_payload(hwnd)
    if (
        info.get("usable") is not True
        or info.get("visible") is not True
        or info.get("iconic") is not False
        or info.get("offscreen") is not False
    ):
        raise RuntimeError("capture target window is not visible and usable")
    value = {
        "hwnd": hwnd,
        "pid": info["pid"],
        **{
            key: info[key]
            for key in ("left", "top", "right", "bottom", "width", "height")
        },
    }
    _validate_outer_window_identity(value)
    return value


def _screen_rect_payload(rect: tuple[int, int, int, int]) -> dict[str, int]:
    left, top, right, bottom = rect
    return {
        "left": left,
        "top": top,
        "right": right,
        "bottom": bottom,
        "width": right - left,
        "height": bottom - top,
    }


def _dwm_extended_frame_bounds(hwnd: int) -> tuple[int, int, int, int]:
    """Read non-client extended frame bounds in physical desktop pixels."""

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    rect = RECT()
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
    except (AttributeError, OSError) as exc:
        raise RuntimeError("DWM extended frame bounds are unavailable") from exc
    get_attribute = dwmapi.DwmGetWindowAttribute
    get_attribute.argtypes = [
        wintypes.HWND,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    get_attribute.restype = ctypes.c_long
    result = get_attribute(
        wintypes.HWND(hwnd),
        wintypes.DWORD(9),
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if result != 0:
        raise RuntimeError(
            "DwmGetWindowAttribute(DWMWA_EXTENDED_FRAME_BOUNDS) failed: "
            f"0x{result & 0xFFFFFFFF:08x}"
        )
    value = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    _validate_screen_rect(
        _screen_rect_payload(value), name="DWM extended frame bounds"
    )
    return value


def _build_capture_geometry(
    *,
    backend: str,
    outer_window: dict[str, int],
    capture_rect: tuple[int, int, int, int],
    frame_size: tuple[int, int],
) -> dict[str, Any]:
    geometry = {
        "schema_version": CAPTURE_GEOMETRY_VERSION,
        "capture_backend": backend,
        "outer_window": dict(outer_window),
        "capture_rect": _screen_rect_payload(capture_rect),
        "capture_origin": {"x": capture_rect[0], "y": capture_rect[1]},
        "frame_size": [frame_size[0], frame_size[1]],
    }
    _validate_capture_geometry(geometry)
    return geometry


def _wgc_capture_geometry(
    *,
    outer_window: dict[str, int],
    dwm_bounds: tuple[int, int, int, int],
    frame_size: tuple[int, int],
) -> dict[str, Any]:
    """Bind WGC pixels only when they exactly match DWM frame bounds."""
    dwm = _screen_rect_payload(dwm_bounds)
    if frame_size != (dwm["width"], dwm["height"]):
        raise RuntimeError(
            "WGC frame size cannot be uniquely bound to DWM extended frame bounds: "
            f"frame={frame_size} dwm={(dwm['width'], dwm['height'])}"
        )
    return _build_capture_geometry(
        backend="wgc",
        outer_window=outer_window,
        capture_rect=dwm_bounds,
        frame_size=frame_size,
    )


def _dxgi_clamped_capture_rect(
    outer_window: dict[str, int],
    *,
    output_width: int,
    output_height: int,
) -> tuple[int, int, int, int]:
    if not _plain_positive_int(output_width) or not _plain_positive_int(
        output_height
    ):
        raise RuntimeError("DXGI output geometry is invalid")
    left = max(0, outer_window["left"])
    top = max(0, outer_window["top"])
    right = min(output_width, outer_window["right"])
    bottom = min(output_height, outer_window["bottom"])
    if right <= left or bottom <= top:
        raise RuntimeError(
            f"Invalid clamped DXGI region: ({left},{top},{right},{bottom})"
        )
    return left, top, right, bottom


def _validate_capture_geometry(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "capture_backend",
        "outer_window",
        "capture_rect",
        "capture_origin",
        "frame_size",
    }:
        raise RuntimeError("capture geometry is missing required fields")
    if value.get("schema_version") != CAPTURE_GEOMETRY_VERSION:
        raise RuntimeError("capture geometry schema is unsupported")
    if value.get("capture_backend") not in {"wgc", "dxgi"}:
        raise RuntimeError("capture geometry backend is not concrete")
    outer = value.get("outer_window")
    _validate_outer_window_identity(outer)
    rect = value.get("capture_rect")
    _validate_screen_rect(rect, name="capture rectangle")
    origin = value.get("capture_origin")
    if (
        not isinstance(origin, dict)
        or set(origin) != {"x", "y"}
        or any(not _plain_int(origin.get(key)) for key in ("x", "y"))
        or origin != {"x": rect["left"], "y": rect["top"]}
    ):
        raise RuntimeError("capture geometry origin is invalid")
    frame_size = value.get("frame_size")
    if (
        not isinstance(frame_size, (list, tuple))
        or len(frame_size) != 2
        or any(not _plain_positive_int(item) for item in frame_size)
        or tuple(frame_size) != (rect["width"], rect["height"])
    ):
        raise RuntimeError("capture geometry frame size is invalid")
    if not (
        outer["left"] <= rect["left"] < rect["right"] <= outer["right"]
        and outer["top"] <= rect["top"] < rect["bottom"] <= outer["bottom"]
    ):
        raise RuntimeError("capture rectangle is outside the outer window")
    return value


def _validate_outer_window_identity(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {
        "hwnd",
        "pid",
        "left",
        "top",
        "right",
        "bottom",
        "width",
        "height",
    }:
        raise RuntimeError("outer window identity is invalid")
    if not _plain_positive_int(value.get("hwnd")) or not _plain_positive_int(
        value.get("pid")
    ):
        raise RuntimeError("outer window identity is invalid")
    _validate_screen_rect(value, name="outer window rectangle")


def _validate_screen_rect(value: Any, *, name: str) -> None:
    if not isinstance(value, dict):
        raise RuntimeError(f"{name} is invalid")
    required = {"left", "top", "right", "bottom", "width", "height"}
    if not required.issubset(value) or any(
        not _plain_int(value.get(key)) for key in required
    ):
        raise RuntimeError(f"{name} is invalid")
    if (
        value["right"] <= value["left"]
        or value["bottom"] <= value["top"]
        or value["right"] - value["left"] != value["width"]
        or value["bottom"] - value["top"] != value["height"]
    ):
        raise RuntimeError(f"{name} is invalid")


def _plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _plain_positive_int(value: Any) -> bool:
    return _plain_int(value) and value > 0


def _enable_physical_pixel_coordinates() -> None:
    """Make all Win32 rectangles use physical pixels."""
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
    except (AttributeError, OSError) as exc:
        raise RuntimeError("Win32 DPI-awareness APIs are unavailable") from exc
    setter = getattr(user32, "SetProcessDpiAwarenessContext", None)
    if setter is None:
        raise RuntimeError("per-monitor DPI awareness v2 is unavailable")
    setter.argtypes = [ctypes.c_void_p]
    setter.restype = wintypes.BOOL
    if not setter(ctypes.c_void_p(-4)):
        error = ctypes.get_last_error()
        getter = getattr(user32, "GetThreadDpiAwarenessContext", None)
        awareness = getattr(user32, "GetAwarenessFromDpiAwarenessContext", None)
        if getter is not None:
            getter.restype = ctypes.c_void_p
        if awareness is not None:
            awareness.argtypes = [ctypes.c_void_p]
            awareness.restype = ctypes.c_int
        if (
            error != 5
            or getter is None
            or awareness is None
            or awareness(getter()) != 2
        ):
            raise RuntimeError(
                "bridge could not establish physical-pixel DPI awareness"
            )


def _usable_rect_reason(
    rect: tuple[int, int, int, int], hwnd: int | None = None
) -> str:
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


def capture_window_dxgi(hwnd: int) -> tuple[bytes, dict[str, Any]]:
    """Capture a visible HWND using DXGI Desktop Duplication."""
    outer_before = _window_geometry_identity(hwnd)
    cam = dxcam.create()
    left, top, right, bottom = _dxgi_clamped_capture_rect(
        outer_before,
        output_width=cam.width,
        output_height=cam.height,
    )

    frame = None
    for _ in range(10):
        frame = cam.grab(region=(left, top, right, bottom))
        if frame is not None and frame.mean() > 1.0:
            break
        time.sleep(0.1)
    del cam
    if frame is None:
        raise RuntimeError("dxcam.grab() returned None after retries")

    image = Image.fromarray(frame)
    expected_size = (right - left, bottom - top)
    if image.size != expected_size:
        raise RuntimeError(
            f"DXGI frame size {image.size} does not match clamped region {expected_size}"
        )
    outer_after = _window_geometry_identity(hwnd)
    if outer_after != outer_before:
        raise RuntimeError("outer window geometry changed during DXGI capture")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), _build_capture_geometry(
        backend="dxgi",
        outer_window=outer_before,
        capture_rect=(left, top, right, bottom),
        frame_size=image.size,
    )


def capture_window_wgc(
    hwnd: int,
    timeout_seconds: float = 5.0,
) -> tuple[bytes, dict[str, Any]]:
    """Capture a visible HWND through Windows Graphics Capture."""
    if WindowsCapture is None:
        raise RuntimeError(
            "windows-capture is not installed; run: python -m pip install windows-capture"
        )
    outer_before = _window_geometry_identity(hwnd)
    dwm_before = _dwm_extended_frame_bounds(hwnd)

    frames: list[tuple[bytes, tuple[int, int]]] = []
    capture = WindowsCapture(
        cursor_capture=False, draw_border=False, window_hwnd=hwnd
    )

    @capture.event
    def on_frame_arrived(frame: Any, control: Any) -> None:
        if (
            frame.width > MIN_WINDOW_DIM
            and frame.height > MIN_WINDOW_DIM
            and frame.frame_buffer.mean() > 1.0
        ):
            array = frame.frame_buffer
            if array.shape[2] == 4:
                image = Image.fromarray(array[:, :, [2, 1, 0, 3]], "RGBA")
            else:
                image = Image.fromarray(array[:, :, ::-1], "RGB")
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            frames.append((buffer.getvalue(), image.size))
        control.stop()

    @capture.event
    def on_closed() -> None:
        return None

    control = capture.start_free_threaded()
    deadline = time.monotonic() + timeout_seconds
    while not frames and time.monotonic() < deadline:
        time.sleep(0.05)
    control.stop()
    if not frames:
        raise RuntimeError(
            "WGC capture timed out or closed without a usable frame after "
            f"{timeout_seconds}s"
        )
    outer_after = _window_geometry_identity(hwnd)
    dwm_after = _dwm_extended_frame_bounds(hwnd)
    if outer_after != outer_before:
        raise RuntimeError("outer window geometry changed during WGC capture")
    if dwm_after != dwm_before:
        raise RuntimeError("DWM extended frame bounds changed during WGC capture")
    frame_bytes, frame_size = frames[0]
    return frame_bytes, _wgc_capture_geometry(
        outer_window=outer_before,
        dwm_bounds=dwm_before,
        frame_size=frame_size,
    )


def _validate_capture_sanity(png_bytes: bytes, *, hwnd: int) -> None:
    with Image.open(BytesIO(png_bytes)) as image:
        width, height = image.size
        if width < MIN_SCREENSHOT_DIM or height < MIN_SCREENSHOT_DIM:
            raise CaptureSanityError(
                "too_small",
                f"Invalid capture: frame too small {width}x{height} for hwnd={hwnd}",
            )

        gray = image.convert("L")
        stats = ImageStat.Stat(gray)
        mean = stats.mean[0] if stats.mean else 0.0
        std = stats.stddev[0] if stats.stddev else 0.0
        if mean < MIN_SCREENSHOT_MEAN:
            raise CaptureSanityError(
                "near_black",
                f"Invalid capture: near-black frame mean={mean:.2f} for hwnd={hwnd}",
                mean=mean,
                std=std,
            )
        if std < MIN_SCREENSHOT_STD:
            raise CaptureSanityError(
                "near_uniform",
                f"Invalid capture: near-uniform frame std={std:.2f} for hwnd={hwnd}",
                mean=mean,
                std=std,
            )

        histogram = gray.histogram()
        if histogram:
            density = max(histogram) / float(width * height)
            if density > MAX_UNIFORM_PIXEL_RATIO:
                raise CaptureSanityError(
                    "saturated",
                    "Invalid capture: saturated single-color frame "
                    f"ratio={density:.3f} for hwnd={hwnd}",
                    mean=mean,
                    std=std,
                    density=density,
                )


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
