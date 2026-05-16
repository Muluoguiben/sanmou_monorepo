from __future__ import annotations

import unittest

from pioneer_agent.core.device import CapabilityFlags
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.risk import RiskLevel
from pioneer_agent.safety.guard import GuardDecision, SafetyGuard


class SafetyGuardTests(unittest.TestCase):
    def test_low_risk_allowlisted_action_is_allowed(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.UPGRADE_BUILDING,
            risk={"level": "low"},
            capabilities=CapabilityFlags(input_control=True),
        )

        self.assertEqual(verdict.decision, GuardDecision.ALLOW)
        self.assertTrue(verdict.allowed)

    def test_high_risk_action_requires_confirmation(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.UPGRADE_BUILDING,
            risk=RiskLevel.HIGH,
            capabilities=CapabilityFlags(input_control=True),
        )

        self.assertEqual(verdict.decision, GuardDecision.REQUIRE_CONFIRMATION)

    def test_observe_only_blocks_ui_execution(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.CLAIM_CHAPTER_REWARD,
            risk="low",
            capabilities=CapabilityFlags(observe_only=True),
        )

        self.assertEqual(verdict.decision, GuardDecision.BLOCK)
        self.assertIn("input_control", verdict.reason)

    def test_sensitive_actions_require_confirmation_by_default(self) -> None:
        for action_type in (
            ActionType.ATTACK_LAND,
            ActionType.ABANDON_LAND,
            ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM,
        ):
            verdict = SafetyGuard().evaluate(
                action_type,
                capabilities=CapabilityFlags(input_control=True),
            )
            self.assertEqual(verdict.decision, GuardDecision.REQUIRE_CONFIRMATION)

    def test_non_allowlisted_action_is_blocked(self) -> None:
        verdict = SafetyGuard(input_allowlist=[]).evaluate(
            ActionType.UPGRADE_BUILDING,
            capabilities=CapabilityFlags(input_control=True),
        )

        self.assertEqual(verdict.decision, GuardDecision.BLOCK)
        self.assertIn("allowlist", verdict.reason)


if __name__ == "__main__":
    unittest.main()
