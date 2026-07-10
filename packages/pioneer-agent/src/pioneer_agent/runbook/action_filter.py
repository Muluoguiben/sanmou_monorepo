"""Single source of truth for Runbook action constraints.

Selection and final dispatch call the same evaluator. Runbook hints describe
desired policy; target facts are resolved by identity from the current runtime
state and are rejected when missing, ambiguous, stale, or mismatched.
"""
from __future__ import annotations

from typing import Any, Mapping

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState
from pioneer_agent.runbook.lineup_binding import trusted_lineup_preset

WAIT_EXEMPT_ACTIONS = frozenset(
    {ActionType.WAIT_FOR_STAMINA, ActionType.WAIT_FOR_RESOURCE}
)

RUNBOOK_FILTER_REJECT_REASON = "runbook_action_filter"
RUNBOOK_CONTEXT_MISSING_REASON = "runbook_context_missing"
RUNBOOK_ALLOWED_ACTION_TYPES_INVALID_REASON = "runbook_allowed_action_types_invalid"
RUNBOOK_TARGET_LEVELS_INVALID_REASON = "runbook_target_land_levels_invalid"
RUNBOOK_TARGET_LEVEL_UNKNOWN_REASON = "runbook_target_land_level_unknown"
RUNBOOK_TARGET_LEVEL_MISMATCH_REASON = "runbook_target_land_level_mismatch"
RUNBOOK_LAND_SCOPE_INVALID_REASON = "runbook_land_scope_invalid"
RUNBOOK_LAND_SCOPE_UNKNOWN_REASON = "runbook_land_scope_unknown"
RUNBOOK_LAND_SCOPE_MISMATCH_REASON = "runbook_land_scope_mismatch"
RUNBOOK_LINEUP_PRESET_INVALID_REASON = "runbook_lineup_preset_invalid"
RUNBOOK_LINEUP_PRESET_UNKNOWN_REASON = "runbook_lineup_preset_unknown"
RUNBOOK_LINEUP_PRESET_MISMATCH_REASON = "runbook_lineup_preset_mismatch"
RUNBOOK_ATTACK_TEAM_UNKNOWN_REASON = "runbook_attack_team_unknown"
RUNBOOK_ATTACK_TEAM_MISMATCH_REASON = "runbook_attack_team_mismatch"

RUNBOOK_ACTION_CONSTRAINT_REASONS = frozenset(
    {
        RUNBOOK_FILTER_REJECT_REASON,
        RUNBOOK_CONTEXT_MISSING_REASON,
        RUNBOOK_ALLOWED_ACTION_TYPES_INVALID_REASON,
        RUNBOOK_TARGET_LEVELS_INVALID_REASON,
        RUNBOOK_TARGET_LEVEL_UNKNOWN_REASON,
        RUNBOOK_TARGET_LEVEL_MISMATCH_REASON,
        RUNBOOK_LAND_SCOPE_INVALID_REASON,
        RUNBOOK_LAND_SCOPE_UNKNOWN_REASON,
        RUNBOOK_LAND_SCOPE_MISMATCH_REASON,
        RUNBOOK_LINEUP_PRESET_INVALID_REASON,
        RUNBOOK_LINEUP_PRESET_UNKNOWN_REASON,
        RUNBOOK_LINEUP_PRESET_MISMATCH_REASON,
        RUNBOOK_ATTACK_TEAM_UNKNOWN_REASON,
        RUNBOOK_ATTACK_TEAM_MISMATCH_REASON,
    }
)

_ACTUAL_LAND_SCOPES = frozenset({"inner_city", "outer_city"})
_POLICY_LAND_SCOPES = frozenset({*_ACTUAL_LAND_SCOPES, "inner_and_outer"})


def normalized_allowed_action_types(selector_hints: Mapping | None) -> set[str] | None:
    """None means no allowlist key; a set (possibly empty) means enforce it."""
    if not isinstance(selector_hints, Mapping) or "allowed_action_types" not in selector_hints:
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


def runbook_action_reject_reason(
    action: CandidateAction,
    selector_hints: Mapping[str, Any] | None,
    *,
    actual_facts: Mapping[str, Any] | None = None,
) -> str | None:
    """Return the stable Runbook policy reason that blocks ``action``."""
    if not isinstance(selector_hints, Mapping):
        return RUNBOOK_CONTEXT_MISSING_REASON

    invalid_reason = _invalid_selector_hints_reason(selector_hints)
    if invalid_reason is not None:
        return invalid_reason

    if "allowed_action_types" in selector_hints:
        allowed = normalized_allowed_action_types(selector_hints)
        if not action_type_allowed(action.action_type, allowed):
            return RUNBOOK_FILTER_REJECT_REASON

    actual_keys = _attack_target_actual_keys(action)
    if actual_keys is None:
        return None
    level_key, scope_key, preset_key = actual_keys
    # Target facts are never accepted from action.params: both production
    # callers must supply the independently state-resolved mapping.
    facts = actual_facts if isinstance(actual_facts, Mapping) else {}
    current_host_match = facts.get("_current_host_team_match")
    if current_host_match is None:
        return RUNBOOK_ATTACK_TEAM_UNKNOWN_REASON
    if current_host_match is not True:
        return RUNBOOK_ATTACK_TEAM_MISMATCH_REASON

    if "target_land_levels" in selector_hints:
        levels = selector_hints.get("target_land_levels")
        actual_level = facts.get(level_key)
        if not _valid_actual_level(actual_level):
            return RUNBOOK_TARGET_LEVEL_UNKNOWN_REASON
        if actual_level not in levels:
            return RUNBOOK_TARGET_LEVEL_MISMATCH_REASON

    if "land_scope" in selector_hints:
        expected_scope = selector_hints.get("land_scope")
        actual_scope = facts.get(scope_key)
        if actual_scope not in _ACTUAL_LAND_SCOPES:
            return RUNBOOK_LAND_SCOPE_UNKNOWN_REASON
        if expected_scope != "inner_and_outer" and actual_scope != expected_scope:
            return RUNBOOK_LAND_SCOPE_MISMATCH_REASON

    if "lineup_preset" in selector_hints:
        expected_preset = selector_hints.get("lineup_preset")
        actual_preset = facts.get(preset_key)
        if not isinstance(actual_preset, str) or not actual_preset.strip():
            return RUNBOOK_LINEUP_PRESET_UNKNOWN_REASON
        if actual_preset != expected_preset.strip():
            return RUNBOOK_LINEUP_PRESET_MISMATCH_REASON

    return None


def resolve_runbook_action_facts(
    state: RuntimeState | None,
    action: CandidateAction,
) -> dict[str, Any]:
    """Resolve policy facts from current state using only action identities.

    Missing or duplicate identities produce unknown facts. This keeps a custom
    selector from satisfying Runbook policy by copying hint values into params.
    """
    actual_keys = _attack_target_actual_keys(action)
    if actual_keys is None:
        return {}
    level_key, scope_key, preset_key = actual_keys
    facts = {
        level_key: None,
        scope_key: None,
        preset_key: None,
        "_current_host_team_match": None,
    }
    if state is None:
        return facts

    land_id = action.params.get("land_id")
    land_matches = []
    if _usable_identity(land_id):
        land_matches = [
            land
            for land in state.map_state.get("candidate_lands", [])
            if isinstance(land, Mapping) and land.get("land_id") == land_id
        ]
    if len(land_matches) == 1:
        facts[level_key] = land_matches[0].get("level")
        facts[scope_key] = land_matches[0].get("land_scope")

    team_id = action.params.get("team_id")
    current_host_team_id = state.main_lineup.get("current_host_team_id")
    team_matches = []
    if _usable_identity(team_id) and _usable_identity(current_host_team_id):
        if team_id != current_host_team_id:
            facts["_current_host_team_match"] = False
            return facts
        team_matches = [
            team
            for team in state.team_containers
            if isinstance(team, Mapping) and team.get("team_id") == team_id
        ]
    if len(team_matches) == 1:
        facts["_current_host_team_match"] = True
        facts[preset_key] = trusted_lineup_preset(state, team_matches[0])
    return facts


def _attack_target_actual_keys(
    action: CandidateAction,
) -> tuple[str, str, str] | None:
    if action.action_type == ActionType.ATTACK_LAND:
        return "level", "land_scope", "lineup_preset"
    unlock = action.params.get("unlock_action_type")
    unlock_value = str(getattr(unlock, "value", unlock))
    if (
        action.action_type == ActionType.WAIT_FOR_STAMINA
        and unlock_value == ActionType.ATTACK_LAND.value
    ):
        return "unlock_land_level", "unlock_land_scope", "unlock_lineup_preset"
    return None


def _valid_target_levels(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_valid_actual_level(level) for level in value)
    )


def _valid_actual_level(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and 1 <= value <= 12


def _usable_identity(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    return not isinstance(value, str) or bool(value.strip())


def _invalid_selector_hints_reason(
    selector_hints: Mapping[str, Any],
) -> str | None:
    if "allowed_action_types" in selector_hints and not isinstance(
        selector_hints.get("allowed_action_types"), list
    ):
        return RUNBOOK_ALLOWED_ACTION_TYPES_INVALID_REASON
    if "target_land_levels" in selector_hints and not _valid_target_levels(
        selector_hints.get("target_land_levels")
    ):
        return RUNBOOK_TARGET_LEVELS_INVALID_REASON
    if "land_scope" in selector_hints and selector_hints.get(
        "land_scope"
    ) not in _POLICY_LAND_SCOPES:
        return RUNBOOK_LAND_SCOPE_INVALID_REASON
    preset = selector_hints.get("lineup_preset")
    if "lineup_preset" in selector_hints and (
        not isinstance(preset, str) or not preset.strip()
    ):
        return RUNBOOK_LINEUP_PRESET_INVALID_REASON
    return None
