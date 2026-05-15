from __future__ import annotations

import unittest

from pioneer_agent.core.device import (
    AccountSession,
    CapabilityFlags,
    DevicePlatform,
    DeviceProfile,
    DeviceSession,
    GridCell,
    MapGridState,
    NormalizedPoint,
    ObservationSource,
    ObservationSourceType,
    Orientation,
    PixelRect,
)


class DeviceModelTests(unittest.TestCase):
    def test_profile_normalizes_inside_game_content_region(self) -> None:
        profile = DeviceProfile(
            platform=DevicePlatform.ANDROID_EMULATOR,
            resolution=(1920, 1080),
            screenshot_size=(1920, 1080),
            orientation=Orientation.LANDSCAPE,
            game_content_region=PixelRect(x=100, y=60, width=1720, height=960),
        )

        point = profile.normalize_content_point(960, 540)
        self.assertAlmostEqual(point.x, 0.5, places=3)
        self.assertAlmostEqual(point.y, 0.5, places=3)
        self.assertEqual(profile.content_point_to_screen(NormalizedPoint(x=0.5, y=0.5)), (960, 540))

    def test_capability_flags_disable_observe_only_when_control_is_enabled(self) -> None:
        flags = CapabilityFlags(input_control=True)
        self.assertFalse(flags.observe_only)
        self.assertTrue(flags.can_execute_input)

    def test_device_session_inherits_source_capabilities(self) -> None:
        source = ObservationSource(
            source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
            capabilities=CapabilityFlags(observe_only=True, live_capture=True),
        )
        session = DeviceSession(
            profile=DeviceProfile(
                platform=DevicePlatform.PC_CLIENT,
                resolution=(1920, 1080),
                orientation=Orientation.LANDSCAPE,
            ),
            source=source,
        )

        self.assertTrue(session.capabilities.observe_only)
        self.assertTrue(session.capabilities.live_capture)

    def test_account_session_allows_only_one_active_live_source(self) -> None:
        source = ObservationSource(
            source_type=ObservationSourceType.WINDOWS_WINDOW_CAPTURE,
            capabilities=CapabilityFlags(observe_only=True, live_capture=True),
        )
        profile = DeviceProfile(platform=DevicePlatform.PC_CLIENT, resolution=(1920, 1080))
        first = DeviceSession(profile=profile, source=source)
        second = DeviceSession(profile=profile, source=source)

        account = AccountSession(server_id="s1").bind_live_source(first)
        self.assertEqual(account.active_live_source_id, first.session_id)
        with self.assertRaises(ValueError):
            account.bind_live_source(second)

    def test_map_grid_state_is_account_scoped_and_device_independent(self) -> None:
        account = AccountSession(server_id="s1")
        grid = MapGridState(account_session_id=account.account_session_id).upsert_cell(
            GridCell(
                cell_id="10:20",
                row=10,
                col=20,
                level=4,
                center=NormalizedPoint(x=0.25, y=0.75),
            )
        )
        account = account.with_map_grid(grid)

        self.assertIn("10:20", account.map_grid_state.cells)  # type: ignore[union-attr]
        self.assertEqual(account.map_grid_state.cells["10:20"].level, 4)  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
