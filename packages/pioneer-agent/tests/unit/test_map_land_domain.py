from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import (
    apply_map_land,
    expire_map_land_candidates,
    extract_map_land,
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
