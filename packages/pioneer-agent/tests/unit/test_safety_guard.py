from __future__ import annotations

import unittest

from pioneer_agent.core.device import CapabilityFlags
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.risk import RiskLevel
from pioneer_agent.safety.guard import GuardDecision, SafetyGuard, SessionMode


class SafetyGuardTests(unittest.TestCase):
    def test_low_risk_allowlisted_action_is_allowed(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.UPGRADE_BUILDING,
            risk={"level": "low"},
            capabilities=CapabilityFlags(input_control=True),
            session_mode=SessionMode.AUTOMATION_TEST,
        )

        self.assertEqual(verdict.decision, GuardDecision.ALLOW)
        self.assertTrue(verdict.allowed)

    def test_high_risk_action_requires_confirmation(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.UPGRADE_BUILDING,
            risk=RiskLevel.HIGH,
            capabilities=CapabilityFlags(input_control=True),
            session_mode=SessionMode.LIVE,
        )

        self.assertEqual(verdict.decision, GuardDecision.REQUIRE_CONFIRMATION)

    def test_high_risk_action_allows_with_confirmation_token(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.UPGRADE_BUILDING,
            risk=RiskLevel.HIGH,
            capabilities=CapabilityFlags(input_control=True),
            session_mode=SessionMode.LIVE,
            confirmation_token="manual-ok",
        )

        self.assertEqual(verdict.decision, GuardDecision.ALLOW)
        self.assertIn("confirmation token", verdict.reason)

    def test_observe_only_blocks_ui_execution(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.CLAIM_CHAPTER_REWARD,
            risk="low",
            capabilities=CapabilityFlags(observe_only=True),
            session_mode=SessionMode.LIVE,
        )

        self.assertEqual(verdict.decision, GuardDecision.BLOCK)
        self.assertIn("input_control", verdict.reason)

    def test_advisor_session_mode_blocks_ui_execution(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.CLAIM_CHAPTER_REWARD,
            risk="low",
            capabilities=CapabilityFlags(input_control=True),
            session_mode=SessionMode.ADVISOR,
        )

        self.assertEqual(verdict.decision, GuardDecision.BLOCK)
        self.assertIn("session mode advisor", verdict.reason)

    def test_automation_test_session_mode_can_execute_allowlisted_action(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.CLAIM_CHAPTER_REWARD,
            risk="low",
            capabilities=CapabilityFlags(input_control=True),
            session_mode="automation_test",
        )

        self.assertEqual(verdict.decision, GuardDecision.ALLOW)

    def test_sensitive_actions_require_confirmation_by_default(self) -> None:
        for action_type in (
            ActionType.ATTACK_LAND,
            ActionType.ABANDON_LAND,
            ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM,
        ):
            verdict = SafetyGuard().evaluate(
                action_type,
                capabilities=CapabilityFlags(input_control=True),
                session_mode=SessionMode.LIVE,
            )
            self.assertEqual(verdict.decision, GuardDecision.REQUIRE_CONFIRMATION)

    def test_sensitive_action_allows_with_confirmation_token(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.ATTACK_LAND,
            capabilities=CapabilityFlags(input_control=True),
            session_mode=SessionMode.LIVE,
            confirmation_token="manual-ok",
        )

        self.assertEqual(verdict.decision, GuardDecision.ALLOW)

    def test_non_allowlisted_action_is_blocked(self) -> None:
        verdict = SafetyGuard(input_allowlist=[]).evaluate(
            ActionType.UPGRADE_BUILDING,
            capabilities=CapabilityFlags(input_control=True),
            session_mode=SessionMode.LIVE,
        )

        self.assertEqual(verdict.decision, GuardDecision.BLOCK)
        self.assertIn("allowlist", verdict.reason)

    def test_missing_capabilities_are_blocked(self) -> None:
        verdict = SafetyGuard().evaluate(
            ActionType.CLAIM_CHAPTER_REWARD,
            session_mode=SessionMode.LIVE,
        )

        self.assertEqual(verdict.decision, GuardDecision.BLOCK)
        self.assertIn("capabilities", verdict.reason)

    def test_missing_or_unknown_session_mode_is_blocked(self) -> None:
        for session_mode in (None, "not-a-session"):
            with self.subTest(session_mode=session_mode):
                verdict = SafetyGuard().evaluate(
                    ActionType.CLAIM_CHAPTER_REWARD,
                    capabilities=CapabilityFlags(input_control=True),
                    session_mode=session_mode,
                )
                self.assertEqual(verdict.decision, GuardDecision.BLOCK)
                self.assertIn("session mode", verdict.reason)


if __name__ == "__main__":
    unittest.main()
