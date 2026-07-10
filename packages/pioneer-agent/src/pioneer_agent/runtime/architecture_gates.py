from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
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
    EVIDENCE_CAPTURE = "evidence_capture"


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


def validate_low_risk_semantic_target(action: CandidateAction) -> ArchitectureGateVerdict:
    """Require a calibrated semantic bbox before low-risk UI automation dispatch."""

    if action.action_type not in LOW_RISK_AUTOMATION_ACTIONS:
        return ArchitectureGateVerdict(
            ArchitectureGateDecision.SKIP,
            "action is outside low-risk semantic target gate",
            {"action_type": action.action_type.value},
        )

    targets = _low_risk_semantic_targets(action)
    for target_name, target in targets:
        if _has_visible_enabled_bbox(target):
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.ALLOW,
                "low-risk action has a visible enabled semantic bbox target",
                {"action_type": action.action_type.value, "target": target_name},
            )

    return ArchitectureGateVerdict(
        ArchitectureGateDecision.BLOCK,
        "low-risk UI action requires a visible enabled semantic bbox target before dispatch",
        {
            "action_type": action.action_type.value,
            "checked_targets": [name for name, _target in targets],
        },
    )


def _low_risk_semantic_targets(action: CandidateAction) -> list[tuple[str, Any]]:
    params = action.params
    if action.action_type == ActionType.CLAIM_CHAPTER_REWARD:
        return [("claim_button", params.get("claim_button"))]
    if action.action_type == ActionType.RECRUIT_SOLDIERS:
        return [("recruit_button", params.get("recruit_button"))]
    if action.action_type == ActionType.UPGRADE_BUILDING:
        dialog = params.get("upgrade_dialog")
        confirm_button = dialog.get("confirm_button") if isinstance(dialog, Mapping) else None
        return [
            ("upgrade_button", params.get("upgrade_button")),
            ("upgrade_dialog.confirm_button", confirm_button),
        ]
    return []


def _has_visible_enabled_bbox(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    if value.get("visible") is not True or value.get("enabled") is not True:
        return False
    bbox = value.get("bbox")
    if not isinstance(bbox, Mapping):
        return False
    required = ("x_min", "y_min", "x_max", "y_max")
    if not all(_is_finite_number(bbox.get(key)) for key in required):
        return False
    x_min, y_min, x_max, y_max = (bbox[key] for key in required)
    return 0 <= x_min < x_max <= 1000 and 0 <= y_min < y_max <= 1000


def _is_finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


@dataclass(frozen=True)
class AutomationReadiness:
    golden_replay_baseline_ready: bool = False
    low_risk_verifier_false_positive_covered: bool = False
    map_land_verifier_ready: bool = False
    battle_result_verifier_ready: bool = False
    team_state_verifier_ready: bool = False
    closure_gate_ready: bool = False
    accepted_actions: frozenset[ActionType | str] = field(default_factory=frozenset)

    @property
    def high_risk_verifier_ready(self) -> bool:
        return (
            self.map_land_verifier_ready
            and self.battle_result_verifier_ready
            and self.team_state_verifier_ready
        )

    @property
    def accepted_action_values(self) -> frozenset[str]:
        return frozenset(_normalize_action_type(item) for item in self.accepted_actions)


@dataclass(frozen=True)
class AutomationReadinessGate:
    readiness: AutomationReadiness = field(default_factory=AutomationReadiness)
    evidence_capture_action: ActionType | str | None = None
    evidence_capture_confirmed: bool = False

    @classmethod
    def for_evidence_capture(
        cls,
        action_type: ActionType | str,
        *,
        human_confirmed: bool,
    ) -> "AutomationReadinessGate":
        normalized = _to_action_type(action_type)
        if normalized not in LOW_RISK_AUTOMATION_ACTIONS:
            raise ValueError("evidence capture is limited to low-risk actions")
        return cls(
            evidence_capture_action=normalized,
            evidence_capture_confirmed=human_confirmed,
        )

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
                ArchitectureGateDecision.BLOCK,
                "advisor mode must never authorize UI automation",
                {"mode": normalized_mode.value, "action_type": normalized_action.value},
            )

        if normalized_mode == AutomationMode.EVIDENCE_CAPTURE:
            return self._evaluate_evidence_capture(
                normalized_action,
                human_confirmed=human_confirmed,
            )

        input_action = (
            normalized_action in LOW_RISK_AUTOMATION_ACTIONS
            or normalized_action in HIGH_RISK_AUTOMATION_ACTIONS
        )
        if not input_action:
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.ALLOW,
                "action is outside UI automation readiness gates",
                {"mode": normalized_mode.value, "action_type": normalized_action.value},
            )

        if not self.readiness.closure_gate_ready:
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.BLOCK,
                "a ready committed closure artifact is required for UI automation",
                {"mode": normalized_mode.value, "action_type": normalized_action.value},
            )

        if normalized_action.value not in self.readiness.accepted_action_values:
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.BLOCK,
                "action is not accepted by the committed closure artifact",
                {
                    "mode": normalized_mode.value,
                    "action_type": normalized_action.value,
                    "accepted_actions": sorted(self.readiness.accepted_action_values),
                },
            )

        if normalized_action in LOW_RISK_AUTOMATION_ACTIONS:
            missing = []
            if not self.readiness.golden_replay_baseline_ready:
                missing.append("golden_replay_baseline_ready")
            if not self.readiness.low_risk_verifier_false_positive_covered:
                missing.append("low_risk_verifier_false_positive_covered")
            if missing:
                return ArchitectureGateVerdict(
                    ArchitectureGateDecision.BLOCK,
                    "low-risk closure prerequisites are not ready",
                    {
                        "action_type": normalized_action.value,
                        "mode": normalized_mode.value,
                        "missing": missing,
                    },
                )
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.ALLOW,
                "low-risk action is accepted by a ready committed closure artifact",
                {"action_type": normalized_action.value, "mode": normalized_mode.value},
            )

        if normalized_action in HIGH_RISK_AUTOMATION_ACTIONS:
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
            if normalized_mode == AutomationMode.SEMI_AUTO and not human_confirmed:
                return ArchitectureGateVerdict(
                    ArchitectureGateDecision.BLOCK,
                    "high-risk semi-auto action requires human confirmation",
                    {"action_type": normalized_action.value, "mode": normalized_mode.value},
                )
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.ALLOW,
                "high-risk action is accepted and all verifier prerequisites are ready",
                {"action_type": normalized_action.value, "mode": normalized_mode.value},
            )

        raise AssertionError("unreachable automation action branch")

    def _evaluate_evidence_capture(
        self,
        action_type: ActionType,
        *,
        human_confirmed: bool,
    ) -> ArchitectureGateVerdict:
        if action_type not in LOW_RISK_AUTOMATION_ACTIONS:
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.BLOCK,
                "evidence-capture mode is limited to low-risk actions",
                {"mode": AutomationMode.EVIDENCE_CAPTURE.value, "action_type": action_type.value},
            )
        expected = (
            _to_action_type(self.evidence_capture_action)
            if self.evidence_capture_action is not None
            else None
        )
        if expected != action_type:
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.BLOCK,
                "action does not match the explicitly confirmed evidence-capture action",
                {
                    "mode": AutomationMode.EVIDENCE_CAPTURE.value,
                    "action_type": action_type.value,
                    "confirmed_action": expected.value if expected is not None else None,
                },
            )
        if not (self.evidence_capture_confirmed or human_confirmed):
            return ArchitectureGateVerdict(
                ArchitectureGateDecision.BLOCK,
                "evidence-capture action requires explicit human confirmation",
                {"mode": AutomationMode.EVIDENCE_CAPTURE.value, "action_type": action_type.value},
            )
        return ArchitectureGateVerdict(
            ArchitectureGateDecision.ALLOW,
            "single-action low-risk evidence capture was explicitly confirmed",
            {"mode": AutomationMode.EVIDENCE_CAPTURE.value, "action_type": action_type.value},
        )


def _normalize_action_type(value: ActionType | str) -> str:
    return value.value if isinstance(value, ActionType) else str(value)


def _to_action_type(value: ActionType | str) -> ActionType:
    return value if isinstance(value, ActionType) else ActionType(str(value))


def _to_automation_mode(value: AutomationMode | str) -> AutomationMode:
    return value if isinstance(value, AutomationMode) else AutomationMode(str(value))
