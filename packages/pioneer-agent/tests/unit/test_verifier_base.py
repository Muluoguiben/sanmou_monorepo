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

    def test_entity_selector_survives_reorder_and_reports_target_label(self) -> None:
        verifier = VerifierBase(
            [
                ExpectedStateDelta(
                    path="soldiers",
                    operator=DeltaOperator.GREATER_THAN_BEFORE,
                    collection_path="teams",
                    identity_field="team_id",
                    identity_value="team-2",
                )
            ]
        )

        result = verifier.verify(
            before_state={
                "teams": [
                    {"team_id": "team-1", "soldiers": 30000},
                    {"team_id": "team-2", "soldiers": 22000},
                ]
            },
            after_state={
                "teams": [
                    {"team_id": "team-2", "soldiers": 24000},
                    {"team_id": "team-1", "soldiers": 30000},
                ]
            },
        )

        self.assertEqual(result.status, VerificationStatus.VERIFIED)
        self.assertEqual(result.checked, ("teams[team_id='team-2'].soldiers",))

    def test_preflight_rejects_duplicate_target_and_stale_timer(self) -> None:
        selector = ExpectedStateDelta(
            path="recruit_finish_time",
            operator=DeltaOperator.BECOMES_PRESENT,
            collection_path="teams",
            identity_field="team_id",
            identity_value="team-2",
        )
        verifier = VerifierBase([selector])
        duplicate = {
            "teams": [
                {"team_id": "team-2"},
                {"team_id": "team-2"},
            ]
        }

        preflight = verifier.validate_before(duplicate)
        stale_preflight = verifier.validate_before(
            {
                "teams": [
                    {"team_id": "team-2", "recruit_finish_time": "00:12:00"}
                ]
            }
        )
        stale = verifier.verify(
            before_state={
                "teams": [
                    {"team_id": "team-2", "recruit_finish_time": "00:12:00"}
                ]
            },
            after_state={
                "teams": [
                    {"team_id": "team-2", "recruit_finish_time": "00:11:59"}
                ]
            },
        )

        self.assertEqual(preflight.status, VerificationStatus.FAILED)
        self.assertIn("got 2", preflight.reason)
        self.assertEqual(stale_preflight.status, VerificationStatus.FAILED)
        self.assertIn("before dispatch", stale_preflight.reason)
        self.assertEqual(stale.status, VerificationStatus.FAILED)
        self.assertIn("absent or empty", stale.reason)

    def test_any_policy_cannot_hide_stale_timer_behind_soldier_increase(self) -> None:
        verifier = VerifierBase(
            [
                ExpectedStateDelta(
                    path="soldiers",
                    operator=DeltaOperator.GREATER_THAN_BEFORE,
                    collection_path="teams",
                    identity_field="team_id",
                    identity_value="team-2",
                ),
                ExpectedStateDelta(
                    path="recruit_finish_time",
                    operator=DeltaOperator.BECOMES_PRESENT,
                    collection_path="teams",
                    identity_field="team_id",
                    identity_value="team-2",
                ),
            ],
            match_policy=DeltaMatchPolicy.ANY,
        )

        result = verifier.verify(
            before_state={
                "teams": [
                    {
                        "team_id": "team-2",
                        "soldiers": 22000,
                        "recruit_finish_time": "00:12:00",
                    }
                ]
            },
            after_state={
                "teams": [
                    {
                        "team_id": "team-2",
                        "soldiers": 24000,
                        "recruit_finish_time": "00:11:59",
                    }
                ]
            },
        )

        self.assertEqual(result.status, VerificationStatus.FAILED)
        self.assertIn("before dispatch", result.reason)

    def test_increases_to_requires_lower_baseline_and_exact_target(self) -> None:
        delta = ExpectedStateDelta(
            path="level",
            operator=DeltaOperator.INCREASES_TO,
            expected_after=11,
            collection_path="city.buildings",
            identity_field="name",
            identity_value="Main Hall",
        )
        verifier = VerifierBase([delta])

        equal_baseline = verifier.validate_before(
            {"city": {"buildings": [{"name": "Main Hall", "level": 11}]}}
        )
        skipped_target = verifier.verify(
            {"city": {"buildings": [{"name": "Main Hall", "level": 10}]}},
            {"city": {"buildings": [{"name": "Main Hall", "level": 12}]}},
        )
        exact_target = verifier.verify(
            {"city": {"buildings": [{"name": "Main Hall", "level": 10}]}},
            {"city": {"buildings": [{"name": "Main Hall", "level": 11}]}},
        )

        self.assertEqual(equal_baseline.status, VerificationStatus.FAILED)
        self.assertIn("below target", equal_baseline.reason)
        self.assertEqual(skipped_target.status, VerificationStatus.FAILED)
        self.assertIn("reach 11", skipped_target.reason)
        self.assertEqual(exact_target.status, VerificationStatus.VERIFIED)


if __name__ == "__main__":
    unittest.main()
