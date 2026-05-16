from __future__ import annotations

import unittest

from pioneer_agent.verifier.base import (
    ExpectedStateDelta,
    VerificationStatus,
    VerifierBase,
)


class VerifierBaseTests(unittest.TestCase):
    def test_verifier_success(self) -> None:
        verifier = VerifierBase(
            [ExpectedStateDelta(path="city.level", before=1, expected_after=2)],
            timeout_seconds=3.0,
        )

        result = verifier.verify(
            before_state={"city": {"level": 1}},
            after_state={"city": {"level": 2}},
        )

        self.assertEqual(result.status, VerificationStatus.VERIFIED)
        self.assertTrue(result.verified)
        self.assertEqual(result.checked, ("city.level",))
        self.assertEqual(result.timeout_seconds, 3.0)

    def test_verifier_fail(self) -> None:
        verifier = VerifierBase(
            [ExpectedStateDelta(path="economy.wood", expected_after=100)]
        )

        result = verifier.verify(
            before_state={"economy": {"wood": 50}},
            after_state={"economy": {"wood": 75}},
        )

        self.assertEqual(result.status, VerificationStatus.FAILED)
        self.assertIn("expected economy.wood", result.reason)

    def test_verifier_unknown_without_expected_delta(self) -> None:
        result = VerifierBase().verify(before_state={}, after_state={})

        self.assertEqual(result.status, VerificationStatus.UNKNOWN)

    def test_verifier_supports_list_index_paths(self) -> None:
        verifier = VerifierBase(
            [ExpectedStateDelta(path="teams.0.recruiting", before=False, expected_after=True)]
        )

        result = verifier.verify(
            before_state={"teams": [{"recruiting": False}]},
            after_state={"teams": [{"recruiting": True}]},
        )

        self.assertEqual(result.status, VerificationStatus.VERIFIED)


if __name__ == "__main__":
    unittest.main()
