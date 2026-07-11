"""Merge perception fragments into a RuntimeState.

A fragment is a partial observation from a single screenshot — only a subset
of `RuntimeState` domains are present. We do a shallow merge on dict-valued
domains (global_state/economy/city/...) so a new observation *adds* fields
without wiping unrelated state carried over from prior syncs.

Lists and scalars get replaced wholesale if the fragment provides them —
partial list updates are domain-specific and handled by their own extractors.

field_meta entries always override: fresher timestamps win.
"""
from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from pioneer_agent.core.models import FieldMeta, RuntimeState

from .battle_report import BattleReportFragment
from .chapter_panel import ChapterPanelFragment
from .city_buildings import CityBuildingsFragment
from .map_land import MapLandFragment
from .mode_hub import ModeHubFragment
from .popup import PopupFragment
from .recruit_panel import RecruitPanelFragment
from .resource_bar import ResourceBarFragment
from .team_detail import TeamDetailFragment
from .team_panel import TeamPanelFragment
from .team_panel import DEFAULT_MISSING_DETAIL_TABS
from .upgrade_dialog import UpgradeDialogFragment

_DICT_DOMAINS = {
    "global_state",
    "progress",
    "economy",
    "city",
    "map_state",
    "swap_window",
    "main_lineup",
    "swap_constraints",
    "timing",
}
_LIST_DOMAINS = {
    "heroes",
    "teams",
    "team_containers",
    "carrier_pool",
}

_MAP_CANDIDATES_META_KEY = "map_state.candidate_lands"
_LATEST_BATTLE_META_KEY = "map_state.latest_battle_report"
_MAP_SNAPSHOT_KEYS = frozenset(
    {
        "map_land_filter",
        "visible_lands",
        "candidate_lands",
        "visible_land_count",
        "candidate_land_count",
        "map_center_coordinate",
    }
)


def expire_map_land_candidates(
    state: RuntimeState,
    *,
    captured_at: datetime,
) -> RuntimeState:
    """Clear actionable map candidates when the current screenshot is not a map snapshot."""
    expiry_meta = FieldMeta(
        value=0,
        confidence=1.0,
        source="vision.page_route",
        updated_at=captured_at,
    )
    if not _snapshot_is_current(
        state.field_meta.get(_MAP_CANDIDATES_META_KEY),
        expiry_meta,
        incomparable_is_current=True,
    ):
        return state

    merged_map = dict(state.map_state)
    merged_map["candidate_lands"] = []
    merged_map["candidate_land_count"] = 0
    merged_meta = dict(state.field_meta)
    merged_meta[_MAP_CANDIDATES_META_KEY] = expiry_meta
    return state.model_copy(
        update={"map_state": merged_map, "field_meta": merged_meta}
    )


def apply_resource_bar(state: RuntimeState, fragment: ResourceBarFragment) -> RuntimeState:
    """Return a new RuntimeState with the resource_bar fragment merged in."""
    updates: dict[str, Any] = {}

    merged_global = dict(state.global_state)
    merged_global.update(fragment.global_state)
    updates["global_state"] = merged_global

    if fragment.economy:
        merged_economy = _deep_merge_two_level(dict(state.economy), fragment.economy)
        updates["economy"] = merged_economy

    merged_meta: dict[str, FieldMeta] = dict(state.field_meta)
    merged_meta.update(fragment.field_meta)
    updates["field_meta"] = merged_meta

    return state.model_copy(update=updates)


def apply_popup(state: RuntimeState, fragment: PopupFragment) -> RuntimeState:
    updates: dict[str, Any] = {}

    if fragment.global_state:
        merged_global = dict(state.global_state)
        merged_global.update(fragment.global_state)
        updates["global_state"] = merged_global

    merged_meta: dict[str, FieldMeta] = dict(state.field_meta)
    merged_meta.update(fragment.field_meta)
    updates["field_meta"] = merged_meta

    return state.model_copy(update=updates)


def apply_mode_hub(state: RuntimeState, fragment: ModeHubFragment) -> RuntimeState:
    updates: dict[str, Any] = {}

    if fragment.global_state:
        merged_global = dict(state.global_state)
        merged_global.update(fragment.global_state)
        updates["global_state"] = merged_global

    merged_meta: dict[str, FieldMeta] = dict(state.field_meta)
    merged_meta.update(fragment.field_meta)
    updates["field_meta"] = merged_meta

    return state.model_copy(update=updates)


def apply_map_land(state: RuntimeState, fragment: MapLandFragment) -> RuntimeState:
    """Replace the map snapshot, rejecting observations older than current state."""
    incoming_meta = fragment.field_meta.get(_MAP_CANDIDATES_META_KEY)
    existing_meta = state.field_meta.get(_MAP_CANDIDATES_META_KEY)
    if not _snapshot_is_current(existing_meta, incoming_meta):
        return state

    merged_map = dict(state.map_state)
    # These values describe one screenshot. They must not accumulate across
    # observations; durable history belongs in a separate domain.
    for key in _MAP_SNAPSHOT_KEYS:
        merged_map.pop(key, None)
    merged_map.update(fragment.map_state)
    merged_meta = dict(state.field_meta)
    merged_meta.update(fragment.field_meta)
    return state.model_copy(
        update={"map_state": merged_map, "field_meta": merged_meta}
    )


def apply_battle_report(
    state: RuntimeState,
    fragment: BattleReportFragment,
) -> RuntimeState:
    """Merge report history while only promoting a non-stale report to latest."""
    if not fragment.map_state:
        return state

    merged_map = dict(state.map_state)
    incoming_reports = fragment.map_state.get("battle_reports") or []
    merged_map["battle_reports"] = _merge_battle_reports(
        state.map_state.get("battle_reports") or [],
        incoming_reports,
    )

    incoming_meta = fragment.field_meta.get(_LATEST_BATTLE_META_KEY)
    existing_meta = state.field_meta.get(_LATEST_BATTLE_META_KEY)
    promote_latest = _snapshot_is_current(existing_meta, incoming_meta)
    merged_meta = dict(state.field_meta)
    if promote_latest:
        for key in ("latest_battle_report", "battle_report_verification"):
            if key in fragment.map_state:
                merged_map[key] = fragment.map_state[key]
        merged_meta.update(fragment.field_meta)

    return state.model_copy(
        update={"map_state": merged_map, "field_meta": merged_meta}
    )


def apply_chapter_panel(state: RuntimeState, fragment: ChapterPanelFragment) -> RuntimeState:
    updates: dict[str, Any] = {}

    if fragment.progress:
        merged_progress = dict(state.progress)
        merged_progress.update(fragment.progress)
        updates["progress"] = merged_progress

    merged_meta: dict[str, FieldMeta] = dict(state.field_meta)
    merged_meta.update(fragment.field_meta)
    updates["field_meta"] = merged_meta

    return state.model_copy(update=updates)


def apply_recruit_panel(state: RuntimeState, fragment: RecruitPanelFragment) -> RuntimeState:
    updates: dict[str, Any] = {}

    if fragment.economy:
        merged_economy = dict(state.economy)
        merged_economy.update(fragment.economy)
        updates["economy"] = merged_economy
    if fragment.teams:
        updates["teams"] = _merge_team_detail_list(state.teams, fragment.teams)

    merged_meta: dict[str, FieldMeta] = dict(state.field_meta)
    merged_meta.update(fragment.field_meta)
    updates["field_meta"] = merged_meta

    return state.model_copy(update=updates)


def apply_city_buildings(state: RuntimeState, fragment: CityBuildingsFragment) -> RuntimeState:
    """Return a new RuntimeState with the city_buildings fragment merged in.

    The `buildings` list is merged per-building by canonical name: updates from
    the fragment override matching entries in the existing state; buildings in
    state that aren't in the fragment are kept (partial observation).
    """
    updates: dict[str, Any] = {}

    if fragment.city:
        merged_city = _merge_city(dict(state.city), fragment.city)
        updates["city"] = merged_city

    merged_meta: dict[str, FieldMeta] = dict(state.field_meta)
    merged_meta.update(fragment.field_meta)
    updates["field_meta"] = merged_meta

    return state.model_copy(update=updates)


def apply_upgrade_dialog(state: RuntimeState, fragment: UpgradeDialogFragment) -> RuntimeState:
    updates: dict[str, Any] = {}

    if fragment.city:
        merged_city = dict(state.city)
        merged_city.update(fragment.city)
        updates["city"] = merged_city

    merged_meta: dict[str, FieldMeta] = dict(state.field_meta)
    merged_meta.update(fragment.field_meta)
    updates["field_meta"] = merged_meta

    return state.model_copy(update=updates)


def apply_team_panel(state: RuntimeState, fragment: TeamPanelFragment) -> RuntimeState:
    """Return a new RuntimeState with a structured team panel observation merged in."""
    updates: dict[str, Any] = {}

    if fragment.teams:
        updates["teams"] = _merge_team_detail_list(state.teams, fragment.teams)
    if fragment.team_containers:
        updates["team_containers"] = _merge_list_by_key(
            state.team_containers,
            fragment.team_containers,
            "team_id",
        )
    if fragment.main_lineup:
        merged_lineup = dict(state.main_lineup)
        merged_lineup.update(fragment.main_lineup)
        updates["main_lineup"] = merged_lineup

    merged_meta: dict[str, FieldMeta] = dict(state.field_meta)
    merged_meta.update(fragment.field_meta)
    updates["field_meta"] = merged_meta

    return state.model_copy(update=updates)


def apply_team_detail(state: RuntimeState, fragment: TeamDetailFragment) -> RuntimeState:
    """Return a new RuntimeState with team detail observations merged in.

    Detail pages often show only one hero and may hide the team slot. In that
    case we attach the observation to the current host team already established
    by the team panel.
    """
    updates: dict[str, Any] = {}
    incoming_teams = _resolve_team_ids(state, fragment.teams)

    if incoming_teams:
        merged_teams = _merge_team_detail_list(state.teams, incoming_teams)
        updates["teams"] = merged_teams
    else:
        merged_teams = state.teams

    if fragment.main_lineup:
        merged_lineup = _merge_main_lineup_detail(dict(state.main_lineup), fragment.main_lineup)
        current_team_id = merged_lineup.get("current_host_team_id")
        current_team = _find_by_key(merged_teams, "team_id", current_team_id)
        if current_team is not None:
            snapshot = current_team.get("team_snapshot")
            if isinstance(snapshot, dict):
                merged_lineup["team_snapshot"] = dict(snapshot)

            readiness = dict(merged_lineup.get("team_readiness") or {})
            missing_detail_tabs = current_team.get("missing_detail_tabs")
            if isinstance(missing_detail_tabs, list):
                readiness["missing_detail_tabs"] = list(missing_detail_tabs)
                readiness["requires_detail_review"] = bool(missing_detail_tabs)
            detail_status = current_team.get("detail_status")
            if isinstance(detail_status, dict):
                readiness["detail_completion"] = _detail_completion(detail_status)
                readiness["pvp_pve_basis_ready"] = not any(
                    detail_status.get(tab) != "observed"
                    for tab in DEFAULT_MISSING_DETAIL_TABS
                )
            merged_lineup["team_readiness"] = readiness

        updates["main_lineup"] = merged_lineup

    merged_meta: dict[str, FieldMeta] = dict(state.field_meta)
    merged_meta.update(fragment.field_meta)
    updates["field_meta"] = merged_meta

    return state.model_copy(update=updates)


def _merge_city(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, new_value in overlay.items():
        if key == "buildings":
            # The city domain reports the complete set visible in the current
            # frame. Wholesale replacement prevents a prior-frame upgrade
            # button from surviving into the live selector.
            merged["buildings"] = [
                dict(item) for item in new_value if isinstance(item, dict)
            ]
        else:
            merged[key] = new_value
    return merged


def _merge_list_by_key(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {
        str(item[key]): dict(item)
        for item in existing
        if key in item and item[key] is not None
    }
    passthrough = [
        dict(item)
        for item in existing
        if key not in item or item[key] is None
    ]
    for entry in incoming:
        value = entry.get(key)
        if value is None:
            passthrough.append(dict(entry))
            continue
        key_value = str(value)
        if key_value in by_key:
            by_key[key_value].update(entry)
        else:
            by_key[key_value] = dict(entry)
    return [*passthrough, *by_key.values()]


def _snapshot_is_current(
    existing: FieldMeta | None,
    incoming: FieldMeta | None,
    *,
    incomparable_is_current: bool = False,
) -> bool:
    if existing is None or existing.updated_at is None:
        return True
    if incoming is None or incoming.updated_at is None:
        return False
    try:
        return incoming.updated_at >= existing.updated_at
    except TypeError:
        # Legacy callers may mix timezone-aware UTC with naive local time. The
        # ordering is unknowable without guessing a timezone, so callers choose
        # the safe direction: candidate application rejects; expiry clears.
        return incomparable_is_current


def _merge_battle_reports(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {
        str(report["report_id"]): dict(report)
        for report in existing
        if report.get("report_id") is not None
    }
    passthrough = [
        dict(report)
        for report in existing
        if report.get("report_id") is None
    ]
    for report in incoming:
        report_id = report.get("report_id")
        if report_id is None:
            passthrough.append(dict(report))
            continue
        key = str(report_id)
        current = by_id.get(key)
        if current is not None and _report_is_older(report, current):
            continue
        if current is None:
            by_id[key] = dict(report)
        else:
            current.update(report)
            by_id[key] = current
    return [*passthrough, *by_id.values()]


def _report_is_older(
    incoming: dict[str, Any],
    existing: dict[str, Any],
) -> bool:
    incoming_at = _parse_datetime(incoming.get("captured_at"))
    existing_at = _parse_datetime(existing.get("captured_at"))
    if existing_at is None:
        return False
    if incoming_at is None:
        return True
    try:
        return incoming_at < existing_at
    except TypeError:
        # Never let an ambiguously ordered observation overwrite a keyed report.
        return True


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _resolve_team_ids(state: RuntimeState, teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fallback_team_id = state.main_lineup.get("current_host_team_id")
    if fallback_team_id is None and state.teams:
        fallback_team_id = state.teams[0].get("team_id")

    resolved: list[dict[str, Any]] = []
    for team in teams:
        payload = dict(team)
        if payload.get("team_id") is None and fallback_team_id is not None:
            payload["team_id"] = fallback_team_id
        resolved.append(payload)
    return resolved


def _merge_team_detail_list(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {
        str(item["team_id"]): dict(item)
        for item in existing
        if item.get("team_id") is not None
    }
    passthrough = [
        dict(item)
        for item in existing
        if item.get("team_id") is None
    ]

    for entry in incoming:
        value = entry.get("team_id")
        if value is None:
            passthrough.append(dict(entry))
            continue
        key_value = str(value)
        if key_value in by_key:
            by_key[key_value] = _merge_team_detail(by_key[key_value], entry)
        else:
            by_key[key_value] = _finalize_team_detail(dict(entry))
    return [*passthrough, *by_key.values()]


def _merge_team_detail(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, new_value in overlay.items():
        if key == "heroes":
            merged["heroes"] = _merge_hero_details(base.get("heroes") or [], new_value)
        elif key == "detail_status":
            merged["detail_status"] = _merge_detail_status(
                base.get("detail_status") or {},
                new_value,
            )
        elif key == "team_snapshot":
            merged["team_snapshot"] = _deep_merge_dicts(
                base.get("team_snapshot") or {},
                new_value,
            )
        elif key == "team_effects":
            merged["team_effects"] = _unique_values(
                [*(base.get("team_effects") or []), *new_value]
            )
        else:
            merged[key] = new_value
    return _finalize_team_detail(merged)


def _finalize_team_detail(team: dict[str, Any]) -> dict[str, Any]:
    detail_status = team.get("detail_status")
    if not isinstance(detail_status, dict):
        return team

    missing_detail_tabs = [
        tab
        for tab in DEFAULT_MISSING_DETAIL_TABS
        if detail_status.get(tab) != "observed"
    ]
    team["missing_detail_tabs"] = missing_detail_tabs

    snapshot = dict(team.get("team_snapshot") or {})
    snapshot["detail_completion"] = _detail_completion(detail_status)
    snapshot["basis_fields"] = [
        tab
        for tab in DEFAULT_MISSING_DETAIL_TABS
        if detail_status.get(tab) == "observed"
    ]
    snapshot["pvp_pve_basis_ready"] = not missing_detail_tabs
    team["team_snapshot"] = snapshot
    return team


def _merge_hero_details(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {
        _hero_key(str(hero["name"])): dict(hero)
        for hero in existing
        if hero.get("name") is not None
    }
    alias_to_key: dict[str, str] = {}
    for key in by_name:
        alias_to_key[key] = key
        stripped = _strip_faction_prefix(key)
        if stripped != key:
            alias_to_key.setdefault(stripped, key)
    passthrough = [
        dict(hero)
        for hero in existing
        if hero.get("name") is None
    ]

    for hero in incoming:
        name = hero.get("name")
        if name is None:
            passthrough.append(dict(hero))
            continue
        key = alias_to_key.get(_hero_key(str(name)), _hero_key(str(name)))
        stripped_key = _strip_faction_prefix(_hero_key(str(name)))
        key = alias_to_key.get(stripped_key, key)
        if key in by_name:
            by_name[key] = _merge_hero_detail(by_name[key], hero)
        else:
            by_name[key] = dict(hero)
            alias_to_key[key] = key
            stripped = _strip_faction_prefix(key)
            if stripped != key:
                alias_to_key.setdefault(stripped, key)
    return [*passthrough, *by_name.values()]


def _merge_hero_detail(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, new_value in overlay.items():
        if key == "name":
            merged[key] = _preferred_hero_name(base.get("name"), new_value)
        elif key in {"attributes", "attribute_points", "mount"}:
            merged[key] = _deep_merge_dicts(base.get(key) or {}, new_value or {})
        elif key == "equipment":
            merged[key] = _merge_object_list(base.get(key) or [], new_value, ("slot", "name"))
        elif key == "books":
            merged[key] = _merge_object_list(base.get(key) or [], new_value, ("slot", "name"))
        elif key == "tactic_details":
            normalized = _normalize_tactic_details(new_value, base.get("tactics") or [])
            merged[key] = _merge_object_list(base.get(key) or [], normalized, ("name",))
        elif key in {"soldier_specialties", "status_notes"}:
            merged[key] = _unique_values([*(base.get(key) or []), *new_value])
        else:
            merged[key] = new_value
    return merged


def _hero_key(name: str) -> str:
    return (
        name.replace("·", "")
        .replace("・", "")
        .replace("•", "")
        .replace(" ", "")
        .strip()
    )


def _strip_faction_prefix(name: str) -> str:
    if len(name) > 2 and name[0] in {"魏", "蜀", "吴", "群", "晋", "汉"}:
        return name[1:]
    return name


def _preferred_hero_name(base_name: Any, incoming_name: Any) -> Any:
    if not base_name:
        return incoming_name
    if not incoming_name:
        return base_name
    base_key = _hero_key(str(base_name))
    incoming_key = _hero_key(str(incoming_name))
    if _strip_faction_prefix(incoming_key) == base_key:
        return base_name
    if _strip_faction_prefix(base_key) == incoming_key:
        return incoming_name
    return incoming_name


def _normalize_tactic_details(
    details: list[dict[str, Any]],
    known_names: list[Any],
) -> list[dict[str, Any]]:
    known = [str(name) for name in known_names if name]
    normalized: list[dict[str, Any]] = []
    for detail in details:
        payload = dict(detail)
        name = payload.get("name")
        if name:
            payload["name"] = _best_known_tactic_name(str(name), known)
        normalized.append(payload)
    return normalized


def _best_known_tactic_name(name: str, known_names: list[str]) -> str:
    if name in known_names:
        return name
    for known in known_names:
        if len(name) == len(known):
            mismatches = sum(1 for left, right in zip(name, known) if left != right)
            if mismatches <= 1:
                return known
    best = max(
        known_names,
        key=lambda known: SequenceMatcher(None, name, known).ratio(),
        default=None,
    )
    if best and SequenceMatcher(None, name, best).ratio() >= 0.75:
        return best
    return name


def _merge_object_list(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    key_candidates: tuple[str, ...],
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    passthrough: list[dict[str, Any]] = []
    for item in existing:
        key = _object_key(item, key_candidates)
        if key is None:
            passthrough.append(dict(item))
        else:
            by_key[key] = dict(item)

    for item in incoming:
        key = _object_key(item, key_candidates)
        if key is None:
            passthrough.append(dict(item))
            continue
        if key in by_key:
            by_key[key] = _deep_merge_dicts(by_key[key], item)
        else:
            by_key[key] = dict(item)
    return [*passthrough, *by_key.values()]


def _object_key(item: dict[str, Any], key_candidates: tuple[str, ...]) -> str | None:
    for key in key_candidates:
        value = item.get(key)
        if value is not None:
            return f"{key}:{value}"
    return None


def _merge_detail_status(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, str]:
    merged = {str(key): str(value) for key, value in base.items()}
    for key, value in overlay.items():
        normalized_key = str(key)
        if value == "observed" or merged.get(normalized_key) != "observed":
            merged[normalized_key] = str(value)
    return merged


def _merge_main_lineup_detail(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key in {"team_readiness", "team_snapshot"}:
            merged[key] = _deep_merge_dicts(base.get(key) or {}, value or {})
        else:
            merged[key] = value
    return merged


def _find_by_key(
    items: list[dict[str, Any]],
    key: str,
    value: Any,
) -> dict[str, Any] | None:
    if value is None:
        return None
    for item in items:
        if item.get(key) == value:
            return item
    return None


def _detail_completion(detail_status: dict[str, Any]) -> dict[str, bool]:
    return {
        tab: detail_status.get(tab) == "observed"
        for tab in DEFAULT_MISSING_DETAIL_TABS
    }


def _deep_merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dicts(current, value)
        elif isinstance(current, list) and isinstance(value, list):
            merged[key] = _unique_values([*current, *value])
        else:
            merged[key] = value
    return merged


def _unique_values(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _deep_merge_two_level(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Merge overlay into base, descending one level into nested dicts.

    economy = {"resources": {...}, "currencies": {...}, "reserve_troops": N}
    — nested dicts (resources/currencies) get per-key merged; scalars replace.
    """
    merged = dict(base)
    for key, new_value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(new_value, dict):
            combined = dict(existing)
            combined.update(new_value)
            merged[key] = combined
        else:
            merged[key] = new_value
    return merged
