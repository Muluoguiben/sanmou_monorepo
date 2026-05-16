from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping

from pioneer_agent.core.enums import ActionType
from pioneer_agent.verifier.base import ExpectedStateDelta, VerifierBase


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

    def build(self) -> VerifierBase:
        return VerifierBase(
            self.expected_deltas,
            timeout_seconds=self.timeout_seconds,
        )


@dataclass(frozen=True)
class VerifierGateVerdict:
    decision: VerifierGateDecision
    reason: str
    action_type: ActionType
    timeout_seconds: float | None = None

    @property
    def allowed(self) -> bool:
        return self.decision == VerifierGateDecision.ALLOW


@dataclass(frozen=True)
class VerifierRegistry:
    specs: Mapping[ActionType, VerifierSpec] = field(default_factory=dict)
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
            )
        if spec.timeout_seconds <= 0:
            return VerifierGateVerdict(
                decision=VerifierGateDecision.BLOCK,
                reason="verifier timeout must be positive",
                action_type=action_type,
                timeout_seconds=spec.timeout_seconds,
            )

        return VerifierGateVerdict(
            decision=VerifierGateDecision.ALLOW,
            reason="verifier spec is available",
            action_type=action_type,
            timeout_seconds=spec.timeout_seconds,
        )
