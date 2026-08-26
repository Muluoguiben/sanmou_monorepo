from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field

from pioneer_agent.adapters.capture import CaptureAdapter, CaptureFrame
from pioneer_agent.core.device import AccountSession, DeviceSession
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import (
    CandidateAction,
    ObservationSnapshot,
    RuntimeState,
    SelectionResult,
)
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.knowledge.strategy_snapshot import load_default_strategy_snapshot
from pioneer_agent.perception.screenshot_interpreter import ScreenshotInterpretation
from pioneer_agent.perception.vision_sync import VisionSync, VisionSyncSummary
from pioneer_agent.runtime.evidence import (
    AdvisorEvidence,
    EvidenceValidationError,
    selector_rule_evidence,
    state_evidence,
    strategy_snapshot_evidence,
    validate_evidence_entry_ids,
    vision_evidence,
)
from pioneer_agent.selector.action_selector import ActionSelector


class ActionRecommendation(BaseModel):
    action_id: str
    action_type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0
    risk: dict[str, Any] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    structured_evidence: list[AdvisorEvidence] = Field(default_factory=list)
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
    structured_evidence: list[AdvisorEvidence] = Field(default_factory=list)
    confidence: float = 1.0
    screenshot_interpretation: ScreenshotInterpretation | None = None
    vision_summary: dict[str, Any] = Field(default_factory=dict)
    selection_reason: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class AdvisorObservationCycle:
    """One atomic observe/perceive/derive/select Advisor result."""

    observation: ObservationSnapshot
    report: AdvisorReport


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
        report, _summary = self._run_tick()
        return report

    def observe(self) -> AdvisorObservationCycle:
        """Run one fresh Advisor cycle and retain its observation binding."""

        report, summary = self._run_tick()
        if summary.observation is None:
            raise ValueError("VisionSync did not return an ObservationSnapshot")
        return AdvisorObservationCycle(observation=summary.observation, report=report)

    def _run_tick(self) -> tuple[AdvisorReport, VisionSyncSummary]:
        frame = self.capture.capture()
        self.state, vision_summary = self.vision_sync.sync(
            frame.png,
            state=self.state,
            captured_at=frame.captured_at,
            capture_geometry=frame.capture_geometry,
        )
        derived = self.deriver.derive(self.state)
        selection = self.selector.select(derived)
        report = build_advisor_report(
            frame=frame,
            state=derived,
            selection=selection,
            vision_summary=vision_summary,
            account_session=self.account_session,
        )
        return report, vision_summary


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
    structured_evidence = _collect_structured_evidence(
        selection,
        vision_summary,
        recommended,
        screenshot_interpretation,
    )
    evidence = _legacy_evidence(structured_evidence)
    confidence_values = [item.confidence for item in available]
    if screenshot_interpretation is not None:
        confidence_values.append(screenshot_interpretation.confidence)
    if vision_summary.unknown_domains:
        confidence_values.append(0.0)
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
        structured_evidence=structured_evidence,
        confidence=confidence,
        screenshot_interpretation=screenshot_interpretation,
        vision_summary={
            "page_type": vision_summary.page_type,
            "domains_run": list(vision_summary.domains_run),
            "unknown_domains": list(vision_summary.unknown_domains),
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
    structured_evidence = _candidate_structured_evidence(state, candidate)
    return ActionRecommendation(
        action_id=candidate.action_id,
        action_type=candidate.action_type,
        params=dict(candidate.params),
        score=candidate.score_total,
        risk=dict(candidate.risk),
        evidence=_legacy_evidence(structured_evidence),
        structured_evidence=structured_evidence,
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


def _candidate_structured_evidence(state: RuntimeState, candidate: CandidateAction) -> list[AdvisorEvidence]:
    evidence: list[AdvisorEvidence] = []
    for ref in candidate.source_state_refs:
        meta = state.field_meta.get(ref)
        evidence.append(
            state_evidence(
                ref,
                confidence=meta.confidence if meta is not None else None,
                source=meta.source if meta is not None else None,
            )
        )
    evidence.extend(_strategy_evidence_from_params(candidate.params))
    return evidence


def _strategy_evidence_from_params(params: dict[str, Any]) -> list[AdvisorEvidence]:
    strategy_key = _optional_string(params.get("strategy_key"))
    entry_ids = _string_list(params.get("strategy_entry_ids"))
    if strategy_key and not entry_ids:
        raise EvidenceValidationError("strategy_key requires strategy_entry_ids evidence")
    if not entry_ids:
        return []

    topic = _optional_string(params.get("strategy_topic")) or _optional_string(params.get("building_name"))
    summary = _optional_string(params.get("strategy_rationale")) or ""
    source_ref = _optional_string(params.get("strategy_source_ref"))
    evidence = [
        strategy_snapshot_evidence(
            entry_id=entry_id,
            topic=topic,
            domain="building",
            summary=summary,
            source_ref=source_ref,
            strategy_key=strategy_key,
        )
        for entry_id in entry_ids
    ]
    validate_evidence_entry_ids(
        evidence,
        allowed_entry_ids=(*_default_strategy_entry_ids(), *_string_list(params.get("qa_entry_ids"))),
    )
    return evidence


def _collect_structured_evidence(
    selection: SelectionResult,
    vision_summary: VisionSyncSummary,
    recommended: ActionRecommendation | None,
    screenshot_interpretation: ScreenshotInterpretation | None,
) -> list[AdvisorEvidence]:
    evidence: list[AdvisorEvidence] = []
    evidence.extend(
        vision_evidence(
            f"vision.domain:{domain}",
            summary="vision extraction domain completed",
        )
        for domain in vision_summary.domains_run
    )
    evidence.extend(
        vision_evidence(
            f"vision.domain_unknown:{domain}",
            summary="vision extraction was attempted but returned no trusted observation",
            confidence=0.0,
            metadata={
                "domain": domain,
                "status": "unknown",
                "trusted_for_state": False,
            },
        )
        for domain in vision_summary.unknown_domains
    )
    if vision_summary.page_type:
        evidence.append(
            vision_evidence(
                f"vision.page_type:{vision_summary.page_type}",
                summary="vision page classification",
            )
        )
    if screenshot_interpretation is not None:
        evidence.append(vision_evidence("vision.interpretation", summary=screenshot_interpretation.summary))
    if recommended is not None:
        evidence.extend(recommended.structured_evidence)
    triggered_rules = selection.selection_reason.get("triggered_rules", [])
    evidence.extend(selector_rule_evidence(str(rule)) for rule in triggered_rules)
    return evidence


def _legacy_evidence(evidence: list[AdvisorEvidence]) -> list[str]:
    return [item.to_legacy_string() for item in evidence]


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    return [str(value)]


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@lru_cache(maxsize=1)
def _default_strategy_entry_ids() -> frozenset[str]:
    snapshot = load_default_strategy_snapshot()
    if snapshot is None:
        return frozenset()
    return frozenset(snapshot.entry_ids())


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
