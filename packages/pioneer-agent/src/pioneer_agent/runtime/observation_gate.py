from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Mapping

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ObservationSnapshot
from pioneer_agent.runtime.architecture_gates import LOW_RISK_AUTOMATION_ACTIONS


class ObservationGateDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    SKIP = "skip"


@dataclass(frozen=True)
class ObservationGateVerdict:
    decision: ObservationGateDecision
    reason: str
    verifier_state: dict[str, Any] | None = None
    dispatch_stage: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision in {
            ObservationGateDecision.ALLOW,
            ObservationGateDecision.SKIP,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "dispatch_stage": self.dispatch_stage,
            "details": dict(self.details),
        }


_DISPATCH_REQUIREMENTS = {
    "claim": ("chapter", "chapter_panel", "progress.chapter_panel", "vision.chapter_panel"),
    "recruit": ("recruit", "recruit_panel", "teams.recruit_panel", "vision.recruit_panel"),
    "upgrade_entry": ("city", "city_buildings", "city", "vision.city_buildings"),
    "upgrade_confirm": (
        frozenset({"building", "upgrade_dialog"}),
        "upgrade_dialog",
        "city.upgrade_dialog",
        "vision.upgrade_dialog",
    ),
}

_POST_REQUIREMENTS = {
    ActionType.CLAIM_CHAPTER_REWARD: _DISPATCH_REQUIREMENTS["claim"],
    ActionType.RECRUIT_SOLDIERS: _DISPATCH_REQUIREMENTS["recruit"],
    ActionType.UPGRADE_BUILDING: _DISPATCH_REQUIREMENTS["upgrade_entry"],
}

_FUTURE_TOLERANCE = timedelta(seconds=1)


def validate_dispatch_observation(
    action: CandidateAction,
    observation: ObservationSnapshot | None,
    *,
    now: datetime | None = None,
    max_age_seconds: float = 30.0,
    allow_fixture_source: bool = False,
) -> ObservationGateVerdict:
    if action.action_type not in LOW_RISK_AUTOMATION_ACTIONS:
        return ObservationGateVerdict(
            decision=ObservationGateDecision.SKIP,
            reason="action does not require a low-risk frame observation",
        )
    if observation is None:
        return _blocked("current frame observation is required before dispatch")

    now = now or datetime.now(UTC)
    metadata_error = _snapshot_metadata_error(
        observation,
        now=now,
        max_age_seconds=max_age_seconds,
        allow_fixture_source=allow_fixture_source,
    )
    if metadata_error:
        return _blocked(metadata_error, observation=observation)

    stage = _dispatch_stage(action)
    requirement = _DISPATCH_REQUIREMENTS[stage]
    requirement_error = _require_observed_domain(
        observation,
        requirement,
        allow_fixture_source=allow_fixture_source,
    )
    if requirement_error:
        return _blocked(requirement_error, observation=observation, stage=stage)

    state = observation.observed_state.model_dump(mode="python")
    target_error = _dispatch_target_error(action, state, stage=stage)
    if target_error:
        return _blocked(target_error, observation=observation, stage=stage)

    verifier_state = _project_verifier_state(action, state, stage=stage)
    return ObservationGateVerdict(
        decision=ObservationGateDecision.ALLOW,
        reason="action target and verifier baseline are bound to the current frame",
        verifier_state=verifier_state,
        dispatch_stage=stage,
        details=_observation_details(observation),
    )


def validate_post_observation(
    action: CandidateAction,
    baseline: ObservationSnapshot,
    observation: ObservationSnapshot | None,
    *,
    dispatch_completed_at: datetime,
    now: datetime | None = None,
    max_age_seconds: float = 30.0,
    allow_fixture_source: bool = False,
) -> ObservationGateVerdict:
    if action.action_type not in LOW_RISK_AUTOMATION_ACTIONS:
        return ObservationGateVerdict(
            decision=ObservationGateDecision.SKIP,
            reason="action does not require a low-risk post observation",
        )
    if observation is None:
        return _blocked("post-action frame observation is missing")
    now = now or datetime.now(UTC)
    metadata_error = _snapshot_metadata_error(
        observation,
        now=now,
        max_age_seconds=max_age_seconds,
        allow_fixture_source=allow_fixture_source,
    )
    if metadata_error:
        return _blocked(metadata_error, observation=observation)
    if observation.observation_id == baseline.observation_id:
        return _blocked("post-action observation reused the dispatch frame", observation=observation)
    if observation.frame_sha256 == baseline.frame_sha256:
        return _blocked(
            "post-action frame is stale: frame SHA256 matches the dispatch frame",
            observation=observation,
        )
    if not _is_aware(dispatch_completed_at):
        return _blocked("dispatch completion timestamp must be timezone-aware")
    if dispatch_completed_at.astimezone(UTC) > now.astimezone(UTC) + _FUTURE_TOLERANCE:
        return _blocked("dispatch completion timestamp is in the future")
    if observation.captured_at.astimezone(UTC) <= dispatch_completed_at.astimezone(UTC):
        return _blocked("post-action observation was not captured after dispatch", observation=observation)

    requirement = _POST_REQUIREMENTS[action.action_type]
    requirement_error = _require_observed_domain(
        observation,
        requirement,
        allow_fixture_source=allow_fixture_source,
    )
    if requirement_error:
        return _blocked(requirement_error, observation=observation)

    state = observation.observed_state.model_dump(mode="python")
    return ObservationGateVerdict(
        decision=ObservationGateDecision.ALLOW,
        reason="post-action verifier state comes from a new observed frame",
        verifier_state=state,
        dispatch_stage="post_action",
        details=_observation_details(observation),
    )


def _dispatch_stage(action: CandidateAction) -> str:
    if action.action_type == ActionType.CLAIM_CHAPTER_REWARD:
        return "claim"
    if action.action_type == ActionType.RECRUIT_SOLDIERS:
        return "recruit"
    dialog = action.params.get("upgrade_dialog")
    return "upgrade_confirm" if isinstance(dialog, dict) and dialog.get("visible") else "upgrade_entry"


def _dispatch_target_error(
    action: CandidateAction,
    state: Mapping[str, Any],
    *,
    stage: str,
) -> str | None:
    if stage == "claim":
        progress = state.get("progress")
        if not isinstance(progress, Mapping):
            return "current chapter observation is missing"
        if not _is_plain_int(progress.get("current_chapter_id")):
            return "current frame does not show a numeric chapter id"
        if progress.get("current_chapter_id") != action.params.get("chapter_id"):
            return "current frame chapter does not match the action target"
        if progress.get("chapter_claimable") is not True:
            return "current frame does not show a claimable chapter"
        return _button_mismatch(
            action.params.get("claim_button"),
            progress.get("chapter_claim_button"),
            label="chapter claim button",
        )

    if stage == "recruit":
        team, error = _unique_entity(
            state.get("teams"),
            identity_field="team_id",
            identity_value=action.params.get("team_id"),
            collection_label="teams",
        )
        if error:
            return error
        assert team is not None
        if isinstance(team.get("soldiers"), bool) or not isinstance(team.get("soldiers"), int):
            return "current frame does not show the target team's soldier baseline"
        return _button_mismatch(
            action.params.get("recruit_button"),
            team.get("recruit_button"),
            label="recruit button",
        )

    if stage == "upgrade_entry":
        city = state.get("city")
        if not isinstance(city, Mapping):
            return "current city observation is missing"
        building, error = _unique_entity(
            city.get("buildings"),
            identity_field="name",
            identity_value=action.params.get("building_name"),
            collection_label="city.buildings",
        )
        if error:
            return error
        assert building is not None
        if not _is_plain_int(building.get("level")):
            return "current frame does not show a numeric building level"
        if building.get("level") != action.params.get("current_level"):
            return "current frame building level does not match the action baseline"
        return _button_mismatch(
            action.params.get("upgrade_button"),
            building.get("upgrade_button"),
            label="building upgrade button",
        )

    city = state.get("city")
    dialog = city.get("upgrade_dialog") if isinstance(city, Mapping) else None
    if not isinstance(dialog, Mapping) or dialog.get("visible") is not True:
        return "current frame upgrade dialog is missing"
    if dialog.get("building_name") != action.params.get("building_name"):
        return "current frame upgrade dialog building does not match the action target"
    if not _is_plain_int(dialog.get("current_level")):
        return "current frame upgrade dialog baseline is not numeric"
    if not _is_plain_int(dialog.get("next_level")):
        return "current frame upgrade dialog target is not numeric"
    if dialog.get("current_level") != action.params.get("current_level"):
        return "current frame upgrade dialog baseline does not match the action"
    if dialog.get("next_level") != action.params.get("target_level"):
        return "current frame upgrade dialog target does not match the action"
    if dialog.get("can_upgrade") is not True:
        return "current frame upgrade dialog is not upgradeable"
    action_dialog = action.params.get("upgrade_dialog")
    action_button = action_dialog.get("confirm_button") if isinstance(action_dialog, Mapping) else None
    return _button_mismatch(
        action_button,
        dialog.get("confirm_button"),
        label="upgrade confirm button",
    )


def _project_verifier_state(
    action: CandidateAction,
    state: dict[str, Any],
    *,
    stage: str,
) -> dict[str, Any]:
    if stage != "upgrade_confirm":
        return state
    city = state.get("city")
    dialog = city.get("upgrade_dialog") if isinstance(city, dict) else {}
    projected = dict(state)
    projected_city = dict(city) if isinstance(city, dict) else {}
    projected_city["buildings"] = [
        {
            "name": action.params.get("building_name"),
            "level": dialog.get("current_level") if isinstance(dialog, dict) else None,
        }
    ]
    projected["city"] = projected_city
    return projected


def _snapshot_metadata_error(
    observation: ObservationSnapshot,
    *,
    now: datetime,
    max_age_seconds: float,
    allow_fixture_source: bool,
) -> str | None:
    if not math.isfinite(max_age_seconds) or max_age_seconds <= 0:
        return "observation freshness limit must be finite and positive"
    structure_error = _snapshot_structure_error(
        observation,
        allow_fixture_source=allow_fixture_source,
    )
    if structure_error:
        return structure_error
    if not _is_aware(now):
        return "observation gate clock must be timezone-aware"
    age_seconds = (
        now.astimezone(UTC) - observation.captured_at.astimezone(UTC)
    ).total_seconds()
    if age_seconds < -_FUTURE_TOLERANCE.total_seconds():
        return "observation timestamp is in the future"
    if age_seconds > max_age_seconds:
        return f"observation is stale ({age_seconds:.3f}s old)"
    return None


def _is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _snapshot_structure_error(
    observation: ObservationSnapshot,
    *,
    allow_fixture_source: bool,
) -> str | None:
    if not observation.observation_id:
        return "observation id is missing"
    if not _is_aware(observation.captured_at):
        return "observation timestamp must be timezone-aware"
    if not _valid_sha256(observation.frame_sha256):
        return "observation frame SHA256 is invalid"
    if (
        observation.frame_size is None
        or len(observation.frame_size) != 2
        or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in observation.frame_size)
    ):
        return "observation frame size is invalid"
    if observation.source != "vision_sync" and not allow_fixture_source:
        return "live dispatch requires a vision_sync observation"
    return None


def _require_observed_domain(
    observation: ObservationSnapshot,
    requirement: tuple[Any, str, str, str],
    *,
    allow_fixture_source: bool,
) -> str | None:
    expected_page, domain, meta_key, meta_source = requirement
    page_matches = (
        observation.page_type in expected_page
        if isinstance(expected_page, frozenset)
        else observation.page_type == expected_page
    )
    if not page_matches:
        return f"current observation page {observation.page_type!r} does not match {expected_page!r}"
    if domain not in observation.domains_run:
        return f"current observation did not run required domain {domain!r}"
    if allow_fixture_source and observation.source != "vision_sync":
        return None
    meta = observation.observed_state.field_meta.get(meta_key)
    if meta is None:
        return f"current observation is missing field metadata {meta_key!r}"
    if meta.observation_id != observation.observation_id:
        return f"field metadata {meta_key!r} is not bound to the current observation"
    if meta.source != meta_source:
        return f"field metadata {meta_key!r} has unexpected source {meta.source!r}"
    if meta.updated_at is None or not _is_aware(meta.updated_at):
        return f"field metadata {meta_key!r} timestamp is not timezone-aware"
    if meta.updated_at.astimezone(UTC) != observation.captured_at.astimezone(UTC):
        return f"field metadata {meta_key!r} timestamp does not match the observation"
    return None


def _unique_entity(
    raw: Any,
    *,
    identity_field: str,
    identity_value: Any,
    collection_label: str,
) -> tuple[Mapping[str, Any] | None, str | None]:
    if not isinstance(raw, list):
        return None, f"current observation is missing {collection_label}"
    matches = [
        item
        for item in raw
        if isinstance(item, Mapping) and item.get(identity_field) == identity_value
    ]
    if len(matches) != 1:
        return (
            None,
            f"expected exactly one {collection_label} target with "
            f"{identity_field}={identity_value!r}, got {len(matches)}",
        )
    return matches[0], None


def _button_mismatch(action_button: Any, observed_button: Any, *, label: str) -> str | None:
    action_normalized = _normalize_button(action_button)
    observed_normalized = _normalize_button(observed_button)
    if action_normalized is None or observed_normalized is None:
        return f"current observation is missing a valid {label}"
    if action_normalized != observed_normalized:
        return f"action {label} does not match the current observation"
    return None


def _normalize_button(raw: Any) -> tuple[bool, bool, tuple[int, int, int, int]] | None:
    if not isinstance(raw, Mapping):
        return None
    bbox = raw.get("bbox")
    if not isinstance(bbox, Mapping):
        return None
    values = tuple(bbox.get(key) for key in ("x_min", "y_min", "x_max", "y_max"))
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        return None
    return bool(raw.get("visible")), bool(raw.get("enabled")), values  # type: ignore[return-value]


def _blocked(
    reason: str,
    *,
    observation: ObservationSnapshot | None = None,
    stage: str | None = None,
) -> ObservationGateVerdict:
    return ObservationGateVerdict(
        decision=ObservationGateDecision.BLOCK,
        reason=reason,
        dispatch_stage=stage,
        details=_observation_details(observation) if observation else {},
    )


def _observation_details(observation: ObservationSnapshot) -> dict[str, Any]:
    return {
        "observation_id": observation.observation_id,
        "captured_at": observation.captured_at.isoformat(),
        "frame_sha256": observation.frame_sha256,
        "frame_size": list(observation.frame_size) if observation.frame_size else None,
        "page_type": observation.page_type,
        "domains_run": list(observation.domains_run),
        "source": observation.source,
    }


def _is_aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True
