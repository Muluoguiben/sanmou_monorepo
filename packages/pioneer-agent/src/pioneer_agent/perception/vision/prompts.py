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


# ---------------------------------------------------------------------------
# City buildings (城内建筑) — internal city view
# ---------------------------------------------------------------------------

KNOWN_CITY_BUILDINGS = (
    "君王殿",  # King's Palace (main building)
    "征兵所",  # Recruitment Office
    "军营",    # Barracks
    "铁匠铺",  # Blacksmith
    "寻访台",  # Scout / Search Tower
    "治铁场",  # Iron Smelter
    "磨坊",    # Mill
    "石工所",  # Stone Workshop
    "木工所",  # Woodwork Shop
    "仓库",    # Warehouse
    "民居",    # Residence
)


class CityBuilding(BaseModel):
    name: str
    level: int | None = None
    upgrading: bool = False
    upgrade_eta: str | None = None  # "HH:MM:SS" countdown, if visible


class CityBuildingsDetection(BaseModel):
    prosperity: int | None = None
    territory: str | None = None  # e.g. "60/60"
    roads: str | None = None       # e.g. "6/35"
    buildings: list[CityBuilding] = Field(default_factory=list)
    visible_notes: list[str] = Field(default_factory=list)


CITY_BUILDINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prosperity": {"type": "integer", "description": "繁荣 value shown top-left."},
        "territory": {
            "type": "string",
            "description": "领地 current/max, e.g. '60/60'.",
        },
        "roads": {
            "type": "string",
            "description": "道路 current/max, e.g. '6/35'.",
        },
        "buildings": {
            "type": "array",
            "description": "One entry per building visible in the city view.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Canonical Chinese name of the building. Known buildings: "
                            "君王殿, 征兵所, 军营, 铁匠铺, 寻访台, 治铁场, 磨坊, "
                            "石工所, 木工所, 仓库, 民居."
                        ),
                    },
                    "level": {
                        "type": "integer",
                        "description": "Current level (小数字显示在建筑图标旁).",
                    },
                    "upgrading": {
                        "type": "boolean",
                        "description": "True if an upgrade countdown is visible on this building.",
                    },
                    "upgrade_eta": {
                        "type": "string",
                        "description": "Countdown text as shown, e.g. '17:45:36'. Null if not upgrading.",
                    },
                },
                "required": ["name"],
            },
        },
        "visible_notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Notable overlays, alerts or banners.",
        },
    },
    "required": ["buildings"],
}


CITY_BUILDINGS_INSTRUCTION = (
    "This is a screenshot of the 城内 (internal city) view from 三国·谋定天下. "
    "Extract every visible building together with its level and any upgrade countdown. "
    "Level numbers appear as small digits beside or on the building icon. "
    "An upgrade is in progress when a countdown timer (HH:MM:SS) is shown on the "
    "building — set upgrading=true and copy the timer into upgrade_eta. "
    "Also capture 繁荣 / 领地 / 道路 from the top-left panel if visible. "
    "Do not invent buildings that are not in the screenshot; omit fields you cannot read."
)
