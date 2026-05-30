"""Tests for the ActionType → handler dispatch table."""
from __future__ import annotations

import unittest

from pioneer_agent.core.device import CapabilityFlags
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction
from pioneer_agent.executor.action_handlers import dispatch
from pioneer_agent.executor.ui_actions import ClickOutcome
from pioneer_agent.executor.ui_runner import UIActionRunner
from pioneer_agent.runtime.architecture_gates import (
    AutomationMode,
    AutomationReadiness,
    AutomationReadinessGate,
)
from pioneer_agent.verifier import ExpectedStateDelta, VerifierRegistry, VerifierSpec


class _NullUI:
    """All handlers take a UIActions, but wait + pending paths never call it."""


class _SemanticUI:
    def __init__(self, *, click_ok: bool = True) -> None:
        self.click_ok = click_ok
        self.clicks: list[dict] = []

    def click_bbox(self, target_key, bbox, *, label=None):  # noqa: ANN001
        self.clicks.append({"target_key": target_key, "bbox": bbox, "label": label})
        return ClickOutcome(
            success=self.click_ok,
            px=(800, 850),
            reason=None if self.click_ok else "bridge click failed",
            matched_label=label,
        )


def _mk_action(t: ActionType, **params) -> CandidateAction:
    return CandidateAction(action_id=f"a-{t.value}", action_type=t, params=params)


class DispatchTests(unittest.TestCase):
    def test_wait_for_stamina_returns_ok(self) -> None:
        res = dispatch(_mk_action(ActionType.WAIT_FOR_STAMINA), _NullUI())  # type: ignore[arg-type]
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.verification_status, "not_applicable")

    def test_wait_for_resource_returns_ok(self) -> None:
        res = dispatch(_mk_action(ActionType.WAIT_FOR_RESOURCE), _NullUI())  # type: ignore[arg-type]
        self.assertEqual(res.status, "ok")

    def test_upgrade_without_building_name_fails(self) -> None:
        res = dispatch(_mk_action(ActionType.UPGRADE_BUILDING), _NullUI())  # type: ignore[arg-type]
        self.assertEqual(res.status, "failed")
        self.assertTrue(res.recovery_required)
        self.assertIn("building_name", (res.failure_reason or ""))

    def test_upgrade_with_building_name_pending(self) -> None:
        res = dispatch(
            _mk_action(ActionType.UPGRADE_BUILDING, building_name="征兵所"),
            _NullUI(),  # type: ignore[arg-type]
        )
        self.assertEqual(res.status, "pending")
        self.assertIn("征兵所", (res.failure_reason or ""))

    def test_claim_chapter_reward_clicks_observed_claim_button(self) -> None:
        ui = _SemanticUI()
        res = dispatch(
            _mk_action(
                ActionType.CLAIM_CHAPTER_REWARD,
                claim_button={
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            ),
            ui,  # type: ignore[arg-type]
        )

        self.assertEqual(res.status, "ok")
        self.assertEqual(res.verification_status, "unverified")
        self.assertEqual(ui.clicks[0]["target_key"], "chapter_claim_button")
        self.assertEqual(res.summary["target_key"], "chapter_claim_button")

    def test_claim_chapter_reward_without_bbox_stays_pending(self) -> None:
        res = dispatch(_mk_action(ActionType.CLAIM_CHAPTER_REWARD), _NullUI())  # type: ignore[arg-type]

        self.assertEqual(res.status, "pending")
        self.assertIn("bbox not observed", res.failure_reason or "")

    def test_recruit_soldiers_clicks_observed_recruit_button(self) -> None:
        ui = _SemanticUI()
        res = dispatch(
            _mk_action(
                ActionType.RECRUIT_SOLDIERS,
                team_id="team-1",
                recruit_button={
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            ),
            ui,  # type: ignore[arg-type]
        )

        self.assertEqual(res.status, "ok")
        self.assertEqual(ui.clicks[0]["target_key"], "recruit_button")

    def test_upgrade_building_clicks_observed_confirm_button(self) -> None:
        ui = _SemanticUI()
        res = dispatch(
            _mk_action(
                ActionType.UPGRADE_BUILDING,
                building_name="君王殿",
                upgrade_dialog={
                    "visible": True,
                    "building_name": "君王殿",
                    "can_upgrade": True,
                    "confirm_button": {
                        "visible": True,
                        "enabled": True,
                        "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                    },
                },
            ),
            ui,  # type: ignore[arg-type]
        )

        self.assertEqual(res.status, "ok")
        self.assertEqual(ui.clicks[0]["target_key"], "upgrade_confirm_button")
        self.assertTrue(res.summary["terminal_for_verifier"])
        self.assertEqual(res.summary["flow_step"], "confirm_upgrade")

    def test_upgrade_building_clicks_observed_upgrade_entry_as_intermediate_step(self) -> None:
        ui = _SemanticUI()
        res = dispatch(
            _mk_action(
                ActionType.UPGRADE_BUILDING,
                building_name="君王殿",
                upgrade_button={
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 100, "y_min": 700, "x_max": 240, "y_max": 900},
                },
            ),
            ui,  # type: ignore[arg-type]
        )

        self.assertEqual(res.status, "ok")
        self.assertEqual(res.verification_status, "not_applicable")
        self.assertFalse(res.summary["terminal_for_verifier"])
        self.assertEqual(res.summary["flow_step"], "open_upgrade_dialog")
        self.assertEqual(ui.clicks[0]["target_key"], "building_upgrade_button")

    def test_upgrade_building_blocks_disabled_confirm_button(self) -> None:
        res = dispatch(
            _mk_action(
                ActionType.UPGRADE_BUILDING,
                building_name="君王殿",
                upgrade_dialog={
                    "visible": True,
                    "building_name": "君王殿",
                    "can_upgrade": True,
                    "confirm_button": {
                        "visible": True,
                        "enabled": False,
                        "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                    },
                },
            ),
            _NullUI(),  # type: ignore[arg-type]
        )

        self.assertEqual(res.status, "failed")
        self.assertIn("disabled", res.failure_reason or "")

    def test_attack_is_pending(self) -> None:
        res = dispatch(_mk_action(ActionType.ATTACK_LAND), _NullUI())  # type: ignore[arg-type]
        self.assertEqual(res.status, "pending")

    def test_every_action_type_has_a_handler(self) -> None:
        for t in ActionType:
            res = dispatch(_mk_action(t, building_name="x"), _NullUI())  # type: ignore[arg-type]
            self.assertIn(res.status, {"ok", "pending", "failed"})
            self.assertNotIn("no handler", res.failure_reason or "")


class UIActionRunnerTests(unittest.TestCase):
    def test_runner_delegates_to_dispatch(self) -> None:
        runner = UIActionRunner(_NullUI())  # type: ignore[arg-type]
        res = runner.run(_mk_action(ActionType.WAIT_FOR_STAMINA))
        self.assertEqual(res.status, "ok")

    def test_runner_blocks_observe_only_sources(self) -> None:
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(observe_only=True),
        )
        res = runner.run(_mk_action(ActionType.CLAIM_CHAPTER_REWARD))
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.verification_status, "not_applicable")
        self.assertIn("input_control", res.failure_reason or "")

    def test_runner_blocks_advisor_session_mode(self) -> None:
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
            session_mode="advisor",
        )
        res = runner.run(_mk_action(ActionType.CLAIM_CHAPTER_REWARD))
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "safety_guard")
        self.assertEqual(res.summary["guard_decision"], "block")
        self.assertIn("session mode advisor", res.failure_reason or "")

    def test_runner_allows_explicit_control_capability(self) -> None:
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
        )
        res = runner.run(_mk_action(ActionType.WAIT_FOR_STAMINA))
        self.assertEqual(res.status, "ok")

    def test_runner_requires_confirmation_for_sensitive_action(self) -> None:
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
        )
        res = runner.run(_mk_action(ActionType.ATTACK_LAND))
        self.assertEqual(res.status, "requires_confirmation")
        self.assertEqual(res.summary["blocked_by"], "safety_guard")
        self.assertEqual(res.summary["guard_decision"], "require_confirmation")

    def test_runner_blocks_low_risk_action_without_semantic_bbox(self) -> None:
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
        )
        res = runner.run(_mk_action(ActionType.CLAIM_CHAPTER_REWARD))
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "semantic_target_gate")
        self.assertIn("semantic bbox target", res.failure_reason or "")

    def test_runner_dispatches_low_risk_action_when_semantic_bbox_is_present(self) -> None:
        runner = UIActionRunner(
            _SemanticUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
        )
        res = runner.run(
            _mk_action(
                ActionType.CLAIM_CHAPTER_REWARD,
                claim_button={
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            )
        )
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.summary["target_key"], "chapter_claim_button")
        self.assertEqual(res.summary["semantic_target_gate"]["decision"], "allow")
        self.assertEqual(res.summary["semantic_target_gate"]["details"]["target"], "claim_button")

    def test_runner_blocks_low_risk_action_with_disabled_semantic_bbox(self) -> None:
        runner = UIActionRunner(
            _SemanticUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
        )
        res = runner.run(
            _mk_action(
                ActionType.RECRUIT_SOLDIERS,
                recruit_button={
                    "visible": True,
                    "enabled": False,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            )
        )
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "semantic_target_gate")

    def test_runner_dispatches_upgrade_confirm_when_semantic_bbox_is_present(self) -> None:
        runner = UIActionRunner(
            _SemanticUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
        )
        res = runner.run(
            _mk_action(
                ActionType.UPGRADE_BUILDING,
                building_name="君王殿",
                upgrade_dialog={
                    "visible": True,
                    "building_name": "君王殿",
                    "can_upgrade": True,
                    "confirm_button": {
                        "visible": True,
                        "enabled": True,
                        "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                    },
                },
            )
        )
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.summary["target_key"], "upgrade_confirm_button")
        self.assertEqual(res.summary["semantic_target_gate"]["decision"], "allow")
        self.assertEqual(
            res.summary["semantic_target_gate"]["details"]["target"],
            "upgrade_dialog.confirm_button",
        )

    def test_runner_blocks_low_risk_action_when_architecture_gate_is_not_ready(self) -> None:
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
            automation_gate=AutomationReadinessGate(
                AutomationReadiness(low_risk_verifier_false_positive_covered=False)
            ),
        )
        res = runner.run(_mk_action(ActionType.CLAIM_CHAPTER_REWARD))
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "architecture_gate")
        self.assertIn("false positive coverage", res.failure_reason or "")

    def test_runner_blocks_confirmed_action_without_verifier_spec(self) -> None:
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
        )
        res = runner.run(
            _mk_action(
                ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM,
                confirmation_token="manual-ok",
            )
        )
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "verifier_registry")
        self.assertIn("requires a verifier", res.failure_reason or "")

    def test_runner_dispatches_confirmed_sensitive_action_with_verifier_spec(self) -> None:
        registry = VerifierRegistry(
            {
                ActionType.ATTACK_LAND: VerifierSpec(
                    action_type=ActionType.ATTACK_LAND,
                    expected_deltas=(
                        ExpectedStateDelta(
                            path="map_state.last_attack_id",
                            expected_after="attack-1",
                        ),
                    ),
                    timeout_seconds=10.0,
                )
            }
        )
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
            verifier_registry=registry,
        )
        res = runner.run(_mk_action(ActionType.ATTACK_LAND, confirmation_token="manual-ok"))
        self.assertEqual(res.status, "pending")
        self.assertIn("attack flow", res.failure_reason or "")

    def test_runner_blocks_high_risk_full_auto_even_with_confirmation_token(self) -> None:
        registry = VerifierRegistry(
            {
                ActionType.ATTACK_LAND: VerifierSpec(
                    action_type=ActionType.ATTACK_LAND,
                    expected_deltas=(
                        ExpectedStateDelta(
                            path="map_state.last_attack_id",
                            expected_after="attack-1",
                        ),
                    ),
                    timeout_seconds=10.0,
                )
            }
        )
        runner = UIActionRunner(
            _NullUI(),  # type: ignore[arg-type]
            capabilities=CapabilityFlags(input_control=True),
            verifier_registry=registry,
            automation_mode=AutomationMode.FULL_AUTO,
        )
        res = runner.run(_mk_action(ActionType.ATTACK_LAND, confirmation_token="manual-ok"))
        self.assertEqual(res.status, "blocked")
        self.assertEqual(res.summary["blocked_by"], "architecture_gate")
        self.assertIn("high-risk full-auto", res.failure_reason or "")


if __name__ == "__main__":
    unittest.main()
