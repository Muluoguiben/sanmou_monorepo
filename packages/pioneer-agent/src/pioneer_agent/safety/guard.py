from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from pioneer_agent.core.device import CapabilityFlags
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.risk import RiskLevel, normalize_risk_level, risk_at_least


class GuardDecision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_CONFIRMATION = "require_confirmation"


class SessionMode(str, Enum):
    OBSERVE_ONLY = "observe_only"
    ADVISOR = "advisor"
    AUTOMATION_TEST = "automation_test"
    LIVE = "live"


@dataclass(frozen=True)
class GuardVerdict:
    decision: GuardDecision
    reason: str
    action_type: str
    risk_level: RiskLevel

    @property
    def allowed(self) -> bool:
        return self.decision == GuardDecision.ALLOW


DEFAULT_INPUT_ALLOWLIST = frozenset(
    {
        ActionType.CLAIM_CHAPTER_REWARD.value,
        ActionType.UPGRADE_BUILDING.value,
        ActionType.RECRUIT_SOLDIERS.value,
        ActionType.WAIT_FOR_RESOURCE.value,
        ActionType.WAIT_FOR_STAMINA.value,
        ActionType.INSPECT_TEAM_READINESS.value,
    }
)

DEFAULT_CONFIRMATION_ACTIONS = frozenset(
    {
        ActionType.ATTACK_LAND.value,
        ActionType.ABANDON_LAND.value,
        ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM.value,
    }
)


@dataclass(frozen=True)
class SafetyGuard:
    input_allowlist: frozenset[str] = field(default_factory=lambda: DEFAULT_INPUT_ALLOWLIST)
    confirmation_actions: frozenset[str] = field(
        default_factory=lambda: DEFAULT_CONFIRMATION_ACTIONS
    )
    confirmation_threshold: RiskLevel = RiskLevel.HIGH

    def __init__(
        self,
        *,
        input_allowlist: Iterable[ActionType | str] | None = None,
        confirmation_actions: Iterable[ActionType | str] | None = None,
        confirmation_threshold: RiskLevel = RiskLevel.HIGH,
    ) -> None:
        object.__setattr__(
            self,
            "input_allowlist",
            _normalize_action_set(input_allowlist, DEFAULT_INPUT_ALLOWLIST),
        )
        object.__setattr__(
            self,
            "confirmation_actions",
            _normalize_action_set(confirmation_actions, DEFAULT_CONFIRMATION_ACTIONS),
        )
        object.__setattr__(self, "confirmation_threshold", confirmation_threshold)

    def evaluate(
        self,
        action_type: ActionType | str,
        *,
        risk: RiskLevel | str | Mapping[str, Any] | None = None,
        capabilities: CapabilityFlags | None = None,
        session_mode: SessionMode | str | None = None,
    ) -> GuardVerdict:
        normalized_action = _normalize_action_type(action_type)
        risk_level = normalize_risk_level(risk)
        normalized_session_mode = _normalize_session_mode(session_mode)

        if normalized_session_mode in (SessionMode.OBSERVE_ONLY, SessionMode.ADVISOR):
            return GuardVerdict(
                decision=GuardDecision.BLOCK,
                reason=f"session mode {normalized_session_mode.value} does not allow UI execution",
                action_type=normalized_action,
                risk_level=risk_level,
            )

        if capabilities is not None and not capabilities.can_execute_input:
            return GuardVerdict(
                decision=GuardDecision.BLOCK,
                reason="input_control capability required for UI execution",
                action_type=normalized_action,
                risk_level=risk_level,
            )

        if normalized_action not in self.input_allowlist:
            if normalized_action in self.confirmation_actions:
                return GuardVerdict(
                    decision=GuardDecision.REQUIRE_CONFIRMATION,
                    reason="sensitive action requires human confirmation",
                    action_type=normalized_action,
                    risk_level=risk_level,
                )
            return GuardVerdict(
                decision=GuardDecision.BLOCK,
                reason="action is not in the computer-use input allowlist",
                action_type=normalized_action,
                risk_level=risk_level,
            )

        if normalized_action in self.confirmation_actions or risk_at_least(
            risk_level, self.confirmation_threshold
        ):
            return GuardVerdict(
                decision=GuardDecision.REQUIRE_CONFIRMATION,
                reason="risk policy requires human confirmation",
                action_type=normalized_action,
                risk_level=risk_level,
            )

        return GuardVerdict(
            decision=GuardDecision.ALLOW,
            reason="action is allowed by safety policy",
            action_type=normalized_action,
            risk_level=risk_level,
        )


def _normalize_action_type(action_type: ActionType | str) -> str:
    if isinstance(action_type, ActionType):
        return action_type.value
    return action_type


def _normalize_session_mode(session_mode: SessionMode | str | None) -> SessionMode | None:
    if session_mode is None:
        return None
    if isinstance(session_mode, SessionMode):
        return session_mode
    return SessionMode(session_mode)


def _normalize_action_set(
    values: Iterable[ActionType | str] | None,
    default: frozenset[str],
) -> frozenset[str]:
    if values is None:
        return default
    return frozenset(_normalize_action_type(value) for value in values)
