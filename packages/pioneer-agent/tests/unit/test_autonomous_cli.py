from __future__ import annotations

import argparse
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

from pioneer_agent.app.autonomous import (
    _add_execution_mode_args,
    _build_live_device_session,
    _evidence_capture_summary,
    main,
)
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ExecutionResult, SelectionResult
from pioneer_agent.executor.operator_confirmation import (
    WaitingOperatorConfirmationProvider,
)
from pioneer_agent.runtime.architecture_gates import (
    ArchitectureGateDecision,
    AutomationMode,
)
from pioneer_agent.runtime.autonomous_loop import TickResult


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
        self.assertEqual(
            kwargs["evidence_action_type"],
            ActionType.CLAIM_CHAPTER_REWARD,
        )
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

    def test_evidence_capture_summary_requires_exact_verified_success(self) -> None:
        expected = ActionType.RECRUIT_SOLDIERS
        selected = CandidateAction(
            action_id="recruit-team-1",
            action_type=expected,
            params={"team_id": "team-1"},
        )
        cases = (
            (
                selected,
                _verified_execution(selected),
                True,
            ),
            (
                selected,
                ExecutionResult(
                    action_id=selected.action_id,
                    status="ok",
                    verification_status="unverified",
                ),
                False,
            ),
            (
                selected,
                ExecutionResult(
                    action_id=selected.action_id,
                    status="blocked",
                    verification_status="unknown",
                ),
                False,
            ),
            (
                selected,
                ExecutionResult(
                    action_id=selected.action_id,
                    status="failed",
                    verification_status="failed",
                ),
                False,
            ),
            (
                selected,
                _verified_execution(selected).model_copy(
                    update={"action_id": "another-action"}
                ),
                False,
            ),
            (
                selected,
                _verified_execution(selected).model_copy(
                    update={"failure_reason": "contradictory failure"}
                ),
                False,
            ),
            (
                selected,
                _verified_execution(selected).model_copy(
                    update={"recovery_required": True}
                ),
                False,
            ),
            (
                selected,
                _verified_execution(selected).model_copy(update={"summary": {}}),
                False,
            ),
            (None, None, False),
        )
        for action, execution, success in cases:
            with self.subTest(action=action, execution=execution):
                result = _tick_result(action, execution)
                summary = _evidence_capture_summary(result, expected_action=expected)
                self.assertIs(summary["success"], success)

    def test_evidence_capture_returns_nonzero_without_verified_outcome(self) -> None:
        action = CandidateAction(
            action_id="claim-17",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
        )
        unverified = _tick_result(
            action,
            ExecutionResult(
                action_id=action.action_id,
                status="ok",
                verification_status="unverified",
            ),
        )
        result, loop_instance, _, stdout = _invoke_main(
            [
                "--max-iterations",
                "1",
                "--evidence-capture",
                "--evidence-action",
                action.action_type.value,
                "--confirm-evidence-capture",
            ],
            tick_result=unverified,
        )
        self.assertEqual(result, 3)
        payload = json.loads(stdout)
        self.assertFalse(payload["success"])
        self.assertIn("execution_not_verified", payload["validation_issues"])
        loop_instance.tick.assert_called_once_with(0)
        loop_instance.run_forever.assert_not_called()

    def test_evidence_capture_returns_nonzero_on_tick_exception(self) -> None:
        secret = "api_key=SHOULD_NOT_APPEAR"
        result, loop_instance, _, stdout = _invoke_main(
            [
                "--max-iterations",
                "1",
                "--evidence-capture",
                "--evidence-action",
                ActionType.UPGRADE_BUILDING.value,
                "--confirm-evidence-capture",
            ],
            tick_error=RuntimeError(secret),
        )
        self.assertEqual(result, 2)
        payload = json.loads(stdout)
        self.assertEqual(payload["error_code"], "evidence_tick_failed")
        self.assertEqual(payload["exception_type"], "RuntimeError")
        self.assertNotIn(secret, stdout)
        loop_instance.tick.assert_called_once_with(0)
        loop_instance.run_forever.assert_not_called()

    def test_no_current_candidate_summary_includes_gate_diagnostics(self) -> None:
        result = _tick_result(None, None)
        result.selection.selection_reason["evidence_action_constraint"] = {
            "required_action_type": "claim_chapter_reward",
            "decision": "no_current_frame_candidate",
            "evaluated_candidates": [
                {
                    "action_id": "claim-stale",
                    "decision": "block",
                    "reason": "current frame chapter does not match the action target",
                }
            ],
        }

        summary = _evidence_capture_summary(
            result,
            expected_action=ActionType.CLAIM_CHAPTER_REWARD,
        )

        self.assertEqual(summary["validation_issues"], ["no_current_frame_candidate"])
        self.assertEqual(
            summary["selection_constraint"]["evaluated_candidates"][0]["decision"],
            "block",
        )


def _main_loop_kwargs(
    argv: list[str],
    *,
    max_iterations: int = 0,
) -> dict[str, object]:
    tick_result = None
    if "--evidence-capture" in argv:
        action_index = argv.index("--evidence-action") + 1
        action_type = ActionType(argv[action_index])
        action = _action_for_type(action_type)
        tick_result = _tick_result(
            action,
            _verified_execution(action),
        )
    result, loop_instance, kwargs, stdout = _invoke_main(
        ["--max-iterations", str(max_iterations), *argv],
        tick_result=tick_result,
    )
    if result != 0:
        raise AssertionError(f"unexpected main result: {result}")
    if "--evidence-capture" in argv:
        payload = json.loads(stdout)
        if payload.get("success") is not True:
            raise AssertionError(f"unexpected evidence payload: {payload}")
        loop_instance.tick.assert_called_once_with(0)
        loop_instance.run_forever.assert_not_called()
    else:
        loop_instance.run_forever.assert_called_once_with(max_iterations=max_iterations)
        loop_instance.tick.assert_not_called()
    return kwargs


def _invoke_main(
    argv: list[str],
    *,
    tick_result=None,
    tick_error: Exception | None = None,
) -> tuple[int, MagicMock, dict[str, object], str]:
    loop_instance = MagicMock()
    if tick_error is not None:
        loop_instance.tick.side_effect = tick_error
    else:
        loop_instance.tick.return_value = tick_result
    stdout = io.StringIO()
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
        redirect_stdout(stdout),
    ):
        result = main(argv)
    return result, loop_instance, dict(loop_cls.call_args.kwargs), stdout.getvalue()


def _tick_result(
    selected_action: CandidateAction | None,
    execution: ExecutionResult | None,
) -> TickResult:
    return TickResult(
        iteration=0,
        summary=MagicMock(),
        selection=SelectionResult(
            selected_action=selected_action,
            ranked_actions=[selected_action] if selected_action is not None else [],
        ),
        execution=execution,
        sleep_s=0.0,
    )


def _action_for_type(action_type: ActionType) -> CandidateAction:
    params = {
        ActionType.CLAIM_CHAPTER_REWARD: {"chapter_id": 17},
        ActionType.RECRUIT_SOLDIERS: {"team_id": "team-1"},
        ActionType.UPGRADE_BUILDING: {
            "building_name": "Main Hall",
            "current_level": 10,
            "target_level": 11,
        },
    }[action_type]
    return CandidateAction(
        action_id=f"verified-{action_type.value}",
        action_type=action_type,
        params=params,
    )


def _verified_execution(action: CandidateAction) -> ExecutionResult:
    target_fields = {
        ActionType.CLAIM_CHAPTER_REWARD: ("chapter_id",),
        ActionType.RECRUIT_SOLDIERS: ("team_id",),
        ActionType.UPGRADE_BUILDING: (
            "building_name",
            "current_level",
            "target_level",
        ),
    }[action.action_type]
    target_identity = {field: action.params[field] for field in target_fields}
    return ExecutionResult(
        action_id=action.action_id,
        status="ok",
        verification_status="verified",
        summary={
            "post_action_verifier": {
                "action_type": action.action_type.value,
                "target_identity": target_identity,
                "status": "verified",
                "checked": ["observed.target"],
                "post_action_delta": [
                    {
                        "path": "observed.target",
                        "operator": "changes_to",
                        "before": True,
                        "after": False,
                    }
                ],
                "post_observe": {
                    "observation": {"observation_id": "post-action"},
                    "frame": {"role": "post_action"},
                },
            }
        },
    )


if __name__ == "__main__":
    unittest.main()
