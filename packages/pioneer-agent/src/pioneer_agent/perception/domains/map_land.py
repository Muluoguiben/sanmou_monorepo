"""Extract a fail-closed land snapshot from a world-map screenshot."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    MAP_LAND_INSTRUCTION,
    MAP_LAND_SCHEMA,
    MapLandCandidateDetection,
    MapLandDetection,
    MapLandFilterToggleDetection,
    MapLandLevelToggleDetection,
)

SOURCE_LABEL = "vision.map_land"


@dataclass
class MapLandFragment:
    map_state: dict[str, Any] = field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: MapLandDetection | None = None


def extract_map_land(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> MapLandFragment:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=MAP_LAND_INSTRUCTION,
        response_schema=MAP_LAND_SCHEMA,
    )
    parsed = MapLandDetection.model_validate(result.data)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: MapLandDetection,
    *,
    captured_at: datetime | None,
) -> MapLandFragment:
    filter_state = _filter_state(parsed)
    visible_lands = [
        _land_dict(land, filter_state=filter_state, captured_at=captured_at)
        for land in parsed.lands
    ]
    candidate_lands = [land for land in visible_lands if _is_candidate_land(land)]

    map_state: dict[str, Any] = {
        "map_land_filter": filter_state,
        "visible_lands": visible_lands,
        "candidate_lands": candidate_lands,
        "visible_land_count": len(visible_lands),
        "candidate_land_count": len(candidate_lands),
    }
    if parsed.map_center_x is not None or parsed.map_center_y is not None:
        map_state["map_center_coordinate"] = _drop_none(
            {"x": parsed.map_center_x, "y": parsed.map_center_y}
        )

    return MapLandFragment(
        map_state=map_state,
        field_meta={
            "map_state.map_land_filter": FieldMeta(
                value="loaded",
                confidence=0.82,
                source=SOURCE_LABEL,
                updated_at=captured_at,
            ),
            "map_state.candidate_lands": FieldMeta(
                value=len(candidate_lands),
                confidence=0.82,
                source=SOURCE_LABEL,
                updated_at=captured_at,
            ),
        },
        notes=list(parsed.visible_notes)
        + [note for land in parsed.lands for note in land.visible_notes],
        raw=parsed,
    )


def _filter_state(parsed: MapLandDetection) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "visible": parsed.filter_panel_visible,
        "resource_filter_enabled": parsed.resource_filter_enabled,
        "selected_resource_types": list(parsed.selected_resource_types),
        "selected_levels": list(parsed.selected_levels),
        "resource_toggles": [_toggle_dict(toggle) for toggle in parsed.resource_toggles],
        "level_toggles": [_level_toggle_dict(toggle) for toggle in parsed.level_toggles],
    }
    filter_button = _button_dict(
        visible=parsed.filter_button_visible,
        enabled=parsed.filter_button_enabled,
        x_min=parsed.filter_button_x_min,
        y_min=parsed.filter_button_y_min,
        x_max=parsed.filter_button_x_max,
        y_max=parsed.filter_button_y_max,
    )
    if filter_button:
        payload["filter_button"] = filter_button
    apply_button = _button_dict(
        visible=parsed.apply_button_visible,
        enabled=parsed.apply_button_enabled,
        x_min=parsed.apply_button_x_min,
        y_min=parsed.apply_button_y_min,
        x_max=parsed.apply_button_x_max,
        y_max=parsed.apply_button_y_max,
    )
    if apply_button:
        payload["apply_button"] = apply_button
    _set_if_not_none(payload, "level_min", parsed.level_min)
    _set_if_not_none(payload, "level_max", parsed.level_max)
    return payload


def _land_dict(
    land: MapLandCandidateDetection,
    *,
    filter_state: dict[str, Any],
    captured_at: datetime | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "land_id": land.land_id or _synthetic_land_id(land),
        "source": SOURCE_LABEL,
        "resource_type": land.resource_type,
        "occupied": land.occupied,
        "protected": land.protected,
        "reachable": land.reachable,
        "can_attack": land.can_attack,
        "selected": land.selected,
        "recommended_marker": land.recommended_marker,
        "strategic_tags": _strategic_tags(land, filter_state),
        "visible_notes": list(land.visible_notes),
    }
    if captured_at is not None:
        payload["observed_at"] = captured_at.isoformat()
    if land.coordinate_x is not None or land.coordinate_y is not None:
        payload["coordinate"] = _drop_none(
            {"x": land.coordinate_x, "y": land.coordinate_y}
        )
    if land.center_x is not None or land.center_y is not None:
        payload["center"] = _drop_none({"x": land.center_x, "y": land.center_y})
    bbox = _bbox(land)
    if bbox:
        payload["bbox"] = bbox
    _set_if_not_none(payload, "level", land.level)
    _set_if_not_none(payload, "owner", land.owner)
    _set_if_not_none(payload, "yield_per_hour", land.yield_per_hour)
    _set_if_not_none(payload, "distance", land.distance)
    _set_if_not_none(payload, "march_seconds", land.march_seconds)
    _set_if_not_none(payload, "expected_win_rate", land.expected_win_rate)
    _set_if_not_none(payload, "expected_battle_loss", land.expected_battle_loss)
    if land.risk_label != "unknown":
        payload["risk_label"] = land.risk_label
    return _drop_none(payload)


def _is_candidate_land(land: dict[str, Any]) -> bool:
    """Only explicit, current, targetable observations become candidates."""
    return (
        land.get("occupied") is False
        and land.get("protected") is False
        and land.get("reachable") is True
        and land.get("can_attack") is True
        and land.get("level") is not None
        and land.get("resource_type") not in {None, "unknown"}
        and isinstance(land.get("bbox"), dict)
        and isinstance(land.get("observed_at"), str)
    )


def _strategic_tags(
    land: MapLandCandidateDetection,
    filter_state: dict[str, Any],
) -> list[str]:
    tags: list[str] = []
    selected_resources = filter_state.get("selected_resource_types") or []
    selected_levels = filter_state.get("selected_levels") or []
    if land.recommended_marker:
        tags.append("visible_recommended")
    if land.resource_type in selected_resources:
        tags.append("resource_filter_match")
    if land.level in selected_levels:
        tags.append("level_filter_match")
    return tags


def _synthetic_land_id(land: MapLandCandidateDetection) -> str:
    if land.coordinate_x is not None and land.coordinate_y is not None:
        return f"land-{land.coordinate_x}-{land.coordinate_y}"
    signature = land.model_dump(exclude_none=True)
    payload = json.dumps(signature, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"vision-land-{digest}"


def _bbox(land: MapLandCandidateDetection) -> dict[str, int] | None:
    return _button_bbox(
        x_min=land.x_min,
        y_min=land.y_min,
        x_max=land.x_max,
        y_max=land.y_max,
    )


def _toggle_dict(toggle: MapLandFilterToggleDetection) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "resource_type": toggle.resource_type,
        "selected": toggle.selected,
        "visible": toggle.visible,
        "enabled": toggle.enabled,
    }
    bbox = _button_bbox(
        x_min=toggle.x_min,
        y_min=toggle.y_min,
        x_max=toggle.x_max,
        y_max=toggle.y_max,
    )
    if bbox:
        payload["bbox"] = bbox
    return payload


def _level_toggle_dict(toggle: MapLandLevelToggleDetection) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "level": toggle.level,
        "selected": toggle.selected,
        "visible": toggle.visible,
        "enabled": toggle.enabled,
    }
    bbox = _button_bbox(
        x_min=toggle.x_min,
        y_min=toggle.y_min,
        x_max=toggle.x_max,
        y_max=toggle.y_max,
    )
    if bbox:
        payload["bbox"] = bbox
    return payload


def _button_dict(
    *,
    visible: bool,
    enabled: bool,
    x_min: int | None,
    y_min: int | None,
    x_max: int | None,
    y_max: int | None,
) -> dict[str, Any] | None:
    if not visible:
        return None
    payload: dict[str, Any] = {"visible": visible, "enabled": enabled}
    bbox = _button_bbox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)
    if bbox:
        payload["bbox"] = bbox
    return payload


def _button_bbox(
    *,
    x_min: int | None,
    y_min: int | None,
    x_max: int | None,
    y_max: int | None,
) -> dict[str, int] | None:
    if any(value is None for value in (x_min, y_min, x_max, y_max)):
        return None
    return {
        "x_min": int(x_min),
        "y_min": int(y_min),
        "x_max": int(x_max),
        "y_max": int(y_max),
    }


def _set_if_not_none(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        payload[key] = value


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
