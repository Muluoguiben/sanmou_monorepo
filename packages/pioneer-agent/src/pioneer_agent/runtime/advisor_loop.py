from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from pioneer_agent.adapters.capture import CaptureAdapter, CaptureFrame
from pioneer_agent.core.device import AccountSession, DeviceSession
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState, SelectionResult
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.perception.screenshot_interpreter import ScreenshotInterpretation
from pioneer_agent.perception.vision_sync import VisionSync, VisionSyncSummary
from pioneer_agent.selector.action_selector import ActionSelector


class ActionRecommendation(BaseModel):
    action_id: str
    action_type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    risk: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    executable: bool = False
    execution_blocked_reason: str = "advisor_mode"


class AdvisorReport(BaseModel):
    mode: str = "advisor"
    captured_at: datetime
    device_session: DeviceSession
    account_session: AccountSession | None = None
    current_state: RuntimeState
    current_state_summary: dict[str, Any] = Field(default_factory=dict)
    available_actions: list[ActionRecommendation] = Field(default_factory=list)
    recommended_action: ActionRecommendation | None = None
    risks: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    screenshot_interpretation: ScreenshotInterpretation | None = None
    vision_summary: dict[str, Any] = Field(default_factory=dict)
    selection_reason: dict[str, Any] = Field(default_factory=dict)


class AdvisorLoop:
    """Observe -> perceive -> derive -> select -> recommend, with no UI input path."""

    def __init__(
        self,
        capture: CaptureAdapter,
        vision_sync: VisionSync,
        *,
        selector: ActionSelector | None = None,
        deriver: StateDeriver | None = None,
        account_session: AccountSession | None = None,
    ) -> None:
        self.capture = capture
        self.vision_sync = vision_sync
        self.selector = selector or ActionSelector()
        self.deriver = deriver or StateDeriver()
        self.account_session = account_session
        self.state = RuntimeState()

    def tick(self) -> AdvisorReport:
        frame = self.capture.capture()
        self.state, vision_summary = self.vision_sync.sync(
            frame.png,
            state=self.state,
            captured_at=frame.captured_at,
        )
        derived = self.deriver.derive(self.state)
        selection = self.selector.select(derived)
        return build_advisor_report(
            frame=frame,
            state=derived,
            selection=selection,
            vision_summary=vision_summary,
            account_session=self.account_session,
        )


def build_advisor_report(
    *,
    frame: CaptureFrame,
    state: RuntimeState,
    selection: SelectionResult,
    vision_summary: VisionSyncSummary,
    account_session: AccountSession | None = None,
    screenshot_interpretation: ScreenshotInterpretation | None = None,
) -> AdvisorReport:
    available = [
        _recommendation_from_candidate(state, candidate)
        for candidate in selection.ranked_actions
    ]
    recommended = (
        _recommendation_from_candidate(state, selection.selected_action)
        if selection.selected_action is not None
        else None
    )
    risks = [item.risk for item in available if item.risk]
    evidence = _collect_evidence(selection, vision_summary, recommended, screenshot_interpretation)
    confidence_values = [item.confidence for item in available]
    if screenshot_interpretation is not None:
        confidence_values.append(screenshot_interpretation.confidence)
    confidence = min(confidence_values, default=1.0)
    return AdvisorReport(
        captured_at=frame.captured_at,
        device_session=frame.device_session,
        account_session=account_session,
        current_state=state,
        current_state_summary=_state_summary(state, vision_summary, screenshot_interpretation),
        available_actions=available,
        recommended_action=recommended,
        risks=risks,
        evidence=evidence,
        confidence=confidence,
        screenshot_interpretation=screenshot_interpretation,
        vision_summary={
            "page_type": vision_summary.page_type,
            "domains_run": list(vision_summary.domains_run),
            "notes": list(vision_summary.notes),
            "interpretation": screenshot_interpretation.model_dump(mode="json")
            if screenshot_interpretation is not None
            else None,
        },
        selection_reason=selection.selection_reason,
    )


def _recommendation_from_candidate(
    state: RuntimeState,
    candidate: CandidateAction,
) -> ActionRecommendation:
    return ActionRecommendation(
        action_id=candidate.action_id,
        action_type=candidate.action_type,
        params=dict(candidate.params),
        score=candidate.score_total,
        risk=dict(candidate.risk),
        evidence=list(candidate.source_state_refs),
        confidence=_confidence_for_candidate(state, candidate),
        executable=False,
        execution_blocked_reason="advisor_mode",
    )


def _confidence_for_candidate(state: RuntimeState, candidate: CandidateAction) -> float:
    confidences: list[float] = []
    for ref in candidate.source_state_refs:
        meta = state.field_meta.get(ref)
        if meta is not None:
            confidences.append(meta.confidence)
    return min(confidences) if confidences else 1.0


def _collect_evidence(
    selection: SelectionResult,
    vision_summary: VisionSyncSummary,
    recommended: ActionRecommendation | None,
    screenshot_interpretation: ScreenshotInterpretation | None,
) -> list[str]:
    evidence: list[str] = []
    evidence.extend(f"vision.domain:{domain}" for domain in vision_summary.domains_run)
    if vision_summary.page_type:
        evidence.append(f"vision.page_type:{vision_summary.page_type}")
    if screenshot_interpretation is not None:
        evidence.append("vision.interpretation")
    if recommended is not None:
        evidence.extend(recommended.evidence)
    triggered_rules = selection.selection_reason.get("triggered_rules", [])
    evidence.extend(f"selector.rule:{rule}" for rule in triggered_rules)
    return evidence


def _state_summary(
    state: RuntimeState,
    vision_summary: VisionSyncSummary,
    screenshot_interpretation: ScreenshotInterpretation | None,
) -> dict[str, Any]:
    summary = {
        "page_type": vision_summary.page_type,
        "phase_tag": state.global_state.get("phase_tag"),
        "current_chapter_id": state.progress.get("current_chapter_id"),
        "chapter_claimable": state.progress.get("chapter_claimable"),
        "resources": state.economy.get("resources"),
        "main_team_id": state.main_lineup.get("current_host_team_id"),
        "candidate_land_count": len(state.map_state.get("candidate_lands", [])),
        "upgradeable_building_count": len(state.city.get("upgradeable_buildings", [])),
        "team_count": len(state.teams),
        "team_readiness": state.main_lineup.get("team_readiness"),
        "team_snapshot": state.main_lineup.get("team_snapshot"),
    }
    if screenshot_interpretation is not None:
        summary.update(
            {
                "interpreted_page_type": screenshot_interpretation.page_type,
                "interpretation_summary": screenshot_interpretation.summary,
            }
        )
    return summary
