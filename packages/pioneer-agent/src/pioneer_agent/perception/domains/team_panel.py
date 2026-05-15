"""Extract structured team / lineup state from a team panel screenshot."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    TEAM_PANEL_INSTRUCTION,
    TEAM_PANEL_SCHEMA,
    TeamHeroDetection,
    TeamPanelDetection,
)

SOURCE_LABEL = "vision.team_panel"
DEFAULT_MISSING_DETAIL_TABS = [
    "装备",
    "马匹",
    "兵书",
    "属性加点",
    "战法等级",
    "兵种适性",
]
DETAIL_TAB_ALIASES = {
    "坐骑": "马匹",
    "加点": "属性加点",
}


@dataclass
class TeamPanelFragment:
    teams: list[dict[str, Any]] = field(default_factory=list)
    team_containers: list[dict[str, Any]] = field(default_factory=list)
    main_lineup: dict[str, Any] = field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: TeamPanelDetection | None = None


def extract_team_panel(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> TeamPanelFragment:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=TEAM_PANEL_INSTRUCTION,
        response_schema=TEAM_PANEL_SCHEMA,
    )
    parsed = TeamPanelDetection.model_validate(result.data)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: TeamPanelDetection,
    *,
    captured_at: datetime | None,
) -> TeamPanelFragment:
    team_id = parsed.team_id or parsed.team_name or "visible_team"
    heroes = [_hero_dict(hero) for hero in parsed.heroes]
    soldiers = _sum_int(hero.soldiers for hero in parsed.heroes)
    max_soldiers = _sum_int(hero.max_soldiers for hero in parsed.heroes)
    total_soldiers = parsed.total_soldiers if parsed.total_soldiers is not None else soldiers
    total_max_soldiers = parsed.max_soldiers if parsed.max_soldiers is not None else max_soldiers
    soldier_deficit = (
        max(total_max_soldiers - total_soldiers, 0)
        if total_soldiers is not None and total_max_soldiers is not None
        else None
    )
    supply_ratio = _ratio(parsed.supply, parsed.supply_max)

    team: dict[str, Any] = {
        "team_id": team_id,
        "page_type": "team_panel",
        "heroes": heroes,
        "formation": parsed.formation,
        "formation_active": parsed.formation_active,
        "bond_active": parsed.bond_active,
        "visible_entry_points": list(parsed.visible_entry_points),
        "readiness_notes": list(parsed.readiness_notes),
        "missing_detail_tabs": _missing_detail_tabs(parsed),
    }
    _set_if_not_none(team, "team_name", parsed.team_name)
    _set_if_not_none(team, "soldiers", total_soldiers)
    _set_if_not_none(team, "max_soldiers", total_max_soldiers)
    _set_if_not_none(team, "soldier_deficit", soldier_deficit)
    _set_if_not_none(team, "supply", parsed.supply)
    _set_if_not_none(team, "supply_max", parsed.supply_max)
    _set_if_not_none(team, "supply_ratio", supply_ratio)
    team = _drop_none(team)

    container: dict[str, Any] = {
        "team_id": team_id,
        "source": SOURCE_LABEL,
        "status": "observed",
        "can_march_now": None,
        "can_recruit_now": None,
    }
    _set_if_not_none(container, "soldiers", total_soldiers)
    _set_if_not_none(container, "max_soldiers", total_max_soldiers)
    _set_if_not_none(container, "soldier_deficit", soldier_deficit)
    if parsed.heroes:
        stamina_values = [hero.stamina for hero in parsed.heroes if hero.stamina is not None]
        if stamina_values:
            container["container_stamina"] = min(stamina_values)
    container = _drop_none(container)

    main_lineup = {
        "current_host_team_id": team_id,
        "team_snapshot_source": SOURCE_LABEL,
        "team_readiness": _readiness_summary(
            parsed,
            soldier_deficit=soldier_deficit,
            missing_detail_tabs=team["missing_detail_tabs"],
        ),
    }

    field_meta: dict[str, FieldMeta] = {}
    if team:
        field_meta["teams"] = FieldMeta(
            value="loaded",
            confidence=0.86,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )
        field_meta["team_containers"] = FieldMeta(
            value="loaded",
            confidence=0.8,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )
        field_meta["main_lineup.team_readiness"] = FieldMeta(
            value="loaded",
            confidence=0.8,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )

    return TeamPanelFragment(
        teams=[team] if team else [],
        team_containers=[container] if container else [],
        main_lineup=main_lineup,
        field_meta=field_meta,
        notes=list(parsed.visible_notes) + list(parsed.readiness_notes),
        raw=parsed,
    )


def _hero_dict(hero: TeamHeroDetection) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": hero.name,
        "level": hero.level,
        "soldiers": hero.soldiers,
        "max_soldiers": hero.max_soldiers,
        "stamina": hero.stamina,
        "stamina_max": hero.stamina_max,
        "position": hero.position,
        "tactics": list(hero.tactics),
        "status_notes": list(hero.status_notes),
    }
    if hero.soldiers is not None and hero.max_soldiers:
        payload["soldier_ratio"] = round(hero.soldiers / hero.max_soldiers, 4)
        payload["soldier_deficit"] = max(hero.max_soldiers - hero.soldiers, 0)
    return _drop_none(payload)


def _readiness_summary(
    parsed: TeamPanelDetection,
    *,
    soldier_deficit: int | None,
    missing_detail_tabs: list[str],
) -> dict[str, Any]:
    return {
        "formation_active": parsed.formation_active,
        "bond_active": parsed.bond_active,
        "soldier_deficit": soldier_deficit,
        "supply_ratio": _ratio(parsed.supply, parsed.supply_max),
        "missing_detail_tabs": missing_detail_tabs,
        "requires_detail_review": bool(missing_detail_tabs),
        "notes": list(parsed.readiness_notes),
    }


def _missing_detail_tabs(parsed: TeamPanelDetection) -> list[str]:
    values: list[str] = []
    for value in [*parsed.missing_detail_tabs, *DEFAULT_MISSING_DETAIL_TABS]:
        normalized = DETAIL_TAB_ALIASES.get(value, value)
        if normalized not in values:
            values.append(normalized)
    return values


def _sum_int(values: Any) -> int | None:
    materialized = [value for value in values if value is not None]
    if not materialized:
        return None
    return int(sum(materialized))


def _ratio(current: int | None, maximum: int | None) -> float | None:
    if current is None or not maximum:
        return None
    return round(current / maximum, 4)


def _set_if_not_none(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        payload[key] = value


def _drop_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
