from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    CHAPTER_PANEL_INSTRUCTION,
    CHAPTER_PANEL_SCHEMA,
    ChapterPanelDetection,
)

SOURCE_LABEL = "vision.chapter_panel"


@dataclass
class ChapterPanelFragment:
    progress: dict[str, Any] = field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: ChapterPanelDetection | None = None


def extract_chapter_panel(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> ChapterPanelFragment:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=CHAPTER_PANEL_INSTRUCTION,
        response_schema=CHAPTER_PANEL_SCHEMA,
    )
    parsed = ChapterPanelDetection.model_validate(result.data, strict=True)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: ChapterPanelDetection,
    *,
    captured_at: datetime | None,
) -> ChapterPanelFragment:
    progress: dict[str, Any] = {
        "chapter_claimable": parsed.chapter_claimable,
        "chapter_tasks": [_task_dict(task) for task in parsed.tasks],
    }
    if parsed.current_chapter_id is not None:
        progress["current_chapter_id"] = parsed.current_chapter_id
    if parsed.current_chapter_title:
        progress["current_chapter_title"] = parsed.current_chapter_title
    if parsed.claim_button_visible:
        progress["chapter_claim_button"] = {
            "visible": parsed.claim_button_visible,
            "enabled": parsed.claim_button_enabled,
        }
        bbox = _claim_button_bbox(parsed)
        if bbox:
            progress["chapter_claim_button"]["bbox"] = bbox

    return ChapterPanelFragment(
        progress=progress,
        field_meta={
            "progress.chapter_panel": FieldMeta(
                value="loaded",
                confidence=0.85,
                source=SOURCE_LABEL,
                updated_at=captured_at,
            )
        },
        notes=list(parsed.visible_notes),
        raw=parsed,
    )


def _task_dict(task: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": task.name,
        "reward_claimable": task.reward_claimable,
    }
    if task.completed is not None:
        item["completed"] = task.completed
    if task.current is not None:
        item["current"] = task.current
    if task.required is not None:
        item["required"] = task.required
    return item


def _claim_button_bbox(parsed: ChapterPanelDetection) -> dict[str, int] | None:
    values = (
        parsed.claim_x_min,
        parsed.claim_y_min,
        parsed.claim_x_max,
        parsed.claim_y_max,
    )
    if any(value is None for value in values):
        return None
    return {
        "x_min": parsed.claim_x_min,  # type: ignore[dict-item]
        "y_min": parsed.claim_y_min,  # type: ignore[dict-item]
        "x_max": parsed.claim_x_max,  # type: ignore[dict-item]
        "y_max": parsed.claim_y_max,  # type: ignore[dict-item]
    }
