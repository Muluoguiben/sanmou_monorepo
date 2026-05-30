from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from pioneer_agent.core.enums import ActionType
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

    def build(self) -> VerifierBase:
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
                path="teams.0.soldiers",
                operator=DeltaOperator.GREATER_THAN_BEFORE,
            ),
            ExpectedStateDelta(
                path="teams.0.recruit_finish_time",
                operator=DeltaOperator.PRESENT,
            ),
            ExpectedStateDelta(
                path="economy.reserve_troops",
                operator=DeltaOperator.LESS_THAN_BEFORE,
            ),
        ),
        timeout_seconds=30.0,
        match_policy=DeltaMatchPolicy.ANY,
    ),
    ActionType.UPGRADE_BUILDING: VerifierSpec(
        action_type=ActionType.UPGRADE_BUILDING,
        expected_deltas=(
            ExpectedStateDelta(
                path="city.buildings.0.level",
                operator=DeltaOperator.GREATER_THAN_BEFORE,
            ),
            ExpectedStateDelta(
                path="economy.resources.wood",
                operator=DeltaOperator.LESS_THAN_BEFORE,
            ),
        ),
        timeout_seconds=20.0,
        match_policy=DeltaMatchPolicy.ANY,
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
