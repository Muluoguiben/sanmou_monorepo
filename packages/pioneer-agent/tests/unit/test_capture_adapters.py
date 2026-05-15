from __future__ import annotations

import io
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from pioneer_agent.adapters.capture import ScreenshotFileCaptureAdapter, WatchFolderCaptureAdapter
from pioneer_agent.core.device import DevicePlatform, ObservationSourceType


def _write_png(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", size, color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    data = buf.getvalue()
    path.write_bytes(data)
    return data


class CaptureAdapterTests(unittest.TestCase):
    def test_screenshot_file_adapter_is_observe_only(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ios.png"
            expected = _write_png(path, (1170, 2532), (1, 2, 3))

            adapter = ScreenshotFileCaptureAdapter(path, platform=DevicePlatform.IOS)
            frame = adapter.capture()

            self.assertEqual(frame.png, expected)
            self.assertEqual(frame.source_type, ObservationSourceType.SCREENSHOT_FILE)
            self.assertEqual(frame.device_session.profile.platform, DevicePlatform.IOS)
            self.assertEqual(frame.device_session.profile.screenshot_size, (1170, 2532))
            self.assertTrue(frame.device_session.capabilities.observe_only)
            self.assertFalse(frame.device_session.capabilities.input_control)

    def test_watch_folder_adapter_uses_newest_image(self) -> None:
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            older = folder / "old.png"
            newest = folder / "new.png"
            _write_png(older, (100, 100), (1, 1, 1))
            time.sleep(0.01)
            expected = _write_png(newest, (200, 100), (2, 2, 2))

            adapter = WatchFolderCaptureAdapter(folder, platform=DevicePlatform.ANDROID)
            frame = adapter.capture()

            self.assertEqual(frame.png, expected)
            self.assertEqual(frame.metadata["path"], str(newest))
            self.assertEqual(frame.device_session.profile.platform, DevicePlatform.ANDROID)
            self.assertTrue(frame.device_session.capabilities.observe_only)


if __name__ == "__main__":
    unittest.main()
