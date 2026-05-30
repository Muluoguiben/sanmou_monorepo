from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction


LOW_RISK_AUTOMATION_ACTIONS = frozenset(
    {
        ActionType.CLAIM_CHAPTER_REWARD,
        ActionType.RECRUIT_SOLDIERS,
        ActionType.UPGRADE_BUILDING,
    }
)

HIGH_RISK_AUTOMATION_ACTIONS = frozenset(
    {
        ActionType.ATTACK_LAND,
        ActionType.ABANDON_LAND,
        ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM,
    }
)


class ArchitectureGateDecision(str, Enum):
    ALLOW = "allow"
    SKIP = "skip"
    BLOCK = "block"


class AutomationMode(str, Enum):
    ADVISOR = "advisor"
    SEMI_AUTO = "semi_auto"
    FULL_AUTO = "full_auto"


@dataclass(frozen=True)
class ArchitectureGateVerdict:
    decision: ArchitectureGateDecision
    reason: str
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.decision == ArchitectureGateDecision.ALLOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class LLMJudgeGate:
    """Runtime policy for the experimental LLM-as-Judge rerank hook.

    The judge is intentionally inert by default. It may only run when explicitly
    enabled, the committed golden replay baseline is considered ready, and the
    top two rule scores are close enough that reranking is useful.
    """

    enabled: bool = False
    golden_replay_baseline_ready: bool = False
    top_score_gap_threshold: float = 5.0

    def evaluate(
        self,
        ranked_actions: Sequence[CandidateAction],
        *,
        top_score_gap: float | None = None,
    ) -> ArchitectureGateVerdict:
        if not self.enabled:
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.SKIP,
                "llm_as_judge_disabled",
                {"enabled": False},
            )
        if not self.golden_replay_baseline_ready:
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.BLOCK,
                "golden replay baseline is required before enabling LLM-as-Judge",
                {"enabled": True, "golden_replay_baseline_ready": False},
            )
        if len(ranked_actions) < 2:
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.SKIP,
                "less than two ranked actions",
                {"ranked_action_count": len(ranked_actions)},
            )

        gap = (
            float(top_score_gap)
            if top_score_gap is not None
            else round(ranked_actions[0].score_total - ranked_actions[1].score_total, 2)
        )
        if gap > self.top_score_gap_threshold:
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.SKIP,
                "top score gap is too large for experimental rerank",
                {"top_score_gap": gap, "threshold": self.top_score_gap_threshold},
            )
        return ArchitectureGateVerdict(
            ArchitectureGateDecision.ALLOW,
            "top scores are close and golden replay baseline is ready",
            {"top_score_gap": gap, "threshold": self.top_score_gap_threshold},
        )


def validate_explainer_boundary(
    action: CandidateAction,
    *,
    draft_action_type: ActionType | str | None = None,
    draft_params: Mapping[str, Any] | None = None,
    base_safety_verdict: str | None = None,
    draft_safety_verdict: str | None = None,
    draft_risk: Mapping[str, Any] | None = None,
) -> ArchitectureGateVerdict:
    """Ensure an ExplainerLLM draft can only add narrative text.

    Future LLM explanation output may echo action metadata for grounding, but it
    must not mutate the selected action, params, risk, or safety verdict.
    """

    if draft_action_type is not None and _normalize_action_type(draft_action_type) != action.action_type.value:
        return ArchitectureGateVerdict(
            ArchitectureGateDecision.BLOCK,
            "explainer draft attempted to change action_type",
            {
                "base_action_type": action.action_type.value,
                "draft_action_type": _normalize_action_type(draft_action_type),
            },
        )
    if draft_params is not None and dict(draft_params) != dict(action.params):
        return ArchitectureGateVerdict(
            ArchitectureGateDecision.BLOCK,
            "explainer draft attempted to change action params",
            {"action_type": action.action_type.value},
        )
    if draft_risk is not None and dict(draft_risk) != dict(action.risk):
        return ArchitectureGateVerdict(
            ArchitectureGateDecision.BLOCK,
            "explainer draft attempted to change risk verdict",
            {"action_type": action.action_type.value},
        )
    if draft_safety_verdict is not None and draft_safety_verdict != base_safety_verdict:
        return ArchitectureGateVerdict(
            ArchitectureGateDecision.BLOCK,
            "explainer draft attempted to change safety verdict",
            {
                "base_safety_verdict": base_safety_verdict,
                "draft_safety_verdict": draft_safety_verdict,
            },
        )
    return ArchitectureGateVerdict(
        ArchitectureGateDecision.ALLOW,
        "explainer draft preserves action, params, risk, and safety verdict",
        {"action_type": action.action_type.value},
    )


@dataclass(frozen=True)
class AutomationReadiness:
    golden_replay_baseline_ready: bool = True
    low_risk_verifier_false_positive_covered: bool = True
    map_land_verifier_ready: bool = False
    battle_result_verifier_ready: bool = False
    team_state_verifier_ready: bool = False

    @property
    def high_risk_verifier_ready(self) -> bool:
        return (
            self.map_land_verifier_ready
            and self.battle_result_verifier_ready
            and self.team_state_verifier_ready
        )


@dataclass(frozen=True)
class AutomationReadinessGate:
    readiness: AutomationReadiness = field(default_factory=AutomationReadiness)

    def evaluate(
        self,
        action_type: ActionType | str,
        *,
        mode: AutomationMode | str,
        human_confirmed: bool = False,
    ) -> ArchitectureGateVerdict:
        normalized_action = _to_action_type(action_type)
        normalized_mode = _to_automation_mode(mode)

        if normalized_mode == AutomationMode.ADVISOR:
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.ALLOW,
                "advisor mode does not dispatch UI automation",
                {"mode": normalized_mode.value, "action_type": normalized_action.value},
            )

        if normalized_action in LOW_RISK_AUTOMATION_ACTIONS:
            if not self.readiness.low_risk_verifier_false_positive_covered:
                return ArchitectureGateVerdict(
                    ArchitectureGateDecision.BLOCK,
                    "low-risk verifier false positive coverage is required before semi-auto",
                    {"action_type": normalized_action.value, "mode": normalized_mode.value},
                )
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.ALLOW,
                "low-risk action has verifier false positive coverage",
                {"action_type": normalized_action.value, "mode": normalized_mode.value},
            )

        if normalized_action in HIGH_RISK_AUTOMATION_ACTIONS:
            if normalized_mode == AutomationMode.SEMI_AUTO and human_confirmed:
                return ArchitectureGateVerdict(
                    ArchitectureGateDecision.ALLOW,
                    "high-risk action is manually confirmed, not full-auto",
                    {"action_type": normalized_action.value, "mode": normalized_mode.value},
                )
            if not self.readiness.high_risk_verifier_ready:
                return ArchitectureGateVerdict(
                    ArchitectureGateDecision.BLOCK,
                    "map, battle-result, and team-state verifiers are required before high-risk full-auto",
                    {
                        "action_type": normalized_action.value,
                        "mode": normalized_mode.value,
                        "map_land_verifier_ready": self.readiness.map_land_verifier_ready,
                        "battle_result_verifier_ready": self.readiness.battle_result_verifier_ready,
                        "team_state_verifier_ready": self.readiness.team_state_verifier_ready,
                    },
                )
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.ALLOW,
                "high-risk full-auto verifier prerequisites are ready",
                {"action_type": normalized_action.value, "mode": normalized_mode.value},
            )

        return ArchitectureGateVerdict(
            ArchitectureGateDecision.ALLOW,
            "action is outside automation stop-condition gates",
            {"action_type": normalized_action.value, "mode": normalized_mode.value},
        )


def _normalize_action_type(value: ActionType | str) -> str:
    return value.value if isinstance(value, ActionType) else str(value)


def _to_action_type(value: ActionType | str) -> ActionType:
    return value if isinstance(value, ActionType) else ActionType(str(value))


def _to_automation_mode(value: AutomationMode | str) -> AutomationMode:
    return value if isinstance(value, AutomationMode) else AutomationMode(str(value))
