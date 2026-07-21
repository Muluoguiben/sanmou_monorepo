"""Reviewer-attributed annotations bound to immutable Record & Replay evidence.

Annotations are deliberately separate from the raw manifest and M0 candidates.
They can describe reviewed semantics, but they never grant execution authority,
prove causality, or satisfy a live runtime verifier.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from pioneer_agent.record_replay.models import InputEventRecord
from pioneer_agent.record_replay.session_store import (
    LoadedRecording,
    load_recording,
    revalidate_loaded_recording,
)
from pioneer_agent.record_replay.validation import (
    read_bounded_regular_file,
    validate_annotation_text,
    validate_canonical_uuid,
    validate_identifier,
    validate_reviewer_id,
    validate_unique_strings,
    validate_workflow_name,
)


ANNOTATION_SCHEMA_VERSION = 1
MAX_ANNOTATION_BYTES = 1_048_576
SHA256_PATTERN = r"^[0-9a-f]{64}$"
PLACEHOLDER_IDENTIFIERS = frozenset(
    {
        "na",
        "not-applicable",
        "not-reviewed",
        "unknown",
        "unreviewed",
        "unset",
        "unspecified",
    }
)


class AnnotationReviewStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PrivacyReviewScope(str, Enum):
    FULL_RAW_SESSION = "full_raw_session"
    FULL_RAW_SESSION_AND_ANNOTATION = "full_raw_session_and_annotation"


class SampleLabel(str, Enum):
    POSITIVE = "positive"
    NO_CHANGE = "no_change"
    MISSING_TARGET = "missing_target"
    AMBIGUOUS_TARGET = "ambiguous_target"
    POPUP_INTERRUPTION = "popup_interruption"
    TIMEOUT = "timeout"
    OPERATOR_CANCELLED = "operator_cancelled"
    OBSERVATION_ONLY = "observation_only"


class RiskClass(str, Enum):
    READ_ONLY = "read_only"
    LOW_RISK_MUTATION = "low_risk_mutation"
    HIGH_RISK_TRACE_ONLY = "high_risk_trace_only"


class EvidenceUse(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    TRACE_ONLY = "trace_only"
    EXCLUDED = "excluded"


class TransitionOutcome(str, Enum):
    APPLIED = "applied"
    NO_CHANGE = "no_change"
    AMBIGUOUS = "ambiguous"
    INTERRUPTED = "interrupted"
    PANEL_OPENED = "panel_opened"
    SELECTION_CHANGED = "selection_changed"
    UNKNOWN = "unknown"


COUNTABLE_TRANSITION_OUTCOME_BY_SAMPLE_LABEL: Mapping[
    SampleLabel, TransitionOutcome
] = MappingProxyType(
    {
        SampleLabel.POSITIVE: TransitionOutcome.APPLIED,
        SampleLabel.NO_CHANGE: TransitionOutcome.NO_CHANGE,
        SampleLabel.TIMEOUT: TransitionOutcome.NO_CHANGE,
        SampleLabel.MISSING_TARGET: TransitionOutcome.AMBIGUOUS,
        SampleLabel.AMBIGUOUS_TARGET: TransitionOutcome.AMBIGUOUS,
        SampleLabel.POPUP_INTERRUPTION: TransitionOutcome.INTERRUPTED,
        SampleLabel.OPERATOR_CANCELLED: TransitionOutcome.INTERRUPTED,
    }
)


def expected_transition_outcome(
    sample_label: SampleLabel,
) -> TransitionOutcome | None:
    """Return the sole countable outcome for a reviewed sample label."""

    return COUNTABLE_TRANSITION_OUTCOME_BY_SAMPLE_LABEL.get(sample_label)


class SemanticTarget(BaseModel):
    """A coordinate-free target description supplied by a human reviewer."""

    model_config = ConfigDict(extra="forbid")

    page: str
    target_kind: str
    target_key: str
    visible_label: str | None = None
    disambiguators: list[str] = Field(default_factory=list, max_length=12)
    unique_in_frame: StrictBool

    @field_validator("page", "target_kind", "target_key")
    @classmethod
    def _identifier(cls, value: str, info: Any) -> str:
        return validate_identifier(value, field_name=info.field_name)

    @field_validator("visible_label")
    @classmethod
    def _visible_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_annotation_text(
            value, field_name="visible_label", max_length=120
        )

    @field_validator("disambiguators")
    @classmethod
    def _disambiguators(cls, values: list[str]) -> list[str]:
        checked = [
            validate_annotation_text(
                value, field_name="disambiguator", max_length=160
            )
            for value in values
        ]
        return validate_unique_strings(checked, field_name="disambiguators")


class SemanticReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReviewDecision = ReviewDecision.PENDING
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    notes: list[str] = Field(default_factory=list, max_length=40)

    @field_validator("reviewed_by")
    @classmethod
    def _reviewer(cls, value: str | None) -> str | None:
        return None if value is None else validate_reviewer_id(value)

    @field_validator("reviewed_at")
    @classmethod
    def _aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("semantic reviewed_at must include a timezone")
        return value

    @field_validator("notes")
    @classmethod
    def _notes(cls, values: list[str]) -> list[str]:
        return [
            validate_annotation_text(value, field_name="semantic note")
            for value in values
        ]

    @model_validator(mode="after")
    def _decision_has_attribution(self) -> SemanticReview:
        if self.status != ReviewDecision.PENDING and (
            self.reviewed_by is None or self.reviewed_at is None
        ):
            raise ValueError("final semantic review requires reviewer and time")
        return self


class PrivacyReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReviewDecision = ReviewDecision.PENDING
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    scope: PrivacyReviewScope = PrivacyReviewScope.FULL_RAW_SESSION
    manifest_reviewed: StrictBool = False
    events_reviewed: StrictBool = False
    reviewed_frame_ids: list[str] = Field(default_factory=list)
    account_identifiers_visible: StrictBool | None = None
    chat_visible: StrictBool | None = None
    player_or_alliance_names_visible: StrictBool | None = None
    payment_or_secret_visible: StrictBool | None = None
    precise_coordinates_visible: StrictBool | None = None
    unrelated_window_visible: StrictBool | None = None
    approved_for_local_derivation: StrictBool = False
    approved_for_eval_candidate: StrictBool = False
    raw_approved_for_repo_storage: StrictBool = False

    @field_validator("reviewed_by")
    @classmethod
    def _reviewer(cls, value: str | None) -> str | None:
        return None if value is None else validate_reviewer_id(value)

    @field_validator("reviewed_at")
    @classmethod
    def _aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("privacy reviewed_at must include a timezone")
        return value

    @field_validator("reviewed_frame_ids")
    @classmethod
    def _unique_frames(cls, values: list[str]) -> list[str]:
        checked = [
            validate_identifier(value, field_name="reviewed_frame_id", max_length=120)
            for value in values
        ]
        return validate_unique_strings(checked, field_name="reviewed_frame_ids")

    @model_validator(mode="after")
    def _approval_is_explicit(self) -> PrivacyReview:
        sensitive = (
            self.account_identifiers_visible,
            self.chat_visible,
            self.player_or_alliance_names_visible,
            self.payment_or_secret_visible,
            self.precise_coordinates_visible,
            self.unrelated_window_visible,
        )
        if self.status != ReviewDecision.PENDING and (
            self.reviewed_by is None or self.reviewed_at is None
        ):
            raise ValueError("final privacy review requires reviewer and time")
        if self.status != ReviewDecision.APPROVED and (
            self.approved_for_local_derivation or self.approved_for_eval_candidate
        ):
            raise ValueError("non-approved privacy review cannot authorize derivation")
        if self.raw_approved_for_repo_storage is not False:
            raise ValueError("raw session storage approval is permanently disabled")
        if self.status == ReviewDecision.APPROVED:
            if any(value is None for value in sensitive):
                raise ValueError(
                    "approved privacy review must explicitly assess every sensitive field"
                )
        if self.approved_for_eval_candidate and not self.approved_for_local_derivation:
            raise ValueError("eval candidate approval requires local derivation approval")
        if (
            self.approved_for_local_derivation or self.approved_for_eval_candidate
        ) and self.scope != PrivacyReviewScope.FULL_RAW_SESSION_AND_ANNOTATION:
            raise ValueError(
                "derivation approval requires privacy review of the full raw session "
                "and annotation text"
            )
        if (
            self.approved_for_local_derivation or self.approved_for_eval_candidate
        ) and (
            not self.manifest_reviewed
            or not self.events_reviewed
            or not self.reviewed_frame_ids
        ):
            raise ValueError(
                "derivation approval requires explicit manifest, events, and frame review"
            )
        if self.approved_for_eval_candidate:
            if any(value is not False for value in sensitive):
                raise ValueError(
                    "eval candidate approval requires every sensitive field to be false"
                )
        return self


class SegmentAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str
    source_event_ids: list[str] = Field(min_length=1)
    before_frame_id: str
    after_frame_id: str
    sample_label: SampleLabel
    risk_class: RiskClass
    page_before: str
    page_after: str
    proposed_action_name: str | None = None
    observation_schema_id: str | None = None
    before_observation_sha256: StrictStr | None = Field(
        default=None, pattern=SHA256_PATTERN
    )
    after_observation_sha256: StrictStr | None = Field(
        default=None, pattern=SHA256_PATTERN
    )
    semantic_target: SemanticTarget | None = None
    observed_preconditions: list[str] = Field(default_factory=list, max_length=40)
    expected_delta_claim: list[str] = Field(default_factory=list, max_length=40)
    observed_delta: list[str] = Field(default_factory=list, max_length=40)
    outcome: TransitionOutcome = TransitionOutcome.UNKNOWN
    evidence_use: EvidenceUse = EvidenceUse.EXCLUDED
    unresolved_assumptions: list[str] = Field(default_factory=list, max_length=40)
    verifier_status: Literal["unproven"] = "unproven"
    causal_verified: StrictBool = False

    @field_validator(
        "segment_id", "before_frame_id", "after_frame_id", "page_before", "page_after"
    )
    @classmethod
    def _identifier(cls, value: str, info: Any) -> str:
        return validate_identifier(value, field_name=info.field_name, max_length=120)

    @field_validator("source_event_ids")
    @classmethod
    def _event_ids(cls, values: list[str]) -> list[str]:
        checked = [
            validate_identifier(value, field_name="source_event_id", max_length=120)
            for value in values
        ]
        return validate_unique_strings(checked, field_name="source_event_ids")

    @field_validator("proposed_action_name", "observation_schema_id")
    @classmethod
    def _optional_identifier(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        return validate_identifier(value, field_name=info.field_name)

    @field_validator(
        "observed_preconditions",
        "expected_delta_claim",
        "observed_delta",
        "unresolved_assumptions",
    )
    @classmethod
    def _claims(cls, values: list[str], info: Any) -> list[str]:
        checked = [
            validate_annotation_text(value, field_name=info.field_name)
            for value in values
        ]
        return validate_unique_strings(checked, field_name=info.field_name)

    @model_validator(mode="after")
    def _evidence_contract(self) -> SegmentAnnotation:
        if self.causal_verified is not False:
            raise ValueError("annotation segments cannot claim causal verification")
        observation_binding = (
            self.observation_schema_id,
            self.before_observation_sha256,
            self.after_observation_sha256,
        )
        if any(value is not None for value in observation_binding) and any(
            value is None for value in observation_binding
        ):
            raise ValueError(
                "observation binding requires schema and both before/after digests"
            )
        if self.evidence_use in {EvidenceUse.POSITIVE, EvidenceUse.NEGATIVE}:
            if (
                self.proposed_action_name is None
                or self.proposed_action_name in PLACEHOLDER_IDENTIFIERS
            ):
                raise ValueError(
                    "countable evidence requires a normalized proposed action name"
                )
            if (
                self.page_before in PLACEHOLDER_IDENTIFIERS
                or self.page_after in PLACEHOLDER_IDENTIFIERS
            ):
                raise ValueError(
                    "countable evidence requires non-placeholder before and after pages"
                )
            if (
                self.observation_schema_id is None
                or self.observation_schema_id in PLACEHOLDER_IDENTIFIERS
                or self.before_observation_sha256 is None
                or self.after_observation_sha256 is None
            ):
                raise ValueError(
                    "countable evidence requires content-addressed before and after observations"
                )
        if self.risk_class == RiskClass.HIGH_RISK_TRACE_ONLY and self.evidence_use not in {
            EvidenceUse.TRACE_ONLY,
            EvidenceUse.EXCLUDED,
        }:
            raise ValueError("high-risk segment can only be trace-only or excluded")
        if (
            self.risk_class == RiskClass.HIGH_RISK_TRACE_ONLY
            and self.sample_label == SampleLabel.POSITIVE
        ):
            raise ValueError("high-risk segment cannot be labeled as a positive sample")
        if self.evidence_use == EvidenceUse.POSITIVE:
            if (
                self.sample_label != SampleLabel.POSITIVE
                or self.semantic_target is None
                or self.semantic_target.unique_in_frame is not True
                or not self.observed_preconditions
                or not self.expected_delta_claim
                or not self.observed_delta
                or self.outcome != TransitionOutcome.APPLIED
            ):
                raise ValueError(
                    "positive evidence requires a unique semantic target and explicit "
                    "observed transition"
                )
        if self.evidence_use == EvidenceUse.NEGATIVE and self.sample_label in {
            SampleLabel.POSITIVE,
            SampleLabel.OBSERVATION_ONLY,
        }:
            raise ValueError("negative evidence requires a negative sample label")
        if self.evidence_use == EvidenceUse.NEGATIVE and (
            self.semantic_target is None
            or not self.observed_preconditions
            or not self.expected_delta_claim
            or not self.observed_delta
        ):
            raise ValueError(
                "negative evidence requires a semantic target and explicit observed transition"
            )
        if self.evidence_use in {EvidenceUse.POSITIVE, EvidenceUse.NEGATIVE} and (
            expected_transition_outcome(self.sample_label) != self.outcome
        ):
            raise ValueError(
                "countable sample label conflicts with its transition outcome"
            )
        if self.outcome in {
            TransitionOutcome.PANEL_OPENED,
            TransitionOutcome.SELECTION_CHANGED,
        } and not (
            self.sample_label == SampleLabel.OBSERVATION_ONLY
            and self.evidence_use == EvidenceUse.TRACE_ONLY
        ):
            raise ValueError(
                "intermediate transition outcome must remain observation-only trace evidence"
            )
        return self


class ExcludedEventAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_event_id: str
    reason: str

    @field_validator("source_event_id")
    @classmethod
    def _event_id(cls, value: str) -> str:
        return validate_identifier(value, field_name="source_event_id", max_length=120)

    @field_validator("reason")
    @classmethod
    def _reason(cls, value: str) -> str:
        return validate_annotation_text(value, field_name="excluded event reason")


class RecordingAnnotationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    annotation_schema_version: StrictInt = ANNOTATION_SCHEMA_VERSION
    artifact_type: Literal["m1_recording_annotation"] = "m1_recording_annotation"
    annotation_id: str
    session_id: str
    workflow_id: str
    workflow_name: str
    capture_group_id: str
    source_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    source_events_sha256: str = Field(pattern=SHA256_PATTERN)
    supersedes_annotation_id: str | None = None
    annotated_by: str
    annotated_at: datetime
    review_status: AnnotationReviewStatus = AnnotationReviewStatus.DRAFT
    semantic_review: SemanticReview = Field(default_factory=SemanticReview)
    privacy_review: PrivacyReview = Field(default_factory=PrivacyReview)
    sample_label: SampleLabel = SampleLabel.OBSERVATION_ONLY
    risk_class: RiskClass = RiskClass.READ_ONLY
    start_page: str = "unknown"
    end_page: str = "unknown"
    start_state_id: str = "unreviewed"
    segments: list[SegmentAnnotation] = Field(default_factory=list)
    excluded_events: list[ExcludedEventAnnotation] = Field(default_factory=list)
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: StrictBool = False
    safe_for_live_replay: StrictBool = False
    terminal_source_eligible: StrictBool = False
    closure_eligible: StrictBool = False
    knowledge_publication_allowed: StrictBool = False

    @field_validator("annotation_schema_version")
    @classmethod
    def _schema_version(cls, value: int) -> int:
        if value != ANNOTATION_SCHEMA_VERSION:
            raise ValueError(
                f"annotation_schema_version must equal {ANNOTATION_SCHEMA_VERSION}"
            )
        return value

    @field_validator("annotation_id", "session_id", "supersedes_annotation_id")
    @classmethod
    def _uuid(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return None
        return validate_canonical_uuid(value, field_name=info.field_name)

    @field_validator("workflow_id", "capture_group_id", "start_page", "end_page", "start_state_id")
    @classmethod
    def _identifier(cls, value: str, info: Any) -> str:
        return validate_identifier(value, field_name=info.field_name, max_length=120)

    @field_validator("workflow_name")
    @classmethod
    def _workflow_name(cls, value: str) -> str:
        return validate_workflow_name(value)

    @field_validator("annotated_by")
    @classmethod
    def _annotator(cls, value: str) -> str:
        return validate_reviewer_id(value)

    @field_validator("annotated_at")
    @classmethod
    def _aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("annotated_at must include a timezone")
        return value

    @model_validator(mode="after")
    def _review_status_is_consistent(self) -> RecordingAnnotationManifest:
        if self.supersedes_annotation_id == self.annotation_id:
            raise ValueError("annotation cannot supersede itself")
        fixed_false = (
            self.live_dispatch_allowed,
            self.safe_for_live_replay,
            self.terminal_source_eligible,
            self.closure_eligible,
            self.knowledge_publication_allowed,
        )
        if any(value is not False for value in fixed_false):
            raise ValueError(
                "annotation cannot grant authority or publication eligibility"
            )
        rejected = (
            self.semantic_review.status == ReviewDecision.REJECTED
            or self.privacy_review.status == ReviewDecision.REJECTED
        )
        if rejected and self.review_status != AnnotationReviewStatus.REJECTED:
            raise ValueError("a rejecting review must reject the whole annotation")
        if (
            self.privacy_review.approved_for_local_derivation
            or self.privacy_review.approved_for_eval_candidate
        ) and self.review_status != AnnotationReviewStatus.APPROVED:
            raise ValueError(
                "privacy derivation approval requires an approved annotation"
            )
        if self.review_status == AnnotationReviewStatus.APPROVED:
            if (
                self.semantic_review.status != ReviewDecision.APPROVED
                or self.privacy_review.status != ReviewDecision.APPROVED
                or not self.privacy_review.approved_for_local_derivation
            ):
                raise ValueError(
                    "approved annotation requires approved semantic and privacy reviews"
                )
        if self.review_status == AnnotationReviewStatus.REJECTED and not (
            rejected
        ):
            raise ValueError("rejected annotation requires a rejecting review")
        for label, reviewed_at in (
            ("semantic reviewed_at", self.semantic_review.reviewed_at),
            ("privacy reviewed_at", self.privacy_review.reviewed_at),
        ):
            if reviewed_at is not None and reviewed_at < self.annotated_at:
                raise ValueError(f"{label} cannot predate annotation creation")
        if any(segment.risk_class != self.risk_class for segment in self.segments):
            raise ValueError("every segment risk class must match the session risk class")
        if (
            self.risk_class == RiskClass.HIGH_RISK_TRACE_ONLY
            and self.sample_label == SampleLabel.POSITIVE
        ):
            raise ValueError("high-risk trace cannot be labeled as a positive sample")
        positive_segments = [
            segment
            for segment in self.segments
            if segment.evidence_use == EvidenceUse.POSITIVE
        ]
        negative_segments = [
            segment
            for segment in self.segments
            if segment.evidence_use == EvidenceUse.NEGATIVE
        ]
        if self.sample_label == SampleLabel.POSITIVE:
            if not positive_segments or negative_segments:
                raise ValueError(
                    "positive sample requires positive-only countable segment evidence"
                )
        elif self.sample_label == SampleLabel.OBSERVATION_ONLY:
            if positive_segments or negative_segments:
                raise ValueError(
                    "observation-only sample cannot contain countable segment evidence"
                )
        else:
            if (
                positive_segments
                or not negative_segments
                or any(
                    segment.sample_label != self.sample_label
                    for segment in negative_segments
                )
            ):
                raise ValueError(
                    "negative sample requires matching negative-only segment evidence"
                )
        return self


class LoadedAnnotation(BaseModel):
    """Validated annotation plus its exact-byte digest."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    path: Path
    sha256: str = Field(pattern=SHA256_PATTERN)
    annotation: RecordingAnnotationManifest


def build_annotation_template(
    recording: LoadedRecording,
    *,
    workflow_id: str,
    annotated_by: str = "unreviewed-template",
    now: datetime | None = None,
) -> RecordingAnnotationManifest:
    """Build a draft only; no field in the template represents human approval."""

    workflow_id = validate_identifier(workflow_id, field_name="workflow_id")
    annotated_by = validate_reviewer_id(annotated_by)
    groups: list[list[InputEventRecord]] = []
    for event in recording.input_events:
        if groups and (
            groups[-1][0].before_frame_id,
            groups[-1][0].after_frame_id,
        ) == (event.before_frame_id, event.after_frame_id):
            groups[-1].append(event)
        else:
            groups.append([event])
    segments = []
    for index, group in enumerate(groups):
        ambiguous = len(group) > 1 or any(event.ambiguous_burst for event in group)
        segments.append(
            SegmentAnnotation(
                segment_id=f"segment-{index:04d}",
                source_event_ids=[event.event_id for event in group],
                before_frame_id=group[0].before_frame_id,
                after_frame_id=group[-1].after_frame_id,
                sample_label=(
                    SampleLabel.AMBIGUOUS_TARGET
                    if ambiguous
                    else SampleLabel.OBSERVATION_ONLY
                ),
                risk_class=RiskClass.READ_ONLY,
                page_before="unknown",
                page_after="unknown",
                outcome=(
                    TransitionOutcome.AMBIGUOUS
                    if ambiguous
                    else TransitionOutcome.UNKNOWN
                ),
                evidence_use=(
                    EvidenceUse.TRACE_ONLY if ambiguous else EvidenceUse.EXCLUDED
                ),
                unresolved_assumptions=[
                    "semantic target has not been reviewed",
                    "preconditions and expected delta have not been reviewed",
                ],
            )
        )
    source_events_sha256 = recording.manifest.events_sha256
    if source_events_sha256 is None:
        raise ValueError("annotation template requires finalized recording evidence")
    return RecordingAnnotationManifest(
        annotation_id=str(uuid4()),
        session_id=recording.manifest.session_id,
        workflow_id=workflow_id,
        workflow_name=recording.manifest.workflow_name,
        capture_group_id=f"capture-{recording.manifest.session_id}",
        source_manifest_sha256=recording.manifest_sha256,
        source_events_sha256=source_events_sha256,
        annotated_by=annotated_by,
        annotated_at=now or datetime.now(UTC),
        segments=segments,
    )


def load_recording_annotation(
    recording: LoadedRecording,
    annotation_path: Path,
    *,
    require_approved: bool = False,
) -> LoadedAnnotation:
    payload = read_regular_file(annotation_path, max_bytes=MAX_ANNOTATION_BYTES)
    try:
        value = _load_strict_json(payload)
        annotation = RecordingAnnotationManifest.model_validate(value)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ValueError("recording annotation is invalid") from exc
    current_recording = revalidate_loaded_recording(recording)
    _bind_annotation(
        current_recording,
        annotation,
        require_approved=require_approved,
    )
    return LoadedAnnotation(
        path=annotation_path.resolve(strict=True),
        sha256=hashlib.sha256(payload).hexdigest(),
        annotation=annotation,
    )


def load_annotation_for_session(
    session_root: Path,
    annotation_path: Path,
    *,
    require_approved: bool = False,
) -> tuple[LoadedRecording, LoadedAnnotation]:
    recording = load_recording(
        session_root, require_complete=True, verify_images=True
    )
    return recording, load_recording_annotation(
        recording, annotation_path, require_approved=require_approved
    )


def annotation_summary(
    recording: LoadedRecording,
    loaded: LoadedAnnotation,
) -> dict[str, object]:
    annotation = loaded.annotation
    return {
        "status": "valid",
        "annotation_id": annotation.annotation_id,
        "annotation_sha256": loaded.sha256,
        "review_status": annotation.review_status.value,
        "session_id": annotation.session_id,
        "workflow_id": annotation.workflow_id,
        "workflow_name": annotation.workflow_name,
        "source_manifest_sha256": annotation.source_manifest_sha256,
        "source_events_sha256": annotation.source_events_sha256,
        "frame_count": len(recording.frames),
        "segment_count": len(annotation.segments),
        "excluded_event_count": len(annotation.excluded_events),
        "sample_label": annotation.sample_label.value,
        "risk_class": annotation.risk_class.value,
        "privacy_status": annotation.privacy_review.status.value,
        "privacy_scope": annotation.privacy_review.scope.value,
        "approved_for_local_derivation": annotation.privacy_review.approved_for_local_derivation,
        "approved_for_eval_candidate": annotation.privacy_review.approved_for_eval_candidate,
        "raw_approved_for_repo_storage": annotation.privacy_review.raw_approved_for_repo_storage,
        "execution_authority": annotation.execution_authority,
        "live_dispatch_allowed": annotation.live_dispatch_allowed,
        "safe_for_live_replay": annotation.safe_for_live_replay,
        "terminal_source_eligible": annotation.terminal_source_eligible,
        "closure_eligible": annotation.closure_eligible,
        "knowledge_publication_allowed": annotation.knowledge_publication_allowed,
    }


def read_regular_file(path: Path, *, max_bytes: int) -> bytes:
    """Read one bounded, non-linked regular review artifact."""

    return read_bounded_regular_file(
        path,
        max_bytes=max_bytes,
        label="review artifact",
    ).payload


def _load_strict_json(payload: bytes) -> object:
    def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON value is forbidden: {value}")

    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=reject_duplicate_pairs,
        parse_constant=reject_constant,
    )


def _bind_annotation(
    recording: LoadedRecording,
    annotation: RecordingAnnotationManifest,
    *,
    require_approved: bool,
) -> None:
    manifest = recording.manifest
    if annotation.session_id != manifest.session_id:
        raise ValueError("annotation session id does not match the recording")
    if annotation.workflow_name != manifest.workflow_name:
        raise ValueError("annotation workflow name does not match the recording")
    if annotation.source_manifest_sha256 != recording.manifest_sha256:
        raise ValueError("annotation manifest SHA256 does not match the recording")
    if annotation.source_events_sha256 != manifest.events_sha256:
        raise ValueError("annotation events SHA256 does not match the recording")
    if manifest.ended_at is None:
        raise ValueError("annotation requires a finalized recording")
    for label, value in (
        ("annotated_at", annotation.annotated_at),
        ("semantic reviewed_at", annotation.semantic_review.reviewed_at),
        ("privacy reviewed_at", annotation.privacy_review.reviewed_at),
    ):
        if value is not None and value < manifest.ended_at:
            raise ValueError(f"{label} cannot predate recording completion")

    raw_events = list(recording.input_events)
    event_by_id = {event.event_id: event for event in raw_events}
    event_index = {event.event_id: index for index, event in enumerate(raw_events)}
    covered: list[str] = []
    previous_end = -1
    for segment in annotation.segments:
        try:
            events = [event_by_id[event_id] for event_id in segment.source_event_ids]
        except KeyError as exc:
            raise ValueError("annotation references an unknown input event") from exc
        indices = [event_index[event.event_id] for event in events]
        if indices != list(range(indices[0], indices[0] + len(indices))):
            raise ValueError("annotation segment input events must be contiguous")
        if indices[0] <= previous_end:
            raise ValueError("annotation segments must follow recording order")
        previous_end = indices[-1]
        if segment.before_frame_id != events[0].before_frame_id:
            raise ValueError("annotation segment before frame does not match the recording")
        if segment.after_frame_id != events[-1].after_frame_id:
            raise ValueError("annotation segment after frame does not match the recording")
        pair = (events[0].before_frame_id, events[0].after_frame_id)
        burst = [
            event
            for event in raw_events
            if (event.before_frame_id, event.after_frame_id) == pair
        ]
        if len(burst) > 1 or any(event.ambiguous_burst for event in burst):
            if [event.event_id for event in events] != [event.event_id for event in burst]:
                raise ValueError(
                    "shared-frame or ambiguous input burst must stay in one annotation segment"
                )
            if (
                segment.sample_label != SampleLabel.AMBIGUOUS_TARGET
                or segment.outcome != TransitionOutcome.AMBIGUOUS
                or segment.evidence_use not in {EvidenceUse.TRACE_ONLY, EvidenceUse.EXCLUDED}
            ):
                raise ValueError("ambiguous input burst cannot be positive evidence")
        if (
            any(event.geometry_changed for event in events)
            and segment.evidence_use == EvidenceUse.POSITIVE
        ):
            raise ValueError("geometry-changing input cannot be positive evidence")
        covered.extend(segment.source_event_ids)

    excluded_ids = [item.source_event_id for item in annotation.excluded_events]
    unknown_excluded = set(excluded_ids) - set(event_by_id)
    if unknown_excluded:
        raise ValueError("annotation excludes an unknown input event")
    excluded_id_set = set(excluded_ids)
    events_by_frame_pair: dict[tuple[str, str], list[InputEventRecord]] = {}
    for event in raw_events:
        events_by_frame_pair.setdefault(
            (event.before_frame_id, event.after_frame_id), []
        ).append(event)
    if any(
        excluded_id_set.intersection(event.event_id for event in burst)
        for burst in events_by_frame_pair.values()
        if len(burst) > 1 or any(event.ambiguous_burst for event in burst)
    ):
        raise ValueError(
            "shared-frame or ambiguous input burst cannot be split into per-event exclusions"
        )
    all_references = covered + excluded_ids
    if len(all_references) != len(set(all_references)):
        raise ValueError("annotation input event coverage contains duplicates")
    if set(all_references) != set(event_by_id):
        raise ValueError("annotation must cover every recorded input event exactly once")

    if annotation.review_status == AnnotationReviewStatus.APPROVED:
        expected_frames = {frame.frame_id for frame in recording.frames}
        if set(annotation.privacy_review.reviewed_frame_ids) != expected_frames:
            raise ValueError("approved privacy review must cover every recorded frame")
        if (
            not annotation.privacy_review.manifest_reviewed
            or not annotation.privacy_review.events_reviewed
        ):
            raise ValueError("approved privacy review must cover manifest and events")
        if annotation.start_page == "unknown" or annotation.end_page == "unknown":
            raise ValueError("approved annotation requires reviewed start and end pages")
        if annotation.start_state_id == "unreviewed":
            raise ValueError("approved annotation requires a reviewed start state")
        if annotation.sample_label == SampleLabel.POSITIVE and (
            manifest.capture_error_count > 0
            or any(event.geometry_changed or event.ambiguous_burst for event in raw_events)
        ):
            raise ValueError("positive sample cannot contain capture or input ambiguity")
    if require_approved and annotation.review_status != AnnotationReviewStatus.APPROVED:
        raise ValueError("recording annotation is not approved")
