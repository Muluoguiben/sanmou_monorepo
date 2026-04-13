"""Proxy script that runs on Windows python.exe.

Connects to the bridge server via localhost and relays commands from
stdin/stdout, allowing WSL2 to bypass network routing issues (e.g. WireGuard).

Protocol: one JSON line per request on stdin, one JSON line per response on stdout.
Screenshot binary data is base64-encoded in the response — unless the server
returned a JSON error (no PNG magic), in which case the error is parsed and
forwarded unchanged so the caller sees a proper error response.

Window un-minimization is done server-side via SendMessage(WM_SYSCOMMAND,
SC_RESTORE), which has no foreground-lock restriction. The proxy does not
manipulate windows.
"""

import base64
import json
import socket
import struct
import sys


_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


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


def recv_frame(sock):
    raw_len = recv_exact(sock, 4)
    msg_len = struct.unpack(">I", raw_len)[0]
    return recv_exact(sock, msg_len)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9877
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    try:
        sock.connect(("127.0.0.1", port))
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), flush=True)
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
