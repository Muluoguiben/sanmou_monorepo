from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    RECRUIT_PANEL_INSTRUCTION,
    RECRUIT_PANEL_SCHEMA,
    RecruitPanelDetection,
)

SOURCE_LABEL = "vision.recruit_panel"


@dataclass
class RecruitPanelFragment:
    economy: dict[str, Any] = field(default_factory=dict)
    teams: list[dict[str, Any]] = field(default_factory=list)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: RecruitPanelDetection | None = None


def extract_recruit_panel(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> RecruitPanelFragment:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=RECRUIT_PANEL_INSTRUCTION,
        response_schema=RECRUIT_PANEL_SCHEMA,
    )
    parsed = RecruitPanelDetection.model_validate(result.data)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: RecruitPanelDetection,
    *,
    captured_at: datetime | None,
) -> RecruitPanelFragment:
    economy: dict[str, Any] = {}
    if parsed.reserve_troops is not None:
        economy["reserve_troops"] = parsed.reserve_troops

    teams = [_team_dict(team) for team in parsed.teams]
    field_meta = {
        "teams.recruit_panel": FieldMeta(
            value="loaded",
            confidence=0.85,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )
    }
    if economy:
        field_meta["economy.reserve_troops"] = FieldMeta(
            value=parsed.reserve_troops,
            confidence=0.85,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )

    return RecruitPanelFragment(
        economy=economy,
        teams=teams,
        field_meta=field_meta,
        notes=list(parsed.visible_notes),
        raw=parsed,
    )


def _team_dict(team: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "status": "recruiting" if team.recruiting else "idle",
        "can_recruit_now": team.can_recruit_now,
    }
    if team.team_id:
        item["team_id"] = team.team_id
    if team.team_name:
        item["team_name"] = team.team_name
    if team.soldiers is not None:
        item["soldiers"] = team.soldiers
    if team.max_soldiers is not None:
        item["max_soldiers"] = team.max_soldiers
    if team.soldiers is not None and team.max_soldiers is not None:
        item["soldier_deficit"] = max(team.max_soldiers - team.soldiers, 0)
    if team.recruit_finish_time:
        item["recruit_finish_time"] = team.recruit_finish_time
    if team.recruit_button_visible:
        item["recruit_button"] = {
            "visible": team.recruit_button_visible,
            "enabled": team.recruit_button_enabled,
        }
        bbox = _button_bbox(team)
        if bbox:
            item["recruit_button"]["bbox"] = bbox
    return item


def _button_bbox(team: Any) -> dict[str, int] | None:
    values = (
        team.button_x_min,
        team.button_y_min,
        team.button_x_max,
        team.button_y_max,
    )
    if any(value is None for value in values):
        return None
    return {
        "x_min": team.button_x_min,
        "y_min": team.button_y_min,
        "x_max": team.button_x_max,
        "y_max": team.button_y_max,
    }
