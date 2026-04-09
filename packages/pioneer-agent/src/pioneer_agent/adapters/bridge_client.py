"""WSL2-side client for the Windows bridge server.

Provides screenshot capture and input injection to the game window
via TCP communication with the Windows-side bridge server.
"""

from __future__ import annotations

import json
import socket
import struct
import subprocess
from pathlib import Path
from typing import Any


class BridgeClient:
    """TCP client that talks to the Windows bridge server."""

    def __init__(self, host: str | None = None, port: int = 9877) -> None:
        self.host = host or self._detect_windows_host()
        self.port = port
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        """Establish connection to the bridge server."""
        if self._sock is not None:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((self.host, self.port))
        self._sock = sock

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._send_json({"cmd": "quit"})
                self._recv_json()
            except Exception:
                pass
            self._sock.close()
            self._sock = None

    def ping(self) -> bool:
        """Check if the bridge server is reachable."""
        try:
            self.connect()
            self._send_json({"cmd": "ping"})
            resp = self._recv_json()
            return resp.get("status") == "ok"
        except Exception:
            return False

    def screenshot(self, save_path: Path | str | None = None) -> bytes:
        """Capture a screenshot of the game window. Returns PNG bytes."""
        self.connect()
        self._send_json({"cmd": "screenshot"})
        png_bytes = self._recv_binary()
        if save_path is not None:
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png_bytes)
        return png_bytes

    def click(self, x: int, y: int, button: str = "left") -> dict[str, Any]:
        """Send a click at window-relative coordinates."""
        self.connect()
        self._send_json({"cmd": "click", "x": x, "y": y, "button": button})
        return self._recv_json()

    def window_info(self) -> dict[str, Any]:
        """Get game window geometry info."""
        self.connect()
        self._send_json({"cmd": "window_info"})
        return self._recv_json()

    def __enter__(self) -> BridgeClient:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- Internal protocol ---

    def _send_json(self, payload: dict[str, Any]) -> None:
        assert self._sock is not None
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._sock.sendall(struct.pack(">I", len(body)) + body)

    def _recv_json(self) -> dict[str, Any]:
        data = self._recv_binary()
        return json.loads(data)

    def _recv_binary(self) -> bytes:
        assert self._sock is not None
        raw_len = self._recv_exact(4)
        msg_len = struct.unpack(">I", raw_len)[0]
        return self._recv_exact(msg_len)

    def _recv_exact(self, n: int) -> bytes:
        assert self._sock is not None
        buf = bytearray()
        while len(buf) < n:
            chunk = self._sock.recv(min(n - len(buf), 65536))
            if not chunk:
                raise ConnectionError("Bridge server disconnected")
            buf.extend(chunk)
        return bytes(buf)

    @staticmethod
    def _detect_windows_host() -> str:
        """Auto-detect the Windows host IP from WSL2."""
        try:
            resolv = Path("/etc/resolv.conf").read_text()
            for line in resolv.splitlines():
                if line.strip().startswith("nameserver"):
                    return line.split()[1]
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=5,
            )
            for token in result.stdout.split():
                if token.count(".") == 3:
                    return token
        except Exception:
            pass
        return "127.0.0.1"
