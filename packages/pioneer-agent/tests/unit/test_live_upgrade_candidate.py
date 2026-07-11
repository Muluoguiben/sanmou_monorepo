from __future__ import annotations

import io
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from PIL import Image

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import RuntimeState
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.perception.vision_sync import VisionSync
from pioneer_agent.selector.action_selector import ActionSelector


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "stub"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _ScriptedVision:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = list(payloads)

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        if not self.payloads:
            raise AssertionError("unexpected vision extraction")
        return _StubResult(self.payloads.pop(0))


class LiveUpgradeCandidateTests(unittest.TestCase):
    def test_real_city_vision_derives_one_selectable_upgrade_target(self) -> None:
        vision = _ScriptedVision(
            [
                {"page_type": "city", "resources": {}, "visible_notes": []},
                {
                    "buildings": [
                        {
                            "name": "Main Hall",
                            "level": 3,
                            "upgrade_button_visible": True,
                            "upgrade_button_enabled": True,
                            "upgrade_button_x_min": 100,
                            "upgrade_button_y_min": 700,
                            "upgrade_button_x_max": 240,
                            "upgrade_button_y_max": 900,
                        }
                    ],
                    "visible_notes": [],
                },
            ]
        )
        observed, summary = VisionSync(vision).sync(
            _png(),
            captured_at=datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
        )

        derived = StateDeriver().derive(observed)
        selection = ActionSelector().select(derived)

        self.assertEqual(summary.page_type, "city")
        self.assertEqual(summary.domains_run, ["resource_bar", "city_buildings"])
        self.assertEqual(len(derived.city["upgradeable_buildings"]), 1)
        self.assertIsNotNone(selection.selected_action)
        action = selection.selected_action
        assert action is not None
        self.assertEqual(action.action_type, ActionType.UPGRADE_BUILDING)
        self.assertEqual(action.params["building_name"], "Main Hall")
        self.assertEqual(action.params["current_level"], 3)
        self.assertEqual(action.params["target_level"], 4)
        self.assertEqual(action.params["upgrade_button"], _button())

    def test_malformed_observed_targets_never_become_candidates(self) -> None:
        invalid_buildings = [
            {**_building(), "name": ""},
            {**_building(), "name": True},
            {**_building(), "level": True},
            {**_building(), "level": 0},
            {**_building(), "level": -1},
            {**_building(), "level": "3"},
            {**_building(), "level": 3.0},
            {**_building(), "upgrade_button": {**_button(), "visible": 1}},
            {**_building(), "upgrade_button": {**_button(), "enabled": "yes"}},
            _with_bbox(x_min=False),
            _with_bbox(x_min="100"),
            _with_bbox(x_min=float("nan")),
            _with_bbox(x_min=float("inf")),
            _with_bbox(x_min=240),
            _with_bbox(x_min=-1),
            _with_bbox(x_max=1001),
        ]

        for building in invalid_buildings:
            with self.subTest(building=building):
                derived = StateDeriver().derive(
                    RuntimeState(city={"buildings": [building]})
                )
                selection = ActionSelector().select(derived)
                self.assertEqual(derived.city["upgradeable_buildings"], [])
                self.assertIsNone(selection.selected_action)

    def test_duplicate_observed_target_is_fail_closed(self) -> None:
        derived = StateDeriver().derive(
            RuntimeState(city={"buildings": [_building(), _building()]})
        )

        self.assertEqual(derived.city["upgradeable_buildings"], [])
        self.assertIsNone(ActionSelector().select(derived).selected_action)

    def test_duplicate_observed_target_cannot_be_rescued_by_dialog(self) -> None:
        state = _state_with_dialog("Main Hall")
        state.city["buildings"] = [_building(), _building()]
        state.city["upgradeable_buildings"] = [
            {
                "building_id": "main_hall",
                "building_name": "Main Hall",
                "current_level": 3,
                "target_level": 4,
            }
        ]

        derived = StateDeriver().derive(state)

        self.assertEqual(derived.city["upgradeable_buildings"], [])
        self.assertIsNone(ActionSelector().select(derived).selected_action)

    def test_current_vision_snapshot_cannot_be_starved_by_stale_button(self) -> None:
        previous = RuntimeState(
            city={
                "buildings": [_building()],
                "upgradeable_buildings": [
                    {
                        "building_id": "main_hall",
                        "building_name": "Main Hall",
                        "current_level": 3,
                        "target_level": 4,
                        "upgrade_button": _button(),
                        "chapter_relevance": "complete_current_task",
                    }
                ],
            }
        )
        current_button = {
            "visible": True,
            "enabled": True,
            "bbox": {
                "x_min": 600,
                "y_min": 700,
                "x_max": 760,
                "y_max": 900,
            },
        }
        vision = _ScriptedVision(
            [
                {"page_type": "city", "resources": {}, "visible_notes": []},
                {
                    "buildings": [
                        {
                            "name": "Barracks",
                            "level": 2,
                            "upgrade_button_visible": True,
                            "upgrade_button_enabled": True,
                            "upgrade_button_x_min": 600,
                            "upgrade_button_y_min": 700,
                            "upgrade_button_x_max": 760,
                            "upgrade_button_y_max": 900,
                        }
                    ],
                    "visible_notes": [],
                },
            ]
        )

        observed, _summary = VisionSync(vision).sync(_png(), state=previous)
        derived = StateDeriver().derive(observed)
        action = ActionSelector().select(derived).selected_action

        self.assertEqual(
            [item["name"] for item in derived.city["buildings"]],
            ["Barracks"],
        )
        self.assertEqual(len(derived.city["upgradeable_buildings"]), 1)
        self.assertIsNotNone(action)
        assert action is not None
        self.assertEqual(action.params["building_name"], "Barracks")
        self.assertEqual(action.params["upgrade_button"], current_button)

    def test_explicit_level_conflict_drops_the_observed_target(self) -> None:
        derived = StateDeriver().derive(
            RuntimeState(
                city={
                    "buildings": [_building()],
                    "upgradeable_buildings": [
                        {
                            "building_id": "main_hall",
                            "building_name": "Main Hall",
                            "current_level": 2,
                            "target_level": 3,
                            "cost": {"wood": 10},
                        }
                    ],
                }
            )
        )

        self.assertEqual(derived.city["upgradeable_buildings"], [])
        self.assertIsNone(ActionSelector().select(derived).selected_action)

    def test_conflicting_explicit_duplicates_are_fail_closed(self) -> None:
        derived = StateDeriver().derive(
            RuntimeState(
                city={
                    "upgradeable_buildings": [
                        {
                            "building_id": "main_hall",
                            "building_name": "Main Hall",
                            "current_level": 3,
                            "target_level": 4,
                        },
                        {
                            "building_id": "main_hall",
                            "building_name": "Main Hall",
                            "current_level": 3,
                            "target_level": 5,
                        },
                    ]
                }
            )
        )

        self.assertEqual(derived.city["upgradeable_buildings"], [])

    def test_conflicting_explicit_target_fields_are_fail_closed(self) -> None:
        derived = StateDeriver().derive(
            RuntimeState(
                city={
                    "buildings": [_building()],
                    "upgradeable_buildings": [
                        {
                            "building_id": "barracks",
                            "building_name": "Main Hall",
                            "current_level": 3,
                            "target_level": 4,
                        }
                    ],
                }
            )
        )

        self.assertEqual(derived.city["upgradeable_buildings"], [])
        self.assertIsNone(ActionSelector().select(derived).selected_action)

    def test_stale_explicit_button_without_current_target_is_not_selectable(self) -> None:
        derived = StateDeriver().derive(
            RuntimeState(
                city={
                    "buildings": [],
                    "upgradeable_buildings": [
                        {
                            "building_id": "main_hall",
                            "building_name": "Main Hall",
                            "current_level": 3,
                            "target_level": 4,
                            "upgrade_button": _button(),
                        }
                    ],
                }
            )
        )

        self.assertEqual(derived.city["upgradeable_buildings"], [])
        self.assertIsNone(ActionSelector().select(derived).selected_action)

    def test_identical_explicit_duplicates_merge_once_with_observation(self) -> None:
        explicit = {
            "building_id": "main_hall",
            "building_name": "Main Hall",
            "current_level": 3,
            "target_level": 4,
            "cost": {"wood": 10},
        }
        derived = StateDeriver().derive(
            RuntimeState(
                city={
                    "buildings": [_building()],
                    "upgradeable_buildings": [dict(explicit), dict(explicit)],
                },
                economy={"resources": {"wood": 10}},
            )
        )

        self.assertEqual(len(derived.city["upgradeable_buildings"]), 1)
        candidate = derived.city["upgradeable_buildings"][0]
        self.assertEqual(candidate["building_id"], "main_hall")
        self.assertEqual(candidate["current_level"], 3)
        self.assertEqual(candidate["target_level"], 4)
        self.assertEqual(candidate["upgrade_button"], _button())
        self.assertEqual(candidate["cost"], {"wood": 10})

    def test_upgrade_dialog_binds_only_to_same_name_and_levels(self) -> None:
        matching = _state_with_dialog("Main Hall")
        mismatched = _state_with_dialog("Barracks")
        malformed_confirm = _state_with_dialog("Main Hall")
        malformed_confirm.city["upgrade_dialog"]["confirm_button"]["enabled"] = 1

        matching_action = ActionSelector().select(
            StateDeriver().derive(matching)
        ).selected_action
        mismatched_action = ActionSelector().select(
            StateDeriver().derive(mismatched)
        ).selected_action
        malformed_confirm_action = ActionSelector().select(
            StateDeriver().derive(malformed_confirm)
        ).selected_action

        self.assertIsNotNone(matching_action)
        self.assertIsNotNone(mismatched_action)
        self.assertIsNotNone(malformed_confirm_action)
        assert (
            matching_action is not None
            and mismatched_action is not None
            and malformed_confirm_action is not None
        )
        self.assertIn("upgrade_dialog", matching_action.params)
        self.assertNotIn("upgrade_dialog", mismatched_action.params)
        self.assertNotIn("upgrade_dialog", malformed_confirm_action.params)


def _png() -> bytes:
    image = Image.new("RGB", (100, 100), (20, 40, 60))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _button() -> dict[str, Any]:
    return {
        "visible": True,
        "enabled": True,
        "bbox": {"x_min": 100, "y_min": 700, "x_max": 240, "y_max": 900},
    }


def _building() -> dict[str, Any]:
    return {"name": "Main Hall", "level": 3, "upgrade_button": _button()}


def _with_bbox(**updates: Any) -> dict[str, Any]:
    button = _button()
    button["bbox"] = {**button["bbox"], **updates}
    return {**_building(), "upgrade_button": button}


def _state_with_dialog(building_name: str) -> RuntimeState:
    return RuntimeState(
        city={
            "buildings": [_building()],
            "upgrade_dialog": {
                "visible": True,
                "building_name": building_name,
                "current_level": 3,
                "next_level": 4,
                "can_upgrade": True,
                "confirm_button": _button(),
            },
        }
    )


if __name__ == "__main__":
    unittest.main()
