"""Single source of truth for runbook action-allowlist semantics.

Both the selection layer (CandidateFilter) and the loop's dispatch backstop
consult these helpers, so the rules cannot drift apart:
- no `allowed_action_types` key (or a non-list value) means no filter;
- an EMPTY list means "block every non-wait action" (fail closed);
- wait actions are always exempt — a phase must never starve on stamina/
  resource waits because of an allowlist;
- entries are normalized via their `.value` when present, so both YAML
  strings and ActionType members compare correctly.
"""
from __future__ import annotations

from typing import Mapping

from pioneer_agent.core.enums import ActionType

WAIT_EXEMPT_ACTIONS = frozenset({ActionType.WAIT_FOR_STAMINA, ActionType.WAIT_FOR_RESOURCE})

RUNBOOK_FILTER_REJECT_REASON = "runbook_action_filter"


def normalized_allowed_action_types(selector_hints: Mapping | None) -> set[str] | None:
    """None = no filter declared; a set (possibly empty) = enforce it."""
    if not isinstance(selector_hints, Mapping):
        return None
    allowed = selector_hints.get("allowed_action_types")
    if not isinstance(allowed, list):
        return None
    return {str(getattr(item, "value", item)) for item in allowed}


def action_type_allowed(action_type: ActionType, allowed: set[str] | None) -> bool:
    if allowed is None:
        return True
    if action_type in WAIT_EXEMPT_ACTIONS:
        return True
    return action_type.value in allowed
