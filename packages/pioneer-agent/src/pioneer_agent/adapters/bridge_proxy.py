"""Proxy script that runs on Windows python.exe.

Connects to the bridge server via localhost and relays commands from
stdin/stdout, allowing WSL2 to bypass network routing issues (e.g. WireGuard).

Protocol: one JSON line per request on stdin, one JSON line per response on stdout.
Current servers return screenshots as a JSON envelope containing base64 pixels,
frame SHA-256, and capture geometry; the proxy forwards that envelope unchanged.
Legacy raw-PNG responses are still translated to base64 so BridgeClient can emit
an explicit upgrade-required error instead of silently losing geometry.

Window un-minimization is done server-side via SendMessage(WM_SYSCOMMAND,
SC_RESTORE), which has no foreground-lock restriction. The proxy does not
manipulate windows.
"""

import base64
import json
import os
import socket
import struct
import sys
from pathlib import Path


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_MAX_PROTOCOL_REQUEST_BYTES = 1_048_576
_MAX_PROTOCOL_RESPONSE_BYTES = 67_108_864
_AUTH_TOKEN_HEX_LENGTH = 64


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
    if len(body) < 2 or len(body) > _MAX_PROTOCOL_REQUEST_BYTES:
        raise ValueError("invalid bridge protocol request length")
    sock.sendall(struct.pack(">I", len(body)) + body)


def recv_frame(sock):
    raw_len = recv_exact(sock, 4)
    msg_len = struct.unpack(">I", raw_len)[0]
    if msg_len < 2 or msg_len > _MAX_PROTOCOL_RESPONSE_BYTES:
        raise ConnectionError("invalid bridge protocol response length")
    return recv_exact(sock, msg_len)


def _auth_token_path() -> Path:
    if len(sys.argv) > 2:
        return Path(sys.argv[2])
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("LOCALAPPDATA is required to locate the bridge auth token")
    return Path(local_app_data) / "SanmouBridge" / "bridge.token"


def _load_auth_token() -> str:
    path = _auth_token_path()
    try:
        token = path.read_text(encoding="utf-8-sig").strip().lower()
    except OSError as exc:
        raise RuntimeError(f"unable to read bridge auth token: {path}") from exc
    if len(token) != _AUTH_TOKEN_HEX_LENGTH or any(
        char not in "0123456789abcdef" for char in token
    ):
        raise RuntimeError("bridge auth token must be exactly 32 random bytes encoded as hex")
    return token


def main():
    # Force UTF-8 on stdio. Windows python.exe otherwise uses the system
    # ANSI codepage (cp936 on zh-CN installs), which garbles Chinese window
    # titles and other non-ASCII JSON fields when piped to WSL.
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9877
    try:
        auth_token = _load_auth_token()
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), flush=True)
        sys.exit(1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    try:
        sock.connect(("127.0.0.1", port))
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), flush=True)
        sys.exit(1)

    try:
        send_cmd(sock, {"cmd": "authenticate", "token": auth_token})
        auth_response = json.loads(recv_frame(sock).decode("utf-8"))
        if auth_response.get("status") != "ok" or auth_response.get("authenticated") is not True:
            raise PermissionError(auth_response.get("message") or "bridge authentication failed")
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), flush=True)
        sock.close()
        sys.exit(1)

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
            send_cmd(sock, req)
            data = recv_frame(sock)
            if cmd == "screenshot" and data.startswith(_PNG_MAGIC):
                print(json.dumps({
                    "status": "ok",
                    "data_b64": base64.b64encode(data).decode("ascii"),
                    "size": len(data),
                }), flush=True)
            else:
                # Either a JSON control response, or a server-side error
                # returned in place of PNG bytes.
                print(data.decode("utf-8"), flush=True)
        except Exception as exc:
            print(json.dumps({"status": "error", "message": str(exc)}), flush=True)

        if cmd == "quit":
            break

    sock.close()


if __name__ == "__main__":
    main()
