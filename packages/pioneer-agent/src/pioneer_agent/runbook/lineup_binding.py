"""Trusted operator bindings between an observed team and a lineup preset.

Runbook ``lineup_preset`` values are desired policy, not observations.  A
live loop can bind a freshly observed team id to a preset only through the
explicit CLI channel in ``pioneer_agent.app.autonomous``.  The binding keeps
its operator provenance and expires instead of silently becoming permanent.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, MutableMapping

from pioneer_agent.core.models import FieldMeta, RuntimeState

OPERATOR_LINEUP_BINDING_SOURCE = "operator.cli.lineup_preset_binding"
LINEUP_BINDING_MAX_AGE = timedelta(hours=4)
LINEUP_BINDING_FUTURE_SKEW = timedelta(minutes=5)
COMPLETE_ROSTER_HERO_COUNT = 3
ROSTER_PAGE_TYPES = frozenset({"team_panel", "team_detail", "lineup_config", "team"})


def parse_operator_lineup_binding(value: str) -> tuple[str, str]:
    """Parse ``TEAM_ID=PRESET`` without accepting empty or ambiguous values."""
    if "=" not in value:
        raise ValueError("expected TEAM_ID=PRESET")
    team_id, preset = (part.strip() for part in value.split("=", 1))
    if not team_id or not preset:
        raise ValueError("TEAM_ID and PRESET must both be non-empty")
    return team_id, preset


def operator_lineup_binding_map(
    bindings: list[tuple[str, str]],
) -> dict[str, str]:
    """Build a unique map; conflicting duplicate team ids are rejected."""
    result: dict[str, str] = {}
    for team_id, preset in bindings:
        previous = result.get(team_id)
        if previous is not None and previous != preset:
            raise ValueError(
                f"team {team_id!r} has conflicting presets {previous!r} and {preset!r}"
            )
        result[team_id] = preset
    return result


def apply_operator_lineup_bindings(
    state: RuntimeState,
    bindings: Mapping[str, str],
    *,
    bound_at: datetime,
    now: datetime | None = None,
    roster_fingerprints: MutableMapping[str, str] | None = None,
) -> None:
    """Annotate unique teams while keeping their first observed roster bound.

    A loop passes one persistent ``roster_fingerprints`` mapping.  Reusing the
    same team slot for different heroes then invalidates the binding instead
    of silently attaching the old preset name to the new lineup.
    """
    current = _aware(now or datetime.now().astimezone())
    bound = _aware(bound_at)
    if bound is None or current is None or not _is_fresh(bound, current):
        return
    captured_rosters = roster_fingerprints if roster_fingerprints is not None else {}

    for raw_team_id, raw_preset in bindings.items():
        if not isinstance(raw_team_id, str) or not isinstance(raw_preset, str):
            continue
        team_id = raw_team_id.strip()
        preset = raw_preset.strip()
        if not team_id or not preset:
            continue
        matches = [
            team
            for team in state.team_containers
            if (
                isinstance(team, dict)
                and team.get("team_id") is not None
                and str(team.get("team_id")).strip()
                and str(team.get("team_id")) == team_id
            )
        ]
        for team in matches:
            _clear_operator_binding(team)
        state.field_meta.pop(f"team_containers.{team_id}.lineup_preset", None)
        if len(matches) != 1:
            continue
        team = matches[0]
        roster_fingerprint = team_roster_fingerprint(state, team.get("team_id"))
        if roster_fingerprint is None:
            continue
        expected_fingerprint = captured_rosters.get(team_id)
        if expected_fingerprint is None:
            captured_rosters[team_id] = roster_fingerprint
            expected_fingerprint = roster_fingerprint
        if roster_fingerprint != expected_fingerprint:
            continue
        team["lineup_preset"] = preset
        team["lineup_preset_source"] = OPERATOR_LINEUP_BINDING_SOURCE
        team["lineup_preset_bound_at"] = bound.isoformat()
        team["lineup_preset_roster_fingerprint"] = expected_fingerprint
        state.field_meta[f"team_containers.{team_id}.lineup_preset"] = FieldMeta(
            value=preset,
            confidence=1.0,
            source=OPERATOR_LINEUP_BINDING_SOURCE,
            updated_at=bound,
        )


def trusted_lineup_preset(
    state: RuntimeState,
    team: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> str | None:
    """Return a preset only when provenance and freshness are both valid."""
    preset = team.get("lineup_preset")
    if not isinstance(preset, str) or not preset.strip():
        return None
    if team.get("lineup_preset_source") != OPERATOR_LINEUP_BINDING_SOURCE:
        return None
    expected_fingerprint = team.get("lineup_preset_roster_fingerprint")
    if not isinstance(expected_fingerprint, str) or not expected_fingerprint:
        return None
    current_fingerprint = team_roster_fingerprint(state, team.get("team_id"))
    if current_fingerprint != expected_fingerprint:
        return None
    raw_bound_at = team.get("lineup_preset_bound_at")
    if not isinstance(raw_bound_at, str):
        return None
    try:
        bound_at = _aware(datetime.fromisoformat(raw_bound_at))
    except ValueError:
        return None
    current = _aware(now or datetime.now().astimezone())
    if bound_at is None or current is None or not _is_fresh(bound_at, current):
        return None
    return preset.strip()


def team_roster_fingerprint(
    state: RuntimeState,
    team_id: Any,
) -> str | None:
    """Hash one complete three-hero identity roster.

    This deliberately attests only visible hero composition, not hidden tactic
    levels, equipment, or formation details.  Exactly three distinct heroes on
    a team page are required; partial observations stay dark.
    """
    if team_id is None or isinstance(team_id, bool):
        return None
    matches = [
        team
        for team in state.teams
        if isinstance(team, Mapping) and team.get("team_id") == team_id
    ]
    if len(matches) != 1:
        return None
    team = matches[0]
    if team.get("page_type") not in ROSTER_PAGE_TYPES:
        return None
    heroes = team.get("heroes")
    if not isinstance(heroes, list) or len(heroes) != COMPLETE_ROSTER_HERO_COUNT:
        return None
    roster: list[dict[str, Any]] = []
    identities: set[str] = set()
    for index, hero in enumerate(heroes):
        if not isinstance(hero, Mapping):
            return None
        identity = hero.get("hero_id") or hero.get("name")
        if not isinstance(identity, (str, int)) or isinstance(identity, bool):
            return None
        roster.append(
            {
                "identity": str(identity).strip(),
                "position": hero.get("position", index),
            }
        )
        normalized_identity = roster[-1]["identity"]
        if not normalized_identity or normalized_identity in identities:
            return None
        identities.add(normalized_identity)
    canonical = json.dumps(
        roster,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _is_fresh(bound_at: datetime, now: datetime) -> bool:
    age = now.astimezone(timezone.utc) - bound_at.astimezone(timezone.utc)
    return -LINEUP_BINDING_FUTURE_SKEW <= age <= LINEUP_BINDING_MAX_AGE


def _clear_operator_binding(team: dict[str, Any]) -> None:
    if team.get("lineup_preset_source") != OPERATOR_LINEUP_BINDING_SOURCE:
        return
    for key in (
        "lineup_preset",
        "lineup_preset_source",
        "lineup_preset_bound_at",
        "lineup_preset_roster_fingerprint",
    ):
        team.pop(key, None)


def _aware(value: datetime) -> datetime | None:
    if value.tzinfo is None or value.utcoffset() is None:
        return None
    return value
