"""Tests for the ActionType → handler dispatch table."""
from __future__ import annotations

import unittest

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction
from pioneer_agent.executor.action_handlers import dispatch
from pioneer_agent.executor.ui_runner import UIActionRunner


class _NullUI:
    """All handlers take a UIActions, but wait + pending paths never call it."""


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


if __name__ == "__main__":
    unittest.main()
