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

from typing import Any

from pioneer_agent.core.models import FieldMeta, RuntimeState

from .city_buildings import CityBuildingsFragment
from .resource_bar import ResourceBarFragment

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


def _merge_city(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, new_value in overlay.items():
        if key == "buildings":
            merged["buildings"] = _merge_building_list(
                base.get("buildings") or [],
                new_value,
            )
        else:
            merged[key] = new_value
    return merged


def _merge_building_list(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {b["name"]: dict(b) for b in existing if "name" in b}
    for entry in incoming:
        name = entry.get("name")
        if not name:
            continue
        if name in by_name:
            by_name[name].update(entry)
        else:
            by_name[name] = dict(entry)
    return list(by_name.values())


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
