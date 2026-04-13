"""Prompt templates and response schemas for each vision extraction domain.

Each domain pairs:
- a Pydantic model describing the parsed structure (for downstream type safety)
- a JSON schema dict passed to Gemini's `response_schema`
- an instruction string grounding the model in the 三国·谋定天下 UI
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PageType = Literal[
    "main_map",
    "city",
    "hero_list",
    "building",
    "battle",
    "chapter",
    "team",
    "lineup",
    "unknown",
]


class ResourceBar(BaseModel):
    military_order: int | None = None
    military_order_max: int | None = None
    copper: int | None = None
    wood: int | None = None
    iron: int | None = None
    stone: int | None = None
    grain: int | None = None
    gold_bead: int | None = None
    yuanbao: int | None = None


class PageDetection(BaseModel):
    page_type: PageType
    resources: ResourceBar = Field(default_factory=ResourceBar)
    visible_notes: list[str] = Field(default_factory=list)


PAGE_DETECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page_type": {
            "type": "string",
            "enum": [
                "main_map",
                "city",
                "hero_list",
                "building",
                "battle",
                "chapter",
                "team",
                "lineup",
                "unknown",
            ],
            "description": "Which game page is shown.",
        },
        "resources": {
            "type": "object",
            "description": "Top bar resources. Omit a field if not visible.",
            "properties": {
                "military_order": {"type": "integer", "description": "军令 current"},
                "military_order_max": {"type": "integer", "description": "军令 cap"},
                "copper": {"type": "integer", "description": "铜币"},
                "wood": {"type": "integer", "description": "木材"},
                "iron": {"type": "integer", "description": "铁矿"},
                "stone": {"type": "integer", "description": "石料"},
                "grain": {"type": "integer", "description": "粮食"},
                "gold_bead": {"type": "integer", "description": "金铢"},
                "yuanbao": {"type": "integer", "description": "元宝"},
            },
        },
        "visible_notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Notable UI elements: buttons, alerts, popups, countdowns.",
        },
    },
    "required": ["page_type", "resources"],
}


PAGE_DETECTION_INSTRUCTION = (
    "This is a screenshot from the Chinese mobile game 三国·谋定天下 "
    "(Sanguo: Strategy Under Heaven). Identify the page type and extract all numeric "
    "resource values from the top bar. "
    "Convert shorthand like '570万' to 5700000, '1.2K' to 1200, '5.22M' to 5220000. "
    "Omit any field you cannot clearly see — do not guess."
)
