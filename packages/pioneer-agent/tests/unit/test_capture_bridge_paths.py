from pathlib import PurePosixPath, PureWindowsPath
import subprocess
import unittest
from unittest.mock import patch

from pioneer_agent.adapters import capture_bridge_client as client_module


class CaptureBridgePathTests(unittest.TestCase):
    def convert(self, path, output):
        with patch.object(client_module.os, "name", "posix"), patch.object(
            client_module.subprocess, "run",
            return_value=subprocess.CompletedProcess([], 0, output, ""),
        ):
            result = client_module._to_windows_path(path)
        return result

    def test_windows_backed_worktree_uses_drive_path(self):
        path = PurePosixPath("/mnt/c/Users/Synthetic User/worktree/bridge_proxy.py")
        expected = r"C:\Users\Synthetic User\worktree\bridge_proxy.py"
        self.assertEqual(self.convert(path, expected + "\n"), expected)

    def test_linux_filesystem_uses_actual_distro_path(self):
        path = PurePosixPath("/home/synthetic/bridge_proxy.py")
        expected = r"\\wsl.localhost\Debian-Testing\home\synthetic\bridge_proxy.py"
        self.assertEqual(self.convert(path, expected + "\r\n"), expected)

    def test_custom_mount_path_is_resolved_by_wslpath(self):
        path = PurePosixPath("/windows/d/synthetic/bridge_proxy.py")
        expected = r"D:\synthetic\bridge_proxy.py"
        self.assertEqual(self.convert(path, expected + "\n"), expected)

    def test_native_windows_path_does_not_spawn_converter(self):
        path = PureWindowsPath(r"C:\Synthetic Folder\bridge_proxy.py")
        with patch.object(client_module.os, "name", "nt"), patch.object(
            client_module.subprocess, "run",
        ) as run:
            self.assertEqual(client_module._to_windows_path(path), str(path))
        run.assert_not_called()

    def test_converter_is_bounded_and_passes_path_as_one_argument(self):
        path = PurePosixPath("/mnt/c/synthetic folder/$(not-a-command)/proxy.py")
        with patch.object(client_module.os, "name", "posix"), patch.object(
            client_module.subprocess, "run", return_value=
            subprocess.CompletedProcess([], 0, "C:\\synthetic\\proxy.py\n", ""),
        ) as run:
            client_module._to_windows_path(path)
        run.assert_called_once_with(
            ["wslpath", "-w", "-a", str(path)],
            check=True, capture_output=True, text=True, encoding="utf-8", timeout=5,
        )

    def test_invalid_converter_output_is_rejected(self):
        for output in ("", "relative.py\n", "C:relative.py\n", "/mnt/c/proxy.py\n",
                       "C:\\proxy.py\nextra\n", "C:\\proxy\x00.py\n"):
            with self.subTest(output=repr(output)), patch.object(
                client_module.os, "name", "posix",
            ), patch.object(client_module.subprocess, "run", return_value=
                subprocess.CompletedProcess([], 0, output, "")):
                with self.assertRaisesRegex(RuntimeError, "WSL proxy path conversion"):
                    client_module._to_windows_path(PurePosixPath("/tmp/proxy.py"))

    def test_missing_failed_or_timed_out_converter_fails_clearly(self):
        for error in (FileNotFoundError("no wslpath"),
                      subprocess.CalledProcessError(1, ["wslpath"]),
                      subprocess.TimeoutExpired(["wslpath"], 5)):
            with self.subTest(error=type(error).__name__), patch.object(
                client_module.os, "name", "posix",
            ), patch.object(client_module.subprocess, "run", side_effect=error):
                with self.assertRaisesRegex(RuntimeError, "WSL proxy path conversion"):
                    client_module._to_windows_path(PurePosixPath("/tmp/proxy.py"))

    def test_failed_conversion_prevents_proxy_start_and_clears_frame(self):
        client = client_module.CaptureBridgeClient()
        client._last_screenshot = object()
        with patch.object(client_module, "_to_windows_path", side_effect=
                          RuntimeError("WSL proxy path conversion failed")), patch.object(
            client_module.subprocess, "Popen",
        ) as spawn:
            with self.assertRaisesRegex(RuntimeError, "WSL proxy path conversion"):
                client.connect()
        spawn.assert_not_called()
        self.assertIsNone(client._proc)
        self.assertIsNone(client.last_screenshot)


if __name__ == "__main__":
    unittest.main()
