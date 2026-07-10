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
from pioneer_agent.core.enums import ActionType
from pioneer_agent.executor.operator_confirmation import (
    WaitingOperatorConfirmationProvider,
)
from pioneer_agent.runtime.architecture_gates import (
    ArchitectureGateDecision,
    AutomationMode,
)


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

        self.assertEqual(parser.parse_args([]).execution_mode, "dry_run")
        self.assertEqual(parser.parse_args(["--dry-run"]).execution_mode, "dry_run")
        self.assertEqual(parser.parse_args(["--execute"]).execution_mode, "execute")
        self.assertEqual(
            parser.parse_args(["--evidence-capture"]).execution_mode,
            "evidence_capture",
        )

    def test_execute_and_dry_run_are_mutually_exclusive(self) -> None:
        parser = argparse.ArgumentParser()
        _add_execution_mode_args(parser)

        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--execute", "--dry-run"])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["--execute", "--evidence-capture"])

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

    def test_main_defaults_to_dry_run_without_live_authority(self) -> None:
        default_kwargs = _main_loop_kwargs([])
        self.assertTrue(default_kwargs["dry_run"])
        self.assertIsNone(default_kwargs["runner"])

    def test_execute_is_unconditionally_disabled_pending_recomputable_qa_attestation(self) -> None:
        stderr = io.StringIO()
        with (
            patch("pioneer_agent.app.autonomous.BridgeClient") as bridge_cls,
            redirect_stderr(stderr),
            self.assertRaises(SystemExit),
        ):
            main(["--max-iterations", "0", "--execute"])

        bridge_cls.assert_not_called()
        message = stderr.getvalue()
        self.assertIn("--execute is disabled", message)
        self.assertIn("committed QA attestation", message)
        self.assertIn("bound live traces", message)

    def test_removed_closure_json_flags_cannot_authorize_execute(self) -> None:
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(
                [
                    "--max-iterations",
                    "0",
                    "--execute",
                    "--closure-artifact",
                    "closure.json",
                    "--closure-artifact-commit",
                    "a" * 40,
                    "--closure-artifact-sha256",
                    "b" * 64,
                ]
            )

    def test_evidence_capture_is_one_tick_bound_low_risk_confirmation(self) -> None:
        invalid_cases = (
            ["--evidence-capture"],
            [
                "--evidence-capture",
                "--max-iterations",
                "2",
                "--evidence-action",
                ActionType.CLAIM_CHAPTER_REWARD.value,
                "--confirm-evidence-capture",
            ],
            [
                "--evidence-capture",
                "--max-iterations",
                "1",
                "--evidence-action",
                ActionType.CLAIM_CHAPTER_REWARD.value,
            ],
            [
                "--evidence-capture",
                "--max-iterations",
                "1",
                "--confirm-evidence-capture",
            ],
            [
                "--evidence-capture",
                "--max-iterations",
                "1",
                "--evidence-action",
                ActionType.ATTACK_LAND.value,
                "--confirm-evidence-capture",
            ],
        )
        for argv in invalid_cases:
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(argv)

        kwargs = _main_loop_kwargs(
            [
                "--evidence-capture",
                "--evidence-action",
                ActionType.CLAIM_CHAPTER_REWARD.value,
                "--confirm-evidence-capture",
            ],
            max_iterations=1,
        )
        runner = kwargs["runner"]
        self.assertFalse(kwargs["dry_run"])
        self.assertEqual(runner.automation_mode, AutomationMode.EVIDENCE_CAPTURE)
        self.assertIsInstance(
            runner.operator_confirmation_provider,
            WaitingOperatorConfirmationProvider,
        )

        allowed = runner.automation_gate.evaluate(
            ActionType.CLAIM_CHAPTER_REWARD,
            mode=runner.automation_mode,
        )
        wrong_low_risk = runner.automation_gate.evaluate(
            ActionType.RECRUIT_SOLDIERS,
            mode=runner.automation_mode,
        )
        high_risk = runner.automation_gate.evaluate(
            ActionType.ATTACK_LAND,
            mode=runner.automation_mode,
            human_confirmed=True,
        )
        self.assertEqual(allowed.decision, ArchitectureGateDecision.ALLOW)
        self.assertEqual(wrong_low_risk.decision, ArchitectureGateDecision.BLOCK)
        self.assertEqual(high_risk.decision, ArchitectureGateDecision.BLOCK)


def _main_loop_kwargs(
    argv: list[str],
    *,
    max_iterations: int = 0,
) -> dict[str, object]:
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
        result = main(["--max-iterations", str(max_iterations), *argv])
    if result != 0:
        raise AssertionError(f"unexpected main result: {result}")
    loop_instance.run_forever.assert_called_once_with(max_iterations=max_iterations)
    return dict(loop_cls.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
