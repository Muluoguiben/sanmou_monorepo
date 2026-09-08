"""Capture-only transport with request-bound responses and fail-closed teardown."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path, PureWindowsPath
from typing import Any

from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError
from pioneer_agent.core.models import CaptureGeometry

PROTOCOL_VERSION = 2
_PROXY_SCRIPT = Path(__file__).with_name("bridge_proxy.py")


@dataclass(frozen=True)
class BridgeScreenshot:
    png: bytes
    frame_sha256: str
    capture_geometry: CaptureGeometry
    captured_at: datetime | None = None
    request_id: str | None = None


def parse_capture_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise RuntimeError("bridge omitted server capture time; update and restart the Windows bridge server")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("naive timestamp")
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise RuntimeError("bridge returned invalid capture time") from exc


def _to_windows_path(path: Path) -> str:
    if os.name == "nt":
        return str(path)
    # WSL owns the mount layout and distro name. A /mnt/c worktree must
    # become a drive path, while a Linux path needs the actual distro UNC.
    try:
        result = subprocess.run(
            ["wslpath", "-w", "-a", str(path)],
            check=True, capture_output=True, text=True, encoding="utf-8", timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("WSL proxy path conversion failed; working wslpath is required") from exc
    converted = result.stdout.rstrip("\r\n")
    if (
        not converted
        or any(character in converted for character in "\r\n\x00")
        or not PureWindowsPath(converted).is_absolute()
    ):
        raise RuntimeError("WSL proxy path conversion returned an invalid Windows path")
    return converted


class CaptureBridgeClient:
    def __init__(self, port: int = 9877, *, capture_backend: str | None = None) -> None:
        self.port = port
        self.capture_backend = capture_backend
        self._proc: subprocess.Popen[str] | None = None
        self._last_screenshot: BridgeScreenshot | None = None
        self._request_started_at = datetime.min.replace(tzinfo=UTC)
        self._response_received_at = self._request_started_at
        self._lock = threading.RLock()

    def connect(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._last_screenshot = None
        try:
            self._proc = subprocess.Popen(
                [sys.executable if os.name == "nt" else "python.exe",
                 _to_windows_path(_PROXY_SCRIPT), str(self.port)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8",
            )
            ready = self._read_line()
            if ready.get("status") != "proxy_ready" or ready.get("protocol_version") != PROTOCOL_VERSION:
                raise ConnectionError("capture proxy unavailable or obsolete")
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        proc, self._proc = self._proc, None
        self._last_screenshot = None
        if proc is not None:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()

    def _request(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            try:
                self.connect()
                request_id = uuid.uuid4().hex
                self._request_started_at = datetime.now(UTC)
                self._send({**payload, "request_id": request_id, "protocol_version": PROTOCOL_VERSION})
                response = self._read_line()
                self._response_received_at = datetime.now(UTC)
                if response.get("protocol_version") != PROTOCOL_VERSION or response.get("request_id") != request_id:
                    raise RuntimeError("bridge response binding invalid; update and restart the Windows bridge server")
                if response.get("status") not in {"ok", "bye"}:
                    raise RuntimeError("capture bridge rejected request")
                return response
            except Exception:
                self.close()
                raise

    def ping(self) -> bool:
        try:
            return self._request({"cmd": "ping"}).get("status") == "ok"
        except Exception:
            return False

    def screenshot_capture(self, save_path: Path | str | None = None) -> BridgeScreenshot:
        with self._lock:
            try:
                return self._screenshot_capture(save_path)
            except Exception:
                self.close()
                raise

    def screenshot(self, save_path: Path | str | None = None) -> bytes:
        """Capture a screenshot of the game window. Returns PNG bytes."""
        return self.screenshot_capture(save_path=save_path).png

    def _screenshot_capture(
        self,
        save_path: Path | str | None = None,
    ) -> BridgeScreenshot:
        """Capture pixels plus their server-attested physical geometry."""
        self._last_screenshot = None
        self.connect()
        payload = {"cmd": "screenshot"}
        if self.capture_backend:
            payload["backend"] = self.capture_backend
        resp = self._request(payload)
        if resp.get("status") != "ok" or "data_b64" not in resp:
            raise RuntimeError("bridge returned an unsuccessful screenshot response")
        try:
            png_bytes = base64.b64decode(resp["data_b64"], validate=True)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("bridge returned invalid screenshot bytes") from exc
        if (
            isinstance(resp.get("size"), bool)
            or not isinstance(resp.get("size"), int)
            or resp.get("size") != len(png_bytes)
        ):
            raise RuntimeError("bridge screenshot byte-length binding is invalid")
        digest = hashlib.sha256(png_bytes).hexdigest()
        if resp.get("frame_sha256") != digest:
            raise RuntimeError("bridge screenshot hash binding is invalid")
        try:
            geometry = CaptureGeometry.model_validate(resp.get("capture_geometry"))
        except (ValidationError, TypeError, ValueError) as exc:
            raise RuntimeError(
                "bridge screenshot lacks valid capture geometry v1; update and restart the Windows bridge server"
            ) from exc
        try:
            with Image.open(BytesIO(png_bytes)) as image:
                image.load()
                decoded_size = image.size
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise RuntimeError("bridge screenshot is not a decodable image") from exc
        if decoded_size != geometry.frame_size:
            raise RuntimeError(
                "bridge screenshot pixels do not match its capture geometry"
            )
        captured_at = parse_capture_time(resp.get("captured_at"))
        if not (self._request_started_at <= captured_at <= self._response_received_at):
            raise RuntimeError("bridge capture time is outside this request")
        screenshot = BridgeScreenshot(
            png=png_bytes,
            frame_sha256=digest,
            capture_geometry=geometry,
            captured_at=captured_at,
            request_id=resp["request_id"],
        )
        if save_path is not None:
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png_bytes)
        # Do not retain a frame if the requested archive write failed.
        self._last_screenshot = screenshot
        return screenshot

    @property
    def last_screenshot(self) -> BridgeScreenshot | None:
        return self._last_screenshot

    def window_info(self) -> dict[str, Any]:
        return self._request({"cmd": "window_info"})

    def list_windows(self, title_substring: str | None = None) -> dict[str, Any]:
        payload = {"cmd": "list_windows"}
        if title_substring is not None:
            payload["title"] = title_substring
        return self._request(payload)

    def _send(self, payload: dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._proc.stdin.flush()

    def _read_line(self) -> dict[str, Any]:
        assert self._proc is not None and self._proc.stdout is not None
        stream = self._proc.stdout
        result: queue.Queue = queue.Queue(maxsize=1)
        def read():
            try:
                result.put(stream.readline(48 * 1024 * 1024 + 1))
            except Exception as exc:
                result.put(exc)
        threading.Thread(target=read, daemon=True).start()
        try:
            line = result.get(timeout=15)
        except queue.Empty as exc:
            raise TimeoutError("capture proxy response timed out") from exc
        if isinstance(line, Exception):
            raise line
        if not line or not line.endswith("\n") or len(line) > 48 * 1024 * 1024:
            raise ConnectionError("capture proxy response missing or oversized")
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("capture proxy response must be an object")
        return value

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
