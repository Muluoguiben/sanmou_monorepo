from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from pioneer_agent.adapters.bridge_client import BridgeClient
from pioneer_agent.core.device import (
    CapabilityFlags,
    DevicePlatform,
    DeviceProfile,
    DeviceSession,
    ObservationSource,
    ObservationSourceType,
    Orientation,
)


class CaptureAdapter(Protocol):
    @property
    def device_session(self) -> DeviceSession: ...

    @property
    def capabilities(self) -> CapabilityFlags: ...

    def capture(self) -> CaptureFrame: ...

    def screenshot(self, save_path: Path | str | None = None) -> bytes: ...


@dataclass(frozen=True)
class CaptureFrame:
    png: bytes
    captured_at: datetime
    device_session: DeviceSession
    source_type: ObservationSourceType
    metadata: dict[str, Any] = field(default_factory=dict)


class ScreenshotFileCaptureAdapter:
    """Observe-only adapter for one user-provided screenshot file."""

    def __init__(
        self,
        path: Path | str,
        *,
        platform: DevicePlatform = DevicePlatform.UNKNOWN,
        profile: DeviceProfile | None = None,
        display_name: str | None = None,
    ) -> None:
        self.path = Path(path)
        if profile is None:
            profile = _profile_from_image_path(self.path, platform)
        source = ObservationSource(
            source_type=ObservationSourceType.SCREENSHOT_FILE,
            uri=str(self.path),
            display_name=display_name or self.path.name,
            capabilities=CapabilityFlags(observe_only=True),
        )
        self._device_session = DeviceSession(profile=profile, source=source)

    @property
    def device_session(self) -> DeviceSession:
        return self._device_session

    @property
    def capabilities(self) -> CapabilityFlags:
        return self._device_session.capabilities

    def capture(self) -> CaptureFrame:
        png = self.path.read_bytes()
        captured_at = datetime.now(UTC)
        self._device_session = self._device_session.mark_observed(captured_at)
        return CaptureFrame(
            png=png,
            captured_at=captured_at,
            device_session=self._device_session,
            source_type=ObservationSourceType.SCREENSHOT_FILE,
            metadata={"path": str(self.path)},
        )

    def screenshot(self, save_path: Path | str | None = None) -> bytes:
        png = self.capture().png
        if save_path is not None:
            Path(save_path).write_bytes(png)
        return png


class WatchFolderCaptureAdapter:
    """Observe-only adapter that reads the newest image in a screenshot folder."""

    IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(
        self,
        folder: Path | str,
        *,
        platform: DevicePlatform = DevicePlatform.UNKNOWN,
        profile: DeviceProfile | None = None,
    ) -> None:
        self.folder = Path(folder)
        latest = self._latest_image()
        if profile is None:
            profile = _profile_from_image_path(latest, platform)
        source = ObservationSource(
            source_type=ObservationSourceType.WATCH_FOLDER,
            uri=str(self.folder),
            display_name=self.folder.name,
            capabilities=CapabilityFlags(observe_only=True),
        )
        self._device_session = DeviceSession(profile=profile, source=source)

    @property
    def device_session(self) -> DeviceSession:
        return self._device_session

    @property
    def capabilities(self) -> CapabilityFlags:
        return self._device_session.capabilities

    def capture(self) -> CaptureFrame:
        path = self._latest_image()
        png = path.read_bytes()
        captured_at = datetime.now(UTC)
        self._device_session = self._device_session.mark_observed(captured_at)
        return CaptureFrame(
            png=png,
            captured_at=captured_at,
            device_session=self._device_session,
            source_type=ObservationSourceType.WATCH_FOLDER,
            metadata={"path": str(path), "folder": str(self.folder)},
        )

    def screenshot(self, save_path: Path | str | None = None) -> bytes:
        png = self.capture().png
        if save_path is not None:
            Path(save_path).write_bytes(png)
        return png

    def _latest_image(self) -> Path:
        if not self.folder.exists():
            raise FileNotFoundError(f"screenshot folder not found: {self.folder}")
        candidates = [
            path
            for path in self.folder.iterdir()
            if path.is_file() and path.suffix.lower() in self.IMAGE_SUFFIXES
        ]
        if not candidates:
            raise FileNotFoundError(f"no screenshot images found in: {self.folder}")
        return max(candidates, key=lambda item: item.stat().st_mtime)


class WindowsBridgeCaptureAdapter:
    """Capture-only view over the existing Windows bridge client."""

    def __init__(
        self,
        bridge: BridgeClient | None = None,
        *,
        profile: DeviceProfile | None = None,
        display_name: str = "Sanmou PC client",
    ) -> None:
        self.bridge = bridge or BridgeClient()
        if profile is None:
            profile = DeviceProfile(
                platform=DevicePlatform.PC_CLIENT,
                resolution=(1920, 1080),
                orientation=Orientation.LANDSCAPE,
            )
        source = ObservationSource(
            source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
            display_name=display_name,
            capabilities=CapabilityFlags(
                observe_only=True,
                live_capture=True,
                reliable_window_info=True,
            ),
        )
        self._device_session = DeviceSession(profile=profile, source=source)

    @property
    def device_session(self) -> DeviceSession:
        return self._device_session

    @property
    def capabilities(self) -> CapabilityFlags:
        return self._device_session.capabilities

    def capture(self) -> CaptureFrame:
        shot = self.bridge.screenshot_capture()
        png = shot.png
        captured_at = datetime.now(UTC)
        profile = _profile_from_image_bytes(
            png,
            self._device_session.profile.platform,
            fallback=self._device_session.profile,
        )
        self._device_session = self._device_session.model_copy(
            update={"profile": profile, "last_observed_at": captured_at}
        )
        metadata: dict[str, Any] = {
            "frame_sha256": shot.frame_sha256,
            "capture_geometry": shot.capture_geometry.model_dump(mode="json"),
        }
        try:
            metadata["window_info"] = self.bridge.window_info()
        except Exception as exc:  # noqa: BLE001
            metadata["window_info_error"] = str(exc)
        return CaptureFrame(
            png=png,
            captured_at=captured_at,
            device_session=self._device_session,
            source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
            metadata=metadata,
        )

    def screenshot(self, save_path: Path | str | None = None) -> bytes:
        frame = self.capture()
        if save_path is not None:
            Path(save_path).write_bytes(frame.png)
        return frame.png


def _profile_from_image_path(path: Path, platform: DevicePlatform) -> DeviceProfile:
    with Image.open(path) as img:
        width, height = img.size
    return DeviceProfile(
        platform=platform,
        resolution=(width, height),
        screenshot_size=(width, height),
        orientation=_orientation(width, height),
    )


def _profile_from_image_bytes(
    png: bytes,
    platform: DevicePlatform,
    *,
    fallback: DeviceProfile | None = None,
) -> DeviceProfile:
    with Image.open(BytesIO(png)) as img:
        width, height = img.size
    base = fallback.model_dump() if fallback is not None else {}
    base.update(
        {
            "platform": platform,
            "resolution": base.get("resolution") or (width, height),
            "screenshot_size": (width, height),
            "orientation": _orientation(width, height),
        }
    )
    return DeviceProfile(**base)


def _orientation(width: int, height: int) -> Orientation:
    if width > height:
        return Orientation.LANDSCAPE
    if height > width:
        return Orientation.PORTRAIT
    return Orientation.UNKNOWN
