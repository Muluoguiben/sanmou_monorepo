from __future__ import annotations

import unittest

from pioneer_agent.core.enums import ActionType
from pioneer_agent.verifier import (
    ExpectedStateDelta,
    VerifierGateDecision,
    VerifierRegistry,
    VerifierSpec,
)


class VerifierRegistryTests(unittest.TestCase):
    def test_wait_action_does_not_require_verifier(self) -> None:
        verdict = VerifierRegistry().evaluate(ActionType.WAIT_FOR_RESOURCE)

        self.assertEqual(verdict.decision, VerifierGateDecision.ALLOW)

    def test_ui_action_without_spec_is_blocked(self) -> None:
        verdict = VerifierRegistry().evaluate(ActionType.RECRUIT_SOLDIERS)

        self.assertEqual(verdict.decision, VerifierGateDecision.BLOCK)
        self.assertIn("requires a verifier", verdict.reason)

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
                )
            }
        )

        verdict = registry.evaluate(ActionType.RECRUIT_SOLDIERS)

        self.assertEqual(verdict.decision, VerifierGateDecision.ALLOW)
        self.assertEqual(verdict.timeout_seconds, 30.0)


if __name__ == "__main__":
    unittest.main()
