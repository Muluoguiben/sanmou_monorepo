"""DispatchGuard: the single seam for every input-dispatch decision."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction
from pioneer_agent.runbook.models import RunbookDecision
from pioneer_agent.runtime.dispatch_guard import KILL_SWITCH_REASON, DispatchGuard
from pioneer_agent.safety.kill_switch import KillSwitch


def _action(action_type: ActionType = ActionType.ATTACK_LAND) -> CandidateAction:
    return CandidateAction(action_id="a", action_type=action_type)


def _decision(**kwargs) -> RunbookDecision:
    defaults = {"phase_id": "p1", "previous_phase_id": "p1"}
    defaults.update(kwargs)
    return RunbookDecision(**defaults)


class DispatchGuardTests(unittest.TestCase):
    def test_allows_by_default(self) -> None:
        guard = DispatchGuard()
        self.assertTrue(guard.action_verdict(_action()).allowed)
        self.assertTrue(guard.recovery_verdict().allowed)

    def test_kill_switch_denies_action_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            switch = KillSwitch(Path(tmp) / "STOP")
            guard = DispatchGuard(kill_switch=switch)
            switch.trigger()
            self.assertEqual(guard.action_verdict(_action()).reason, KILL_SWITCH_REASON)
            self.assertEqual(guard.recovery_verdict().reason, KILL_SWITCH_REASON)
            switch.clear()
            self.assertTrue(guard.action_verdict(_action()).allowed)
            self.assertTrue(guard.recovery_verdict().allowed)

    def test_blocking_hold_denies_action_and_recovery(self) -> None:
        guard = DispatchGuard()
        for hold in ("abort_triggered", "human_gate_pending", "runbook_completed"):
            guard.update_decision(_decision(hold_reason=hold))
            self.assertEqual(guard.action_verdict(_action()).reason, f"runbook_hold:{hold}")
            self.assertEqual(guard.recovery_verdict().reason, f"runbook_hold:{hold}")

    def test_non_blocking_holds_allow_dispatch(self) -> None:
        guard = DispatchGuard()
        for hold in (None, "exit_metrics_unknown", "abort_metrics_unknown", "transition_deferred"):
            guard.update_decision(_decision(hold_reason=hold))
            self.assertTrue(guard.action_verdict(_action()).allowed, hold)
            self.assertTrue(guard.recovery_verdict().allowed, hold)

    def test_allowlist_denies_action_but_not_recovery(self) -> None:
        guard = DispatchGuard()
        guard.update_decision(
            _decision(selector_hints={"allowed_action_types": ["claim_chapter_reward"]})
        )
        self.assertEqual(guard.action_verdict(_action()).reason, "runbook_action_filter")
        self.assertTrue(guard.action_verdict(_action(ActionType.WAIT_FOR_STAMINA)).allowed)
        self.assertTrue(guard.recovery_verdict().allowed)


if __name__ == "__main__":
    unittest.main()
