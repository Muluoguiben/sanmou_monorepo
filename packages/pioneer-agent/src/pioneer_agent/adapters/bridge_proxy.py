"""Windows stdin/stdout relay for authenticated capture protocol v2.

Any timeout, partial frame, mismatch or server error closes the socket and
ends this proxy. A caller must create a new proxy for the next observation.
"""
import json
import os
import socket
import struct
import sys
import time

PROTOCOL_VERSION = 2
MAX_RESPONSE_BYTES = 48 * 1024 * 1024
READ_ONLY_COMMANDS = frozenset({"ping", "capabilities", "screenshot", "window_info", "list_windows", "quit"})


def recv_exact(sock, n, *, deadline=None):
    buf = bytearray()
    while len(buf) < n:
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("capture response deadline exceeded")
            sock.settimeout(remaining)
        chunk = sock.recv(min(n - len(buf), 65536))
        if not chunk:
            raise ConnectionError("Bridge server disconnected")
        buf.extend(chunk)
    return bytes(buf)


def send_cmd(sock, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(body) > 65536:
        raise ValueError("capture request too large")
    sock.sendall(struct.pack(">I", len(body)) + body)


def recv_frame(sock):
    deadline = time.monotonic() + 10
    raw_len = recv_exact(sock, 4, deadline=deadline)
    msg_len = struct.unpack(">I", raw_len)[0]
    if not 0 < msg_len <= MAX_RESPONSE_BYTES:
        raise ValueError("invalid capture response length")
    return recv_exact(sock, msg_len, deadline=deadline)


def exchange(sock, request, auth_token):
    """One request, one bound JSON response; invalid streams are never reused."""
    try:
        if (
            not isinstance(request, dict)
            or request.get("cmd") not in READ_ONLY_COMMANDS
            or request.get("protocol_version") != PROTOCOL_VERSION
            or not isinstance(request.get("request_id"), str)
            or len(request["request_id"]) != 32
            or any(c not in "0123456789abcdef" for c in request["request_id"])
        ):
            raise ValueError("invalid capture-only request")
        sock.settimeout(10)
        send_cmd(sock, {**request, "auth_token": auth_token})
        response = json.loads(recv_frame(sock))
        if (
            not isinstance(response, dict)
            or response.get("protocol_version") != PROTOCOL_VERSION
            or response.get("request_id") != request["request_id"]
            or response.get("status") not in {"ok", "bye"}
        ):
            raise ValueError("invalid capture response binding")
        return response
    except Exception:
        sock.close()
        raise


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass
    token = os.environ.get("SANMOU_CAPTURE_TOKEN", "")
    if not (32 <= len(token) <= 256 and token.isascii() and not any(c.isspace() for c in token)):
        print(json.dumps({"status": "error", "message": "capture authentication is not configured"}), flush=True)
        return 1
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9877
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    try:
        sock.connect(("127.0.0.1", port))
        print(json.dumps({"status": "proxy_ready", "protocol_version": PROTOCOL_VERSION}), flush=True)
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                request = json.loads(line)
                response = exchange(sock, request, token)
                print(json.dumps(response, ensure_ascii=False), flush=True)
                if request["cmd"] == "quit":
                    break
            except Exception:
                print(json.dumps({"status": "error", "message": "capture transport invalidated"}), flush=True)
                return 1
    except Exception:
        print(json.dumps({"status": "error", "message": "capture connection failed"}), flush=True)
        return 1
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
