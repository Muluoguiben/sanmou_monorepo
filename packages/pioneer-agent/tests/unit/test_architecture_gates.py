from __future__ import annotations

import unittest

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction
from pioneer_agent.runtime.architecture_gates import (
    ArchitectureGateDecision,
    AutomationMode,
    AutomationReadiness,
    AutomationReadinessGate,
    LLMJudgeGate,
    validate_explainer_boundary,
    validate_low_risk_semantic_target,
)
from pioneer_agent.selector.action_selector import ActionSelector


def _action(action_type: ActionType, score: float, **params) -> CandidateAction:
    return CandidateAction(
        action_id=f"a-{action_type.value}-{score}",
        action_type=action_type,
        params=params,
    ).model_copy(update={"score_total": score})


class ArchitectureGateTests(unittest.TestCase):
    def test_llm_judge_gate_defaults_to_disabled(self) -> None:
        verdict = LLMJudgeGate().evaluate(
            [
                _action(ActionType.RECRUIT_SOLDIERS, 100),
                _action(ActionType.UPGRADE_BUILDING, 99),
            ],
            top_score_gap=1.0,
        )

        self.assertEqual(verdict.decision, ArchitectureGateDecision.SKIP)
        self.assertEqual(verdict.reason, "llm_as_judge_disabled")

    def test_llm_judge_gate_blocks_without_golden_replay_baseline(self) -> None:
        verdict = LLMJudgeGate(enabled=True).evaluate(
            [
                _action(ActionType.RECRUIT_SOLDIERS, 100),
                _action(ActionType.UPGRADE_BUILDING, 99),
            ],
            top_score_gap=1.0,
        )

        self.assertEqual(verdict.decision, ArchitectureGateDecision.BLOCK)
        self.assertIn("golden replay baseline", verdict.reason)

    def test_llm_judge_gate_allows_only_close_top_scores_after_baseline(self) -> None:
        gate = LLMJudgeGate(
            enabled=True,
            golden_replay_baseline_ready=True,
            top_score_gap_threshold=3.0,
        )

        wide = gate.evaluate(
            [
                _action(ActionType.RECRUIT_SOLDIERS, 100),
                _action(ActionType.UPGRADE_BUILDING, 90),
            ],
            top_score_gap=10.0,
        )
        close = gate.evaluate(
            [
                _action(ActionType.RECRUIT_SOLDIERS, 100),
                _action(ActionType.UPGRADE_BUILDING, 98),
            ],
            top_score_gap=2.0,
        )

        self.assertEqual(wide.decision, ArchitectureGateDecision.SKIP)
        self.assertEqual(close.decision, ArchitectureGateDecision.ALLOW)

    def test_selector_exposes_default_judge_gate_in_selection_reason(self) -> None:
        result = ActionSelector(load_default_strategy=False).select(
            state=_state_with_two_close_candidates()
        )

        self.assertEqual(
            result.selection_reason["llm_judge_gate"]["decision"],
            ArchitectureGateDecision.SKIP.value,
        )
        self.assertEqual(
            result.selection_reason["llm_judge_gate"]["reason"],
            "llm_as_judge_disabled",
        )

    def test_explainer_boundary_allows_text_only_or_exact_metadata_echo(self) -> None:
        action = _action(
            ActionType.UPGRADE_BUILDING,
            100,
            building_id="main_hall",
            building_name="君王殿",
        ).model_copy(update={"risk": {"level": "low"}})

        text_only = validate_explainer_boundary(action)
        exact_echo = validate_explainer_boundary(
            action,
            draft_action_type=ActionType.UPGRADE_BUILDING,
            draft_params=action.params,
            base_safety_verdict="advisor_mode",
            draft_safety_verdict="advisor_mode",
            draft_risk=action.risk,
        )

        self.assertEqual(text_only.decision, ArchitectureGateDecision.ALLOW)
        self.assertEqual(exact_echo.decision, ArchitectureGateDecision.ALLOW)

    def test_explainer_boundary_blocks_action_param_and_safety_mutation(self) -> None:
        action = _action(
            ActionType.RECRUIT_SOLDIERS,
            100,
            team_id="team-1",
            recruit_amount=3000,
        )

        changed_action = validate_explainer_boundary(
            action,
            draft_action_type=ActionType.ATTACK_LAND,
        )
        changed_params = validate_explainer_boundary(
            action,
            draft_params={"team_id": "team-1", "recruit_amount": 9000},
        )
        changed_safety = validate_explainer_boundary(
            action,
            base_safety_verdict="advisor_mode",
            draft_safety_verdict="executable",
        )

        self.assertEqual(changed_action.decision, ArchitectureGateDecision.BLOCK)
        self.assertEqual(changed_params.decision, ArchitectureGateDecision.BLOCK)
        self.assertEqual(changed_safety.decision, ArchitectureGateDecision.BLOCK)

    def test_automation_readiness_defaults_fully_closed(self) -> None:
        readiness = AutomationReadiness()

        self.assertFalse(readiness.golden_replay_baseline_ready)
        self.assertFalse(readiness.low_risk_verifier_false_positive_covered)
        self.assertFalse(readiness.map_land_verifier_ready)
        self.assertFalse(readiness.battle_result_verifier_ready)
        self.assertFalse(readiness.team_state_verifier_ready)
        self.assertFalse(readiness.closure_gate_ready)
        self.assertEqual(readiness.accepted_action_values, frozenset())

    def test_automation_gate_blocks_advisor_mode(self) -> None:
        verdict = AutomationReadinessGate().evaluate(
            ActionType.RECRUIT_SOLDIERS,
            mode=AutomationMode.ADVISOR,
        )

        self.assertEqual(verdict.decision, ArchitectureGateDecision.BLOCK)
        self.assertIn("must never authorize", verdict.reason)

    def test_automation_gate_blocks_low_risk_semiauto_without_closure_artifact(self) -> None:
        gate = AutomationReadinessGate(
            AutomationReadiness(
                golden_replay_baseline_ready=True,
                low_risk_verifier_false_positive_covered=True,
                accepted_actions=frozenset({ActionType.RECRUIT_SOLDIERS}),
            )
        )

        verdict = gate.evaluate(ActionType.RECRUIT_SOLDIERS, mode=AutomationMode.SEMI_AUTO)

        self.assertEqual(verdict.decision, ArchitectureGateDecision.BLOCK)
        self.assertIn("committed closure artifact", verdict.reason)

    def test_automation_gate_allows_only_artifact_accepted_low_risk_action(self) -> None:
        gate = AutomationReadinessGate(
            AutomationReadiness(
                golden_replay_baseline_ready=True,
                low_risk_verifier_false_positive_covered=True,
                closure_gate_ready=True,
                accepted_actions=frozenset({ActionType.CLAIM_CHAPTER_REWARD}),
            )
        )

        allowed = gate.evaluate(
            ActionType.CLAIM_CHAPTER_REWARD,
            mode=AutomationMode.SEMI_AUTO,
        )
        rejected = gate.evaluate(
            ActionType.RECRUIT_SOLDIERS,
            mode=AutomationMode.SEMI_AUTO,
        )

        self.assertEqual(allowed.decision, ArchitectureGateDecision.ALLOW)
        self.assertEqual(rejected.decision, ArchitectureGateDecision.BLOCK)
        self.assertIn("not accepted", rejected.reason)

    def test_automation_gate_blocks_high_risk_full_auto_without_closure_artifact(self) -> None:
        verdict = AutomationReadinessGate().evaluate(
            ActionType.ATTACK_LAND,
            mode=AutomationMode.FULL_AUTO,
        )

        self.assertEqual(verdict.decision, ArchitectureGateDecision.BLOCK)
        self.assertIn("committed closure artifact", verdict.reason)

    def test_automation_gate_allows_manually_confirmed_high_risk_semiauto(self) -> None:
        gate = AutomationReadinessGate(
            AutomationReadiness(
                map_land_verifier_ready=True,
                battle_result_verifier_ready=True,
                team_state_verifier_ready=True,
                closure_gate_ready=True,
                accepted_actions=frozenset({ActionType.ATTACK_LAND}),
            )
        )
        verdict = gate.evaluate(
            ActionType.ATTACK_LAND,
            mode=AutomationMode.SEMI_AUTO,
            human_confirmed=True,
        )

        self.assertEqual(verdict.decision, ArchitectureGateDecision.ALLOW)
        self.assertIn("verifier prerequisites", verdict.reason)

    def test_evidence_capture_requires_bound_low_risk_manual_confirmation(self) -> None:
        unconfirmed = AutomationReadinessGate.for_evidence_capture(
            ActionType.CLAIM_CHAPTER_REWARD,
            human_confirmed=False,
        )
        confirmed = AutomationReadinessGate.for_evidence_capture(
            ActionType.CLAIM_CHAPTER_REWARD,
            human_confirmed=True,
        )

        missing_confirmation = unconfirmed.evaluate(
            ActionType.CLAIM_CHAPTER_REWARD,
            mode=AutomationMode.EVIDENCE_CAPTURE,
        )
        wrong_action = confirmed.evaluate(
            ActionType.RECRUIT_SOLDIERS,
            mode=AutomationMode.EVIDENCE_CAPTURE,
        )
        high_risk = confirmed.evaluate(
            ActionType.ATTACK_LAND,
            mode=AutomationMode.EVIDENCE_CAPTURE,
            human_confirmed=True,
        )
        allowed = confirmed.evaluate(
            ActionType.CLAIM_CHAPTER_REWARD,
            mode=AutomationMode.EVIDENCE_CAPTURE,
        )

        self.assertEqual(missing_confirmation.decision, ArchitectureGateDecision.BLOCK)
        self.assertEqual(wrong_action.decision, ArchitectureGateDecision.BLOCK)
        self.assertEqual(high_risk.decision, ArchitectureGateDecision.BLOCK)
        self.assertEqual(allowed.decision, ArchitectureGateDecision.ALLOW)

        with self.assertRaises(ValueError):
            AutomationReadinessGate.for_evidence_capture(
                ActionType.ATTACK_LAND,
                human_confirmed=True,
            )

    def test_low_risk_semantic_target_gate_requires_visible_enabled_bbox(self) -> None:
        missing = validate_low_risk_semantic_target(_action(ActionType.CLAIM_CHAPTER_REWARD, 100))
        disabled = validate_low_risk_semantic_target(
            _action(
                ActionType.RECRUIT_SOLDIERS,
                100,
                recruit_button={
                    "visible": True,
                    "enabled": False,
                    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                },
            )
        )
        invalid_bbox = validate_low_risk_semantic_target(
            _action(
                ActionType.RECRUIT_SOLDIERS,
                100,
                recruit_button={
                    "visible": True,
                    "enabled": True,
                    "bbox": {"x_min": 900, "y_min": 800, "x_max": 700, "y_max": 900},
                },
            )
        )

        self.assertEqual(missing.decision, ArchitectureGateDecision.BLOCK)
        self.assertEqual(disabled.decision, ArchitectureGateDecision.BLOCK)
        self.assertEqual(invalid_bbox.decision, ArchitectureGateDecision.BLOCK)

        for invalid_value in (True, "700", float("nan"), float("inf")):
            with self.subTest(invalid_value=invalid_value):
                verdict = validate_low_risk_semantic_target(
                    _action(
                        ActionType.RECRUIT_SOLDIERS,
                        100,
                        recruit_button={
                            "visible": True,
                            "enabled": True,
                            "bbox": {
                                "x_min": invalid_value,
                                "y_min": 800,
                                "x_max": 900,
                                "y_max": 900,
                            },
                        },
                    )
                )
                self.assertEqual(verdict.decision, ArchitectureGateDecision.BLOCK)

    def test_low_risk_semantic_target_gate_allows_upgrade_confirm_bbox(self) -> None:
        verdict = validate_low_risk_semantic_target(
            _action(
                ActionType.UPGRADE_BUILDING,
                100,
                upgrade_dialog={
                    "visible": True,
                    "confirm_button": {
                        "visible": True,
                        "enabled": True,
                        "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
                    },
                },
            )
        )

        self.assertEqual(verdict.decision, ArchitectureGateDecision.ALLOW)
        self.assertEqual(verdict.details["target"], "upgrade_dialog.confirm_button")

    def test_low_risk_semantic_target_gate_skips_non_low_risk_actions(self) -> None:
        verdict = validate_low_risk_semantic_target(_action(ActionType.WAIT_FOR_STAMINA, 100))

        self.assertEqual(verdict.decision, ArchitectureGateDecision.SKIP)


def _state_with_two_close_candidates():
    from pioneer_agent.core.models import RuntimeState

    return RuntimeState(
        economy={"reserve_troops": 5000},
        teams=[
            {
                "team_id": "team-1",
                "soldiers": 2000,
                "max_soldiers": 5000,
                "status": "idle",
                "can_recruit_now": True,
            }
        ],
        city={
            "upgradeable_buildings": [
                {
                    "building_id": "main_hall",
                    "building_name": "君王殿",
                    "resource_ready": True,
                    "chapter_relevance": "prepare_next_chapter",
                }
            ]
        },
    )


if __name__ == "__main__":
    unittest.main()
