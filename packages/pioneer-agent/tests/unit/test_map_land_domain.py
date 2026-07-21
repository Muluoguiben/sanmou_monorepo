from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import (
    apply_map_land,
    expire_map_land_candidates,
    extract_map_land,
)
from pioneer_agent.perception.vision.prompts import (
    BATTLE_REPORT_INSTRUCTION,
    MAP_LAND_INSTRUCTION,
    MAP_LAND_SCHEMA,
)


@dataclass
class _StubResult:
    data: dict[str, Any]


class _StubVision:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        return _StubResult(data=self.payload)


def _payload(land: dict[str, Any]) -> dict[str, Any]:
    return {
        "page_type": "main_map",
        "filter_panel_visible": False,
        "resource_filter_enabled": False,
        "selected_resource_types": [],
        "selected_levels": [],
        "filter_button_visible": False,
        "filter_button_enabled": False,
        "apply_button_visible": False,
        "apply_button_enabled": False,
        "resource_toggles": [],
        "level_toggles": [],
        "lands": [land],
        "visible_notes": [],
    }


def _safe_land(**updates: Any) -> dict[str, Any]:
    land: dict[str, Any] = {
        "land_id": "L-1",
        "level": 6,
        "resource_type": "stone",
        "land_scope": "inner_city",
        "occupied": False,
        "protected": False,
        "reachable": True,
        "can_attack": True,
        "x_min": 400,
        "y_min": 420,
        "x_max": 500,
        "y_max": 520,
    }
    land.update(updates)
    return land


class MapLandDomainTests(unittest.TestCase):
    def test_occupation_fields_and_no_victory_inference_are_in_vision_contract(self) -> None:
        lands = MAP_LAND_SCHEMA["properties"]["lands"]["items"]["properties"]

        self.assertEqual(lands["occupation_pending"]["type"], "boolean")
        self.assertEqual(lands["occupation_countdown"]["type"], "string")
        self.assertIn("must not cause occupied=true", MAP_LAND_INSTRUCTION)
        self.assertIn(
            "keep occupation_result unknown",
            BATTLE_REPORT_INSTRUCTION,
        )

    def test_only_explicit_current_targetable_land_becomes_candidate(self) -> None:
        captured_at = datetime(2026, 7, 10, 12, 0, 0)
        fragment = extract_map_land(
            b"png",
            client=_StubVision(_payload(_safe_land())),
            captured_at=captured_at,
        )

        self.assertEqual(fragment.map_state["visible_land_count"], 1)
        self.assertEqual(fragment.map_state["candidate_land_count"], 1)
        candidate = fragment.map_state["candidate_lands"][0]
        self.assertEqual(candidate["land_id"], "L-1")
        self.assertEqual(candidate["land_scope"], "inner_city")
        self.assertEqual(candidate["observed_at"], captured_at.isoformat())
        self.assertEqual(
            candidate["bbox"],
            {"x_min": 400, "y_min": 420, "x_max": 500, "y_max": 520},
        )

    def test_pending_occupation_countdown_is_retained_and_blocks_candidate(self) -> None:
        fragment = extract_map_land(
            b"png",
            client=_StubVision(
                _payload(
                    _safe_land(
                        occupation_pending=True,
                        occupation_countdown="02:35",
                    )
                )
            ),
            captured_at=datetime(2026, 7, 11, 12, 0, 0),
        )

        self.assertEqual(fragment.map_state["visible_land_count"], 1)
        self.assertEqual(fragment.map_state["candidate_land_count"], 0)
        visible = fragment.map_state["visible_lands"][0]
        self.assertIs(visible["occupation_pending"], True)
        self.assertEqual(visible["occupation_countdown"], "02:35")
        self.assertIn("occupation_pending", visible["strategic_tags"])

    def test_unknown_or_false_occupation_pending_keeps_existing_contract(self) -> None:
        for name, updates in {
            "unknown": {},
            "explicit_false": {"occupation_pending": False},
        }.items():
            with self.subTest(name=name):
                fragment = extract_map_land(
                    b"png",
                    client=_StubVision(_payload(_safe_land(**updates))),
                    captured_at=datetime(2026, 7, 11, 12, 0, 0),
                )
                self.assertEqual(fragment.map_state["candidate_land_count"], 1)

    def test_occupation_fields_reject_non_json_types_and_orphan_countdown(self) -> None:
        invalid_updates = {
            "pending_integer": {"occupation_pending": 1},
            "pending_string": {"occupation_pending": "true"},
            "countdown_integer": {
                "occupation_pending": True,
                "occupation_countdown": 155,
            },
            "countdown_without_pending": {"occupation_countdown": "02:35"},
            "blank_countdown": {
                "occupation_pending": True,
                "occupation_countdown": "   ",
            },
        }
        for name, updates in invalid_updates.items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    extract_map_land(
                        b"png",
                        client=_StubVision(_payload(_safe_land(**updates))),
                        captured_at=datetime(2026, 7, 11, 12, 0, 0),
                    )

    def test_map_land_safety_and_ui_booleans_are_strict(self) -> None:
        top_level_fields = (
            "filter_panel_visible",
            "resource_filter_enabled",
            "filter_button_visible",
            "filter_button_enabled",
            "apply_button_visible",
            "apply_button_enabled",
        )
        for field in top_level_fields:
            with self.subTest(scope="top_level", field=field):
                payload = _payload(_safe_land())
                payload[field] = 1
                with self.assertRaises(ValidationError):
                    extract_map_land(b"png", client=_StubVision(payload))

        land_fields = (
            "occupied",
            "occupation_pending",
            "reachable",
            "can_attack",
            "protected",
            "selected",
            "recommended_marker",
        )
        for field in land_fields:
            with self.subTest(scope="land", field=field):
                payload = _payload(_safe_land(**{field: "false"}))
                with self.assertRaises(ValidationError):
                    extract_map_land(b"png", client=_StubVision(payload))

        for toggle_key, base_toggle in {
            "resource_toggles": {
                "resource_type": "stone",
                "selected": False,
                "visible": False,
                "enabled": False,
            },
            "level_toggles": {
                "level": 5,
                "selected": False,
                "visible": False,
                "enabled": False,
            },
        }.items():
            for field in ("selected", "visible", "enabled"):
                with self.subTest(scope=toggle_key, field=field):
                    payload = _payload(_safe_land())
                    payload["filter_panel_visible"] = True
                    toggle = dict(base_toggle)
                    toggle[field] = 1
                    payload[toggle_key] = [toggle]
                    with self.assertRaises(ValidationError):
                        extract_map_land(b"png", client=_StubVision(payload))

    def test_all_map_land_levels_are_strict_and_bounded(self) -> None:
        for invalid_level in (True, "5", 0, 13):
            with self.subTest(scope="land", level=invalid_level):
                with self.assertRaises(ValidationError):
                    extract_map_land(
                        b"png",
                        client=_StubVision(
                            _payload(_safe_land(level=invalid_level))
                        ),
                    )

            for field in ("selected_levels", "level_min", "level_max"):
                with self.subTest(scope=field, level=invalid_level):
                    payload = _payload(_safe_land())
                    payload[field] = (
                        [invalid_level] if field == "selected_levels" else invalid_level
                    )
                    with self.assertRaises(ValidationError):
                        extract_map_land(b"png", client=_StubVision(payload))

            with self.subTest(scope="level_toggle", level=invalid_level):
                payload = _payload(_safe_land())
                payload["filter_panel_visible"] = True
                payload["level_toggles"] = [
                    {
                        "level": invalid_level,
                        "selected": False,
                        "visible": False,
                        "enabled": False,
                    }
                ]
                with self.assertRaises(ValidationError):
                    extract_map_land(b"png", client=_StubVision(payload))

        valid = _payload(_safe_land(level=1))
        valid["selected_levels"] = [1, 12]
        valid["level_min"] = 1
        valid["level_max"] = 12
        fragment = extract_map_land(b"png", client=_StubVision(valid))
        self.assertEqual(fragment.map_state["map_land_filter"]["selected_levels"], [1, 12])

    def test_map_land_level_range_is_ordered_and_contains_selected_levels(self) -> None:
        cases = {
            "reversed": {"selected_levels": [], "level_min": 8, "level_max": 5},
            "below_min": {"selected_levels": [4], "level_min": 5, "level_max": 8},
            "above_max": {"selected_levels": [9], "level_min": 5, "level_max": 8},
        }
        for name, updates in cases.items():
            with self.subTest(name=name):
                payload = _payload(_safe_land())
                payload.update(updates)
                with self.assertRaises(ValidationError):
                    extract_map_land(b"png", client=_StubVision(payload))

    def test_map_center_and_land_coordinate_pairs_are_atomic(self) -> None:
        invalid_payloads: dict[str, dict[str, Any]] = {}
        for field in ("map_center_x", "map_center_y"):
            payload = _payload(_safe_land())
            payload[field] = 100
            invalid_payloads[field] = payload
        for field in ("coordinate_x", "coordinate_y", "center_x", "center_y"):
            invalid_payloads[field] = _payload(_safe_land(**{field: 100}))

        for name, payload in invalid_payloads.items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    extract_map_land(b"png", client=_StubVision(payload))

        valid = _payload(
            _safe_land(
                coordinate_x=123,
                coordinate_y=456,
                center_x=450,
                center_y=470,
            )
        )
        valid["map_center_x"] = 120
        valid["map_center_y"] = 455
        fragment = extract_map_land(b"png", client=_StubVision(valid))
        self.assertEqual(
            fragment.map_state["map_center_coordinate"],
            {"x": 120, "y": 455},
        )

    def test_map_geometry_and_numeric_land_facts_are_strict_integers(self) -> None:
        top_level_fields = ("map_center_x", "filter_button_x_min", "apply_button_y_max")
        land_fields = (
            "coordinate_x",
            "center_x",
            "x_min",
            "yield_per_hour",
            "distance",
            "march_seconds",
            "expected_battle_loss",
        )
        invalid_values = (True, "400", 400.0)

        for field in top_level_fields:
            for value in invalid_values:
                with self.subTest(scope="top_level", field=field, value=value):
                    payload = _payload(_safe_land())
                    if field == "map_center_x":
                        payload.update({"map_center_x": value, "map_center_y": 455})
                    elif field.startswith("filter_button"):
                        payload.update(
                            {
                                "filter_button_visible": True,
                                "filter_button_enabled": True,
                                "filter_button_x_min": value,
                                "filter_button_y_min": 100,
                                "filter_button_x_max": 200,
                                "filter_button_y_max": 200,
                            }
                        )
                    else:
                        payload.update(
                            {
                                "filter_panel_visible": True,
                                "apply_button_visible": True,
                                "apply_button_enabled": True,
                                "apply_button_x_min": 700,
                                "apply_button_y_min": 700,
                                "apply_button_x_max": 800,
                                "apply_button_y_max": value,
                            }
                        )
                    with self.assertRaises(ValidationError):
                        extract_map_land(b"png", client=_StubVision(payload))

        for field in land_fields:
            for value in invalid_values:
                with self.subTest(scope="land", field=field, value=value):
                    updates: dict[str, Any] = {field: value}
                    if field == "coordinate_x":
                        updates["coordinate_y"] = 456
                    elif field == "center_x":
                        updates["center_y"] = 470
                    payload = _payload(_safe_land(**updates))
                    with self.assertRaises(ValidationError):
                        extract_map_land(b"png", client=_StubVision(payload))

    def test_expected_win_rate_is_strict_finite_and_bounded(self) -> None:
        invalid_values = (
            True,
            "0.75",
            float("nan"),
            float("inf"),
            float("-inf"),
            -0.01,
            1.01,
        )
        for value in invalid_values:
            with self.subTest(value=repr(value)):
                payload = _payload(_safe_land(expected_win_rate=value))
                with self.assertRaises(ValidationError):
                    extract_map_land(b"png", client=_StubVision(payload))

        for value in (0.0, 0.75, 1.0):
            with self.subTest(valid=value):
                payload = _payload(_safe_land(expected_win_rate=value))
                fragment = extract_map_land(b"png", client=_StubVision(payload))
                self.assertEqual(
                    fragment.map_state["visible_lands"][0]["expected_win_rate"],
                    value,
                )

        expected_win_rate_schema = MAP_LAND_SCHEMA["properties"]["lands"]["items"][
            "properties"
        ]["expected_win_rate"]
        self.assertEqual(expected_win_rate_schema["minimum"], 0.0)
        self.assertEqual(expected_win_rate_schema["maximum"], 1.0)

    def test_count_like_land_facts_are_nonnegative(self) -> None:
        fields = (
            "yield_per_hour",
            "distance",
            "march_seconds",
            "expected_battle_loss",
        )
        land_properties = MAP_LAND_SCHEMA["properties"]["lands"]["items"][
            "properties"
        ]
        for field in fields:
            with self.subTest(field=field, value=-1):
                payload = _payload(_safe_land(**{field: -1}))
                with self.assertRaises(ValidationError):
                    extract_map_land(b"png", client=_StubVision(payload))

            with self.subTest(field=field, value=0):
                payload = _payload(_safe_land(**{field: 0}))
                fragment = extract_map_land(b"png", client=_StubVision(payload))
                self.assertEqual(fragment.map_state["visible_lands"][0][field], 0)

            self.assertEqual(land_properties[field]["minimum"], 0)

    def test_unknown_map_land_fields_are_rejected_at_every_model_boundary(self) -> None:
        top_level = _payload(_safe_land())
        top_level["untrusted_top_level"] = True

        land = _payload(_safe_land(untrusted_land_fact="value"))

        resource_toggle = _payload(_safe_land())
        resource_toggle.update(
            {
                "filter_panel_visible": True,
                "resource_toggles": [
                    {
                        "resource_type": "stone",
                        "selected": False,
                        "visible": False,
                        "enabled": False,
                        "untrusted_toggle_fact": "value",
                    }
                ],
            }
        )

        level_toggle = _payload(_safe_land())
        level_toggle.update(
            {
                "filter_panel_visible": True,
                "level_toggles": [
                    {
                        "level": 5,
                        "selected": False,
                        "visible": False,
                        "enabled": False,
                        "untrusted_toggle_fact": "value",
                    }
                ],
            }
        )

        cases = {
            "snapshot": (top_level, ("untrusted_top_level",)),
            "land": (land, ("lands", 0, "untrusted_land_fact")),
            "resource_toggle": (
                resource_toggle,
                ("resource_toggles", 0, "untrusted_toggle_fact"),
            ),
            "level_toggle": (
                level_toggle,
                ("level_toggles", 0, "untrusted_toggle_fact"),
            ),
        }
        for name, (payload, expected_location) in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError) as raised:
                    extract_map_land(b"png", client=_StubVision(payload))
                extra_errors = [
                    error
                    for error in raised.exception.errors()
                    if error["type"] == "extra_forbidden"
                ]
                self.assertEqual(len(extra_errors), 1)
                self.assertEqual(extra_errors[0]["loc"], expected_location)

    def test_complete_stone_level_five_filter_snapshot_is_accepted(self) -> None:
        payload = _payload(_safe_land(level=5, resource_type="stone"))
        payload.update(
            {
                "filter_panel_visible": True,
                "resource_filter_enabled": True,
                "selected_resource_types": ["stone"],
                "selected_levels": [5],
                "level_min": 5,
                "level_max": 5,
                "filter_button_visible": True,
                "filter_button_enabled": True,
                "filter_button_x_min": 850,
                "filter_button_y_min": 100,
                "filter_button_x_max": 900,
                "filter_button_y_max": 150,
                "apply_button_visible": True,
                "apply_button_enabled": True,
                "apply_button_x_min": 700,
                "apply_button_y_min": 820,
                "apply_button_x_max": 820,
                "apply_button_y_max": 900,
                "resource_toggles": [
                    {
                        "resource_type": "stone",
                        "selected": True,
                        "visible": True,
                        "enabled": True,
                        "x_min": 200,
                        "y_min": 300,
                        "x_max": 300,
                        "y_max": 360,
                    }
                ],
                "level_toggles": [
                    {
                        "level": 5,
                        "selected": True,
                        "visible": True,
                        "enabled": True,
                        "x_min": 400,
                        "y_min": 500,
                        "x_max": 470,
                        "y_max": 560,
                    }
                ],
            }
        )

        fragment = extract_map_land(
            b"png",
            client=_StubVision(payload),
            captured_at=datetime(2026, 7, 21, 12, 0, 0),
        )

        self.assertEqual(fragment.parse_status, "observed")
        filter_state = fragment.map_state["map_land_filter"]
        self.assertEqual(filter_state["selected_resource_types"], ["stone"])
        self.assertEqual(filter_state["selected_levels"], [5])
        self.assertEqual(
            filter_state["apply_button"]["bbox"],
            {"x_min": 700, "y_min": 820, "x_max": 820, "y_max": 900},
        )
        self.assertTrue(filter_state["resource_toggles"][0]["selected"])
        self.assertTrue(filter_state["level_toggles"][0]["selected"])
        candidate = fragment.map_state["candidate_lands"][0]
        self.assertIn("resource_filter_match", candidate["strategic_tags"])
        self.assertIn("level_filter_match", candidate["strategic_tags"])

    def test_filter_panel_cannot_expose_hidden_panel_controls(self) -> None:
        apply_payload = _payload(_safe_land())
        apply_payload.update(
            {
                "apply_button_visible": True,
                "apply_button_enabled": True,
                "apply_button_x_min": 700,
                "apply_button_y_min": 700,
                "apply_button_x_max": 800,
                "apply_button_y_max": 800,
            }
        )
        resource_toggle_payload = _payload(_safe_land())
        resource_toggle_payload["resource_toggles"] = [
            {
                "resource_type": "stone",
                "selected": False,
                "visible": False,
                "enabled": False,
            }
        ]
        level_toggle_payload = _payload(_safe_land())
        level_toggle_payload["level_toggles"] = [
            {
                "level": 5,
                "selected": False,
                "visible": False,
                "enabled": False,
            }
        ]

        for name, payload in {
            "apply": apply_payload,
            "resource_toggle": resource_toggle_payload,
            "level_toggle": level_toggle_payload,
        }.items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    extract_map_land(b"png", client=_StubVision(payload))

    def test_selected_filter_summaries_cannot_conflict_with_toggles(self) -> None:
        resource_conflict = _payload(_safe_land())
        resource_conflict.update(
            {
                "filter_panel_visible": True,
                "resource_filter_enabled": True,
                "selected_resource_types": ["stone"],
                "resource_toggles": [
                    {
                        "resource_type": "stone",
                        "selected": False,
                        "visible": True,
                        "enabled": True,
                        "x_min": 100,
                        "y_min": 100,
                        "x_max": 200,
                        "y_max": 200,
                    }
                ],
            }
        )
        level_conflict = _payload(_safe_land())
        level_conflict.update(
            {
                "filter_panel_visible": True,
                "selected_levels": [5],
                "level_toggles": [
                    {
                        "level": 5,
                        "selected": False,
                        "visible": True,
                        "enabled": True,
                        "x_min": 100,
                        "y_min": 100,
                        "x_max": 200,
                        "y_max": 200,
                    }
                ],
            }
        )
        disabled_resource_filter = _payload(_safe_land())
        disabled_resource_filter["selected_resource_types"] = ["stone"]
        duplicate_summary = _payload(_safe_land())
        duplicate_summary["selected_levels"] = [5, 5]

        for name, payload in {
            "resource_toggle": resource_conflict,
            "level_toggle": level_conflict,
            "disabled_resource_filter": disabled_resource_filter,
            "duplicate_summary": duplicate_summary,
        }.items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    extract_map_land(b"png", client=_StubVision(payload))

    def test_unknown_page_emits_only_an_untrusted_empty_fragment(self) -> None:
        payload = _payload(_safe_land())
        payload.update({"page_type": "unknown", "lands": []})

        fragment = extract_map_land(b"png", client=_StubVision(payload))
        self.assertEqual(fragment.raw.page_type, "unknown")
        self.assertEqual(fragment.parse_status, "unknown")
        self.assertEqual(fragment.map_state, {})
        self.assertEqual(fragment.field_meta, {})
        previous = RuntimeState(
            map_state={"candidate_lands": [{"land_id": "existing"}]}
        )
        self.assertEqual(apply_map_land(previous, fragment), previous)

        populated = dict(payload)
        populated["selected_levels"] = [5]
        with self.assertRaises(ValidationError):
            extract_map_land(b"png", client=_StubVision(populated))

    def test_filter_prompt_disambiguates_the_magnifying_glass_entry(self) -> None:
        self.assertIn("magnifying-glass icon", MAP_LAND_INSTRUCTION)
        self.assertIn("adjacent eye/view control", MAP_LAND_INSTRUCTION)
        self.assertIn("when ambiguous set filter_button_visible=false", MAP_LAND_INSTRUCTION)
        self.assertEqual(
            MAP_LAND_SCHEMA["properties"]["selected_levels"]["items"]["minimum"],
            1,
        )
        self.assertEqual(
            MAP_LAND_SCHEMA["properties"]["selected_levels"]["items"]["maximum"],
            12,
        )

    def test_four_safety_fields_are_tri_state_and_fail_closed(self) -> None:
        cases = {
            "occupied_missing": ("occupied", None, True),
            "occupied_true": ("occupied", True, False),
            "protected_missing": ("protected", None, True),
            "protected_true": ("protected", True, False),
            "reachable_missing": ("reachable", None, True),
            "reachable_false": ("reachable", False, False),
            "can_attack_missing": ("can_attack", None, True),
            "can_attack_false": ("can_attack", False, False),
        }
        for name, (field, value, remove) in cases.items():
            with self.subTest(name=name):
                land = _safe_land()
                if remove:
                    land.pop(field)
                else:
                    land[field] = value
                fragment = extract_map_land(
                    b"png",
                    client=_StubVision(_payload(land)),
                    captured_at=datetime(2026, 7, 10, 12, 0, 0),
                )
                self.assertEqual(fragment.map_state["visible_land_count"], 1)
                self.assertEqual(fragment.map_state["candidate_land_count"], 0)

    def test_level_resource_bbox_and_capture_time_are_required_for_candidate(self) -> None:
        cases = {
            "level": {"level": None},
            "resource": {"resource_type": "unknown"},
            "bbox": {"x_min": None, "y_min": None, "x_max": None, "y_max": None},
        }
        for name, updates in cases.items():
            with self.subTest(name=name):
                fragment = extract_map_land(
                    b"png",
                    client=_StubVision(_payload(_safe_land(**updates))),
                    captured_at=datetime(2026, 7, 10, 12, 0, 0),
                )
                self.assertEqual(fragment.map_state["candidate_land_count"], 0)

        missing_time = extract_map_land(
            b"png",
            client=_StubVision(_payload(_safe_land())),
            captured_at=None,
        )
        self.assertEqual(missing_time.map_state["candidate_land_count"], 0)

    def test_snapshot_replaces_lists_and_rejects_older_fragment(self) -> None:
        newer_at = datetime(2026, 7, 10, 12, 0, 0)
        older_at = newer_at - timedelta(seconds=1)
        latest_at = newer_at + timedelta(seconds=1)
        newer = extract_map_land(
            b"png",
            client=_StubVision(_payload(_safe_land(land_id="newer"))),
            captured_at=newer_at,
        )
        older = extract_map_land(
            b"png",
            client=_StubVision(_payload(_safe_land(land_id="older"))),
            captured_at=older_at,
        )
        latest = extract_map_land(
            b"png",
            client=_StubVision(_payload(_safe_land(land_id="latest"))),
            captured_at=latest_at,
        )

        state = apply_map_land(
            RuntimeState(map_state={"map_center_coordinate": {"x": 1, "y": 2}}),
            newer,
        )
        self.assertNotIn("map_center_coordinate", state.map_state)
        state = apply_map_land(state, older)
        self.assertEqual(
            [land["land_id"] for land in state.map_state["visible_lands"]],
            ["newer"],
        )

        state = apply_map_land(state, latest)
        self.assertEqual(
            [land["land_id"] for land in state.map_state["visible_lands"]],
            ["latest"],
        )
        self.assertEqual(
            [land["land_id"] for land in state.map_state["candidate_lands"]],
            ["latest"],
        )

    def test_empty_non_map_expiry_advances_watermark(self) -> None:
        expired_at = datetime(2026, 7, 10, 12, 0, 0)
        state = expire_map_land_candidates(RuntimeState(), captured_at=expired_at)

        self.assertEqual(state.map_state["candidate_lands"], [])
        self.assertEqual(state.map_state["candidate_land_count"], 0)
        self.assertEqual(
            state.field_meta["map_state.candidate_lands"].updated_at,
            expired_at,
        )

        older = extract_map_land(
            b"png",
            client=_StubVision(_payload(_safe_land(land_id="late-old"))),
            captured_at=expired_at - timedelta(seconds=1),
        )
        state = apply_map_land(state, older)
        self.assertEqual(state.map_state["candidate_lands"], [])

    def test_mixed_timezone_map_application_rejects_but_expiry_clears(self) -> None:
        aware_at = datetime(2026, 7, 10, 4, 0, 0, tzinfo=timezone.utc)
        state = apply_map_land(
            RuntimeState(),
            extract_map_land(
                b"png",
                client=_StubVision(_payload(_safe_land(land_id="aware"))),
                captured_at=aware_at,
            ),
        )
        ambiguous_naive = datetime(2026, 7, 10, 13, 0, 0)
        state = apply_map_land(
            state,
            extract_map_land(
                b"png",
                client=_StubVision(_payload(_safe_land(land_id="ambiguous"))),
                captured_at=ambiguous_naive,
            ),
        )
        self.assertEqual(state.map_state["candidate_lands"][0]["land_id"], "aware")

        state = expire_map_land_candidates(state, captured_at=ambiguous_naive)
        self.assertEqual(state.map_state["candidate_lands"], [])

    def test_aware_offsets_compare_by_absolute_time(self) -> None:
        china = timezone(timedelta(hours=8))
        existing = extract_map_land(
            b"png",
            client=_StubVision(_payload(_safe_land(land_id="existing"))),
            captured_at=datetime(2026, 7, 10, 12, 0, 0, tzinfo=china),
        )
        newer = extract_map_land(
            b"png",
            client=_StubVision(_payload(_safe_land(land_id="newer"))),
            captured_at=datetime(2026, 7, 10, 5, 0, 0, tzinfo=timezone.utc),
        )

        state = apply_map_land(RuntimeState(), existing)
        state = apply_map_land(state, newer)
        self.assertEqual(state.map_state["candidate_lands"][0]["land_id"], "newer")


if __name__ == "__main__":
    unittest.main()
