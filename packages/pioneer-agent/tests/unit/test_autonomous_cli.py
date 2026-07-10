from __future__ import annotations

import argparse
import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import MagicMock, patch

from pioneer_agent.app.autonomous import (
    _add_execution_mode_args,
    _build_live_device_session,
    main,
)
from pioneer_agent.safety.guard import SessionMode


class _Bridge:
    port = 9877

    def __init__(self, **overrides: object) -> None:
        self.info = {
            "width": 1286,
            "height": 666,
            "usable": True,
            "visible": True,
            "iconic": False,
            "offscreen": False,
            "hwnd": 17,
            "pid": 23,
            **overrides,
        }

    def window_info(self) -> dict[str, object]:
        return self.info

    def __enter__(self) -> _Bridge:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class AutonomousCliTests(unittest.TestCase):
    def test_execution_mode_defaults_to_dry_run(self) -> None:
        parser = argparse.ArgumentParser()
        _add_execution_mode_args(parser)

        self.assertTrue(parser.parse_args([]).dry_run)
        self.assertTrue(parser.parse_args(["--dry-run"]).dry_run)
        self.assertFalse(parser.parse_args(["--execute"]).dry_run)

    def test_execute_and_dry_run_are_mutually_exclusive(self) -> None:
        parser = argparse.ArgumentParser()
        _add_execution_mode_args(parser)

        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--execute", "--dry-run"])

    def test_live_session_binds_control_capability_to_usable_window(self) -> None:
        session = _build_live_device_session(_Bridge())  # type: ignore[arg-type]

        self.assertTrue(session.active)
        self.assertTrue(session.capabilities.can_execute_input)
        self.assertEqual(session.capabilities, session.source.capabilities)
        self.assertEqual(session.profile.resolution, (1286, 666))
        self.assertEqual(session.source.metadata["hwnd"], 17)

    def test_live_session_rejects_unusable_window(self) -> None:
        for overrides in (
            {"usable": False},
            {"visible": False},
            {"width": 0},
            {"iconic": True},
            {"iconic": None},
            {"offscreen": True},
            {"hwnd": 0},
            {"pid": None},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(RuntimeError):
                _build_live_device_session(_Bridge(**overrides))  # type: ignore[arg-type]

    def test_main_only_builds_live_authority_for_execute(self) -> None:
        default_kwargs = _main_loop_kwargs([])
        self.assertTrue(default_kwargs["dry_run"])
        self.assertIsNone(default_kwargs["runner"])

        execute_kwargs = _main_loop_kwargs(["--execute"])
        self.assertFalse(execute_kwargs["dry_run"])
        runner = execute_kwargs["runner"]
        self.assertIsNotNone(runner.device_session)
        self.assertTrue(runner.device_session.active)
        self.assertTrue(runner.device_session.capabilities.can_execute_input)
        self.assertEqual(runner.session_mode, SessionMode.LIVE)


def _main_loop_kwargs(argv: list[str]) -> dict[str, object]:
    loop_instance = MagicMock()
    with (
        patch("pioneer_agent.app.autonomous.BridgeClient", return_value=_Bridge()),
        patch("pioneer_agent.app.autonomous.build_vision_client", return_value=object()),
        patch("pioneer_agent.app.autonomous.UIRegistry.load", return_value=object()),
        patch("pioneer_agent.app.autonomous.UIActions", return_value=object()),
        patch("pioneer_agent.app.autonomous.LoopLogger", return_value=object()),
        patch("pioneer_agent.app.autonomous.TraceStore", return_value=object()),
        patch("pioneer_agent.app.autonomous.logging.basicConfig"),
        patch("pioneer_agent.app.autonomous.logging.getLogger", return_value=MagicMock()),
        patch(
            "pioneer_agent.app.autonomous.AutonomousLoop",
            return_value=loop_instance,
        ) as loop_cls,
    ):
        result = main(["--max-iterations", "0", *argv])
    if result != 0:
        raise AssertionError(f"unexpected main result: {result}")
    loop_instance.run_forever.assert_called_once_with(max_iterations=0)
    return dict(loop_cls.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
