from __future__ import annotations

import math
import re
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable, Mapping

from pioneer_agent.core.models import CandidateAction, RuntimeState
from pioneer_agent.runtime.advisor_loop import ActionRecommendation, AdvisorReport
from pioneer_agent.runtime.evidence import AdvisorEvidence


MAX_PUBLIC_COLLECTION_ITEMS = 50
MAX_PUBLIC_DEPTH = 6
# Explicit finite domain shapes include roster -> gear -> attributes and
# snapshot -> judgement -> per-mode issues. They cannot recurse on input keys.
MAX_PUBLIC_DOMAIN_DEPTH = 10
MAX_PUBLIC_STRING_LENGTH = 500

_DROP = object()
_URI_RE = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.-]*://|(?:data|file|ftp|s3|gs):)", re.IGNORECASE)
_WINDOWS_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_PUBLIC_IDENTIFIER_RE = re.compile(r"^[^/\\\r\n]{1,160}$")
_FIELD_REF_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")

# RuntimeState intentionally contains flexible mappings. The MCP boundary does
# not serialize them wholesale. Only reviewed game-domain keys survive this
# projection; new runtime fields stay private until explicitly added here.
RUNTIME_TOP_LEVEL_FIELDS = (
    "global_state",
    "progress",
    "economy",
    "city",
    "heroes",
    "teams",
    "map_state",
    "swap_window",
    "main_lineup",
    "team_containers",
    "carrier_pool",
    "swap_constraints",
    "timing",
)

PUBLIC_GAME_KEYS = frozenset(
    {
        "active",
        "advisor_only",
        "attributes",
        "automation",
        "avg_level",
        "basis_fields",
        "battle_support_gain",
        "blocked_by",
        "bond_active",
        "books",
        "building_id",
        "building_name",
        "buildings",
        "can_attack",
        "can_host_now",
        "can_march_now",
        "can_recruit_now",
        "can_upgrade",
        "candidate_land_count",
        "candidate_lands",
        "carrier_available",
        "chapter_claimable",
        "chapter_id",
        "chapter_relevance",
        "combat_readiness_if_hosting_main",
        "combat_readiness_score",
        "combat_support",
        "completed",
        "confidence",
        "container_stamina",
        "copper",
        "cost",
        "current",
        "current_chapter_id",
        "current_host_score",
        "current_host_team_id",
        "current_level",
        "current_position_context",
        "current_soldiers",
        "current_stamina",
        "current_time",
        "detail_completion",
        "detail_status",
        "economy_gain",
        "enabled",
        "equipment",
        "exists",
        "expected_battle_loss",
        "expected_win_rate",
        "formation",
        "formation_active",
        "from_team_id",
        "grain",
        "hero_id",
        "hero_ids",
        "hero_names",
        "heroes",
        "host_score",
        "host_score_delta",
        "host_stamina_gap",
        "hours_remaining",
        "hours_since_server_open",
        "hours_until_settlement",
        "idle_seconds",
        "income_per_hour",
        "interruptible",
        "interpreted_page_type",
        "interpretation_summary",
        "iron",
        "is_main_host",
        "land_id",
        "land_scope",
        "level",
        "level_fit",
        "level_readiness",
        "lineup_preset",
        "main_team_id",
        "march_seconds",
        "max_core_level",
        "max_level",
        "max_soldiers",
        "mill",
        "min_core_level",
        "missing_amount",
        "missing_detail_tabs",
        "mount",
        "name",
        "next_level",
        "notes",
        "observed_at",
        "occupied",
        "overall_status",
        "page_type",
        "phase_tag",
        "position_context",
        "position_readiness",
        "primary_constraint",
        "protected",
        "pvp_pve_basis_ready",
        "reachable",
        "readiness_judgement",
        "readiness_notes",
        "recruit_amount",
        "recruit_finish_time",
        "red_level",
        "requires_detail_review",
        "required_stamina",
        "reserve_troops",
        "reserve_troops_available",
        "resource_cost_penalty",
        "resource_ready",
        "resource_shortages",
        "resources",
        "review_items",
        "season_id",
        "server_open_time",
        "skills",
        "slot",
        "slot_unlocked",
        "soldier_deficit",
        "soldier_deficit_ratio",
        "soldier_fill_ratio",
        "soldier_fill_ratio_after",
        "soldier_gap",
        "soldier_readiness",
        "soldier_specialties",
        "soldiers",
        "source",
        "stability_readiness",
        "stamina",
        "stamina_gap",
        "stamina_max",
        "stamina_readiness",
        "stamina_regen_per_hour",
        "status",
        "stone",
        "strategy_entry_ids",
        "strategy_key",
        "strategy_rationale",
        "strategy_topic",
        "strategic_tags",
        "supply",
        "supply_max",
        "supply_ratio",
        "swap_enabled",
        "tactic_details",
        "tactics",
        "target",
        "target_host_score",
        "target_land_level",
        "target_level",
        "target_position_context",
        "target_resource",
        "target_soldiers",
        "target_stamina",
        "target_team_id",
        "target_time",
        "task_progress",
        "team_count",
        "team_effects",
        "team_id",
        "team_readiness",
        "team_snapshot",
        "teams",
        "timing",
        "unlock_action_type",
        "unlock_chapter_relevance",
        "unlock_land_level",
        "unlock_land_scope",
        "unlock_lineup_preset",
        "unlock_score_hint",
        "upgrade_dialog",
        "upgradeable_building_count",
        "upgradeable_buildings",
        "usable_for_swap",
        "visible",
        "visible_entry_points",
        "wait_seconds",
        "wait_seconds_for_resources",
        "wait_target_resource",
        "wood",
        "yield_per_hour",
        "兵书",
        "兵种适性",
        "属性加点",
        "战法等级",
        "智力",
        "武力",
        "统率",
        "装备",
        "马匹",
    }
)

ACTION_PARAM_KEYS = PUBLIC_GAME_KEYS | frozenset({"resource_type", "occupation_pending", "occupation_countdown"})
RISK_KEYS = frozenset(
    {
        "advisor_only",
        "expected_win_rate",
        "macro_action",
        "pvp_pve_basis_ready",
        "readiness_judgement",
        "requires_detail_review",
        "risk_level",
        "level",
        "confirmation_required",
        "summary",
    }
)
SELECTION_REASON_KEYS = frozenset(
    {
        "decision",
        "details",
        "generated",
        "llm_judge_gate",
        "phase_tag",
        "pipeline",
        "primary_constraint",
        "reason",
        "rejected",
        "rejected_by_reason",
        "selected_score",
        "selection_mode",
        "summary",
        "top_score_gap",
        "triggered_rules",
        "viable",
    }
)
EVIDENCE_METADATA_KEYS = frozenset(
    {"domain", "source", "status", "strategy_key", "trusted_for_state"}
)
EVIDENCE_FIELDS = (
    "evidence_id",
    "source_type",
    "ref",
    "entry_id",
    "topic",
    "domain",
    "summary",
    "confidence",
)



# Domain-aware output shapes, not a second tool/input catalog. None denotes a
# scalar, a one-item tuple a collection, and a mapping an explicit object.
# Keys admitted in one domain are never implicitly admitted in another.
def _fields(names: str) -> dict[str, Any]:
    return dict.fromkeys(names.split())


_COORDINATE = _fields("x y")
_GAME_PROSE = object()
_BUTTON = _fields("visible enabled")
_RESOURCES = _fields("wood stone iron grain copper")
_DETAIL_TABS = _fields("装备 马匹 兵书 属性加点 战法等级 兵种适性")
_ATTRIBUTES = _fields("武力 智力 统率 先攻 military intelligence command initiative")
_GEAR = {
    **_fields("slot name level max_level rarity quality active"),
    "attributes": _ATTRIBUTES, "effects": (None,), "skills": (None,),
    "status_notes": (None,),
}
_HERO = {
    **_fields("hero_id name level red_level soldiers max_soldiers stamina stamina_max position role soldier_ratio soldier_deficit usable_for_swap available"),
    "tactics": (None,), "status_notes": (None,), "attributes": _ATTRIBUTES,
    "attribute_points": _ATTRIBUTES, "soldier_specialties": (None,),
    "equipment": (_GEAR,), "books": (_GEAR,), "mount": _GEAR,
    "tactic_details": (_GEAR,),
}
_ISSUE = {**_fields("code severity"), "message": _GAME_PROSE, "modes": (None,)}
_MODE_JUDGEMENT = {**_fields("status risk_level"), "summary": _GAME_PROSE, "issues": (None,)}
_JUDGEMENT = {
    **_fields("source basis_ready overall_status confidence"),
    "facts": {
        **_fields("hero_count detailed_hero_count detail_coverage_ratio soldier_fill_ratio soldier_deficit min_stamina min_tactic_level tactic_level_count tactic_max_level_count formation_active bond_active supply_ratio"),
        "missing_detail_tabs": (None,), "detail_completion": _DETAIL_TABS,
    },
    "issues": (_ISSUE,), "blocking_issues": (_ISSUE,),
    "mode_judgement": {mode: _MODE_JUDGEMENT for mode in ("pvp", "pve", "expedition")},
    "next_steps": (_GAME_PROSE,),
}
_SNAPSHOT = {
    **_fields("source pvp_pve_basis_ready"), "detail_completion": _DETAIL_TABS,
    "basis_fields": (None,),
    "readiness_judgement": _JUDGEMENT,
}
_READINESS = {
    **_fields("formation_active bond_active soldier_deficit supply_ratio requires_detail_review pvp_pve_basis_ready overall_status soldier_readiness stamina_readiness level_readiness position_readiness stability_readiness"),
    "missing_detail_tabs": (None,), "notes": (None,), "review_items": (None,),
    "detail_completion": _DETAIL_TABS,
    "readiness_judgement": _JUDGEMENT,
}
_TEAM = {
    **_fields("team_id page_type formation formation_active bond_active soldiers max_soldiers soldier_deficit supply supply_max supply_ratio status can_recruit_now recruit_finish_time"),
    "heroes": (_HERO,), "visible_entry_points": (None,),
    "readiness_notes": (None,), "missing_detail_tabs": (None,),
    "detail_status": _DETAIL_TABS, "team_snapshot": _SNAPSHOT,
    "team_effects": (None,),
    "readiness_judgement": _JUDGEMENT, "recruit_button": _BUTTON,
}
_LAND = {
    **_fields("land_id source resource_type land_scope occupied occupation_pending occupation_countdown protected reachable can_attack selected recommended_marker observed_at level yield_per_hour distance march_seconds expected_win_rate expected_battle_loss risk_label required_stamina chapter_relevance host_stamina_gap level_fit"),
    "coordinate": _COORDINATE, "strategic_tags": (None,),
}
_FILTER = {
    **_fields("visible resource_filter_enabled level_min level_max"),
    "selected_resource_types": (None,), "selected_levels": (None,),
    "resource_toggles": ({**_BUTTON, **_fields("resource_type selected")},),
    "level_toggles": ({**_BUTTON, **_fields("level selected")},),
    "filter_button": _BUTTON, "apply_button": _BUTTON,
}
_BATTLE_VERIFICATION = {
    **_fields("parse_status action_verification_ready verifier_status"),
    "checks": _fields("battle_result loss_measured occupation loss_consistency report_parse"),
    "issues": (None,),
}
_BATTLE_HERO = {
    **_fields("name level initial_soldiers remaining_soldiers losses loss_ratio"),
    "tactics": (None,),
}
_BATTLE_REPORT = {
    **_fields("report_id report_id_source report_identity_confidence source page_type result occupation_result resource_type report_time captured_at land_level attacker_team_id attacker_initial_soldiers attacker_remaining_soldiers attacker_losses defender_initial_soldiers defender_remaining_soldiers defender_losses rounds experience_gained honor_gained attacker_loss_ratio"),
    "target_coordinate": _COORDINATE,
    "attacker_heroes": (_BATTLE_HERO,), "defender_heroes": (_BATTLE_HERO,),
    "visible_sections": (None,), "measurement_issues": (None,),
    "verification": _BATTLE_VERIFICATION,
}
_TASK = _fields("name reward_claimable completed current required target_level target")
_BUILDING = {
    **_fields("building_id building_name name level current_level next_level target_level can_upgrade chapter_relevance economy_gain battle_support_gain resource_ready wait_target_resource wait_seconds_for_resources"),
    "cost": _RESOURCES, "resource_shortages": _RESOURCES, "blocked_by": (None,),
}
_CONTAINER = _fields("team_id source status slot_unlocked exists container_stamina soldiers max_soldiers soldier_deficit soldier_gap soldier_fill_ratio position_context can_host_now can_march_now can_recruit_now is_main_host is_hosting_main_lineup combat_readiness_if_hosting_main host_score")
_MODE = {
    **_fields("page_type title active_tab total_score rank phase_status countdown"),
    "entries": (_fields("name status can_enter can_claim can_reset can_register score rank countdown button_label"),),
}
RUNTIME_PROJECTION = {
    "global_state": {
        **_fields("page_type server_open_time current_time settlement_time season_id hours_since_server_open hours_until_settlement phase_tag military_order military_order_max interpreted_page_type interpretation_summary"),
        "mode_hub": _MODE, "event_tournament": _MODE,
        # Popup message/title and battle/map notes can contain chat or account
        # text; publish decision status, not arbitrary recognized screen prose.
        "popup": {
            **_fields("visible type blocking safe_default_action"),
            "buttons": (_fields("label role enabled"),),
        },
    },
    "progress": {
        **_fields("chapter_claimable chapter_id current_chapter_id current_chapter_title"),
        "chapter_tasks": (_TASK,), "chapter_claim_button": _BUTTON,
        "task_progress": {"occupy_land": _TASK, "upgrade_building": _TASK},
    },
    "economy": {
        "resources": _RESOURCES, "income_per_hour": _RESOURCES,
        "currencies": _fields("copper gold_bead yuanbao"),
        **_fields("reserve_troops reserve_troops_available"),
    },
    "city": {
        "buildings": (_BUILDING,), "upgradeable_buildings": (_BUILDING,),
        **_fields("upgradeable_building_count"), "notes": (None,),
        "upgrade_dialog": {
            **_BUILDING, **_fields("visible enabled cannot_upgrade_reason"),
            "costs": (_fields("name required available enough"),),
            "confirm_button": _BUTTON, "close_button": _BUTTON,
        },
    },
    "heroes": (_HERO,), "teams": (_TEAM,),
    "map_state": {
        "map_land_filter": _FILTER, "visible_lands": (_LAND,),
        "candidate_lands": (_LAND,), "map_center_coordinate": _COORDINATE,
        **_fields("visible_land_count candidate_land_count"),
        "latest_battle_report": _BATTLE_REPORT,
        "battle_reports": (_BATTLE_REPORT,),
        "battle_report_verification": _BATTLE_VERIFICATION,
    },
    "swap_window": _fields("enabled hours_remaining"),
    "main_lineup": {
        **_fields("current_host_team_id team_snapshot_source avg_level min_core_level max_core_level primary_constraint combat_readiness_score current_host_score current_position_context"),
        "hero_ids": (None,), "hero_names": (None,),
        "team_snapshot": _SNAPSHOT, "team_readiness": _READINESS,
    },
    "team_containers": (_CONTAINER,), "carrier_pool": (_HERO,),
    "swap_constraints": _fields("stamina_regen_per_hour swap_enabled carrier_available"),
    "timing": {
        **_fields("next_recruit_finish_time next_team_return_time next_action_ready_time"),
        "next_stamina_threshold_times": (_fields("team_id target_stamina target_time"),),
        "next_resource_threshold_times": _RESOURCES,
    },
}
_RISK_PROJECTION = {
    **dict.fromkeys(RISK_KEYS), "readiness_judgement": _JUDGEMENT,
}
_SUMMARY_PROJECTION = {
    **_fields("page_type phase_tag current_chapter_id chapter_claimable main_team_id candidate_land_count upgradeable_building_count team_count interpreted_page_type interpretation_summary"),
    "resources": _RESOURCES, "team_readiness": _READINESS, "team_snapshot": _SNAPSHOT,
}


def _project_domain(value: Any, shape: Any, depth: int = 0) -> Any:
    if depth >= MAX_PUBLIC_DOMAIN_DEPTH:
        return _DROP
    if shape is _GAME_PROSE:
        if not isinstance(value, str):
            return _DROP
        # These fixed game labels occur in generated readiness explanations.
        # Only their separators are recognized; other slashes, paths, URIs and
        # image-like strings still go through the existing privacy rejection.
        checked = value
        for label in ("兵书/韬略", "PVP/PVE/远征", "PVP/PVE", "战斗/远征", "远征/连续战斗"):
            checked = checked.replace(label, label.replace("/", ""))
        return value[:MAX_PUBLIC_STRING_LENGTH] if public_text(checked) is not None else _DROP
    if shape is None:
        if isinstance(value, (Mapping, list, tuple, set)):
            return _DROP
        return _project_value(value, allowed_keys=frozenset(), depth=0)
    if isinstance(shape, tuple):
        if not isinstance(value, (list, tuple)):
            return _DROP
        result = []
        for item in value[:MAX_PUBLIC_COLLECTION_ITEMS]:
            projected = _project_domain(item, shape[0], depth + 1)
            if projected is not _DROP:
                result.append(projected)
        return result
    if not isinstance(value, Mapping):
        return _DROP
    result = {}
    for key, child_shape in shape.items():
        if key not in value:
            continue
        projected = _project_domain(value[key], child_shape, depth + 1)
        if projected is not _DROP:
            result[key] = projected
    return result


def project_runtime_state(state: RuntimeState) -> dict[str, Any]:
    projected = {}
    for field_name, shape in RUNTIME_PROJECTION.items():
        value = _project_domain(getattr(state, field_name), shape)
        if value is not _DROP:
            projected[field_name] = value

    field_meta: dict[str, Any] = {}
    for ref, meta in list(state.field_meta.items())[:MAX_PUBLIC_COLLECTION_ITEMS]:
        if not _FIELD_REF_RE.fullmatch(ref):
            continue
        item = {
            "confidence": meta.confidence,
            "source": public_text(meta.source),
            "updated_at": meta.updated_at.isoformat() if meta.updated_at else None,
            "observation_id": public_text(meta.observation_id),
        }
        field_meta[ref] = {key: value for key, value in item.items() if value is not None}
    projected["field_meta"] = field_meta
    return projected


def project_advisor_report(report: AdvisorReport) -> dict[str, Any]:
    return {
        "mode": public_required_text(report.mode),
        "captured_at": report.captured_at.isoformat(),
        "current_state": project_runtime_state(report.current_state),
        "current_state_summary": _project_domain(report.current_state_summary, _SUMMARY_PROJECTION),
        "available_actions": [project_recommendation(item) for item in report.available_actions],
        "recommended_action": (
            project_recommendation(report.recommended_action)
            if report.recommended_action is not None
            else None
        ),
        "risks": [project_risk(item) for item in report.risks],
        "evidence": project_text_list(report.evidence),
        "structured_evidence": [project_evidence(item) for item in report.structured_evidence],
        "confidence": report.confidence,
        "vision_summary": project_mapping(
            report.vision_summary,
            allowed_keys=frozenset({"page_type", "domains_run", "unknown_domains", "notes"}),
        ),
        "selection_reason": project_selection_reason(report.selection_reason),
    }


def project_recommendation(action: ActionRecommendation) -> dict[str, Any]:
    return {
        "action_id": public_required_text(action.action_id),
        "action_type": action.action_type.value,
        "params": project_mapping(action.params, allowed_keys=ACTION_PARAM_KEYS),
        "score": action.score,
        "risk": project_risk(action.risk),
        "evidence": project_text_list(action.evidence),
        "structured_evidence": [project_evidence(item) for item in action.structured_evidence],
        "confidence": action.confidence,
        "executable": False,
        "execution_blocked_reason": public_required_text(
            action.execution_blocked_reason or "advisor_mode"
        ),
        "execution_authority": "none",
    }


def project_candidate_action(action: CandidateAction) -> dict[str, Any]:
    return {
        "action_id": public_required_text(action.action_id),
        "action_type": action.action_type.value,
        "params": project_mapping(action.params, allowed_keys=ACTION_PARAM_KEYS),
        "score_total": action.score_total,
        "risk": project_risk(action.risk),
        "preconditions": project_text_list(action.preconditions),
        "source_state_refs": project_text_list(action.source_state_refs),
    }


def project_evidence(evidence: AdvisorEvidence) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for field_name in EVIDENCE_FIELDS:
        value = getattr(evidence, field_name)
        if value is None:
            continue
        safe = _project_value(value, allowed_keys=frozenset(), depth=0)
        if safe is not _DROP:
            projected[field_name] = safe
    metadata = project_mapping(evidence.metadata, allowed_keys=EVIDENCE_METADATA_KEYS)
    if metadata:
        projected["metadata"] = metadata
    return projected


def project_selection_reason(value: Mapping[str, Any]) -> dict[str, Any]:
    return project_mapping(value, allowed_keys=SELECTION_REASON_KEYS)


def project_risk(value: Mapping[str, Any]) -> dict[str, Any]:
    projected = _project_domain(value, _RISK_PROJECTION)
    return projected if isinstance(projected, dict) else {}


def project_mapping(
    value: Mapping[str, Any] | None,
    *,
    allowed_keys: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    projected = _project_value(value, allowed_keys=allowed_keys, depth=0)
    return projected if isinstance(projected, dict) else {}


def project_text_list(values: Iterable[Any]) -> list[str]:
    projected: list[str] = []
    for value in list(values)[:MAX_PUBLIC_COLLECTION_ITEMS]:
        text = public_text(value)
        if text is not None:
            projected.append(text)
    return projected


def public_required_text(value: Any, *, fallback: str = "redacted") -> str:
    return public_text(value) or fallback


def public_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text or _looks_private_string(text):
        return None
    return text[:MAX_PUBLIC_STRING_LENGTH]


def _project_value(
    value: Any,
    *,
    allowed_keys: frozenset[str],
    depth: int,
) -> Any:
    if depth >= MAX_PUBLIC_DEPTH:
        return _DROP
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else _DROP
    if isinstance(value, Enum):
        return _project_value(value.value, allowed_keys=allowed_keys, depth=depth)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str):
        text = public_text(value)
        return text if text is not None else _DROP
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for key, item in list(value.items())[:MAX_PUBLIC_COLLECTION_ITEMS]:
            key_text = str(key)
            if key_text not in allowed_keys:
                continue
            safe = _project_value(item, allowed_keys=allowed_keys, depth=depth + 1)
            if safe is not _DROP:
                projected[key_text] = safe
        return projected
    if isinstance(value, (list, tuple, set)):
        projected_items = []
        for item in list(value)[:MAX_PUBLIC_COLLECTION_ITEMS]:
            safe = _project_value(item, allowed_keys=allowed_keys, depth=depth + 1)
            if safe is not _DROP:
                projected_items.append(safe)
        return projected_items
    return _DROP


def _looks_private_string(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if stripped.startswith(("/", "~/", "./", "../", "\\")):
        return True
    if _WINDOWS_PATH_RE.match(stripped) or _URI_RE.match(stripped):
        return True
    if "/" in stripped or "\\" in stripped:
        return True
    if len(stripped) >= 128 and len(stripped) % 4 == 0 and _BASE64_RE.fullmatch(stripped):
        return True
    return False


def is_public_identifier(value: str) -> bool:
    return bool(_PUBLIC_IDENTIFIER_RE.fullmatch(value)) and public_text(value) is not None
