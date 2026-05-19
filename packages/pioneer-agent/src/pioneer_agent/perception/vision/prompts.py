"""Prompt templates and response schemas for each vision extraction domain.

Each domain pairs:
- a Pydantic model describing the parsed structure (for downstream type safety)
- a JSON schema dict passed to Gemini's `response_schema`
- an instruction string grounding the model in the 三国·谋定天下 UI
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

PageType = Literal[
    "main_map",
    "city",
    "hero_list",
    "building",
    "upgrade_dialog",
    "battle",
    "chapter",
    "recruit",
    "team",
    "team_panel",
    "lineup",
    "lineup_config",
    "hero_detail",
    "tactic_detail",
    "equipment_mount",
    "formation_books",
    "event_tournament",
    "mode_hub",
    "unknown",
]

BBoxFields = tuple[str, str, str, str]


def _bbox_values(model: BaseModel, fields: BBoxFields) -> list[int | None]:
    return [getattr(model, field) for field in fields]


def _bbox_has_any(model: BaseModel, fields: BBoxFields) -> bool:
    return any(value is not None for value in _bbox_values(model, fields))


def _validate_bbox(model: BaseModel, fields: BBoxFields, label: str, *, required: bool = False) -> None:
    values = _bbox_values(model, fields)
    if not required and not any(value is not None for value in values):
        return
    if any(value is None for value in values):
        raise ValueError(f"{label} bbox must include x_min, y_min, x_max, y_max")
    x_min, y_min, x_max, y_max = values
    if x_min >= x_max or y_min >= y_max:
        raise ValueError(f"{label} bbox must satisfy x_min < x_max and y_min < y_max")


def _validate_visible_button(
    model: BaseModel,
    *,
    visible_field: str,
    enabled_field: str,
    bbox_fields: BBoxFields,
    label: str,
) -> None:
    visible = bool(getattr(model, visible_field))
    enabled = bool(getattr(model, enabled_field))
    if enabled and not visible:
        raise ValueError(f"{label} cannot be enabled when not visible")
    if not visible and _bbox_has_any(model, bbox_fields):
        raise ValueError(f"{label} bbox cannot be present when not visible")
    _validate_bbox(model, bbox_fields, label, required=visible)


def _validate_visible_bbox(
    model: BaseModel,
    *,
    visible_field: str,
    bbox_fields: BBoxFields,
    label: str,
) -> None:
    visible = bool(getattr(model, visible_field))
    if not visible and _bbox_has_any(model, bbox_fields):
        raise ValueError(f"{label} bbox cannot be present when not visible")
    _validate_bbox(model, bbox_fields, label, required=visible)


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
                "upgrade_dialog",
                "battle",
                "chapter",
                "recruit",
                "team",
                "team_panel",
                "lineup",
                "lineup_config",
                "hero_detail",
                "tactic_detail",
                "equipment_mount",
                "formation_books",
                "event_tournament",
                "mode_hub",
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
# Popup detector (通用弹窗 / 确认框)
# ---------------------------------------------------------------------------

class PopupButtonDetection(BaseModel):
    label: str
    role: Literal["confirm", "cancel", "close", "other"] = "other"
    enabled: bool = True
    x_min: int | None = Field(default=None, ge=0, le=1000)
    y_min: int | None = Field(default=None, ge=0, le=1000)
    x_max: int | None = Field(default=None, ge=0, le=1000)
    y_max: int | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def _validate_button_bbox(self):
        _validate_bbox(self, ("x_min", "y_min", "x_max", "y_max"), "popup button")
        return self


class PopupDetection(BaseModel):
    popup_visible: bool = False
    popup_type: Literal["confirmation", "reward", "error", "notice", "unknown"] = "unknown"
    title: str | None = None
    message: str | None = None
    blocking: bool = False
    safe_default_action: Literal["close", "cancel", "confirm", "none", "unknown"] = "unknown"
    buttons: list[PopupButtonDetection] = Field(default_factory=list)
    visible_notes: list[str] = Field(default_factory=list)


POPUP_DETECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "popup_visible": {"type": "boolean"},
        "popup_type": {
            "type": "string",
            "enum": ["confirmation", "reward", "error", "notice", "unknown"],
        },
        "title": {"type": "string"},
        "message": {"type": "string"},
        "blocking": {"type": "boolean"},
        "safe_default_action": {
            "type": "string",
            "enum": ["close", "cancel", "confirm", "none", "unknown"],
        },
        "buttons": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "role": {
                        "type": "string",
                        "enum": ["confirm", "cancel", "close", "other"],
                    },
                    "enabled": {"type": "boolean"},
                    "x_min": {"type": "integer"},
                    "y_min": {"type": "integer"},
                    "x_max": {"type": "integer"},
                    "y_max": {"type": "integer"},
                },
                "required": ["label", "role"],
            },
        },
        "visible_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["popup_visible", "popup_type", "buttons"],
}


POPUP_DETECTION_INSTRUCTION = (
    "This screenshot may contain a modal popup, confirmation dialog, reward panel, "
    "notice, error dialog, or blocking overlay in 三国·谋定天下. Detect only the "
    "topmost blocking popup. Extract its title, visible message, buttons and "
    "button roles. Use 0-1000 normalized bbox coordinates for buttons when clear. "
    "safe_default_action should be close/cancel for unknown or risky dialogs; only "
    "use confirm for clearly harmless reward/acknowledgement popups."
)


# ---------------------------------------------------------------------------
# Mode hub / event tournament (征战入口 / 演武大会等活动)
# ---------------------------------------------------------------------------

class ModeHubEntryDetection(BaseModel):
    name: str
    status: Literal["available", "locked", "in_progress", "finished", "unknown"] = "unknown"
    score: int | None = None
    rank: int | None = None
    countdown: str | None = None
    can_enter: bool = False
    can_claim: bool = False
    can_reset: bool = False
    can_register: bool = False
    button_label: str | None = None
    x_min: int | None = Field(default=None, ge=0, le=1000)
    y_min: int | None = Field(default=None, ge=0, le=1000)
    x_max: int | None = Field(default=None, ge=0, le=1000)
    y_max: int | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def _validate_entry_bbox(self):
        _validate_bbox(self, ("x_min", "y_min", "x_max", "y_max"), "mode hub entry")
        return self


class ModeHubDetection(BaseModel):
    page_type: Literal["event_tournament", "mode_hub", "unknown"] = "unknown"
    title: str | None = None
    active_tab: str | None = None
    entries: list[ModeHubEntryDetection] = Field(default_factory=list)
    total_score: int | None = None
    rank: int | None = None
    phase_status: str | None = None
    countdown: str | None = None
    visible_notes: list[str] = Field(default_factory=list)


MODE_HUB_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page_type": {
            "type": "string",
            "enum": ["event_tournament", "mode_hub", "unknown"],
        },
        "title": {"type": "string"},
        "active_tab": {"type": "string"},
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["available", "locked", "in_progress", "finished", "unknown"],
                    },
                    "score": {"type": "integer"},
                    "rank": {"type": "integer"},
                    "countdown": {"type": "string"},
                    "can_enter": {"type": "boolean"},
                    "can_claim": {"type": "boolean"},
                    "can_reset": {"type": "boolean"},
                    "can_register": {"type": "boolean"},
                    "button_label": {"type": "string"},
                    "x_min": {"type": "integer"},
                    "y_min": {"type": "integer"},
                    "x_max": {"type": "integer"},
                    "y_max": {"type": "integer"},
                },
                "required": ["name", "status"],
            },
        },
        "total_score": {"type": "integer"},
        "rank": {"type": "integer"},
        "phase_status": {"type": "string"},
        "countdown": {"type": "string"},
        "visible_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["page_type", "entries"],
}


MODE_HUB_INSTRUCTION = (
    "This screenshot may show 三国·谋定天下 mode hub / 征战入口 / 演武大会 / "
    "远征 / 军演 / 养士兴功 pages. Extract the page type, title, active tab, "
    "visible activity entries, score, rank, countdown, phase/status, and whether "
    "each entry can be entered, claimed, reset, or registered. Use 0-1000 "
    "normalized bbox coordinates for clear entry/action buttons."
)


# ---------------------------------------------------------------------------
# Chapter panel (章节任务 / 章节奖励)
# ---------------------------------------------------------------------------

class ChapterTaskDetection(BaseModel):
    name: str
    completed: bool | None = None
    current: int | None = None
    required: int | None = None
    reward_claimable: bool = False


class ChapterPanelDetection(BaseModel):
    current_chapter_id: int | None = None
    current_chapter_title: str | None = None
    chapter_claimable: bool = False
    claim_button_visible: bool = False
    claim_button_enabled: bool = False
    claim_x_min: int | None = Field(default=None, ge=0, le=1000)
    claim_y_min: int | None = Field(default=None, ge=0, le=1000)
    claim_x_max: int | None = Field(default=None, ge=0, le=1000)
    claim_y_max: int | None = Field(default=None, ge=0, le=1000)
    tasks: list[ChapterTaskDetection] = Field(default_factory=list)
    visible_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_claim_button(self):
        _validate_visible_button(
            self,
            visible_field="claim_button_visible",
            enabled_field="claim_button_enabled",
            bbox_fields=("claim_x_min", "claim_y_min", "claim_x_max", "claim_y_max"),
            label="chapter claim button",
        )
        if self.chapter_claimable and not self.claim_button_enabled:
            raise ValueError("chapter_claimable requires an enabled claim button")
        return self


CHAPTER_PANEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "current_chapter_id": {"type": "integer"},
        "current_chapter_title": {"type": "string"},
        "chapter_claimable": {"type": "boolean"},
        "claim_button_visible": {"type": "boolean"},
        "claim_button_enabled": {"type": "boolean"},
        "claim_x_min": {"type": "integer"},
        "claim_y_min": {"type": "integer"},
        "claim_x_max": {"type": "integer"},
        "claim_y_max": {"type": "integer"},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "completed": {"type": "boolean"},
                    "current": {"type": "integer"},
                    "required": {"type": "integer"},
                    "reward_claimable": {"type": "boolean"},
                },
                "required": ["name"],
            },
        },
        "visible_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["chapter_claimable", "claim_button_visible", "claim_button_enabled", "tasks"],
}


CHAPTER_PANEL_INSTRUCTION = (
    "This screenshot shows the chapter task panel in 三国·谋定天下. Extract the "
    "current chapter id/title, visible task rows, progress numbers, completion "
    "state, and whether any chapter reward can be claimed now. If a claim/reward "
    "button is visible, report whether it is enabled and provide its 0-1000 "
    "normalized bbox coordinates when clear. Do not mark chapter_claimable true "
    "unless a visible enabled reward/领取 button is present."
)


# ---------------------------------------------------------------------------
# Recruit panel (征兵 / 预备兵 / 队伍兵力)
# ---------------------------------------------------------------------------

class RecruitTeamDetection(BaseModel):
    team_id: str | None = None
    team_name: str | None = None
    soldiers: int | None = None
    max_soldiers: int | None = None
    recruiting: bool = False
    recruit_finish_time: str | None = None
    can_recruit_now: bool = True
    recruit_button_visible: bool = False
    recruit_button_enabled: bool = False
    button_x_min: int | None = Field(default=None, ge=0, le=1000)
    button_y_min: int | None = Field(default=None, ge=0, le=1000)
    button_x_max: int | None = Field(default=None, ge=0, le=1000)
    button_y_max: int | None = Field(default=None, ge=0, le=1000)

    @model_validator(mode="after")
    def _validate_recruit_button(self):
        _validate_visible_button(
            self,
            visible_field="recruit_button_visible",
            enabled_field="recruit_button_enabled",
            bbox_fields=("button_x_min", "button_y_min", "button_x_max", "button_y_max"),
            label="recruit button",
        )
        return self


class RecruitPanelDetection(BaseModel):
    reserve_troops: int | None = None
    teams: list[RecruitTeamDetection] = Field(default_factory=list)
    visible_notes: list[str] = Field(default_factory=list)


RECRUIT_PANEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reserve_troops": {"type": "integer"},
        "teams": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "team_id": {"type": "string"},
                    "team_name": {"type": "string"},
                    "soldiers": {"type": "integer"},
                    "max_soldiers": {"type": "integer"},
                    "recruiting": {"type": "boolean"},
                    "recruit_finish_time": {"type": "string"},
                    "can_recruit_now": {"type": "boolean"},
                    "recruit_button_visible": {"type": "boolean"},
                    "recruit_button_enabled": {"type": "boolean"},
                    "button_x_min": {"type": "integer"},
                    "button_y_min": {"type": "integer"},
                    "button_x_max": {"type": "integer"},
                    "button_y_max": {"type": "integer"},
                },
            },
        },
        "visible_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["teams"],
}


RECRUIT_PANEL_INSTRUCTION = (
    "This screenshot shows the recruitment/soldier panel in 三国·谋定天下. "
    "Extract reserve troops (预备兵), each visible team slot, current soldiers, "
    "max soldiers, whether recruiting is already in progress, recruitment finish "
    "countdown/time, and whether the recruit/征兵 button is visible and enabled. "
    "Use 0-1000 normalized bbox coordinates for the recruit button when clear."
)


# ---------------------------------------------------------------------------
# Upgrade dialog (建筑升级确认框)
# ---------------------------------------------------------------------------

class UpgradeResourceCostDetection(BaseModel):
    name: str
    required: int | None = None
    available: int | None = None
    enough: bool | None = None


class UpgradeDialogDetection(BaseModel):
    dialog_visible: bool = False
    building_name: str | None = None
    current_level: int | None = None
    next_level: int | None = None
    can_upgrade: bool | None = None
    cannot_upgrade_reason: str | None = None
    costs: list[UpgradeResourceCostDetection] = Field(default_factory=list)
    confirm_button_visible: bool = False
    confirm_button_enabled: bool = False
    confirm_x_min: int | None = Field(default=None, ge=0, le=1000)
    confirm_y_min: int | None = Field(default=None, ge=0, le=1000)
    confirm_x_max: int | None = Field(default=None, ge=0, le=1000)
    confirm_y_max: int | None = Field(default=None, ge=0, le=1000)
    close_button_visible: bool = False
    close_x_min: int | None = Field(default=None, ge=0, le=1000)
    close_y_min: int | None = Field(default=None, ge=0, le=1000)
    close_x_max: int | None = Field(default=None, ge=0, le=1000)
    close_y_max: int | None = Field(default=None, ge=0, le=1000)
    visible_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_dialog_semantics(self):
        confirm_fields = ("confirm_x_min", "confirm_y_min", "confirm_x_max", "confirm_y_max")
        close_fields = ("close_x_min", "close_y_min", "close_x_max", "close_y_max")
        if not self.dialog_visible:
            has_dialog_payload = any(
                (
                    self.building_name,
                    self.current_level is not None,
                    self.next_level is not None,
                    self.can_upgrade is not None,
                    self.cannot_upgrade_reason,
                    self.costs,
                    self.confirm_button_visible,
                    self.confirm_button_enabled,
                    self.close_button_visible,
                    _bbox_has_any(self, confirm_fields),
                    _bbox_has_any(self, close_fields),
                )
            )
            if has_dialog_payload:
                raise ValueError("upgrade dialog fields require dialog_visible=true")
            return self
        _validate_visible_button(
            self,
            visible_field="confirm_button_visible",
            enabled_field="confirm_button_enabled",
            bbox_fields=confirm_fields,
            label="upgrade confirm button",
        )
        _validate_visible_bbox(
            self,
            visible_field="close_button_visible",
            bbox_fields=close_fields,
            label="upgrade close button",
        )
        if self.can_upgrade is True and not self.confirm_button_enabled:
            raise ValueError("can_upgrade requires an enabled confirm button")
        return self


UPGRADE_DIALOG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "dialog_visible": {"type": "boolean"},
        "building_name": {"type": "string"},
        "current_level": {"type": "integer"},
        "next_level": {"type": "integer"},
        "can_upgrade": {"type": "boolean"},
        "cannot_upgrade_reason": {"type": "string"},
        "costs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "required": {"type": "integer"},
                    "available": {"type": "integer"},
                    "enough": {"type": "boolean"},
                },
                "required": ["name"],
            },
        },
        "confirm_button_visible": {"type": "boolean"},
        "confirm_button_enabled": {"type": "boolean"},
        "confirm_x_min": {"type": "integer"},
        "confirm_y_min": {"type": "integer"},
        "confirm_x_max": {"type": "integer"},
        "confirm_y_max": {"type": "integer"},
        "close_button_visible": {"type": "boolean"},
        "close_x_min": {"type": "integer"},
        "close_y_min": {"type": "integer"},
        "close_x_max": {"type": "integer"},
        "close_y_max": {"type": "integer"},
        "visible_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["dialog_visible", "costs", "confirm_button_visible", "confirm_button_enabled"],
}


UPGRADE_DIALOG_INSTRUCTION = (
    "This screenshot may show a building upgrade confirmation dialog in 三国·谋定天下. "
    "Extract building name, current/next level, required resources, available resources, "
    "whether the upgrade can proceed, any visible disabled reason, and confirm/close "
    "button states. Use 0-1000 normalized bbox coordinates for confirm and close buttons "
    "when clear. Do not mark can_upgrade true unless the visible upgrade/升级 button is enabled."
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


# ---------------------------------------------------------------------------
# Team panel / lineup (部队总览 / 阵容基础状态)
# ---------------------------------------------------------------------------

class TeamHeroDetection(BaseModel):
    name: str
    level: int | None = None
    soldiers: int | None = None
    max_soldiers: int | None = None
    stamina: int | None = None
    stamina_max: int | None = None
    position: str | None = None
    tactics: list[str] = Field(default_factory=list)
    status_notes: list[str] = Field(default_factory=list)


class TeamPanelDetection(BaseModel):
    page_type: Literal["team_panel", "lineup_config", "team", "unknown"] = "team_panel"
    team_id: str | None = None
    team_name: str | None = None
    formation: str | None = None
    formation_active: bool | None = None
    bond_active: bool | None = None
    total_soldiers: int | None = None
    max_soldiers: int | None = None
    supply: int | None = None
    supply_max: int | None = None
    heroes: list[TeamHeroDetection] = Field(default_factory=list)
    visible_entry_points: list[str] = Field(default_factory=list)
    readiness_notes: list[str] = Field(default_factory=list)
    missing_detail_tabs: list[str] = Field(default_factory=list)
    visible_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_page_domain(self):
        if self.page_type == "unknown" and any(
            (
                self.team_id,
                self.team_name,
                self.formation,
                self.heroes,
                self.visible_entry_points,
            )
        ):
            raise ValueError("unknown team page_type cannot include team panel payload")
        return self


TEAM_PANEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page_type": {
            "type": "string",
            "enum": ["team_panel", "lineup_config", "team", "unknown"],
            "description": "Team-related page kind. Prefer team_panel for 部队总览.",
        },
        "team_id": {
            "type": "string",
            "description": "Visible team slot id, e.g. 部队一, 部队二. Omit if not visible.",
        },
        "team_name": {
            "type": "string",
            "description": "Visible custom team name or team label. Omit if not visible.",
        },
        "formation": {
            "type": "string",
            "description": "阵法 name, e.g. 雁形阵. Omit if not visible.",
        },
        "formation_active": {
            "type": "boolean",
            "description": "True if the UI explicitly shows 阵 已激活.",
        },
        "bond_active": {
            "type": "boolean",
            "description": "True if the UI explicitly shows 缘 已激活.",
        },
        "total_soldiers": {"type": "integer", "description": "Team total soldiers current."},
        "max_soldiers": {"type": "integer", "description": "Team max soldiers."},
        "supply": {"type": "integer", "description": "补给 current."},
        "supply_max": {"type": "integer", "description": "补给 max."},
        "heroes": {
            "type": "array",
            "description": "Visible heroes in the team, in screen order if possible.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "武将姓名."},
                    "level": {"type": "integer", "description": "武将等级."},
                    "soldiers": {"type": "integer", "description": "兵力 current."},
                    "max_soldiers": {"type": "integer", "description": "兵力 max."},
                    "stamina": {"type": "integer", "description": "体力 current."},
                    "stamina_max": {"type": "integer", "description": "体力 max."},
                    "position": {
                        "type": "string",
                        "description": "Visible position/role, e.g. 主将, 副将, 前锋. Omit if not visible.",
                    },
                    "tactics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Visible 战法 names under this hero.",
                    },
                    "status_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Warnings or visible markers for this hero.",
                    },
                },
                "required": ["name"],
            },
        },
        "visible_entry_points": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Visible buttons/tabs such as 编队, 配将助手, 装备, 兵书.",
        },
        "readiness_notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observable readiness notes: missing soldiers, low stamina, inactive bond, etc.",
        },
        "missing_detail_tabs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Important team details not visible from this screenshot but needed for advice.",
        },
        "visible_notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Other notable visible UI text or uncertainty notes.",
        },
    },
    "required": ["page_type", "heroes"],
}


TEAM_PANEL_INSTRUCTION = (
    "This is a screenshot from 三国·谋定天下 focused on a team, lineup, or 部队总览 panel. "
    "Extract only visible team facts into structured JSON: team slot, formation, 阵/缘 activation, "
    "total soldiers, supply, hero names, levels, per-hero soldiers, stamina, and visible tactics. "
    "Do not infer equipment, mounts, stat allocation, books, hidden tactic levels, or combat strength "
    "unless the screenshot explicitly shows them. Put those missing-but-important details in "
    "`missing_detail_tabs`. Use Chinese strings for visible labels and notes."
)


# ---------------------------------------------------------------------------
# Team detail pages — equipment / mount / books / stats / tactic levels
# ---------------------------------------------------------------------------

class TeamEquipmentDetection(BaseModel):
    slot: str | None = None
    name: str
    level: int | None = None
    rarity: str | None = None
    attributes: dict[str, int | float | str] = Field(default_factory=dict)
    effects: list[str] = Field(default_factory=list)
    status_notes: list[str] = Field(default_factory=list)


class TeamMountDetection(BaseModel):
    name: str | None = None
    level: int | None = None
    quality: str | None = None
    attributes: dict[str, int | float | str] = Field(default_factory=dict)
    skills: list[str] = Field(default_factory=list)
    status_notes: list[str] = Field(default_factory=list)


class TeamBookDetection(BaseModel):
    slot: str | None = None
    name: str
    level: int | None = None
    active: bool | None = None
    effects: list[str] = Field(default_factory=list)
    status_notes: list[str] = Field(default_factory=list)


class TeamTacticDetection(BaseModel):
    name: str
    level: int | None = None
    max_level: int | None = None
    slot: str | None = None
    quality: str | None = None
    effects: list[str] = Field(default_factory=list)
    status_notes: list[str] = Field(default_factory=list)


class TeamHeroDetailDetection(BaseModel):
    name: str
    level: int | None = None
    role: str | None = None
    attributes: dict[str, int | float | str] = Field(default_factory=dict)
    attribute_points: dict[str, int | float | str] = Field(default_factory=dict)
    soldier_specialties: list[str] = Field(default_factory=list)
    equipment: list[TeamEquipmentDetection] = Field(default_factory=list)
    mount: TeamMountDetection | None = None
    books: list[TeamBookDetection] = Field(default_factory=list)
    tactic_details: list[TeamTacticDetection] = Field(default_factory=list)
    status_notes: list[str] = Field(default_factory=list)


class TeamDetailDetection(BaseModel):
    page_type: Literal[
        "hero_detail",
        "tactic_detail",
        "equipment_mount",
        "formation_books",
        "lineup_config",
        "unknown",
    ] = "hero_detail"
    team_id: str | None = None
    team_name: str | None = None
    detail_tabs_observed: list[str] = Field(default_factory=list)
    heroes: list[TeamHeroDetailDetection] = Field(default_factory=list)
    team_effects: list[str] = Field(default_factory=list)
    missing_detail_tabs: list[str] = Field(default_factory=list)
    visible_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_page_domain(self):
        if self.page_type == "unknown" and any(
            (
                self.team_id,
                self.team_name,
                self.detail_tabs_observed,
                self.heroes,
                self.team_effects,
            )
        ):
            raise ValueError("unknown team detail page_type cannot include detail payload")
        return self


TEAM_DETAIL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page_type": {
            "type": "string",
            "enum": [
                "hero_detail",
                "tactic_detail",
                "equipment_mount",
                "formation_books",
                "lineup_config",
                "unknown",
            ],
            "description": "Detail page kind currently visible.",
        },
        "team_id": {
            "type": "string",
            "description": "Visible team slot id such as 部队一. Omit if hidden.",
        },
        "team_name": {
            "type": "string",
            "description": "Visible team name or label. Omit if hidden.",
        },
        "detail_tabs_observed": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Team detail areas explicitly shown: 装备, 马匹, 兵书, 属性加点, 战法等级, 兵种适性.",
        },
        "heroes": {
            "type": "array",
            "description": "Hero detail records visible on this page.",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "武将姓名."},
                    "level": {"type": "integer", "description": "武将等级 if visible."},
                    "role": {"type": "string", "description": "主将/副将/前锋等 if visible."},
                    "attributes": {
                        "type": "object",
                        "description": "Visible final attributes, e.g. 武力/智力/统率/先攻/速度.",
                    },
                    "attribute_points": {
                        "type": "object",
                        "description": "Visible allocation values, e.g. 武力+10, 智力+30.",
                    },
                    "soldier_specialties": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Visible 兵种适性 labels or troop-type fit notes.",
                    },
                    "equipment": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "slot": {"type": "string", "description": "武器/防具/宝物/饰品等."},
                                "name": {"type": "string", "description": "装备名称."},
                                "level": {"type": "integer", "description": "装备等级."},
                                "rarity": {"type": "string", "description": "品质/稀有度."},
                                "attributes": {"type": "object", "description": "Visible stat bonuses."},
                                "effects": {"type": "array", "items": {"type": "string"}},
                                "status_notes": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["name"],
                        },
                    },
                    "mount": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "level": {"type": "integer"},
                            "quality": {"type": "string"},
                            "attributes": {"type": "object"},
                            "skills": {"type": "array", "items": {"type": "string"}},
                            "status_notes": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "books": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "slot": {"type": "string"},
                                "name": {"type": "string"},
                                "level": {"type": "integer"},
                                "active": {"type": "boolean"},
                                "effects": {"type": "array", "items": {"type": "string"}},
                                "status_notes": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["name"],
                        },
                    },
                    "tactic_details": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "level": {"type": "integer"},
                                "max_level": {"type": "integer"},
                                "slot": {"type": "string", "description": "自带/第一战法/第二战法等."},
                                "quality": {"type": "string"},
                                "effects": {"type": "array", "items": {"type": "string"}},
                                "status_notes": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["name"],
                        },
                    },
                    "status_notes": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name"],
            },
        },
        "team_effects": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Visible team-wide effects such as active formation/book/bond effects.",
        },
        "missing_detail_tabs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Important detail areas not visible in this screenshot.",
        },
        "visible_notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Other visible labels or uncertainty notes.",
        },
    },
    "required": ["page_type", "heroes"],
}


TEAM_DETAIL_INSTRUCTION = (
    "This is a detail screenshot from 三国·谋定天下 for a team, hero, tactic, equipment, mount, "
    "兵书, stat allocation, or troop specialty page. Extract only facts that are explicitly visible. "
    "Focus on fields needed to judge whether the team is ready for PVP, PVE, and 远征: 装备, 马匹, "
    "兵书, 属性加点, 战法等级, and 兵种适性. Use `detail_tabs_observed` for each category that is "
    "actually visible. Do not infer hidden heroes or hidden equipment. If a category is needed but "
    "not visible, put it in `missing_detail_tabs`. Preserve Chinese names and labels exactly."
)


# ---------------------------------------------------------------------------
# Generic element locator — returns bounding boxes normalized to 0-1000
# ---------------------------------------------------------------------------

class ElementBox(BaseModel):
    label: str
    # Gemini convention: [ymin, xmin, ymax, xmax] normalized to 0-1000.
    # We preserve ordering here to avoid silent axis swaps downstream.
    y_min: int = Field(ge=0, le=1000)
    x_min: int = Field(ge=0, le=1000)
    y_max: int = Field(ge=0, le=1000)
    x_max: int = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def _validate_box_order(self):
        _validate_bbox(self, ("x_min", "y_min", "x_max", "y_max"), "element")
        return self


class ElementLocation(BaseModel):
    matches: list[ElementBox] = Field(default_factory=list)


ELEMENT_LOCATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "matches": {
            "type": "array",
            "description": (
                "Zero or more bounding boxes for elements matching the query. "
                "Coordinates are normalized to 0-1000 on each axis of the INPUT "
                "image (not the game window). Return the tightest box around "
                "the clickable target."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Short identifier — the text or icon name.",
                    },
                    "y_min": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "x_min": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "y_max": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "x_max": {"type": "integer", "minimum": 0, "maximum": 1000},
                },
                "required": ["label", "y_min", "x_min", "y_max", "x_max"],
            },
        },
    },
    "required": ["matches"],
}


def build_element_location_instruction(query: str) -> str:
    return (
        "You are looking at a screenshot from the Chinese mobile game "
        "三国·谋定天下. Find all UI elements matching this description: "
        f"\"{query}\". "
        "Return each match's bounding box in the `matches` array. "
        "Coordinates must be normalized to 0-1000 on each axis of the image "
        "(the image center is y_min~450 y_max~550 x_min~450 x_max~550). "
        "Give the tightest box around the clickable target. "
        "If nothing matches, return an empty matches array — do not invent matches."
    )
