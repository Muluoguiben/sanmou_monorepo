from __future__ import annotations

import unittest

from pioneer_agent.verifier.base import (
    DeltaMatchPolicy,
    DeltaOperator,
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

    def test_any_policy_accepts_one_matching_delta(self) -> None:
        verifier = VerifierBase(
            [
                ExpectedStateDelta(
                    path="teams.0.soldiers",
                    operator=DeltaOperator.GREATER_THAN_BEFORE,
                ),
                ExpectedStateDelta(
                    path="teams.0.recruit_finish_time",
                    operator=DeltaOperator.PRESENT,
                ),
            ],
            match_policy=DeltaMatchPolicy.ANY,
        )

        result = verifier.verify(
            before_state={"teams": [{"soldiers": 22000}]},
            after_state={"teams": [{"soldiers": 22000, "recruit_finish_time": "00:12:00"}]},
        )

        self.assertEqual(result.status, VerificationStatus.VERIFIED)
        self.assertIn("at least one", result.reason)

    def test_any_policy_fails_when_no_delta_matches(self) -> None:
        verifier = VerifierBase(
            [
                ExpectedStateDelta(
                    path="economy.reserve_troops",
                    operator=DeltaOperator.LESS_THAN_BEFORE,
                ),
                ExpectedStateDelta(
                    path="teams.0.recruit_finish_time",
                    operator=DeltaOperator.PRESENT,
                ),
            ],
            match_policy=DeltaMatchPolicy.ANY,
        )

        result = verifier.verify(
            before_state={"economy": {"reserve_troops": 40000}, "teams": [{}]},
            after_state={"economy": {"reserve_troops": 40000}, "teams": [{}]},
        )

        self.assertEqual(result.status, VerificationStatus.FAILED)
        self.assertIn("no expected state delta matched", result.reason)

    def test_absent_operator_accepts_removed_path(self) -> None:
        verifier = VerifierBase(
            [ExpectedStateDelta(path="city.upgradeable_buildings.0", operator=DeltaOperator.ABSENT)]
        )

        result = verifier.verify(
            before_state={"city": {"upgradeable_buildings": [{"building_id": "main_hall"}]}},
            after_state={"city": {"upgradeable_buildings": []}},
        )

        self.assertEqual(result.status, VerificationStatus.VERIFIED)


if __name__ == "__main__":
    unittest.main()
