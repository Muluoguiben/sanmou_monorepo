from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    MODE_HUB_INSTRUCTION,
    MODE_HUB_SCHEMA,
    ModeHubDetection,
)

SOURCE_LABEL = "vision.mode_hub"


@dataclass
class ModeHubFragment:
    global_state: dict[str, Any] = field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: ModeHubDetection | None = None


def extract_mode_hub(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> ModeHubFragment:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=MODE_HUB_INSTRUCTION,
        response_schema=MODE_HUB_SCHEMA,
    )
    parsed = ModeHubDetection.model_validate(result.data)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: ModeHubDetection,
    *,
    captured_at: datetime | None,
) -> ModeHubFragment:
    payload: dict[str, Any] = {
        "page_type": parsed.page_type,
        "entries": [_entry_dict(entry) for entry in parsed.entries],
    }
    for key, value in (
        ("title", parsed.title),
        ("active_tab", parsed.active_tab),
        ("total_score", parsed.total_score),
        ("rank", parsed.rank),
        ("phase_status", parsed.phase_status),
        ("countdown", parsed.countdown),
    ):
        if value is not None:
            payload[key] = value

    state_key = "event_tournament" if parsed.page_type == "event_tournament" else "mode_hub"
    return ModeHubFragment(
        global_state={state_key: payload},
        field_meta={
            f"global_state.{state_key}": FieldMeta(
                value="loaded",
                confidence=0.85,
                source=SOURCE_LABEL,
                updated_at=captured_at,
            )
        },
        notes=list(parsed.visible_notes),
        raw=parsed,
    )


def _entry_dict(entry: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": entry.name,
        "status": entry.status,
        "can_enter": entry.can_enter,
        "can_claim": entry.can_claim,
        "can_reset": entry.can_reset,
        "can_register": entry.can_register,
    }
    for key in ("score", "rank", "countdown", "button_label"):
        value = getattr(entry, key)
        if value is not None:
            item[key] = value
    bbox = _bbox(entry.x_min, entry.y_min, entry.x_max, entry.y_max)
    if bbox:
        item["bbox"] = bbox
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
