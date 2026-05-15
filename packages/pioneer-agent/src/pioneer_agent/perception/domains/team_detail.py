"""Extract structured team detail state from hero/equipment/book/tactic pages."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    TEAM_DETAIL_INSTRUCTION,
    TEAM_DETAIL_SCHEMA,
    TeamDetailDetection,
    TeamHeroDetailDetection,
)
from .team_panel import DEFAULT_MISSING_DETAIL_TABS, DETAIL_TAB_ALIASES

SOURCE_LABEL = "vision.team_detail"


@dataclass
class TeamDetailFragment:
    teams: list[dict[str, Any]] = field(default_factory=list)
    main_lineup: dict[str, Any] = field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: TeamDetailDetection | None = None


def extract_team_detail(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> TeamDetailFragment:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=TEAM_DETAIL_INSTRUCTION,
        response_schema=TEAM_DETAIL_SCHEMA,
    )
    parsed = TeamDetailDetection.model_validate(result.data)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: TeamDetailDetection,
    *,
    captured_at: datetime | None,
) -> TeamDetailFragment:
    observed_tabs = _observed_tabs(parsed)
    detail_status = _detail_status(observed_tabs, parsed.missing_detail_tabs)
    missing_detail_tabs = _missing_tabs(detail_status)
    team_id = parsed.team_id or parsed.team_name

    team: dict[str, Any] = {
        "page_type": "team_detail",
        "detail_status": detail_status,
        "missing_detail_tabs": missing_detail_tabs,
        "heroes": [_hero_detail_dict(hero) for hero in parsed.heroes],
        "team_effects": list(parsed.team_effects),
        "team_snapshot": {
            "source": SOURCE_LABEL,
            "detail_completion": _detail_completion(detail_status),
            "pvp_pve_basis_ready": not missing_detail_tabs,
            "basis_fields": _basis_fields(detail_status),
        },
    }
    _set_if_not_none(team, "team_id", team_id)
    _set_if_not_none(team, "team_name", parsed.team_name)
    team = _drop_empty(team)
    team["missing_detail_tabs"] = missing_detail_tabs

    readiness = {
        "missing_detail_tabs": missing_detail_tabs,
        "requires_detail_review": bool(missing_detail_tabs),
        "detail_completion": _detail_completion(detail_status),
        "pvp_pve_basis_ready": not missing_detail_tabs,
    }

    main_lineup = {
        "team_snapshot_source": SOURCE_LABEL,
        "team_snapshot": team.get("team_snapshot", {}),
        "team_readiness": readiness,
    }
    if team_id:
        main_lineup["current_host_team_id"] = team_id

    field_meta: dict[str, FieldMeta] = {}
    if team:
        field_meta["teams.team_detail"] = FieldMeta(
            value="loaded",
            confidence=0.84,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )
        field_meta["main_lineup.team_snapshot"] = FieldMeta(
            value="loaded",
            confidence=0.78,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )
        field_meta["main_lineup.team_readiness"] = FieldMeta(
            value="loaded",
            confidence=0.78,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )

    return TeamDetailFragment(
        teams=[team] if team else [],
        main_lineup=main_lineup,
        field_meta=field_meta,
        notes=list(parsed.visible_notes),
        raw=parsed,
    )


def _hero_detail_dict(hero: TeamHeroDetailDetection) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": hero.name,
        "level": hero.level,
        "role": hero.role,
        "attributes": dict(hero.attributes),
        "attribute_points": dict(hero.attribute_points),
        "soldier_specialties": list(hero.soldier_specialties),
        "equipment": [_equipment_dict(item) for item in hero.equipment],
        "mount": _mount_dict(hero.mount) if hero.mount is not None else None,
        "books": [_book_dict(item) for item in hero.books],
        "tactic_details": [_tactic_dict(item) for item in hero.tactic_details],
        "status_notes": list(hero.status_notes),
    }
    return _drop_empty(payload)


def _equipment_dict(item: Any) -> dict[str, Any]:
    return _drop_empty(
        {
            "slot": item.slot,
            "name": item.name,
            "level": item.level,
            "rarity": item.rarity,
            "attributes": dict(item.attributes),
            "effects": list(item.effects),
            "status_notes": list(item.status_notes),
        }
    )


def _mount_dict(item: Any) -> dict[str, Any]:
    return _drop_empty(
        {
            "name": item.name,
            "level": item.level,
            "quality": item.quality,
            "attributes": dict(item.attributes),
            "skills": list(item.skills),
            "status_notes": list(item.status_notes),
        }
    )


def _book_dict(item: Any) -> dict[str, Any]:
    return _drop_empty(
        {
            "slot": item.slot,
            "name": item.name,
            "level": item.level,
            "active": item.active,
            "effects": list(item.effects),
            "status_notes": list(item.status_notes),
        }
    )


def _tactic_dict(item: Any) -> dict[str, Any]:
    return _drop_empty(
        {
            "name": item.name,
            "level": item.level,
            "max_level": item.max_level,
            "slot": item.slot,
            "quality": item.quality,
            "effects": list(item.effects),
            "status_notes": list(item.status_notes),
        }
    )


def _observed_tabs(parsed: TeamDetailDetection) -> list[str]:
    observed = [_normalize_tab(tab) for tab in parsed.detail_tabs_observed]
    for hero in parsed.heroes:
        if hero.equipment:
            observed.append("装备")
        if hero.mount is not None:
            observed.append("马匹")
        if hero.books:
            observed.append("兵书")
        if hero.attribute_points:
            observed.append("属性加点")
        if hero.tactic_details:
            observed.append("战法等级")
        if hero.soldier_specialties:
            observed.append("兵种适性")
    return _unique(tab for tab in observed if tab)


def _detail_status(observed_tabs: list[str], missing_tabs: list[str]) -> dict[str, str]:
    status = {tab: "missing" for tab in DEFAULT_MISSING_DETAIL_TABS}
    for tab in missing_tabs:
        normalized = _normalize_tab(tab)
        if normalized:
            status.setdefault(normalized, "missing")
    for tab in observed_tabs:
        status[tab] = "observed"
    return status


def _missing_tabs(detail_status: dict[str, str]) -> list[str]:
    return [tab for tab in DEFAULT_MISSING_DETAIL_TABS if detail_status.get(tab) != "observed"]


def _detail_completion(detail_status: dict[str, str]) -> dict[str, bool]:
    return {
        tab: detail_status.get(tab) == "observed"
        for tab in DEFAULT_MISSING_DETAIL_TABS
    }


def _basis_fields(detail_status: dict[str, str]) -> list[str]:
    return [
        tab
        for tab in DEFAULT_MISSING_DETAIL_TABS
        if detail_status.get(tab) == "observed"
    ]


def _normalize_tab(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    return DETAIL_TAB_ALIASES.get(stripped, stripped)


def _unique(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _set_if_not_none(payload: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        payload[key] = value


def _drop_empty(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != {} and value != []
    }
