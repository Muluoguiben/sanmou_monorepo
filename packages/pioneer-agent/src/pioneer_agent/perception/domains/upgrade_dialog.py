from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    UPGRADE_DIALOG_INSTRUCTION,
    UPGRADE_DIALOG_SCHEMA,
    UpgradeDialogDetection,
)

SOURCE_LABEL = "vision.upgrade_dialog"


@dataclass
class UpgradeDialogFragment:
    city: dict[str, Any] = field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: UpgradeDialogDetection | None = None


def extract_upgrade_dialog(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> UpgradeDialogFragment:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=UPGRADE_DIALOG_INSTRUCTION,
        response_schema=UPGRADE_DIALOG_SCHEMA,
    )
    parsed = UpgradeDialogDetection.model_validate(result.data)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: UpgradeDialogDetection,
    *,
    captured_at: datetime | None,
) -> UpgradeDialogFragment:
    dialog: dict[str, Any] = {
        "visible": parsed.dialog_visible,
        "costs": [_cost_dict(cost) for cost in parsed.costs],
        "confirm_button": {
            "visible": parsed.confirm_button_visible,
            "enabled": parsed.confirm_button_enabled,
        },
        "close_button": {"visible": parsed.close_button_visible},
    }
    for key, value in (
        ("building_name", parsed.building_name),
        ("current_level", parsed.current_level),
        ("next_level", parsed.next_level),
        ("can_upgrade", parsed.can_upgrade),
        ("cannot_upgrade_reason", parsed.cannot_upgrade_reason),
    ):
        if value is not None:
            dialog[key] = value
    confirm_bbox = _bbox(
        parsed.confirm_x_min,
        parsed.confirm_y_min,
        parsed.confirm_x_max,
        parsed.confirm_y_max,
    )
    if confirm_bbox:
        dialog["confirm_button"]["bbox"] = confirm_bbox
    close_bbox = _bbox(
        parsed.close_x_min,
        parsed.close_y_min,
        parsed.close_x_max,
        parsed.close_y_max,
    )
    if close_bbox:
        dialog["close_button"]["bbox"] = close_bbox

    return UpgradeDialogFragment(
        city={"upgrade_dialog": dialog},
        field_meta={
            "city.upgrade_dialog": FieldMeta(
                value="loaded",
                confidence=0.85,
                source=SOURCE_LABEL,
                updated_at=captured_at,
            )
        },
        notes=list(parsed.visible_notes),
        raw=parsed,
    )


def _cost_dict(cost: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"name": cost.name}
    if cost.required is not None:
        item["required"] = cost.required
    if cost.available is not None:
        item["available"] = cost.available
    if cost.enough is not None:
        item["enough"] = cost.enough
    return item


def _bbox(
    x_min: int | None,
    y_min: int | None,
    x_max: int | None,
    y_max: int | None,
) -> dict[str, int] | None:
    if any(value is None for value in (x_min, y_min, x_max, y_max)):
        return None
    return {
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
    }
