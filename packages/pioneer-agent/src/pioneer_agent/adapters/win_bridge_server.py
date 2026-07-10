"""Windows-side bridge server for game screenshot capture and input injection.

This script runs on the Windows host and exposes a TCP interface for the
WSL2-side agent to capture screenshots and send clicks to the game window.

Usage (from Windows or WSL):
    python win_bridge_server.py [--port 9877] [--window "三国：谋定天下"]
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import time
from typing import Any

from io import BytesIO

try:
    import dxcam
    import win32con
    import win32gui
    import win32process
    from PIL import Image, ImageStat
except ImportError as exc:
    print(f"Missing dependency: {exc}", file=sys.stderr)
    print("Install with: pip install dxcam opencv-python pyautogui pywin32 Pillow windows-capture", file=sys.stderr)
    sys.exit(1)

try:
    from windows_capture import WindowsCapture
except ImportError:
    WindowsCapture = None  # type: ignore[assignment]

pyautogui = None


MIN_WINDOW_DIM = 20
MIN_SCREENSHOT_DIM = 48
MAX_UNIFORM_PIXEL_RATIO = 0.985
MIN_SCREENSHOT_MEAN = 1.0
MIN_SCREENSHOT_STD = 1.0


class CaptureSanityError(RuntimeError):
    """Raised when a captured image is considered unusable by sanity checks."""

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


def _normalize_title(title: str) -> str:
    return title.strip().lower()


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


def capture_window_dxgi(hwnd: int) -> bytes:
    """Capture a screenshot of the game window using DXGI Desktop Duplication (dxcam).

    This works for DirectX/hardware-accelerated windows where GDI-based
    capture (mss, BitBlt, PrintWindow) returns black frames.
    """
    _ensure_window_onscreen(hwnd)
    rect = win32gui.GetWindowRect(hwnd)
    cam = dxcam.create()

    # Clamp to screen bounds
    left = max(0, rect[0])
    top = max(0, rect[1])
    right = min(cam.width, rect[2])
    bottom = min(cam.height, rect[3])
    if right <= left or bottom <= top:
        del cam
        raise RuntimeError(f"Invalid clamped region: ({left},{top},{right},{bottom}) from rect {rect}")

    # Grab with retries — first grab may be stale/None
    frame = None
    for _ in range(10):
        frame = cam.grab(region=(left, top, right, bottom))
        if frame is not None and frame.mean() > 1.0:
            break
        time.sleep(0.1)
    del cam
    if frame is None:
        raise RuntimeError("dxcam.grab() returned None after retries")

    img = Image.fromarray(frame)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def capture_window_wgc(hwnd: int, timeout_seconds: float = 5.0) -> bytes:
    """Capture a target window through Windows Graphics Capture.

    WGC is the preferred backend when the user is actively switching windows:
    it captures the target HWND instead of a screen rectangle, so it is less
    sensitive to foreground occlusion than CopyFromScreen/dxcam region grabs.
    """
    if WindowsCapture is None:
        raise RuntimeError("windows-capture is not installed; run: python -m pip install windows-capture")
    _ensure_window_onscreen(hwnd)

    frame_bytes: list[bytes] = []
    capture = WindowsCapture(cursor_capture=False, draw_border=False, window_hwnd=hwnd)

    @capture.event
    def on_frame_arrived(frame: Any, control: Any) -> None:
        if frame.width > 20 and frame.height > 20 and frame.frame_buffer.mean() > 1.0:
            arr = frame.frame_buffer
            if arr.shape[2] == 4:
                image = Image.fromarray(arr[:, :, [2, 1, 0, 3]], "RGBA")
            else:
                image = Image.fromarray(arr[:, :, ::-1], "RGB")
            buf = BytesIO()
            image.save(buf, format="PNG")
            frame_bytes.append(buf.getvalue())
        control.stop()

    @capture.event
    def on_closed() -> None:
        return None

    control = capture.start_free_threaded()
    deadline = time.monotonic() + timeout_seconds
    while not frame_bytes and time.monotonic() < deadline:
        time.sleep(0.05)
    control.stop()
    if not frame_bytes:
        raise RuntimeError(f"WGC capture timed out or closed without a usable frame after {timeout_seconds}s")
    return frame_bytes[0]


def _validate_capture_sanity(png_bytes: bytes, *, hwnd: int) -> None:
    with Image.open(BytesIO(png_bytes)) as img:
        width, height = img.size
        if width < MIN_SCREENSHOT_DIM or height < MIN_SCREENSHOT_DIM:
            raise CaptureSanityError(
                "too_small",
                f"Invalid capture: frame too small {width}x{height} for hwnd={hwnd}",
                mean=0.0,
                std=0.0,
            )

        gray = img.convert("L")
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
                    f"Invalid capture: saturated single-color frame ratio={density:.3f} for hwnd={hwnd}",
                    mean=mean,
                    std=std,
                    density=density,
                )


def _resolve_window(window_title: str, hwnd: int | None) -> int:
    if hwnd is not None and win32gui.IsWindow(hwnd):
        current = _rect_payload(hwnd)
        if current["usable"] and _normalize_title(current["title"]).find(_normalize_title(window_title)) >= 0:
            return hwnd
    return find_window(window_title)


def capture_window(hwnd: int, backend: str = "auto") -> bytes:
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


def _pyautogui() -> Any:
    global pyautogui
    if pyautogui is None:
        import pyautogui as loaded_pyautogui

        pyautogui = loaded_pyautogui
    return pyautogui


def click_at(x: int, y: int, button: str = "left") -> None:
    """Click at absolute screen coordinates."""
    _pyautogui().click(x, y, button=button)


def click_window_relative(
    hwnd: int,
    rx: int,
    ry: int,
    button: str = "left",
    *,
    expected_window: dict[str, Any] | None = None,
) -> None:
    """Click at coordinates relative to the window's top-left corner."""
    if expected_window is None:
        _ensure_window_onscreen(hwnd)
    else:
        _assert_expected_window(hwnd, expected_window)
        _assert_guarded_relative_point(rx, ry, expected_window)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        if expected_window is not None:
            raise RuntimeError("failed to foreground guarded click target") from exc
    time.sleep(0.05)
    if expected_window is not None:
        _assert_expected_window(hwnd, expected_window)
        if win32gui.GetForegroundWindow() != hwnd:
            raise RuntimeError("guarded click target is not the foreground window")
    rect = win32gui.GetWindowRect(hwnd)
    abs_x = rect[0] + rx
    abs_y = rect[1] + ry
    if expected_window is not None:
        point_window = win32gui.WindowFromPoint((abs_x, abs_y))
        point_root = (
            win32gui.GetAncestor(point_window, win32con.GA_ROOT)
            if point_window
            else None
        )
        if point_root != hwnd:
            raise RuntimeError("guarded click point is covered by another window")
    _pyautogui().click(abs_x, abs_y, button=button)


def _assert_expected_window(hwnd: int, expected: dict[str, Any]) -> None:
    required = ("hwnd", "pid", "width", "height")
    for key in required:
        value = expected.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise RuntimeError(f"invalid expected window {key}")
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
    expected: dict[str, Any],
) -> None:
    if (
        isinstance(rx, bool)
        or not isinstance(rx, int)
        or isinstance(ry, bool)
        or not isinstance(ry, int)
        or rx < 0
        or ry < 0
        or rx >= expected["width"]
        or ry >= expected["height"]
    ):
        raise RuntimeError("guarded click point is outside the observed frame")


def move_window_relative(hwnd: int, rx: int, ry: int, duration: float = 0.0) -> None:
    """Move mouse to window-relative coords. Useful for hover."""
    _ensure_window_onscreen(hwnd)
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
    _ensure_window_onscreen(hwnd)
    rect = win32gui.GetWindowRect(hwnd)
    start = (rect[0] + x1, rect[1] + y1)
    end = (rect[0] + x2, rect[1] + y2)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.05)
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
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        raise RuntimeError("failed to foreground key target") from exc
    time.sleep(0.05)
    if win32gui.GetForegroundWindow() != hwnd:
        raise RuntimeError("key target is not the foreground window")
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
    data = _recv_exact(conn, msg_len)
    return json.loads(data)


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

def handle_client(conn: socket.socket, window_title: str, capture_backend: str) -> None:
    hwnd = None

    while True:
        try:
            msg = recv_msg(conn)
        except ConnectionError:
            break

        cmd = msg.get("cmd", "")

        try:
            if cmd == "ping":
                send_json(conn, {"status": "ok"})

            elif cmd == "screenshot":
                hwnd = _resolve_window(window_title, hwnd)
                png_bytes = capture_window(hwnd, backend=str(msg.get("backend") or capture_backend))
                _validate_capture_sanity(png_bytes, hwnd=hwnd)
                send_binary(conn, png_bytes)

            elif cmd == "click":
                hwnd = _resolve_window(window_title, hwnd)
                rx, ry = int(msg["x"]), int(msg["y"])
                button = msg.get("button", "left")
                expected_window = msg.get("expected_window")
                if expected_window is not None and not isinstance(expected_window, dict):
                    raise RuntimeError("expected_window must be an object")
                click_window_relative(
                    hwnd,
                    rx,
                    ry,
                    button,
                    expected_window=expected_window,
                )
                send_json(conn, {"status": "ok"})

            elif cmd == "move":
                hwnd = _resolve_window(window_title, hwnd)
                rx, ry = int(msg["x"]), int(msg["y"])
                duration = float(msg.get("duration", 0.0))
                move_window_relative(hwnd, rx, ry, duration=duration)
                send_json(conn, {"status": "ok"})

            elif cmd == "drag":
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Windows bridge server for game automation.")
    parser.add_argument("--port", type=int, default=9877, help="TCP port to listen on.")
    parser.add_argument("--window", default="三国：谋定天下", help="Game window title substring.")
    parser.add_argument(
        "--capture-backend",
        choices=("auto", "wgc", "dxgi"),
        default="auto",
        help="Window capture backend. auto tries WGC first, then DXGI desktop duplication.",
    )
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", args.port))
    sock.listen(1)

    print(f"Bridge server listening on 0.0.0.0:{args.port}")
    print(f"Target window: {args.window}")
    print(f"Capture backend: {args.capture_backend}")

    try:
        while True:
            print("Waiting for agent connection...")
            conn, addr = sock.accept()
            print(f"Agent connected from {addr}")
            try:
                handle_client(conn, args.window, args.capture_backend)
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
