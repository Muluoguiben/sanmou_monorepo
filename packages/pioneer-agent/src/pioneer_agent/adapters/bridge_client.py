"""WSL2-side client for the Windows bridge server.

Communicates with the bridge server via a python.exe subprocess proxy,
bypassing WSL2 network routing issues (e.g. WireGuard, NAT).
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from typing import Any


_PROXY_SCRIPT = Path(__file__).with_name("bridge_proxy.py")


def _to_windows_path(linux_path: Path) -> str:
    """Convert a WSL Linux path to a \\\\wsl$\\ UNC path for python.exe."""
    return f"\\\\wsl$\\Ubuntu{linux_path}"


class BridgeClient:
    """Client that talks to the Windows bridge server via python.exe proxy."""

    def __init__(self, port: int = 9877) -> None:
        self.port = port
        self._proc: subprocess.Popen[str] | None = None

    def connect(self) -> None:
        """Start the proxy subprocess and wait for it to be ready."""
        if self._proc is not None and self._proc.poll() is None:
            return
        win_script = _to_windows_path(_PROXY_SCRIPT)
        self._proc = subprocess.Popen(
            ["python.exe", win_script, str(self.port)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/mnt/c",
        )
        ready = self._read_line()
        if ready.get("status") != "proxy_ready":
            raise ConnectionError(f"Proxy failed to start: {ready}")

    def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._send({"cmd": "quit"})
                self._read_line()
            except Exception:
                pass
            self._proc.terminate()
            self._proc.wait(timeout=5)
        self._proc = None

    def ping(self) -> bool:
        """Check if the bridge server is reachable."""
        try:
            self.connect()
            self._send({"cmd": "ping"})
            resp = self._read_line()
            return resp.get("status") == "ok"
        except Exception:
            return False

    def screenshot(self, save_path: Path | str | None = None) -> bytes:
        """Capture a screenshot of the game window. Returns PNG bytes."""
        self.connect()
        self._send({"cmd": "screenshot"})
        resp = self._read_line()
        if resp.get("status") != "ok" or "data_b64" not in resp:
            raise RuntimeError(resp.get("message") or f"Screenshot failed: {resp}")
        png_bytes = base64.b64decode(resp["data_b64"])
        if save_path is not None:
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png_bytes)
        return png_bytes

    def click(self, x: int, y: int, button: str = "left") -> dict[str, Any]:
        """Send a click at window-relative coordinates."""
        self.connect()
        self._send({"cmd": "click", "x": x, "y": y, "button": button})
        return self._read_line()

    def window_info(self) -> dict[str, Any]:
        """Get game window geometry info."""
        self.connect()
        self._send({"cmd": "window_info"})
        return self._read_line()

    def __enter__(self) -> BridgeClient:
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- Internal ---

    def _send(self, payload: dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _read_line(self) -> dict[str, Any]:
        assert self._proc is not None and self._proc.stdout is not None
        line = self._proc.stdout.readline()
        if not line:
            raise ConnectionError("Proxy process exited unexpectedly")
        return json.loads(line)
