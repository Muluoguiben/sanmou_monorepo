from __future__ import annotations

import unittest

from pioneer_agent.executor.input_policy import InputKind, InputPolicy


class InputPolicyTests(unittest.TestCase):
    def test_registered_button_is_allowed_by_default(self) -> None:
        verdict = InputPolicy().evaluate_button("city", registered_keys=["city"])

        self.assertTrue(verdict.allowed)
        self.assertEqual(verdict.kind, InputKind.CLICK_BUTTON)

    def test_unregistered_button_is_blocked(self) -> None:
        verdict = InputPolicy().evaluate_button("unknown", registered_keys=["city"])

        self.assertFalse(verdict.allowed)
        self.assertIn("not registered", verdict.reason)

    def test_dynamic_query_requires_allowlist(self) -> None:
        verdict = InputPolicy().evaluate_element_query("征兵所 building")

        self.assertFalse(verdict.allowed)
        self.assertIn("not allowlisted", verdict.reason)

    def test_dynamic_query_can_be_allowlisted(self) -> None:
        policy = InputPolicy(allowed_element_queries=frozenset({"征兵所 building"}))

        verdict = policy.evaluate_element_query("征兵所 building")

        self.assertTrue(verdict.allowed)

    def test_semantic_bbox_target_is_allowlisted_by_default(self) -> None:
        verdict = InputPolicy().evaluate_semantic_target("chapter_claim_button")

        self.assertTrue(verdict.allowed)
        self.assertEqual(verdict.kind, InputKind.CLICK_SEMANTIC_BBOX)

    def test_building_upgrade_button_is_allowlisted_by_default(self) -> None:
        verdict = InputPolicy().evaluate_semantic_target("building_upgrade_button")

        self.assertTrue(verdict.allowed)
        self.assertEqual(verdict.kind, InputKind.CLICK_SEMANTIC_BBOX)

    def test_unknown_semantic_bbox_target_is_blocked(self) -> None:
        verdict = InputPolicy().evaluate_semantic_target("unknown_button")

        self.assertFalse(verdict.allowed)
        self.assertIn("not allowlisted", verdict.reason)

    def test_drag_is_opt_in(self) -> None:
        self.assertFalse(InputPolicy().evaluate_drag().allowed)
        self.assertTrue(InputPolicy(allow_map_drag=True).evaluate_drag().allowed)

    def test_escape_key_is_allowed_by_default(self) -> None:
        self.assertTrue(InputPolicy().evaluate_key("escape").allowed)
        self.assertFalse(InputPolicy().evaluate_key("enter").allowed)


if __name__ == "__main__":
    unittest.main()
