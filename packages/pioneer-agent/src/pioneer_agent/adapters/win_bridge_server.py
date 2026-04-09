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
    import pyautogui
    import win32gui
    from PIL import Image
except ImportError as exc:
    print(f"Missing dependency: {exc}", file=sys.stderr)
    print("Install with: pip install dxcam opencv-python-headless pyautogui pywin32 Pillow", file=sys.stderr)
    sys.exit(1)



def find_window(title_substring: str) -> int:
    """Find a window handle by partial title match."""
    result = []

    def callback(hwnd: int, _: Any) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_substring in title:
                result.append(hwnd)
        return True

    win32gui.EnumWindows(callback, None)
    if not result:
        raise RuntimeError(f"Window not found: {title_substring}")
    return result[0]


def capture_window(hwnd: int) -> bytes:
    """Capture a screenshot of the game window using DXGI Desktop Duplication (dxcam).

    This works for DirectX/hardware-accelerated windows where GDI-based
    capture (mss, BitBlt, PrintWindow) returns black frames.
    Forces the window to foreground before capture.
    """
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


def click_at(x: int, y: int, button: str = "left") -> None:
    """Click at absolute screen coordinates."""
    pyautogui.click(x, y, button=button)


def click_window_relative(hwnd: int, rx: int, ry: int, button: str = "left") -> None:
    """Click at coordinates relative to the window's top-left corner."""
    rect = win32gui.GetWindowRect(hwnd)
    abs_x = rect[0] + rx
    abs_y = rect[1] + ry
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(0.05)
    pyautogui.click(abs_x, abs_y, button=button)


def get_window_info(hwnd: int) -> dict[str, Any]:
    """Return basic window geometry info."""
    rect = win32gui.GetWindowRect(hwnd)
    left, top, right, bottom = rect
    return {
        "hwnd": hwnd,
        "title": win32gui.GetWindowText(hwnd),
        "left": left,
        "top": top,
        "width": right - left,
        "height": bottom - top,
    }


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

def handle_client(conn: socket.socket, window_title: str) -> None:
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
                if hwnd is None or not win32gui.IsWindow(hwnd):
                    hwnd = find_window(window_title)
                png_bytes = capture_window(hwnd)
                send_binary(conn, png_bytes)

            elif cmd == "click":
                if hwnd is None or not win32gui.IsWindow(hwnd):
                    hwnd = find_window(window_title)
                rx, ry = int(msg["x"]), int(msg["y"])
                button = msg.get("button", "left")
                click_window_relative(hwnd, rx, ry, button)
                send_json(conn, {"status": "ok"})

            elif cmd == "window_info":
                if hwnd is None or not win32gui.IsWindow(hwnd):
                    hwnd = find_window(window_title)
                send_json(conn, get_window_info(hwnd))

            elif cmd == "quit":
                send_json(conn, {"status": "bye"})
                break

            else:
                send_json(conn, {"status": "error", "message": f"Unknown command: {cmd}"})

        except Exception as exc:
            send_json(conn, {"status": "error", "message": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description="Windows bridge server for game automation.")
    parser.add_argument("--port", type=int, default=9877, help="TCP port to listen on.")
    parser.add_argument("--window", default="三国：谋定天下", help="Game window title substring.")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", args.port))
    sock.listen(1)

    print(f"Bridge server listening on 0.0.0.0:{args.port}")
    print(f"Target window: {args.window}")

    try:
        while True:
            print("Waiting for agent connection...")
            conn, addr = sock.accept()
            print(f"Agent connected from {addr}")
            try:
                handle_client(conn, args.window)
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
