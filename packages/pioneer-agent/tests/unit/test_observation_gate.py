from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta, timezone

from pydantic import ValidationError

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import (
    CandidateAction,
    FieldMeta,
    ObservationSnapshot,
    RuntimeState,
)
from pioneer_agent.runtime.observation_gate import (
    ObservationGateDecision,
    validate_dispatch_observation,
    validate_post_observation,
)


BUTTON = {
    "visible": True,
    "enabled": True,
    "bbox": {"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
}


def _snapshot(
    *,
    observed_state: RuntimeState,
    page_type: str,
    domains: list[str],
    meta_key: str,
    meta_source: str,
    captured_at: datetime,
    observation_id: str,
) -> ObservationSnapshot:
    state = observed_state.model_copy(deep=True)
    state.field_meta[meta_key] = FieldMeta(
        value="loaded",
        source=meta_source,
        updated_at=captured_at,
        observation_id=observation_id,
    )
    return ObservationSnapshot(
        observation_id=observation_id,
        captured_at=captured_at,
        frame_sha256="a" * 64,
        frame_size=(1920, 1080),
        page_type=page_type,
        domains_run=domains,
        observed_state=state,
        source="vision_sync",
    )


class ObservationGateTests(unittest.TestCase):
    def test_observation_source_is_required_and_cannot_default_to_live_trust(self) -> None:
        with self.assertRaises(ValidationError):
            ObservationSnapshot(
                observation_id="missing-source",
                captured_at=datetime.now(UTC),
                frame_sha256="a" * 64,
                frame_size=(1920, 1080),
                observed_state=RuntimeState(),
            )

    def test_claim_dispatch_requires_current_frame_target_and_bbox(self) -> None:
        captured_at = datetime.now(UTC)
        action = CandidateAction(
            action_id="claim-17",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
            params={"chapter_id": 17, "claim_button": BUTTON},
        )
        observation = _snapshot(
            observed_state=RuntimeState(
                progress={
                    "current_chapter_id": 17,
                    "chapter_claimable": True,
                    "chapter_claim_button": BUTTON,
                }
            ),
            page_type="chapter",
            domains=["resource_bar", "chapter_panel"],
            meta_key="progress.chapter_panel",
            meta_source="vision.chapter_panel",
            captured_at=captured_at,
            observation_id="claim-current",
        )

        verdict = validate_dispatch_observation(
            action,
            observation,
            now=captured_at + timedelta(seconds=1),
        )
        stale = validate_dispatch_observation(
            action,
            observation,
            now=captured_at + timedelta(seconds=31),
        )
        wrong_bbox_action = action.model_copy(
            update={
                "params": {
                    **action.params,
                    "claim_button": {
                        **BUTTON,
                        "bbox": {"x_min": 600, "y_min": 800, "x_max": 900, "y_max": 900},
                    },
                }
            }
        )
        wrong_bbox = validate_dispatch_observation(
            wrong_bbox_action,
            observation,
            now=captured_at + timedelta(seconds=1),
        )

        self.assertEqual(verdict.decision, ObservationGateDecision.ALLOW)
        self.assertEqual(verdict.verifier_state["progress"]["current_chapter_id"], 17)
        self.assertEqual(stale.decision, ObservationGateDecision.BLOCK)
        self.assertIn("stale", stale.reason)
        self.assertEqual(wrong_bbox.decision, ObservationGateDecision.BLOCK)
        self.assertIn("does not match", wrong_bbox.reason)

    def test_merged_residual_fields_cannot_substitute_for_observed_fields(self) -> None:
        captured_at = datetime.now(UTC)
        action = CandidateAction(
            action_id="claim-17",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
            params={"chapter_id": 17, "claim_button": BUTTON},
        )
        observation = _snapshot(
            observed_state=RuntimeState(
                progress={"current_chapter_id": 17, "chapter_claimable": True}
            ),
            page_type="chapter",
            domains=["resource_bar", "chapter_panel"],
            meta_key="progress.chapter_panel",
            meta_source="vision.chapter_panel",
            captured_at=captured_at,
            observation_id="claim-no-button",
        )

        verdict = validate_dispatch_observation(action, observation, now=captured_at)

        self.assertEqual(verdict.decision, ObservationGateDecision.BLOCK)
        self.assertIn("missing a valid chapter claim button", verdict.reason)

    def test_recruit_target_must_be_unique_in_the_current_frame(self) -> None:
        captured_at = datetime.now(UTC)
        action = CandidateAction(
            action_id="recruit-team-2",
            action_type=ActionType.RECRUIT_SOLDIERS,
            params={"team_id": "team-2", "recruit_button": BUTTON},
        )
        observation = _snapshot(
            observed_state=RuntimeState(
                teams=[
                    {"team_id": "team-2", "soldiers": 22000, "recruit_button": BUTTON},
                    {"team_id": "team-2", "soldiers": 10000, "recruit_button": BUTTON},
                ]
            ),
            page_type="recruit",
            domains=["resource_bar", "recruit_panel"],
            meta_key="teams.recruit_panel",
            meta_source="vision.recruit_panel",
            captured_at=captured_at,
            observation_id="recruit-duplicate",
        )

        verdict = validate_dispatch_observation(action, observation, now=captured_at)

        self.assertEqual(verdict.decision, ObservationGateDecision.BLOCK)
        self.assertIn("got 2", verdict.reason)

    def test_upgrade_confirm_projects_dialog_as_terminal_baseline(self) -> None:
        captured_at = datetime.now(UTC)
        dialog = {
            "visible": True,
            "building_name": "君王殿",
            "current_level": 10,
            "next_level": 11,
            "can_upgrade": True,
            "confirm_button": BUTTON,
        }
        action = CandidateAction(
            action_id="upgrade-main-hall",
            action_type=ActionType.UPGRADE_BUILDING,
            params={
                "building_id": "main_hall",
                "building_name": "君王殿",
                "current_level": 10,
                "target_level": 11,
                "upgrade_dialog": dialog,
            },
        )
        observation = _snapshot(
            observed_state=RuntimeState(city={"upgrade_dialog": dialog}),
            page_type="upgrade_dialog",
            domains=["resource_bar", "upgrade_dialog"],
            meta_key="city.upgrade_dialog",
            meta_source="vision.upgrade_dialog",
            captured_at=captured_at,
            observation_id="upgrade-dialog",
        )

        verdict = validate_dispatch_observation(action, observation, now=captured_at)

        self.assertEqual(verdict.decision, ObservationGateDecision.ALLOW)
        self.assertEqual(
            verdict.verifier_state["city"]["buildings"],
            [{"name": "君王殿", "level": 10}],
        )

    def test_post_observation_must_be_new_later_and_from_required_domain(self) -> None:
        plus_eight = timezone(timedelta(hours=8))
        baseline_time = datetime(2026, 7, 10, 12, 0, 0, tzinfo=plus_eight)
        dispatch_completed = datetime(2026, 7, 10, 4, 0, 1, tzinfo=UTC)
        action = CandidateAction(
            action_id="claim-17",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
            params={"chapter_id": 17, "claim_button": BUTTON},
        )
        baseline = _snapshot(
            observed_state=RuntimeState(
                progress={
                    "current_chapter_id": 17,
                    "chapter_claimable": True,
                    "chapter_claim_button": BUTTON,
                }
            ),
            page_type="chapter",
            domains=["resource_bar", "chapter_panel"],
            meta_key="progress.chapter_panel",
            meta_source="vision.chapter_panel",
            captured_at=baseline_time,
            observation_id="before",
        )
        post_time = datetime(2026, 7, 10, 12, 0, 2, tzinfo=plus_eight)
        post = _snapshot(
            observed_state=RuntimeState(
                progress={"current_chapter_id": 17, "chapter_claimable": False}
            ),
            page_type="chapter",
            domains=["resource_bar", "chapter_panel"],
            meta_key="progress.chapter_panel",
            meta_source="vision.chapter_panel",
            captured_at=post_time,
            observation_id="after",
        )

        allowed = validate_post_observation(
            action,
            baseline,
            post,
            dispatch_completed_at=dispatch_completed,
            now=post_time,
        )
        reused = validate_post_observation(
            action,
            baseline,
            post.model_copy(update={"observation_id": "before"}),
            dispatch_completed_at=dispatch_completed,
            now=post_time,
        )
        wrong_domain = validate_post_observation(
            action,
            baseline,
            post.model_copy(update={"page_type": "city", "domains_run": ["city_buildings"]}),
            dispatch_completed_at=dispatch_completed,
            now=post_time,
        )

        self.assertEqual(allowed.decision, ObservationGateDecision.ALLOW)
        self.assertEqual(reused.decision, ObservationGateDecision.BLOCK)
        self.assertIn("reused", reused.reason)
        self.assertEqual(wrong_domain.decision, ObservationGateDecision.BLOCK)
        self.assertIn("does not match", wrong_domain.reason)

    def test_post_observation_rejects_future_and_runner_stale_frames(self) -> None:
        captured_at = datetime(2026, 7, 10, 4, 0, 0, tzinfo=UTC)
        action = CandidateAction(
            action_id="claim-17",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
            params={"chapter_id": 17, "claim_button": BUTTON},
        )
        baseline = _snapshot(
            observed_state=RuntimeState(progress={"current_chapter_id": 17}),
            page_type="chapter",
            domains=["chapter_panel"],
            meta_key="progress.chapter_panel",
            meta_source="vision.chapter_panel",
            captured_at=captured_at,
            observation_id="before",
        )
        future = _snapshot(
            observed_state=RuntimeState(
                progress={"current_chapter_id": 17, "chapter_claimable": False}
            ),
            page_type="chapter",
            domains=["chapter_panel"],
            meta_key="progress.chapter_panel",
            meta_source="vision.chapter_panel",
            captured_at=captured_at + timedelta(days=365),
            observation_id="future",
        )
        stale = future.model_copy(
            update={
                "observation_id": "stale",
                "captured_at": captured_at + timedelta(seconds=2),
                "observed_state": future.observed_state.model_copy(
                    update={
                        "field_meta": {
                            "progress.chapter_panel": FieldMeta(
                                value="loaded",
                                source="vision.chapter_panel",
                                updated_at=captured_at + timedelta(seconds=2),
                                observation_id="stale",
                            )
                        }
                    }
                ),
            }
        )

        future_verdict = validate_post_observation(
            action,
            baseline,
            future,
            dispatch_completed_at=captured_at + timedelta(seconds=1),
            now=captured_at + timedelta(seconds=2),
            max_age_seconds=1,
        )
        stale_verdict = validate_post_observation(
            action,
            baseline,
            stale,
            dispatch_completed_at=captured_at + timedelta(seconds=1),
            now=captured_at + timedelta(seconds=4),
            max_age_seconds=1,
        )

        self.assertEqual(future_verdict.decision, ObservationGateDecision.BLOCK)
        self.assertIn("future", future_verdict.reason)
        self.assertEqual(stale_verdict.decision, ObservationGateDecision.BLOCK)
        self.assertIn("stale", stale_verdict.reason)

    def test_dispatch_rejects_boolean_chapter_and_building_levels(self) -> None:
        captured_at = datetime.now(UTC)
        claim = CandidateAction(
            action_id="claim-1",
            action_type=ActionType.CLAIM_CHAPTER_REWARD,
            params={"chapter_id": 1, "claim_button": BUTTON},
        )
        claim_observation = _snapshot(
            observed_state=RuntimeState(
                progress={
                    "current_chapter_id": True,
                    "chapter_claimable": True,
                    "chapter_claim_button": BUTTON,
                }
            ),
            page_type="chapter",
            domains=["chapter_panel"],
            meta_key="progress.chapter_panel",
            meta_source="vision.chapter_panel",
            captured_at=captured_at,
            observation_id="bool-chapter",
        )
        upgrade = CandidateAction(
            action_id="upgrade-1",
            action_type=ActionType.UPGRADE_BUILDING,
            params={
                "building_name": "Main Hall",
                "current_level": 1,
                "target_level": 2,
                "upgrade_button": BUTTON,
            },
        )
        upgrade_observation = _snapshot(
            observed_state=RuntimeState(
                city={
                    "buildings": [
                        {"name": "Main Hall", "level": True, "upgrade_button": BUTTON}
                    ]
                }
            ),
            page_type="city",
            domains=["city_buildings"],
            meta_key="city",
            meta_source="vision.city_buildings",
            captured_at=captured_at,
            observation_id="bool-building",
        )

        claim_verdict = validate_dispatch_observation(
            claim, claim_observation, now=captured_at
        )
        upgrade_verdict = validate_dispatch_observation(
            upgrade, upgrade_observation, now=captured_at
        )

        self.assertEqual(claim_verdict.decision, ObservationGateDecision.BLOCK)
        self.assertIn("numeric chapter", claim_verdict.reason)
        self.assertEqual(upgrade_verdict.decision, ObservationGateDecision.BLOCK)
        self.assertIn("numeric building", upgrade_verdict.reason)


if __name__ == "__main__":
    unittest.main()
