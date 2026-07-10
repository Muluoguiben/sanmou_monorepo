from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction
from pioneer_agent.verifier.base import (
    DeltaMatchPolicy,
    DeltaOperator,
    ExpectedStateDelta,
    VerifierBase,
)


UI_ACTIONS_REQUIRING_VERIFIER = frozenset(
    {
        ActionType.CLAIM_CHAPTER_REWARD,
        ActionType.UPGRADE_BUILDING,
        ActionType.RECRUIT_SOLDIERS,
        ActionType.ATTACK_LAND,
        ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM,
        ActionType.ABANDON_LAND,
    }
)


class VerifierGateDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass(frozen=True)
class VerifierSpec:
    action_type: ActionType
    expected_deltas: tuple[ExpectedStateDelta, ...]
    timeout_seconds: float
    match_policy: DeltaMatchPolicy | str = DeltaMatchPolicy.ALL

    def bind(self, action: CandidateAction) -> VerifierSpec:
        if action.action_type != self.action_type:
            raise ValueError("verifier action type does not match candidate action")
        _validate_action_target_params(action)
        return replace(
            self,
            expected_deltas=tuple(
                _bind_delta(delta, action.params) for delta in self.expected_deltas
            ),
        )

    def build(self) -> VerifierBase:
        for delta in self.expected_deltas:
            if (
                delta.identity_param is not None
                or delta.before_param is not None
                or delta.expected_after_param is not None
            ):
                raise ValueError("verifier spec must be bound to an action before build")
            if delta.collection_path is not None and (
                not delta.identity_field or delta.identity_value is None
            ):
                raise ValueError("entity-bound verifier delta has no concrete identity")
        return VerifierBase(
            self.expected_deltas,
            timeout_seconds=self.timeout_seconds,
            match_policy=self.match_policy,
        )


@dataclass(frozen=True)
class VerifierGateVerdict:
    decision: VerifierGateDecision
    reason: str
    action_type: ActionType
    timeout_seconds: float | None = None
    match_policy: DeltaMatchPolicy | str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision == VerifierGateDecision.ALLOW


DEFAULT_VERIFIER_SPECS: dict[ActionType, VerifierSpec] = {
    ActionType.CLAIM_CHAPTER_REWARD: VerifierSpec(
        action_type=ActionType.CLAIM_CHAPTER_REWARD,
        expected_deltas=(
            ExpectedStateDelta(
                path="progress.current_chapter_id",
                operator=DeltaOperator.EQUALS,
                before_param="chapter_id",
                expected_after_param="chapter_id",
            ),
            ExpectedStateDelta(
                path="progress.chapter_claimable",
                before=True,
                expected_after=False,
            ),
        ),
        timeout_seconds=10.0,
    ),
    ActionType.RECRUIT_SOLDIERS: VerifierSpec(
        action_type=ActionType.RECRUIT_SOLDIERS,
        expected_deltas=(
            ExpectedStateDelta(
                path="soldiers",
                operator=DeltaOperator.GREATER_THAN_BEFORE,
                collection_path="teams",
                identity_field="team_id",
                identity_param="team_id",
            ),
            ExpectedStateDelta(
                path="recruit_finish_time",
                operator=DeltaOperator.BECOMES_PRESENT,
                collection_path="teams",
                identity_field="team_id",
                identity_param="team_id",
            ),
        ),
        timeout_seconds=30.0,
        match_policy=DeltaMatchPolicy.ANY,
    ),
    ActionType.UPGRADE_BUILDING: VerifierSpec(
        action_type=ActionType.UPGRADE_BUILDING,
        expected_deltas=(
            ExpectedStateDelta(
                path="level",
                operator=DeltaOperator.INCREASES_TO,
                collection_path="city.buildings",
                identity_field="name",
                identity_param="building_name",
                before_param="current_level",
                expected_after_param="target_level",
            ),
        ),
        timeout_seconds=20.0,
        match_policy=DeltaMatchPolicy.ALL,
    ),
}


@dataclass(frozen=True)
class VerifierRegistry:
    specs: Mapping[ActionType, VerifierSpec] = field(
        default_factory=lambda: dict(DEFAULT_VERIFIER_SPECS)
    )
    required_actions: frozenset[ActionType] = field(
        default_factory=lambda: UI_ACTIONS_REQUIRING_VERIFIER
    )

    def get(self, action_type: ActionType) -> VerifierSpec | None:
        return self.specs.get(action_type)

    def get_for_action(self, action: CandidateAction) -> VerifierSpec | None:
        spec = self.get(action.action_type)
        return spec.bind(action) if spec is not None else None

    def evaluate_action(self, action: CandidateAction) -> VerifierGateVerdict:
        verdict = self.evaluate(action.action_type)
        if not verdict.allowed:
            return verdict
        spec = self.get(action.action_type)
        if spec is None:
            return verdict
        try:
            bound = spec.bind(action)
            bound.build()
        except ValueError as exc:
            return VerifierGateVerdict(
                decision=VerifierGateDecision.BLOCK,
                reason=f"action-bound verifier unavailable: {exc}",
                action_type=action.action_type,
                timeout_seconds=spec.timeout_seconds,
                match_policy=spec.match_policy,
            )
        return verdict

    def evaluate(self, action_type: ActionType) -> VerifierGateVerdict:
        if action_type not in self.required_actions:
            return VerifierGateVerdict(
                decision=VerifierGateDecision.ALLOW,
                reason="action does not require post-action verifier",
                action_type=action_type,
            )

        spec = self.get(action_type)
        if spec is None:
            return VerifierGateVerdict(
                decision=VerifierGateDecision.BLOCK,
                reason="UI action requires a verifier spec before execution",
                action_type=action_type,
            )
        if not spec.expected_deltas:
            return VerifierGateVerdict(
                decision=VerifierGateDecision.BLOCK,
                reason="verifier spec must declare at least one expected state delta",
                action_type=action_type,
                timeout_seconds=spec.timeout_seconds,
                match_policy=spec.match_policy,
            )
        if spec.timeout_seconds <= 0:
            return VerifierGateVerdict(
                decision=VerifierGateDecision.BLOCK,
                reason="verifier timeout must be positive",
                action_type=action_type,
                timeout_seconds=spec.timeout_seconds,
                match_policy=spec.match_policy,
            )

        return VerifierGateVerdict(
            decision=VerifierGateDecision.ALLOW,
            reason="verifier spec is available",
            action_type=action_type,
            timeout_seconds=spec.timeout_seconds,
            match_policy=spec.match_policy,
        )


def serialize_verifier_spec(spec: VerifierSpec | None) -> dict | None:
    if spec is None:
        return None
    return {
        "action_type": spec.action_type.value,
        "timeout_seconds": spec.timeout_seconds,
        "match_policy": _match_policy_value(spec.match_policy),
        "expected_deltas": [
            {
                "path": delta.path,
                "operator": _operator_value(delta.operator),
                "before": delta.before,
                "expected_after": delta.expected_after,
                "collection_path": delta.collection_path,
                "identity_field": delta.identity_field,
                "identity_value": delta.identity_value,
                "identity_param": delta.identity_param,
                "before_param": delta.before_param,
                "expected_after_param": delta.expected_after_param,
            }
            for delta in spec.expected_deltas
        ],
    }


def _match_policy_value(value: DeltaMatchPolicy | str) -> str:
    if isinstance(value, DeltaMatchPolicy):
        return value.value
    return DeltaMatchPolicy(str(value)).value


def _operator_value(value: DeltaOperator | str) -> str:
    if isinstance(value, DeltaOperator):
        return value.value
    return DeltaOperator(str(value)).value


def _bind_delta(
    delta: ExpectedStateDelta,
    params: Mapping[str, Any],
) -> ExpectedStateDelta:
    updates: dict[str, Any] = {}
    for param_field, value_field in (
        ("identity_param", "identity_value"),
        ("before_param", "before"),
        ("expected_after_param", "expected_after"),
    ):
        param_name = getattr(delta, param_field)
        if param_name is None:
            continue
        value = params.get(param_name)
        if value is None or value == "":
            raise ValueError(f"missing required action param {param_name!r}")
        updates[value_field] = value
        updates[param_field] = None
    return replace(delta, **updates)


def _validate_action_target_params(action: CandidateAction) -> None:
    params = action.params
    if action.action_type == ActionType.CLAIM_CHAPTER_REWARD:
        _require_positive_int(params, "chapter_id")
        return
    if action.action_type == ActionType.RECRUIT_SOLDIERS:
        _require_nonempty_str(params, "team_id")
        return
    if action.action_type != ActionType.UPGRADE_BUILDING:
        return

    _require_nonempty_str(params, "building_name")
    building_id = params.get("building_id")
    if building_id is not None:
        _require_nonempty_str(params, "building_id")
    current_level = _require_nonnegative_int(params, "current_level")
    target_level = _require_positive_int(params, "target_level")
    if target_level != current_level + 1:
        raise ValueError(
            "upgrade target_level must be exactly one level above current_level"
        )


def _require_nonempty_str(params: Mapping[str, Any], name: str) -> str:
    value = params.get(name)
    if value is None or value == "":
        raise ValueError(f"missing required action param {name!r}")
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"action param {name!r} must be a non-empty string")
    return value


def _require_positive_int(params: Mapping[str, Any], name: str) -> int:
    value = params.get(name)
    if value is None or value == "":
        raise ValueError(f"missing required action param {name!r}")
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"action param {name!r} must be a positive integer")
    return value


def _require_nonnegative_int(params: Mapping[str, Any], name: str) -> int:
    value = params.get(name)
    if value is None or value == "":
        raise ValueError(f"missing required action param {name!r}")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"action param {name!r} must be a non-negative integer")
    return value
