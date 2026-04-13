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
