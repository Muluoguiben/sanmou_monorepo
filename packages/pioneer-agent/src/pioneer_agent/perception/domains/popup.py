from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    POPUP_DETECTION_INSTRUCTION,
    POPUP_DETECTION_SCHEMA,
    PopupDetection,
)

SOURCE_LABEL = "vision.popup"


@dataclass
class PopupFragment:
    global_state: dict[str, Any] = field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: PopupDetection | None = None


def extract_popup(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> PopupFragment:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=POPUP_DETECTION_INSTRUCTION,
        response_schema=POPUP_DETECTION_SCHEMA,
    )
    parsed = PopupDetection.model_validate(result.data)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: PopupDetection,
    *,
    captured_at: datetime | None,
) -> PopupFragment:
    popup = {
        "visible": parsed.popup_visible,
        "type": parsed.popup_type,
        "blocking": parsed.blocking,
        "safe_default_action": parsed.safe_default_action,
        "buttons": [_button_dict(button) for button in parsed.buttons],
    }
    if parsed.title:
        popup["title"] = parsed.title
    if parsed.message:
        popup["message"] = parsed.message

    field_meta = {
        "global_state.popup": FieldMeta(
            value="loaded",
            confidence=0.85,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )
    }
    return PopupFragment(
        global_state={"popup": popup},
        field_meta=field_meta,
        notes=list(parsed.visible_notes),
        raw=parsed,
    )


def _button_dict(button: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "label": button.label,
        "role": button.role,
        "enabled": button.enabled,
    }
    if all(
        value is not None
        for value in (button.x_min, button.y_min, button.x_max, button.y_max)
    ):
        item["bbox"] = {
            "x_min": button.x_min,
            "y_min": button.y_min,
            "x_max": button.x_max,
            "y_max": button.y_max,
        }
    return item
