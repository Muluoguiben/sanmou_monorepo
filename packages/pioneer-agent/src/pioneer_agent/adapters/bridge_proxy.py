"""Proxy script that runs on Windows python.exe.

Connects to the bridge server via localhost and relays commands from
stdin/stdout, allowing WSL2 to bypass network routing issues (e.g. WireGuard).

Protocol: one JSON line per request on stdin, one JSON line per response on stdout.
Screenshot binary data is base64-encoded in the response.
"""

import base64
import ctypes
import json
import socket
import struct
import sys
import time


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(n - len(buf), 65536))
        if not chunk:
            raise ConnectionError("Bridge server disconnected")
        buf.extend(chunk)
    return bytes(buf)


def send_cmd(sock, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    sock.sendall(struct.pack(">I", len(body)) + body)


def recv_response(sock, is_binary=False):
    raw_len = recv_exact(sock, 4)
    msg_len = struct.unpack(">I", raw_len)[0]
    data = recv_exact(sock, msg_len)
    if is_binary:
        return data
    return json.loads(data)


def _focus_game_window(title_sub: str = "三国") -> bool:
    """Bring the game window to the foreground.

    This runs inside the proxy (a short-lived python.exe), which Windows
    allows to call SetForegroundWindow — unlike the long-running server.
    """
    try:
        import win32gui  # noqa: available on Windows python.exe

        result = []
        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                if title_sub in win32gui.GetWindowText(hwnd):
                    result.append(hwnd)
            return True
        win32gui.EnumWindows(cb, None)
        if not result:
            return False
        hwnd = result[0]

        if win32gui.IsIconic(hwnd):
            win32gui.SendMessage(hwnd, 0x0112, 0xF120, 0)  # SC_RESTORE
            time.sleep(0.5)

        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        return True
    except Exception:
        return False


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9877
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    try:
        sock.connect(("127.0.0.1", port))
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), flush=True)
        sys.exit(1)

    # Signal ready
    print(json.dumps({"status": "proxy_ready"}), flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            print(json.dumps({"status": "error", "message": f"Bad JSON: {exc}"}), flush=True)
            continue

        cmd = req.get("cmd", "")
        try:
            if cmd == "screenshot":
                _focus_game_window()
            send_cmd(sock, req)
            if cmd == "screenshot":
                data = recv_response(sock, is_binary=True)
                print(json.dumps({
                    "status": "ok",
                    "data_b64": base64.b64encode(data).decode("ascii"),
                    "size": len(data),
                }), flush=True)
            else:
                resp = recv_response(sock)
                print(json.dumps(resp), flush=True)
        except Exception as exc:
            print(json.dumps({"status": "error", "message": str(exc)}), flush=True)

        if cmd == "quit":
            break

    sock.close()


if __name__ == "__main__":
    main()
