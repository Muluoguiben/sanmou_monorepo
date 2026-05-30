from __future__ import annotations

import unittest

from pioneer_agent.core.enums import ActionType
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
                [("progress.chapter_claimable", DeltaOperator.EQUALS)],
            ),
            ActionType.RECRUIT_SOLDIERS: (
                30.0,
                DeltaMatchPolicy.ANY,
                [
                    ("teams.0.soldiers", DeltaOperator.GREATER_THAN_BEFORE),
                    ("teams.0.recruit_finish_time", DeltaOperator.PRESENT),
                    ("economy.reserve_troops", DeltaOperator.LESS_THAN_BEFORE),
                ],
            ),
            ActionType.UPGRADE_BUILDING: (
                20.0,
                DeltaMatchPolicy.ANY,
                [
                    ("city.buildings.0.level", DeltaOperator.GREATER_THAN_BEFORE),
                    ("economy.resources.wood", DeltaOperator.LESS_THAN_BEFORE),
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
                    [(delta.path, delta.operator) for delta in spec.expected_deltas],
                    deltas,
                )

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
