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

ACTION_PARAM_KEYS = PUBLIC_GAME_KEYS
RISK_KEYS = frozenset(
    {
        "advisor_only",
        "expected_win_rate",
        "macro_action",
        "pvp_pve_basis_ready",
        "readiness_judgement",
        "requires_detail_review",
        "risk_level",
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


def project_runtime_state(state: RuntimeState) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for field_name in RUNTIME_TOP_LEVEL_FIELDS:
        value = _project_value(
            getattr(state, field_name),
            allowed_keys=PUBLIC_GAME_KEYS,
            depth=0,
        )
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
        "current_state_summary": project_mapping(
            report.current_state_summary,
            allowed_keys=PUBLIC_GAME_KEYS,
        ),
        "available_actions": [project_recommendation(item) for item in report.available_actions],
        "recommended_action": (
            project_recommendation(report.recommended_action)
            if report.recommended_action is not None
            else None
        ),
        "risks": [project_mapping(item, allowed_keys=RISK_KEYS) for item in report.risks],
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
        "risk": project_mapping(action.risk, allowed_keys=RISK_KEYS),
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
        "risk": project_mapping(action.risk, allowed_keys=RISK_KEYS),
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
