"""Fail-closed, observation-only classification for map-filter transitions.

The classifier combines two already-parsed map observations with reviewer-attributed
boundary evidence.  It deliberately ignores map movement and land/candidate counts:
those changes cannot prove that a filter was applied.  Even an ``applied`` result is
human-demonstration evidence only; it never carries execution authority or proves
runtime causality.
"""
from __future__ import annotations

from enum import Enum
import hashlib
import json
from typing import Annotated, Any, Literal, Mapping

from pydantic import (
    AwareDatetime,
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

from pioneer_agent.perception.vision.prompts import MapLandDetection
from pioneer_agent.record_replay.annotations import (
    AnnotationReviewStatus,
    EvidenceUse,
    LoadedAnnotation,
    SampleLabel,
    expected_transition_outcome,
    load_recording_annotation,
)
from pioneer_agent.record_replay.session_store import (
    LoadedRecording,
    revalidate_loaded_recording,
)


MapFilterLevel = Annotated[StrictInt, Field(ge=1, le=12)]
MapResourceType = Literal["wood", "stone", "iron", "grain"]
Sha256 = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
MAP_FILTER_WORKFLOW_ID = "map-filter-apply"
MAP_FILTER_ACTION_NAME = MAP_FILTER_WORKFLOW_ID
MAP_FILTER_OBSERVATION_SCHEMA_ID = "map-land-filter-v1"
MAP_FILTER_TARGET_PAGE = "main-map"
MAP_FILTER_TARGET_KIND = "map-filter-control"
MAP_FILTER_TARGET_KEY = "apply-filter"
MAP_FILTER_PANEL_OPEN_ACTION_NAME = "map-filter-open-panel"
MAP_FILTER_PANEL_OPEN_TARGET_KIND = "map-filter-control"
MAP_FILTER_PANEL_OPEN_TARGET_KEY = "open-filter-panel"
MAP_FILTER_SELECTION_ACTION_NAME = "map-filter-change-selection"
MAP_FILTER_SELECTION_TARGET_KIND = "map-filter-selection-control"
MAP_FILTER_SELECTION_TARGET_KEY = "change-filter-selection"


class MapFilterTransitionOutcome(str, Enum):
    PANEL_OPENED = "panel_opened"
    SELECTION_CHANGED = "selection_changed"
    APPLIED = "applied"
    NO_CHANGE = "no_change"
    INTERRUPTED = "interrupted"
    AMBIGUOUS = "ambiguous"


class MapFilterSelection(BaseModel):
    """Coordinate-free semantic filter state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_filter_enabled: StrictBool = False
    resource_types: tuple[MapResourceType, ...] = ()
    levels: tuple[MapFilterLevel, ...] = ()
    level_min: MapFilterLevel | None = None
    level_max: MapFilterLevel | None = None

    @field_validator("resource_types")
    @classmethod
    def _canonical_resources(
        cls, values: tuple[MapResourceType, ...]
    ) -> tuple[MapResourceType, ...]:
        return tuple(sorted(values))

    @field_validator("levels")
    @classmethod
    def _canonical_levels(
        cls, values: tuple[MapFilterLevel, ...]
    ) -> tuple[MapFilterLevel, ...]:
        return tuple(sorted(values))

    @model_validator(mode="after")
    def _selection_is_consistent(self) -> MapFilterSelection:
        if len(self.resource_types) != len(set(self.resource_types)):
            raise ValueError("resource_types cannot contain duplicates")
        if len(self.levels) != len(set(self.levels)):
            raise ValueError("levels cannot contain duplicates")
        if self.resource_types and not self.resource_filter_enabled:
            raise ValueError(
                "resource_types requires resource_filter_enabled=true"
            )
        if (
            self.level_min is not None
            and self.level_max is not None
            and self.level_min > self.level_max
        ):
            raise ValueError("level_min must be <= level_max")
        if self.level_min is not None and any(
            level < self.level_min for level in self.levels
        ):
            raise ValueError("selected level cannot be below level_min")
        if self.level_max is not None and any(
            level > self.level_max for level in self.levels
        ):
            raise ValueError("selected level cannot exceed level_max")
        return self


class BoundaryFrameEvidence(BaseModel):
    """Reviewer-visible facts for one side of the transition boundary.

    Optional identity fields let incomplete annotations be represented and rejected
    by the classifier as ambiguous instead of silently inventing defaults.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    frame_id: StrictStr | None
    frame_sha256: Sha256 | None = None
    source_png_sha256: Sha256 | None = None
    perception_sha256: Sha256 | None = None
    captured_at: AwareDatetime | None
    page_type: Literal["main_map", "unknown"] | None
    target_window_id: StrictStr | None
    geometry_id: StrictStr | None
    geometry_complete: StrictBool
    capture_complete: StrictBool
    capture_error: StrictBool


class ReviewedApplyEventEvidence(BaseModel):
    """Review status for the input event believed to be the Apply activation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_status: Literal["not_present", "reviewed", "unreviewed", "ambiguous"]
    event_id: StrictStr | None = None
    observed_at: AwareDatetime | None = None


class ReviewedFilterResultMarker(BaseModel):
    """A reviewer-read result marker, expressed without UI coordinates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    review_status: Literal["not_present", "reviewed", "unreviewed", "ambiguous"]
    observed_filter: MapFilterSelection | None = None
    fresh_in_after_frame: StrictBool = False


class ReviewedSourceBinding(BaseModel):
    """Content-addressed link to one reviewed raw event and annotation segment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: StrictStr | None = None
    source_manifest_sha256: Sha256 | None = None
    source_events_sha256: Sha256 | None = None
    annotation_id: StrictStr | None = None
    annotation_sha256: Sha256 | None = None
    annotation_segment_id: StrictStr | None = None
    source_event_id: StrictStr | None = None


class ReviewerBoundaryEvidence(BaseModel):
    """Explicit human review of a before/event/after observation boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    review_status: Literal["reviewed", "unreviewed", "ambiguous"]
    reviewed_by: StrictStr | None
    reviewed_at: AwareDatetime | None
    source_binding: ReviewedSourceBinding | None = None
    before_frame: BoundaryFrameEvidence
    after_frame: BoundaryFrameEvidence
    after_frame_fresh: StrictBool
    apply_event: ReviewedApplyEventEvidence
    requested_filter: MapFilterSelection | None = None
    result_marker: ReviewedFilterResultMarker = Field(
        default_factory=lambda: ReviewedFilterResultMarker(
            review_status="not_present"
        )
    )
    target_window_replaced: StrictBool = False
    geometry_changed: StrictBool = False
    ambiguous_input_burst: StrictBool = False
    interrupted: StrictBool = False

    @field_validator("reviewed_by")
    @classmethod
    def _nonempty_reviewer(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or value != value.strip()):
            raise ValueError("reviewed_by must be normalized and non-empty")
        return value


class MapFilterTransitionResult(BaseModel):
    """Non-authoritative transition evidence returned by the classifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: MapFilterTransitionOutcome
    reasons: tuple[StrictStr, ...] = ()
    requested_filter: MapFilterSelection | None = None
    observed_before_filter: MapFilterSelection | None = None
    observed_after_filter: MapFilterSelection | None = None
    causal_verified: Literal[False] = False
    verifier_status: Literal["unproven"] = "unproven"
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    safe_for_live_replay: Literal[False] = False
    terminal_source_eligible: Literal[False] = False
    closure_eligible: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False


def classify_map_filter_transition(
    before: MapLandDetection | Mapping[str, Any] | None,
    after: MapLandDetection | Mapping[str, Any] | None,
    evidence: ReviewerBoundaryEvidence | Mapping[str, Any],
    *,
    recording: LoadedRecording | None = None,
    annotation: LoadedAnnotation | None = None,
) -> MapFilterTransitionResult:
    """Classify one reviewed boundary without inferring causality or authority.

    Invalid or incomplete inputs return ``ambiguous``.  The function never uses target
    coordinates, the map centre, visible-land deltas, or candidate counts.
    """

    before_observation, before_error = _strict_observation(before)
    after_observation, after_error = _strict_observation(after)
    boundary, boundary_error = _strict_boundary(evidence)

    before_filter = _selection_from_observation(before_observation)
    after_filter = _selection_from_observation(after_observation)
    parse_reasons = tuple(
        reason
        for reason in (before_error, after_error, boundary_error)
        if reason is not None
    )
    if parse_reasons or boundary is None:
        return _result(
            MapFilterTransitionOutcome.AMBIGUOUS,
            parse_reasons or ("invalid_boundary_evidence",),
            before_filter=before_filter,
            after_filter=after_filter,
        )

    ambiguity_reasons = _boundary_ambiguities(boundary)
    if before_observation is None or after_observation is None:
        ambiguity_reasons.append("missing_map_observation")
    else:
        if before_observation.page_type != "main_map":
            ambiguity_reasons.append("before_page_unknown")
        if after_observation.page_type != "main_map":
            ambiguity_reasons.append("after_page_unknown")

    ambiguity_reasons.extend(_event_evidence_ambiguities(boundary))
    ambiguity_reasons.extend(_marker_evidence_ambiguities(boundary))
    ambiguity_reasons.extend(
        _source_binding_ambiguities(
            boundary,
            before_observation,
            after_observation,
            recording=recording,
            annotation=annotation,
        )
    )
    if ambiguity_reasons:
        return _result(
            MapFilterTransitionOutcome.AMBIGUOUS,
            ambiguity_reasons,
            requested_filter=boundary.requested_filter,
            before_filter=before_filter,
            after_filter=after_filter,
        )

    assert before_observation is not None
    assert after_observation is not None

    if boundary.apply_event.review_status == "reviewed":
        apply_context_reasons: list[str] = []
        if boundary.requested_filter is None:
            apply_context_reasons.append("reviewed_apply_missing_requested_filter")
        if not before_observation.filter_panel_visible:
            apply_context_reasons.append("reviewed_apply_without_visible_filter_panel")
        if not before_observation.apply_button_visible:
            apply_context_reasons.append("reviewed_apply_without_visible_apply_control")
        if not before_observation.apply_button_enabled:
            apply_context_reasons.append("reviewed_apply_without_enabled_apply_control")
        if apply_context_reasons:
            return _result(
                MapFilterTransitionOutcome.AMBIGUOUS,
                apply_context_reasons,
                requested_filter=boundary.requested_filter,
                before_filter=before_filter,
                after_filter=after_filter,
            )

    if boundary.interrupted:
        return _result_with_annotation_contract(
            MapFilterTransitionOutcome.INTERRUPTED,
            ("reviewed_interruption",),
            boundary=boundary,
            annotation=annotation,
            requested_filter=boundary.requested_filter,
            before_filter=before_filter,
            after_filter=after_filter,
        )

    if boundary.apply_event.review_status == "reviewed":
        requested = boundary.requested_filter
        assert requested is not None
        marker_matches = (
            boundary.result_marker.review_status == "reviewed"
            and boundary.result_marker.fresh_in_after_frame
            and boundary.result_marker.observed_filter == requested
        )
        if marker_matches and after_filter != requested:
            return _result(
                MapFilterTransitionOutcome.AMBIGUOUS,
                ("result_marker_conflicts_with_after_filter",),
                requested_filter=requested,
                before_filter=before_filter,
                after_filter=after_filter,
            )
        if before_filter == requested:
            if after_filter != requested:
                return _result(
                    MapFilterTransitionOutcome.AMBIGUOUS,
                    ("repeated_apply_conflicts_with_after_filter",),
                    requested_filter=requested,
                    before_filter=before_filter,
                    after_filter=after_filter,
                )
            return _result_with_annotation_contract(
                MapFilterTransitionOutcome.NO_CHANGE,
                ("requested_filter_already_observed_before_apply",),
                boundary=boundary,
                annotation=annotation,
                requested_filter=requested,
                before_filter=before_filter,
                after_filter=after_filter,
            )
        after_matches = after_filter == requested
        if marker_matches or after_matches:
            reasons = ["reviewed_apply_event", "fresh_post_frame"]
            reasons.append(
                "reviewed_result_marker_matches_request"
                if marker_matches
                else "after_filter_matches_request"
            )
            return _result_with_annotation_contract(
                MapFilterTransitionOutcome.APPLIED,
                reasons,
                boundary=boundary,
                annotation=annotation,
                requested_filter=requested,
                before_filter=before_filter,
                after_filter=after_filter,
            )

        if before_filter != after_filter:
            return _result(
                MapFilterTransitionOutcome.AMBIGUOUS,
                ("unexpected_after_filter_state",),
                requested_filter=requested,
                before_filter=before_filter,
                after_filter=after_filter,
            )
        return _result_with_annotation_contract(
            MapFilterTransitionOutcome.NO_CHANGE,
            (
                (
                    "requested_filter_already_observed_before_apply"
                    if before_filter == requested
                    else "reviewed_apply_without_result_evidence"
                ),
            ),
            boundary=boundary,
            annotation=annotation,
            requested_filter=requested,
            before_filter=before_filter,
            after_filter=after_filter,
        )

    if (
        not before_observation.filter_panel_visible
        and after_observation.filter_panel_visible
    ):
        return _result_with_annotation_contract(
            MapFilterTransitionOutcome.PANEL_OPENED,
            ("filter_panel_became_visible",),
            boundary=boundary,
            annotation=annotation,
            before_filter=before_filter,
            after_filter=after_filter,
        )

    if (
        before_observation.filter_panel_visible
        and after_observation.filter_panel_visible
        and before_filter != after_filter
    ):
        return _result_with_annotation_contract(
            MapFilterTransitionOutcome.SELECTION_CHANGED,
            ("visible_filter_selection_changed",),
            boundary=boundary,
            annotation=annotation,
            before_filter=before_filter,
            after_filter=after_filter,
        )

    if before_filter != after_filter:
        return _result(
            MapFilterTransitionOutcome.AMBIGUOUS,
            ("filter_state_changed_outside_visible_panel",),
            before_filter=before_filter,
            after_filter=after_filter,
        )

    reason = (
        "panel_closed_without_reviewed_apply"
        if before_observation.filter_panel_visible
        and not after_observation.filter_panel_visible
        else "no_reviewed_filter_delta"
    )
    return _result_with_annotation_contract(
        MapFilterTransitionOutcome.NO_CHANGE,
        (reason,),
        boundary=boundary,
        annotation=annotation,
        before_filter=before_filter,
        after_filter=after_filter,
    )


def _strict_observation(
    value: MapLandDetection | Mapping[str, Any] | None,
) -> tuple[MapLandDetection | None, str | None]:
    if value is None:
        return None, "missing_map_observation"
    if isinstance(value, MapLandDetection):
        value = value.model_dump(mode="python", warnings=False)
    elif not isinstance(value, Mapping):
        return None, "invalid_map_observation"
    if set(value) - set(MapLandDetection.model_fields):
        return None, "invalid_map_observation"
    try:
        return MapLandDetection.model_validate(value, strict=True), None
    except (TypeError, ValidationError, ValueError):
        return None, "invalid_map_observation"


def _strict_boundary(
    value: ReviewerBoundaryEvidence | Mapping[str, Any],
) -> tuple[ReviewerBoundaryEvidence | None, str | None]:
    if isinstance(value, ReviewerBoundaryEvidence):
        value = value.model_dump(mode="python", warnings=False)
    elif not isinstance(value, Mapping):
        return None, "invalid_boundary_evidence"
    try:
        # JSON arrays/timestamps remain valid transport representations.  Every
        # primitive safety field is Strict*, so this does not permit bool/int/string
        # coercions that could change the review meaning.
        return ReviewerBoundaryEvidence.model_validate(value), None
    except (TypeError, ValidationError, ValueError):
        return None, "invalid_boundary_evidence"


def _selection_from_observation(
    observation: MapLandDetection | None,
) -> MapFilterSelection | None:
    if observation is None:
        return None
    try:
        return MapFilterSelection(
            resource_filter_enabled=observation.resource_filter_enabled,
            resource_types=tuple(observation.selected_resource_types),
            levels=tuple(observation.selected_levels),
            level_min=observation.level_min,
            level_max=observation.level_max,
        )
    except ValidationError:
        return None


def map_filter_perception_sha256(
    observation: MapLandDetection | Mapping[str, Any],
) -> str:
    """Hash the fully validated perception payload in canonical JSON form."""

    parsed, error = _strict_observation(observation)
    if error is not None or parsed is None:
        raise ValueError("cannot digest an invalid map-filter perception")
    payload = json.dumps(
        parsed.model_dump(mode="json"),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _source_binding_ambiguities(
    evidence: ReviewerBoundaryEvidence,
    before_observation: MapLandDetection | None,
    after_observation: MapLandDetection | None,
    *,
    recording: LoadedRecording | None,
    annotation: LoadedAnnotation | None,
) -> list[str]:
    """Deny transition evidence not tied to one validated immutable source slice."""

    if recording is None or annotation is None:
        return ["missing_validated_source_evidence"]
    if not isinstance(recording, LoadedRecording) or not isinstance(
        annotation, LoadedAnnotation
    ):
        return ["invalid_validated_source_evidence"]
    try:
        recording = revalidate_loaded_recording(recording)
    except ValueError:
        return ["stale_or_invalid_loaded_recording"]
    try:
        current_annotation = load_recording_annotation(
            recording,
            annotation.path,
            require_approved=True,
        )
    except ValueError:
        return ["stale_or_invalid_loaded_annotation"]
    if (
        current_annotation.sha256 != annotation.sha256
        or current_annotation.annotation != annotation.annotation
    ):
        return ["stale_or_invalid_loaded_annotation"]
    annotation = current_annotation

    binding = evidence.source_binding
    if binding is None:
        return ["missing_source_binding"]
    required = (
        binding.session_id,
        binding.source_manifest_sha256,
        binding.source_events_sha256,
        binding.annotation_id,
        binding.annotation_sha256,
        binding.annotation_segment_id,
        binding.source_event_id,
    )
    if not all(required):
        return ["incomplete_source_binding"]

    reasons: list[str] = []
    manifest = recording.manifest
    reviewed = annotation.annotation
    events_sha256 = manifest.events_sha256

    if reviewed.review_status != AnnotationReviewStatus.APPROVED:
        reasons.append("source_annotation_not_approved")
    if not reviewed.privacy_review.approved_for_local_derivation:
        reasons.append("source_annotation_not_approved_for_local_derivation")
    if binding.session_id != manifest.session_id:
        reasons.append("source_session_mismatch")
    if binding.source_manifest_sha256 != recording.manifest_sha256:
        reasons.append("source_manifest_digest_mismatch")
    if events_sha256 is None or binding.source_events_sha256 != events_sha256:
        reasons.append("source_events_digest_mismatch")
    if reviewed.session_id != manifest.session_id:
        reasons.append("annotation_session_mismatch")
    if reviewed.source_manifest_sha256 != recording.manifest_sha256:
        reasons.append("annotation_manifest_digest_mismatch")
    if reviewed.source_events_sha256 != events_sha256:
        reasons.append("annotation_events_digest_mismatch")
    if binding.annotation_id != reviewed.annotation_id:
        reasons.append("annotation_id_mismatch")
    if binding.annotation_sha256 != annotation.sha256:
        reasons.append("annotation_digest_mismatch")

    frame_by_id = {frame.frame_id: frame for frame in recording.frames}
    for label, frame_evidence, observation in (
        ("before", evidence.before_frame, before_observation),
        ("after", evidence.after_frame, after_observation),
    ):
        if frame_evidence.frame_id is None:
            continue
        frame = frame_by_id.get(frame_evidence.frame_id)
        if frame is None:
            reasons.append(f"{label}_source_frame_missing")
            continue
        if frame_evidence.frame_sha256 != frame.sha256:
            reasons.append(f"{label}_frame_digest_mismatch")
        if frame_evidence.source_png_sha256 != frame.source_png_sha256:
            reasons.append(f"{label}_source_png_digest_mismatch")
        if frame_evidence.captured_at != frame.captured_at:
            reasons.append(f"{label}_frame_time_mismatch")
        if observation is None:
            reasons.append(f"{label}_perception_missing")
        elif frame_evidence.perception_sha256 != map_filter_perception_sha256(
            observation
        ):
            reasons.append(f"{label}_perception_digest_mismatch")

    source_event = next(
        (
            event
            for event in recording.input_events
            if event.event_id == binding.source_event_id
        ),
        None,
    )
    if source_event is None:
        reasons.append("source_input_event_missing")
    else:
        if (
            source_event.before_frame_id != evidence.before_frame.frame_id
            or source_event.after_frame_id != evidence.after_frame.frame_id
        ):
            reasons.append("source_input_event_boundary_mismatch")
        if source_event.ambiguous_burst != evidence.ambiguous_input_burst:
            reasons.append("source_input_event_ambiguity_mismatch")
        if source_event.geometry_changed != evidence.geometry_changed:
            reasons.append("source_input_event_geometry_mismatch")
        if evidence.apply_event.review_status == "reviewed":
            if evidence.apply_event.event_id != source_event.event_id:
                reasons.append("reviewed_apply_event_source_mismatch")
            if evidence.apply_event.observed_at != source_event.occurred_at:
                reasons.append("reviewed_apply_event_time_mismatch")

    segment = next(
        (
            item
            for item in reviewed.segments
            if item.segment_id == binding.annotation_segment_id
        ),
        None,
    )
    if segment is None:
        reasons.append("annotation_segment_missing")
    else:
        if segment.source_event_ids != [binding.source_event_id]:
            reasons.append("annotation_segment_event_mismatch")
        if (
            segment.before_frame_id != evidence.before_frame.frame_id
            or segment.after_frame_id != evidence.after_frame.frame_id
        ):
            reasons.append("annotation_segment_boundary_mismatch")
        if reviewed.workflow_id != MAP_FILTER_WORKFLOW_ID:
            reasons.append("annotation_workflow_not_map_filter_apply")
        if reviewed.risk_class.value != "read_only":
            reasons.append("annotation_risk_not_read_only")
        if segment.page_before != MAP_FILTER_TARGET_PAGE or segment.page_after not in {
            "main-map",
            "main-map-filtered",
        }:
            reasons.append("annotation_pages_not_map_filter_transition")
        if segment.observation_schema_id != MAP_FILTER_OBSERVATION_SCHEMA_ID:
            reasons.append("annotation_observation_schema_mismatch")
        if before_observation is not None and (
            segment.before_observation_sha256
            != map_filter_perception_sha256(before_observation)
        ):
            reasons.append("annotation_before_observation_digest_mismatch")
        if after_observation is not None and (
            segment.after_observation_sha256
            != map_filter_perception_sha256(after_observation)
        ):
            reasons.append("annotation_after_observation_digest_mismatch")
    return reasons


def _result_with_annotation_contract(
    outcome: MapFilterTransitionOutcome,
    reasons: tuple[str, ...] | list[str],
    *,
    boundary: ReviewerBoundaryEvidence,
    annotation: LoadedAnnotation,
    requested_filter: MapFilterSelection | None = None,
    before_filter: MapFilterSelection | None = None,
    after_filter: MapFilterSelection | None = None,
) -> MapFilterTransitionResult:
    contract_reasons = _annotation_outcome_ambiguities(
        boundary,
        annotation,
        outcome,
    )
    if contract_reasons:
        return _result(
            MapFilterTransitionOutcome.AMBIGUOUS,
            contract_reasons,
            requested_filter=requested_filter,
            before_filter=before_filter,
            after_filter=after_filter,
        )
    return _result(
        outcome,
        reasons,
        requested_filter=requested_filter,
        before_filter=before_filter,
        after_filter=after_filter,
    )


def _annotation_outcome_ambiguities(
    boundary: ReviewerBoundaryEvidence,
    annotation: LoadedAnnotation,
    outcome: MapFilterTransitionOutcome,
) -> list[str]:
    binding = boundary.source_binding
    if binding is None or binding.annotation_segment_id is None:
        return ["missing_annotation_outcome_contract"]
    reviewed = annotation.annotation
    segment = next(
        (
            item
            for item in reviewed.segments
            if item.segment_id == binding.annotation_segment_id
        ),
        None,
    )
    if segment is None:
        return ["missing_annotation_outcome_contract"]

    if outcome == MapFilterTransitionOutcome.PANEL_OPENED:
        if not (
            reviewed.sample_label == SampleLabel.OBSERVATION_ONLY
            and segment.sample_label == SampleLabel.OBSERVATION_ONLY
            and segment.evidence_use == EvidenceUse.TRACE_ONLY
            and segment.outcome.value == outcome.value
        ):
            return ["annotation_contract_conflicts_with_panel_opened"]
    elif outcome == MapFilterTransitionOutcome.SELECTION_CHANGED:
        if not (
            reviewed.sample_label == SampleLabel.OBSERVATION_ONLY
            and segment.sample_label == SampleLabel.OBSERVATION_ONLY
            and segment.evidence_use == EvidenceUse.TRACE_ONLY
            and segment.outcome.value == outcome.value
        ):
            return ["annotation_contract_conflicts_with_selection_changed"]
    else:
        expected = expected_transition_outcome(reviewed.sample_label)
        expected_evidence_use = (
            EvidenceUse.POSITIVE
            if reviewed.sample_label == SampleLabel.POSITIVE
            else EvidenceUse.NEGATIVE
        )
        if not (
            segment.sample_label == reviewed.sample_label
            and expected is not None
            and segment.outcome == expected
            and expected.value == outcome.value
            and segment.evidence_use == expected_evidence_use
        ):
            return [f"annotation_contract_conflicts_with_{outcome.value}"]
    return _annotation_semantic_contract_ambiguities(segment, outcome)


def _annotation_semantic_contract_ambiguities(
    segment: Any,
    outcome: MapFilterTransitionOutcome,
) -> list[str]:
    if outcome == MapFilterTransitionOutcome.PANEL_OPENED:
        action_name = MAP_FILTER_PANEL_OPEN_ACTION_NAME
        target_kind = MAP_FILTER_PANEL_OPEN_TARGET_KIND
        target_key = MAP_FILTER_PANEL_OPEN_TARGET_KEY
        suffix = "map_filter_panel_open"
    elif outcome == MapFilterTransitionOutcome.SELECTION_CHANGED:
        action_name = MAP_FILTER_SELECTION_ACTION_NAME
        target_kind = MAP_FILTER_SELECTION_TARGET_KIND
        target_key = MAP_FILTER_SELECTION_TARGET_KEY
        suffix = "map_filter_selection_change"
    else:
        action_name = MAP_FILTER_ACTION_NAME
        target_kind = MAP_FILTER_TARGET_KIND
        target_key = MAP_FILTER_TARGET_KEY
        suffix = "map_filter_apply"

    reasons: list[str] = []
    if segment.proposed_action_name != action_name:
        reasons.append(f"annotation_action_not_{suffix}")
    target = segment.semantic_target
    if target is None or (
        target.page != MAP_FILTER_TARGET_PAGE
        or target.target_kind != target_kind
        or target.target_key != target_key
        or target.unique_in_frame is not True
    ):
        reasons.append(f"annotation_target_not_{suffix}")
    return reasons


def _boundary_ambiguities(evidence: ReviewerBoundaryEvidence) -> list[str]:
    reasons: list[str] = []
    if evidence.review_status != "reviewed":
        reasons.append("boundary_not_reviewed")
    if evidence.reviewed_by is None or evidence.reviewed_at is None:
        reasons.append("missing_reviewer_attribution")
    if evidence.ambiguous_input_burst:
        reasons.append("ambiguous_input_burst")

    for label, frame in (
        ("before", evidence.before_frame),
        ("after", evidence.after_frame),
    ):
        if frame.capture_error:
            reasons.append(f"{label}_capture_error")
        if not frame.capture_complete:
            reasons.append(f"{label}_capture_incomplete")
        if not frame.geometry_complete:
            reasons.append(f"{label}_geometry_incomplete")
        if not all(
            (
                frame.frame_id,
                frame.captured_at,
                frame.page_type,
                frame.target_window_id,
                frame.geometry_id,
            )
        ):
            reasons.append(f"{label}_boundary_incomplete")
        if frame.page_type != "main_map":
            reasons.append(f"{label}_page_not_main_map")

    before = evidence.before_frame
    after = evidence.after_frame
    if before.frame_id is not None and before.frame_id == after.frame_id:
        reasons.append("post_frame_reused")
    if not evidence.after_frame_fresh:
        reasons.append("post_frame_not_fresh")
    if (
        before.captured_at is not None
        and after.captured_at is not None
        and after.captured_at <= before.captured_at
    ):
        reasons.append("non_forward_frame_time")
    if (
        evidence.reviewed_at is not None
        and after.captured_at is not None
        and evidence.reviewed_at < after.captured_at
    ):
        reasons.append("review_predates_post_frame")
    if evidence.target_window_replaced or (
        before.target_window_id is not None
        and after.target_window_id is not None
        and before.target_window_id != after.target_window_id
    ):
        reasons.append("target_window_changed")
    if evidence.geometry_changed or (
        before.geometry_id is not None
        and after.geometry_id is not None
        and before.geometry_id != after.geometry_id
    ):
        reasons.append("capture_geometry_changed")
    return reasons


def _event_evidence_ambiguities(
    evidence: ReviewerBoundaryEvidence,
) -> list[str]:
    event = evidence.apply_event
    if event.review_status in {"unreviewed", "ambiguous"}:
        return ["apply_event_not_unambiguous"]
    if event.review_status == "not_present":
        if event.event_id is not None or event.observed_at is not None:
            return ["inconsistent_absent_apply_event"]
        return []
    if not event.event_id or event.observed_at is None:
        return ["reviewed_apply_event_incomplete"]

    before_at = evidence.before_frame.captured_at
    after_at = evidence.after_frame.captured_at
    if (
        before_at is None
        or after_at is None
        or event.observed_at <= before_at
        or event.observed_at >= after_at
    ):
        return ["apply_event_outside_frame_boundary"]
    return []


def _marker_evidence_ambiguities(
    evidence: ReviewerBoundaryEvidence,
) -> list[str]:
    marker = evidence.result_marker
    if marker.review_status in {"unreviewed", "ambiguous"}:
        return ["result_marker_not_unambiguous"]
    if marker.review_status == "not_present":
        if marker.observed_filter is not None or marker.fresh_in_after_frame:
            return ["inconsistent_absent_result_marker"]
        return []
    if marker.observed_filter is None or not marker.fresh_in_after_frame:
        return ["reviewed_result_marker_incomplete"]
    if evidence.apply_event.review_status != "reviewed":
        return ["result_marker_without_reviewed_apply_event"]
    if evidence.requested_filter is None:
        return ["result_marker_without_requested_filter"]
    if marker.observed_filter != evidence.requested_filter:
        return ["result_marker_conflicts_with_request"]
    return []


def _result(
    outcome: MapFilterTransitionOutcome,
    reasons: tuple[str, ...] | list[str],
    *,
    requested_filter: MapFilterSelection | None = None,
    before_filter: MapFilterSelection | None = None,
    after_filter: MapFilterSelection | None = None,
) -> MapFilterTransitionResult:
    return MapFilterTransitionResult(
        outcome=outcome,
        reasons=tuple(dict.fromkeys(reasons)),
        requested_filter=requested_filter,
        observed_before_filter=before_filter,
        observed_after_filter=after_filter,
    )
