"""Tests for the city_buildings vision domain extractor + merge helper.

Uses a stub VisionClient so the real Gemini API is never called.
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pioneer_agent.core.models import FieldMeta, RuntimeState
from pioneer_agent.perception.domains import (
    apply_city_buildings,
    extract_city_buildings,
)


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "stub"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _StubVisionClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.calls = 0

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        self.calls += 1
        return _StubResult(data=self._payload)


class CityBuildingsExtractionTests(unittest.TestCase):
    def test_full_payload_maps_to_fragment(self) -> None:
        stub = _StubVisionClient(
            {
                "prosperity": 165883,
                "territory": "60/60",
                "roads": "6/35",
                "buildings": [
                    {"name": "君王殿", "level": 25},
                    {"name": "铁匠铺", "level": 22, "upgrading": True, "upgrade_eta": "17:45:36"},
                    {"name": "木工所", "level": 25},
                ],
                "visible_notes": ["New Season 4d"],
            }
        )

        fragment = extract_city_buildings(b"fake-bytes", client=stub)

        self.assertEqual(fragment.city["prosperity"], 165883)
        self.assertEqual(fragment.city["territory"], "60/60")
        self.assertEqual(fragment.city["roads"], "6/35")
        self.assertEqual(len(fragment.city["buildings"]), 3)
        blacksmith = next(b for b in fragment.city["buildings"] if b["name"] == "铁匠铺")
        self.assertTrue(blacksmith["upgrading"])
        self.assertEqual(blacksmith["upgrade_eta"], "17:45:36")
        king = next(b for b in fragment.city["buildings"] if b["name"] == "君王殿")
        self.assertNotIn("upgrading", king)
        self.assertNotIn("upgrade_eta", king)
        self.assertEqual(fragment.field_meta["city"].source, "vision.city_buildings")

    def test_missing_prosperity_is_omitted(self) -> None:
        stub = _StubVisionClient(
            {"buildings": [{"name": "军营", "level": 20}]}
        )

        fragment = extract_city_buildings(b"fake-bytes", client=stub)

        self.assertNotIn("prosperity", fragment.city)
        self.assertNotIn("territory", fragment.city)
        self.assertEqual(fragment.city["buildings"], [{"name": "军营", "level": 20}])

    def test_empty_buildings_yields_no_city(self) -> None:
        stub = _StubVisionClient({"buildings": []})
        fragment = extract_city_buildings(b"fake-bytes", client=stub)
        self.assertEqual(fragment.city, {})
        self.assertNotIn("city", fragment.field_meta)


class ApplyCityBuildingsTests(unittest.TestCase):
    def test_merge_buildings_by_name_updates_and_adds(self) -> None:
        from pioneer_agent.perception.domains import CityBuildingsFragment

        state = RuntimeState(
            city={
                "prosperity": 100000,
                "buildings": [
                    {"name": "君王殿", "level": 20},
                    {"name": "民居", "level": 15},
                ],
            }
        )
        fragment = CityBuildingsFragment(
            city={
                "prosperity": 165883,
                "buildings": [
                    {"name": "君王殿", "level": 25},              # update
                    {"name": "铁匠铺", "level": 22, "upgrading": True},  # new
                ],
            },
        )

        new_state = apply_city_buildings(state, fragment)

        by_name = {b["name"]: b for b in new_state.city["buildings"]}
        self.assertEqual(by_name["君王殿"]["level"], 25)
        self.assertEqual(by_name["民居"]["level"], 15)
        self.assertTrue(by_name["铁匠铺"]["upgrading"])
        self.assertEqual(new_state.city["prosperity"], 165883)

    def test_merge_preserves_unrelated_top_level_city_fields(self) -> None:
        from pioneer_agent.perception.domains import CityBuildingsFragment

        state = RuntimeState(city={"some_other_thing": "keep_me", "roads": "5/35"})
        fragment = CityBuildingsFragment(
            city={"roads": "6/35", "buildings": [{"name": "军营", "level": 20}]},
        )

        new_state = apply_city_buildings(state, fragment)

        self.assertEqual(new_state.city["some_other_thing"], "keep_me")
        self.assertEqual(new_state.city["roads"], "6/35")

    def test_field_meta_overrides(self) -> None:
        from pioneer_agent.perception.domains import CityBuildingsFragment

        older = datetime(2026, 4, 13, 9, 0, 0)
        newer = datetime(2026, 4, 13, 12, 0, 0)
        state = RuntimeState(
            field_meta={"city": FieldMeta(value="loaded", source="old", updated_at=older)}
        )
        fragment = CityBuildingsFragment(
            city={"buildings": [{"name": "军营", "level": 20}]},
            field_meta={
                "city": FieldMeta(
                    value="loaded",
                    confidence=0.85,
                    source="vision.city_buildings",
                    updated_at=newer,
                )
            },
        )

        new_state = apply_city_buildings(state, fragment)

        self.assertEqual(new_state.field_meta["city"].source, "vision.city_buildings")
        self.assertEqual(new_state.field_meta["city"].updated_at, newer)


if __name__ == "__main__":
    unittest.main()
