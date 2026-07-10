from __future__ import annotations

import unittest

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction
from pioneer_agent.verifier import (
    DeltaMatchPolicy,
    DeltaOperator,
    ExpectedStateDelta,
    VerifierGateDecision,
    VerifierRegistry,
    VerifierSpec,
)


class VerifierRegistryTests(unittest.TestCase):
    def test_wait_action_does_not_require_verifier(self) -> None:
        verdict = VerifierRegistry().evaluate(ActionType.WAIT_FOR_RESOURCE)

        self.assertEqual(verdict.decision, VerifierGateDecision.ALLOW)

    def test_high_risk_ui_action_without_default_spec_is_blocked(self) -> None:
        verdict = VerifierRegistry().evaluate(ActionType.ABANDON_LAND)

        self.assertEqual(verdict.decision, VerifierGateDecision.BLOCK)
        self.assertIn("requires a verifier", verdict.reason)

    def test_default_specs_allow_low_risk_pr6_actions(self) -> None:
        registry = VerifierRegistry()

        expected = {
            ActionType.CLAIM_CHAPTER_REWARD: (
                10.0,
                DeltaMatchPolicy.ALL,
                [
                    (
                        "progress.current_chapter_id",
                        DeltaOperator.EQUALS,
                        None,
                        None,
                        None,
                        "chapter_id",
                        "chapter_id",
                    ),
                    (
                        "progress.chapter_claimable",
                        DeltaOperator.EQUALS,
                        None,
                        None,
                        None,
                        None,
                        None,
                    ),
                ],
            ),
            ActionType.RECRUIT_SOLDIERS: (
                30.0,
                DeltaMatchPolicy.ANY,
                [
                    (
                        "soldiers",
                        DeltaOperator.GREATER_THAN_BEFORE,
                        "teams",
                        "team_id",
                        "team_id",
                        None,
                        None,
                    ),
                    (
                        "recruit_finish_time",
                        DeltaOperator.BECOMES_PRESENT,
                        "teams",
                        "team_id",
                        "team_id",
                        None,
                        None,
                    ),
                ],
            ),
            ActionType.UPGRADE_BUILDING: (
                20.0,
                DeltaMatchPolicy.ALL,
                [
                    (
                        "level",
                        DeltaOperator.INCREASES_TO,
                        "city.buildings",
                        "name",
                        "building_name",
                        "current_level",
                        "target_level",
                    ),
                ],
            ),
        }

        for action_type, (timeout, match_policy, deltas) in expected.items():
            with self.subTest(action_type=action_type.value):
                verdict = registry.evaluate(action_type)
                spec = registry.get(action_type)

                self.assertEqual(verdict.decision, VerifierGateDecision.ALLOW)
                self.assertEqual(verdict.timeout_seconds, timeout)
                self.assertEqual(spec.timeout_seconds if spec else None, timeout)
                self.assertEqual(spec.match_policy if spec else None, match_policy)
                self.assertEqual(
                    [
                        (
                            delta.path,
                            delta.operator,
                            delta.collection_path,
                            delta.identity_field,
                            delta.identity_param,
                            delta.before_param,
                            delta.expected_after_param,
                        )
                        for delta in spec.expected_deltas
                    ],
                    deltas,
                )

    def test_action_binding_resolves_target_identity_and_required_params(self) -> None:
        registry = VerifierRegistry()
        action = CandidateAction(
            action_id="recruit-team-2",
            action_type=ActionType.RECRUIT_SOLDIERS,
            params={"team_id": "team-2"},
        )

        verdict = registry.evaluate_action(action)
        bound = registry.get_for_action(action)

        self.assertEqual(verdict.decision, VerifierGateDecision.ALLOW)
        self.assertIsNotNone(bound)
        self.assertEqual(
            [delta.identity_value for delta in bound.expected_deltas],
            ["team-2", "team-2"],
        )
        self.assertTrue(all(delta.identity_param is None for delta in bound.expected_deltas))

        for action_type, params in (
            (ActionType.CLAIM_CHAPTER_REWARD, {}),
            (ActionType.RECRUIT_SOLDIERS, {}),
            (ActionType.UPGRADE_BUILDING, {"building_name": "仓库"}),
        ):
            with self.subTest(action_type=action_type.value):
                missing = CandidateAction(
                    action_id=f"missing-{action_type.value}",
                    action_type=action_type,
                    params=params,
                )
                blocked = registry.evaluate_action(missing)
                self.assertEqual(blocked.decision, VerifierGateDecision.BLOCK)
                self.assertIn("missing required action param", blocked.reason)

    def test_action_binding_rejects_bool_and_invalid_upgrade_levels(self) -> None:
        registry = VerifierRegistry()
        cases = (
            CandidateAction(
                action_id="claim-bool",
                action_type=ActionType.CLAIM_CHAPTER_REWARD,
                params={"chapter_id": True},
            ),
            CandidateAction(
                action_id="recruit-numeric",
                action_type=ActionType.RECRUIT_SOLDIERS,
                params={"team_id": 1},
            ),
            CandidateAction(
                action_id="upgrade-equal",
                action_type=ActionType.UPGRADE_BUILDING,
                params={
                    "building_name": "仓库",
                    "current_level": 11,
                    "target_level": 11,
                },
            ),
        )

        for action in cases:
            with self.subTest(action_id=action.action_id):
                verdict = registry.evaluate_action(action)
                self.assertEqual(verdict.decision, VerifierGateDecision.BLOCK)

    def test_spec_must_declare_expected_delta(self) -> None:
        registry = VerifierRegistry(
            {
                ActionType.RECRUIT_SOLDIERS: VerifierSpec(
                    action_type=ActionType.RECRUIT_SOLDIERS,
                    expected_deltas=(),
                    timeout_seconds=10.0,
                )
            }
        )

        verdict = registry.evaluate(ActionType.RECRUIT_SOLDIERS)

        self.assertEqual(verdict.decision, VerifierGateDecision.BLOCK)
        self.assertIn("expected state delta", verdict.reason)

    def test_spec_must_declare_positive_timeout(self) -> None:
        registry = VerifierRegistry(
            {
                ActionType.RECRUIT_SOLDIERS: VerifierSpec(
                    action_type=ActionType.RECRUIT_SOLDIERS,
                    expected_deltas=(
                        ExpectedStateDelta(
                            path="teams.0.soldiers",
                            expected_after=1000,
                        ),
                    ),
                    timeout_seconds=0,
                )
            }
        )

        verdict = registry.evaluate(ActionType.RECRUIT_SOLDIERS)

        self.assertEqual(verdict.decision, VerifierGateDecision.BLOCK)
        self.assertIn("timeout", verdict.reason)

    def test_complete_spec_allows_ui_action(self) -> None:
        registry = VerifierRegistry(
            {
                ActionType.RECRUIT_SOLDIERS: VerifierSpec(
                    action_type=ActionType.RECRUIT_SOLDIERS,
                    expected_deltas=(
                        ExpectedStateDelta(
                            path="teams.0.recruiting",
                            expected_after=True,
                        ),
                    ),
                    timeout_seconds=30.0,
                    match_policy=DeltaMatchPolicy.ALL,
                )
            }
        )

        verdict = registry.evaluate(ActionType.RECRUIT_SOLDIERS)

        self.assertEqual(verdict.decision, VerifierGateDecision.ALLOW)
        self.assertEqual(verdict.timeout_seconds, 30.0)


if __name__ == "__main__":
    unittest.main()
