"""Extract city building state from an internal-city screenshot.

Maps Gemini's `CityBuildingsDetection` output into a `RuntimeState.city`
fragment:

    city = {
      "prosperity": int,
      "territory": "60/60",
      "roads": "6/35",
      "buildings": [
        {"name": str, "level": int|None, "upgrading": bool, "upgrade_eta": str|None},
        ...
      ],
    }

Fields missing from the screenshot are omitted rather than null-filled so
the merge layer can distinguish "not observed" from "observed as 0".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    CITY_BUILDINGS_INSTRUCTION,
    CITY_BUILDINGS_SCHEMA,
    CityBuildingsDetection,
)

SOURCE_LABEL = "vision.city_buildings"


@dataclass
class CityBuildingsFragment:
    city: dict[str, Any] = field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: CityBuildingsDetection | None = None


def extract_city_buildings(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> CityBuildingsFragment:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=CITY_BUILDINGS_INSTRUCTION,
        response_schema=CITY_BUILDINGS_SCHEMA,
    )
    parsed = CityBuildingsDetection.model_validate(result.data)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: CityBuildingsDetection,
    *,
    captured_at: datetime | None,
) -> CityBuildingsFragment:
    city: dict[str, Any] = {}
    if parsed.prosperity is not None:
        city["prosperity"] = parsed.prosperity
    if parsed.territory:
        city["territory"] = parsed.territory
    if parsed.roads:
        city["roads"] = parsed.roads
    if parsed.buildings:
        city["buildings"] = [
            _building_dict(b) for b in parsed.buildings
        ]

    field_meta: dict[str, FieldMeta] = {}
    if city:
        field_meta["city"] = FieldMeta(
            value="loaded",
            confidence=0.85,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )

    return CityBuildingsFragment(
        city=city,
        field_meta=field_meta,
        notes=list(parsed.visible_notes),
        raw=parsed,
    )


def _building_dict(b: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": b.name}
    if b.level is not None:
        entry["level"] = b.level
    if b.upgrading:
        entry["upgrading"] = True
        if b.upgrade_eta:
            entry["upgrade_eta"] = b.upgrade_eta
    return entry
