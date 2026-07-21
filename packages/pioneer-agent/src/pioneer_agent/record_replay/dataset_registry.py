"""Read-only audit for reviewed Record & Replay datasets.

The registry assigns complete human-recording sessions to one corpus split.  It
does not compile traces, expose holdout data to a learner, publish knowledge, or
grant input authority.  A successful coverage audit means only that the
provisional sample-count floor is met and a separate human promotion decision
may be considered.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    field_validator,
    model_validator,
)

from pioneer_agent.record_replay.annotations import (
    EvidenceUse,
    RecordingAnnotationManifest,
    RiskClass,
    SampleLabel,
    TransitionOutcome,
    expected_transition_outcome,
    load_recording_annotation,
    read_regular_file,
)
from pioneer_agent.record_replay.models import FrameRecord, SESSION_RECORD_ADAPTER
from pioneer_agent.record_replay.session_store import LoadedRecording, load_recording
from pioneer_agent.record_replay.validation import (
    validate_canonical_uuid,
    validate_identifier,
    validate_unique_strings,
)
from pioneer_agent.record_replay.visual_fingerprint import (
    VisualFrameFingerprint,
    fingerprint_frame,
)


DATASET_REGISTRY_SCHEMA_VERSION = 1
MAX_REGISTRY_BYTES = 1_048_576
MAX_MANIFEST_BYTES = 1_048_576
MAX_EVENTS_BYTES = 67_108_864
MAX_FRAME_BYTES = 16_777_216
MAX_SESSION_FRAME_BYTES = 67_108_864
MAX_CORPUS_EVENTS_BYTES = 134_217_728
MAX_CORPUS_FRAME_BYTES = 536_870_912
MAX_CORPUS_DECODED_PIXELS = 268_435_456
SHA256_PATTERN = r"^[0-9a-f]{64}$"

DatasetSplit = Literal["generation", "holdout"]
DatasetRiskClass = Literal[
    "harmless_navigation",
    "low_risk_mutation",
    "high_risk_trace_only",
]
SplitStatus = Literal["collecting", "frozen", "retired"]


class ReviewReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    path: str
    sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("path")
    @classmethod
    def _safe_relative_path(cls, value: str) -> str:
        return _validate_relative_review_path(value)


class DatasetSessionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    session_id: str
    source_events_sha256: str = Field(pattern=SHA256_PATTERN)
    split: DatasetSplit
    capture_group_id: str
    review_ref: ReviewReference
    source_kind: Literal["human_recording"] = "human_recording"

    @field_validator("session_id")
    @classmethod
    def _canonical_session_id(cls, value: str) -> str:
        return validate_canonical_uuid(value, field_name="session_id")

    @field_validator("capture_group_id")
    @classmethod
    def _capture_group(cls, value: str) -> str:
        return validate_identifier(
            value, field_name="capture_group_id", max_length=120
        )


class SemanticTargetContract(BaseModel):
    """Coordinate-free identity required for every countable segment."""

    model_config = ConfigDict(extra="forbid", strict=True)

    action_name: str
    page: str
    target_kind: str
    target_key: str

    @field_validator("action_name", "page", "target_kind", "target_key")
    @classmethod
    def _identifier(cls, value: str, info: Any) -> str:
        return validate_identifier(value, field_name=info.field_name, max_length=120)


class DevelopmentArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    artifact_id: str
    source_session_ids: list[str] = Field(min_length=1)

    @field_validator("artifact_id")
    @classmethod
    def _artifact_id(cls, value: str) -> str:
        return validate_identifier(value, field_name="artifact_id", max_length=120)

    @field_validator("source_session_ids")
    @classmethod
    def _source_sessions(cls, values: list[str]) -> list[str]:
        checked = [
            validate_canonical_uuid(value, field_name="source_session_id")
            for value in values
        ]
        return validate_unique_strings(checked, field_name="source_session_ids")


class DatasetRegistry(BaseModel):
    """One corpus-wide, session-level generation/holdout assignment."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = DATASET_REGISTRY_SCHEMA_VERSION
    artifact_type: Literal["record_replay_dataset_registry"] = (
        "record_replay_dataset_registry"
    )
    corpus_id: str
    dataset_id: str
    workflow_id: str
    risk_class: DatasetRiskClass
    split_status: SplitStatus = "collecting"
    split_unit: Literal["corpus_session_capture_group"] = (
        "corpus_session_capture_group"
    )
    countable_semantic_contract: SemanticTargetContract
    sessions: list[DatasetSessionEntry]
    development_artifacts: list[DevelopmentArtifact] = Field(default_factory=list)
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    safe_for_live_replay: Literal[False] = False
    terminal_source_eligible: Literal[False] = False
    closure_eligible: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False

    @field_validator("corpus_id", "dataset_id", "workflow_id")
    @classmethod
    def _identifier(cls, value: str, info: Any) -> str:
        return validate_identifier(value, field_name=info.field_name, max_length=120)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _strict_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != DATASET_REGISTRY_SCHEMA_VERSION:
            raise ValueError("schema_version must be integer 1")
        return value

    @field_validator(
        "live_dispatch_allowed",
        "safe_for_live_replay",
        "terminal_source_eligible",
        "closure_eligible",
        "knowledge_publication_allowed",
        mode="before",
    )
    @classmethod
    def _strict_false_safety_flag(cls, value: object, info: Any) -> object:
        if value is not False:
            raise ValueError(f"{info.field_name} must be boolean false")
        return value

    @model_validator(mode="after")
    def _registry_references_are_unique(self) -> DatasetRegistry:
        if self.countable_semantic_contract.action_name != self.workflow_id:
            raise ValueError(
                "semantic contract action name must equal the registry workflow id"
            )
        session_ids = [entry.session_id for entry in self.sessions]
        if len(session_ids) != len(set(session_ids)):
            raise ValueError("registry contains a duplicate session id")
        artifact_ids = [artifact.artifact_id for artifact in self.development_artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("registry contains a duplicate development artifact id")
        return self


class SplitCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    session_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    geometry_count: int = Field(ge=0)
    start_state_count: int = Field(ge=0)
    negative_categories: list[
        Literal["target", "interruption", "no_change_timeout"]
    ] = Field(default_factory=list)


class DatasetAuditReport(BaseModel):
    """A coverage report, never a promotion or execution authorization."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["valid"] = "valid"
    registry_sha256: str = Field(pattern=SHA256_PATTERN)
    corpus_id: str
    dataset_id: str
    workflow_id: str
    risk_class: DatasetRiskClass
    split_status: SplitStatus
    integrity_valid: Literal[True] = True
    registry_internal_leak_free: Literal[True] = True
    corpus_catalog_verified: Literal[False] = False
    development_lineage_verified: Literal[False] = False
    holdout_oracle_verified: Literal[False] = False
    human_capture_provenance_verified: Literal[False] = False
    visual_near_duplicate_checked: Literal[False] = False
    structured_start_state_verified: Literal[False] = False
    filesystem_race_hardened: Literal[False] = False
    independent_eval_ready: Literal[False] = False
    coverage_scope: Literal["provisional_policy_floor_only"] = (
        "provisional_policy_floor_only"
    )
    coverage_ready: StrictBool
    generation: SplitCoverage
    holdout: SplitCoverage
    blockers: list[str]
    image_model_exercised: Literal[False] = False
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    safe_for_live_replay: Literal[False] = False
    manual_promotion_required: Literal[True] = True
    terminal_source_eligible: Literal[False] = False
    closure_eligible: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False


@dataclass(frozen=True)
class LoadedDatasetRegistry:
    path: Path
    sha256: str
    registry: DatasetRegistry


@dataclass(frozen=True)
class DatasetSessionIdentity:
    """In-memory identities needed for a corpus-wide leakage audit."""

    session_id: str
    split: DatasetSplit
    source_events_sha256: str
    capture_group_id: str
    annotation_id: str
    annotation_sha256: str
    encoded_frame_sha256s: tuple[str, ...]
    source_png_sha256s: tuple[str, ...]
    visual_fingerprints: tuple[VisualFrameFingerprint, ...]
    expected_transition_outcome: TransitionOutcome | None
    annotation_reviewed_at: datetime


@dataclass(frozen=True)
class AuditedDatasetRegistry:
    """One strictly audited registry plus its non-sensitive identity inventory."""

    loaded_registry: LoadedDatasetRegistry
    report: DatasetAuditReport
    session_identities: tuple[DatasetSessionIdentity, ...]
    events_bytes: int
    frame_bytes: int
    decoded_pixels: int


@dataclass(frozen=True)
class _AuditedSample:
    session_id: str
    split: DatasetSplit
    label: SampleLabel
    geometry_key: str
    start_state_id: str


_NEGATIVE_LABELS = frozenset(
    {
        SampleLabel.NO_CHANGE,
        SampleLabel.MISSING_TARGET,
        SampleLabel.AMBIGUOUS_TARGET,
        SampleLabel.POPUP_INTERRUPTION,
        SampleLabel.TIMEOUT,
        SampleLabel.OPERATOR_CANCELLED,
    }
)
_NEGATIVE_CATEGORIES: dict[str, frozenset[SampleLabel]] = {
    "target": frozenset(
        {SampleLabel.MISSING_TARGET, SampleLabel.AMBIGUOUS_TARGET}
    ),
    "interruption": frozenset(
        {SampleLabel.POPUP_INTERRUPTION, SampleLabel.OPERATOR_CANCELLED}
    ),
    "no_change_timeout": frozenset(
        {SampleLabel.NO_CHANGE, SampleLabel.TIMEOUT}
    ),
}
_ANNOTATION_RISK_BY_DATASET: dict[str, RiskClass] = {
    "harmless_navigation": RiskClass.READ_ONLY,
    "low_risk_mutation": RiskClass.LOW_RISK_MUTATION,
    "high_risk_trace_only": RiskClass.HIGH_RISK_TRACE_ONLY,
}


def load_dataset_registry(path: Path) -> LoadedDatasetRegistry:
    """Load a registry through the same pinned, no-link review-file reader."""

    payload = read_regular_file(path, max_bytes=MAX_REGISTRY_BYTES)
    try:
        value = _load_strict_json(payload)
        registry = DatasetRegistry.model_validate(value)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ValueError("dataset registry is invalid") from exc
    return LoadedDatasetRegistry(
        path=path.resolve(strict=True),
        sha256=hashlib.sha256(payload).hexdigest(),
        registry=registry,
    )


def audit_dataset_registry(
    registry_path: Path,
    *,
    sessions_root: Path,
    reviews_root: Path,
) -> DatasetAuditReport:
    """Audit one registry and return its no-authority coverage report."""

    return audit_dataset_registry_bundle(
        registry_path,
        sessions_root=sessions_root,
        reviews_root=reviews_root,
    ).report


def audit_dataset_registry_bundle(
    registry_path: Path,
    *,
    sessions_root: Path,
    reviews_root: Path,
    max_corpus_events_bytes: int = MAX_CORPUS_EVENTS_BYTES,
    max_corpus_frame_bytes: int = MAX_CORPUS_FRAME_BYTES,
    max_corpus_decoded_pixels: int = MAX_CORPUS_DECODED_PIXELS,
) -> AuditedDatasetRegistry:
    """Audit immutable inputs and report provisional dataset coverage.

    Integrity, binding, privacy, or leakage failures raise ``ValueError``.
    Missing samples are normal while collecting and are returned as blockers.
    """

    loaded_registry = load_dataset_registry(registry_path)
    registry = loaded_registry.registry
    if (
        max_corpus_events_bytes < 0
        or max_corpus_frame_bytes < 0
        or max_corpus_decoded_pixels < 0
    ):
        raise ValueError("dataset audit resource limits cannot be negative")
    events_limit = min(max_corpus_events_bytes, MAX_CORPUS_EVENTS_BYTES)
    frame_limit = min(max_corpus_frame_bytes, MAX_CORPUS_FRAME_BYTES)
    decoded_pixel_limit = min(
        max_corpus_decoded_pixels, MAX_CORPUS_DECODED_PIXELS
    )
    sessions_root = _resolve_directory_root(sessions_root, label="sessions root")
    reviews_root = _resolve_directory_root(reviews_root, label="reviews root")

    seen_events: dict[str, str] = {}
    seen_annotation_ids: dict[str, str] = {}
    seen_annotation_hashes: dict[str, str] = {}
    seen_encoded_frames: dict[str, str] = {}
    seen_source_frames: dict[str, str] = {}
    seen_capture_groups: dict[str, str] = {}
    samples: list[_AuditedSample] = []
    session_identities: list[DatasetSessionIdentity] = []
    split_by_session: dict[str, DatasetSplit] = {}
    corpus_events_bytes = 0
    corpus_frame_bytes = 0
    corpus_decoded_pixels = 0

    expected_annotation_risk = _ANNOTATION_RISK_BY_DATASET[registry.risk_class]
    for entry in registry.sessions:
        session_root = _safe_session_root(sessions_root, entry.session_id)
        (
            recording,
            event_bytes,
            frame_bytes,
            visual_fingerprints,
            decoded_pixels,
        ) = _load_hardened_recording(
            session_root,
            remaining_corpus_events_bytes=(
                events_limit - corpus_events_bytes
            ),
            remaining_corpus_frame_bytes=(
                frame_limit - corpus_frame_bytes
            ),
            remaining_corpus_decoded_pixels=(
                decoded_pixel_limit - corpus_decoded_pixels
            ),
        )
        corpus_events_bytes += event_bytes
        corpus_frame_bytes += frame_bytes
        corpus_decoded_pixels += decoded_pixels
        if recording.manifest.session_id != entry.session_id:
            raise ValueError("registry session id does not match the raw recording")
        if recording.manifest.events_sha256 != entry.source_events_sha256:
            raise ValueError("registry events SHA256 does not match the raw recording")

        review_path = _safe_review_file(reviews_root, entry.review_ref.path)
        review_payload = read_regular_file(review_path, max_bytes=MAX_REGISTRY_BYTES)
        review_sha256 = hashlib.sha256(review_payload).hexdigest()
        if review_sha256 != entry.review_ref.sha256:
            raise ValueError("registry review SHA256 does not match the annotation")
        loaded_annotation = load_recording_annotation(
            recording, review_path, require_approved=True
        )
        if loaded_annotation.sha256 != entry.review_ref.sha256:
            raise ValueError("annotation changed while the registry was audited")
        annotation = loaded_annotation.annotation
        if annotation.workflow_id != registry.workflow_id:
            raise ValueError("annotation workflow id does not match the registry")
        if annotation.capture_group_id != entry.capture_group_id:
            raise ValueError("annotation capture group does not match the registry")
        if annotation.risk_class != expected_annotation_risk:
            raise ValueError("annotation risk class does not match the registry")
        if not annotation.privacy_review.approved_for_eval_candidate:
            raise ValueError("dataset annotation is not privacy-approved for eval use")
        if annotation.start_state_id == "unknown":
            raise ValueError("dataset annotation requires a specific start state")
        _validate_annotation_evidence(
            annotation,
            expected_annotation_risk,
            workflow_id=registry.workflow_id,
            semantic_contract=registry.countable_semantic_contract,
        )

        _claim_unique(
            seen_events,
            entry.source_events_sha256,
            entry.session_id,
            label="events SHA256",
        )
        _claim_unique(
            seen_annotation_ids,
            annotation.annotation_id,
            entry.session_id,
            label="annotation id",
        )
        _claim_unique(
            seen_annotation_hashes,
            loaded_annotation.sha256,
            entry.session_id,
            label="annotation SHA256",
        )
        _claim_unique(
            seen_capture_groups,
            entry.capture_group_id,
            entry.session_id,
            label="capture group",
        )
        for digest in {frame.sha256 for frame in recording.frames}:
            _claim_unique(
                seen_encoded_frames,
                digest,
                entry.session_id,
                label="encoded frame SHA256",
            )
        for digest in {frame.source_png_sha256 for frame in recording.frames}:
            _claim_unique(
                seen_source_frames,
                digest,
                entry.session_id,
                label="source PNG SHA256",
            )

        split_by_session[entry.session_id] = entry.split
        review_times = (
            annotation.semantic_review.reviewed_at,
            annotation.privacy_review.reviewed_at,
        )
        if any(value is None for value in review_times):
            raise ValueError("approved annotation is missing a review timestamp")
        session_identities.append(
            DatasetSessionIdentity(
                session_id=entry.session_id,
                split=entry.split,
                source_events_sha256=entry.source_events_sha256,
                capture_group_id=entry.capture_group_id,
                annotation_id=annotation.annotation_id,
                annotation_sha256=loaded_annotation.sha256,
                encoded_frame_sha256s=tuple(
                    sorted({frame.sha256 for frame in recording.frames})
                ),
                source_png_sha256s=tuple(
                    sorted({frame.source_png_sha256 for frame in recording.frames})
                ),
                visual_fingerprints=visual_fingerprints,
                expected_transition_outcome=expected_transition_outcome(
                    annotation.sample_label
                ),
                annotation_reviewed_at=max(
                    value for value in review_times if value is not None
                ),
            )
        )
        samples.append(
            _AuditedSample(
                session_id=entry.session_id,
                split=entry.split,
                label=annotation.sample_label,
                geometry_key=_geometry_key(recording),
                start_state_id=annotation.start_state_id,
            )
        )

    for artifact in registry.development_artifacts:
        for session_id in artifact.source_session_ids:
            split = split_by_session.get(session_id)
            if split is None:
                raise ValueError(
                    "development artifact references a session outside the registry"
                )
            if split == "holdout":
                raise ValueError("holdout session cannot feed a development artifact")

    generation_samples = [sample for sample in samples if sample.split == "generation"]
    holdout_samples = [sample for sample in samples if sample.split == "holdout"]
    generation = _coverage(generation_samples)
    holdout = _coverage(holdout_samples)
    blockers = _coverage_blockers(
        registry=registry,
        generation=generation,
        holdout=holdout,
        generation_samples=generation_samples,
        holdout_samples=holdout_samples,
    )
    report = DatasetAuditReport(
        registry_sha256=loaded_registry.sha256,
        corpus_id=registry.corpus_id,
        dataset_id=registry.dataset_id,
        workflow_id=registry.workflow_id,
        risk_class=registry.risk_class,
        split_status=registry.split_status,
        coverage_ready=not blockers,
        generation=generation,
        holdout=holdout,
        blockers=blockers,
    )
    return AuditedDatasetRegistry(
        loaded_registry=loaded_registry,
        report=report,
        session_identities=tuple(session_identities),
        events_bytes=corpus_events_bytes,
        frame_bytes=corpus_frame_bytes,
        decoded_pixels=corpus_decoded_pixels,
    )


def audit_dataset(
    registry_path: Path,
    *,
    sessions_root: Path,
    reviews_root: Path,
) -> DatasetAuditReport:
    """Concise public alias used by callers that do not need registry internals."""

    return audit_dataset_registry(
        registry_path, sessions_root=sessions_root, reviews_root=reviews_root
    )


def _validate_annotation_evidence(
    annotation: RecordingAnnotationManifest,
    risk_class: RiskClass,
    *,
    workflow_id: str,
    semantic_contract: SemanticTargetContract,
) -> None:
    relevant_segments = [
        segment
        for segment in annotation.segments
        if segment.evidence_use != EvidenceUse.EXCLUDED
    ]
    if any(segment.risk_class != risk_class for segment in relevant_segments):
        raise ValueError("annotation segment risk class is inconsistent")
    if any(
        segment.evidence_use in {EvidenceUse.POSITIVE, EvidenceUse.NEGATIVE}
        and segment.proposed_action_name != workflow_id
        for segment in relevant_segments
    ):
        raise ValueError("counted segment action does not match the registry workflow")
    if any(
        segment.evidence_use in {EvidenceUse.POSITIVE, EvidenceUse.NEGATIVE}
        for segment in relevant_segments
    ) and annotation.start_page != semantic_contract.page:
        raise ValueError("counted session start page violates the semantic contract")
    for segment in relevant_segments:
        if segment.evidence_use not in {EvidenceUse.POSITIVE, EvidenceUse.NEGATIVE}:
            continue
        if segment.page_before != semantic_contract.page:
            raise ValueError("counted segment page violates the semantic contract")
        target = segment.semantic_target
        if target is None or (
            target.page,
            target.target_kind,
            target.target_key,
        ) != (
            semantic_contract.page,
            semantic_contract.target_kind,
            semantic_contract.target_key,
        ):
            raise ValueError("counted segment target violates the semantic contract")
    if risk_class == RiskClass.HIGH_RISK_TRACE_ONLY:
        if annotation.sample_label == SampleLabel.POSITIVE or any(
            segment.evidence_use not in {EvidenceUse.TRACE_ONLY, EvidenceUse.EXCLUDED}
            for segment in annotation.segments
        ):
            raise ValueError("high-risk dataset evidence must remain trace-only")
        return
    negative_segments = [
        segment
        for segment in relevant_segments
        if segment.evidence_use == EvidenceUse.NEGATIVE
    ]
    if annotation.sample_label in _NEGATIVE_LABELS:
        if not negative_segments or any(
            segment.sample_label != annotation.sample_label
            for segment in negative_segments
        ):
            raise ValueError(
                "negative dataset sample requires one consistent segment label"
            )
    if any(
        expected_transition_outcome(segment.sample_label) != segment.outcome
        for segment in negative_segments
    ):
        raise ValueError("negative sample label conflicts with its transition outcome")
    if annotation.sample_label == SampleLabel.OBSERVATION_ONLY:
        if any(
            segment.evidence_use in {EvidenceUse.POSITIVE, EvidenceUse.NEGATIVE}
            for segment in annotation.segments
        ):
            raise ValueError("observation-only sample contains counted evidence")


def _coverage(samples: list[_AuditedSample]) -> SplitCoverage:
    positive = [sample for sample in samples if sample.label == SampleLabel.POSITIVE]
    negative = [sample for sample in samples if sample.label in _NEGATIVE_LABELS]
    categories = [
        category
        for category, labels in _NEGATIVE_CATEGORIES.items()
        if any(sample.label in labels for sample in negative)
    ]
    return SplitCoverage(
        session_count=len(samples),
        positive_count=len(positive),
        negative_count=len(negative),
        geometry_count=len({sample.geometry_key for sample in positive}),
        start_state_count=len({sample.start_state_id for sample in samples}),
        negative_categories=categories,
    )


def _coverage_blockers(
    *,
    registry: DatasetRegistry,
    generation: SplitCoverage,
    holdout: SplitCoverage,
    generation_samples: list[_AuditedSample],
    holdout_samples: list[_AuditedSample],
) -> list[str]:
    blockers: list[str] = []
    if registry.risk_class == "high_risk_trace_only":
        blockers.append("high_risk_trace_only")
    elif registry.risk_class == "harmless_navigation":
        if generation.positive_count < 3:
            blockers.append("generation_positive_below_3")
        if generation.geometry_count < 2:
            blockers.append("generation_positive_geometries_below_2")
        for category in _NEGATIVE_CATEGORIES:
            if category not in generation.negative_categories:
                blockers.append(f"generation_negative_category_missing_{category}")
        if holdout.positive_count < 2:
            blockers.append("holdout_positive_below_2")
        for category in _NEGATIVE_CATEGORIES:
            if category not in holdout.negative_categories:
                blockers.append(f"holdout_negative_category_missing_{category}")
    elif registry.risk_class == "low_risk_mutation":
        if generation.positive_count < 5:
            blockers.append("generation_positive_below_5")
        if generation.geometry_count < 2:
            blockers.append("generation_positive_geometries_below_2")
        if generation.negative_count < 5:
            blockers.append("generation_negative_below_5")
        for category in _NEGATIVE_CATEGORIES:
            if category not in generation.negative_categories:
                blockers.append(f"generation_negative_category_missing_{category}")
        if holdout.positive_count < 3:
            blockers.append("holdout_positive_below_3")
        if holdout.negative_count < 5:
            blockers.append("holdout_negative_below_5")
        for category in _NEGATIVE_CATEGORIES:
            if category not in holdout.negative_categories:
                blockers.append(f"holdout_negative_category_missing_{category}")

    if registry.risk_class != "high_risk_trace_only":
        countable_generation = [
            sample
            for sample in generation_samples
            if sample.label == SampleLabel.POSITIVE or sample.label in _NEGATIVE_LABELS
        ]
        countable_holdout = [
            sample
            for sample in holdout_samples
            if sample.label == SampleLabel.POSITIVE or sample.label in _NEGATIVE_LABELS
        ]
        generation_geometries = {
            sample.geometry_key for sample in countable_generation
        }
        generation_start_states = {
            sample.start_state_id for sample in countable_generation
        }
        has_unseen_holdout = any(
            sample.geometry_key not in generation_geometries
            or sample.start_state_id not in generation_start_states
            for sample in countable_holdout
        )
        if not has_unseen_holdout:
            blockers.append("holdout_has_no_unseen_geometry_or_start_state")
    if registry.split_status == "collecting":
        blockers.append("dataset_is_still_collecting")
    elif registry.split_status == "retired":
        blockers.append("dataset_is_retired")
    return blockers


def _geometry_key(recording: LoadedRecording) -> str:
    geometry = recording.manifest.initial_capture_geometry
    width, height = geometry.frame_size
    return f"{geometry.capture_backend}:{width}x{height}"


def _claim_unique(
    seen: dict[str, str],
    key: str,
    session_id: str,
    *,
    label: str,
) -> None:
    previous = seen.get(key)
    if previous is not None and previous != session_id:
        raise ValueError(
            f"duplicate {label} across dataset sessions: {previous}, {session_id}"
        )
    seen[key] = session_id


def _load_hardened_recording(
    session_root: Path,
    *,
    remaining_corpus_events_bytes: int,
    remaining_corpus_frame_bytes: int,
    remaining_corpus_decoded_pixels: int,
) -> tuple[
    LoadedRecording,
    int,
    int,
    tuple[VisualFrameFingerprint, ...],
    int,
]:
    if (
        remaining_corpus_events_bytes < 0
        or remaining_corpus_frame_bytes < 0
        or remaining_corpus_decoded_pixels < 0
    ):
        raise ValueError("recording corpus exceeds the fixed audit size limits")
    manifest_path = _safe_existing_child(session_root, "manifest.json")
    events_path = _safe_existing_child(session_root, "events.jsonl")
    manifest_payload = read_regular_file(
        manifest_path, max_bytes=MAX_MANIFEST_BYTES
    )
    events_payload = read_regular_file(
        events_path,
        max_bytes=min(MAX_EVENTS_BYTES, remaining_corpus_events_bytes),
    )
    preflight_frames = _preflight_frames(
        session_root,
        events_payload,
        remaining_corpus_frame_bytes=remaining_corpus_frame_bytes,
    )
    recording = load_recording(
        session_root, require_complete=True, verify_images=True
    )
    if hashlib.sha256(manifest_payload).hexdigest() != recording.manifest_sha256:
        raise ValueError("raw manifest changed while the dataset was audited")
    if hashlib.sha256(events_payload).hexdigest() != recording.manifest.events_sha256:
        raise ValueError("raw events changed while the dataset was audited")
    if {
        (frame.path, frame.sha256, frame.byte_size) for frame in recording.frames
    } != {
        (frame.path, frame.sha256, frame.byte_size) for frame in preflight_frames
    }:
        raise ValueError("raw frame inventory changed while the dataset was audited")
    visual_fingerprints: list[VisualFrameFingerprint] = []
    decoded_pixels = 0
    for frame in recording.frames:
        declared_pixels = frame.image_size[0] * frame.image_size[1]
        if decoded_pixels + declared_pixels > remaining_corpus_decoded_pixels:
            raise ValueError(
                "recording corpus exceeds the fixed decoded pixel limit"
            )
        frame_path = _safe_existing_child(session_root, frame.path)
        payload = read_regular_file(frame_path, max_bytes=MAX_FRAME_BYTES)
        if len(payload) != frame.byte_size or hashlib.sha256(payload).hexdigest() != frame.sha256:
            raise ValueError("raw frame changed while the dataset was audited")
        fingerprint = fingerprint_frame(frame, payload)
        decoded_pixels += fingerprint.decoded_pixels
        visual_fingerprints.append(fingerprint)
    return (
        recording,
        len(events_payload),
        sum(frame.byte_size for frame in preflight_frames),
        tuple(visual_fingerprints),
        decoded_pixels,
    )


def _preflight_frames(
    session_root: Path,
    events_payload: bytes,
    *,
    remaining_corpus_frame_bytes: int,
) -> list[FrameRecord]:
    frames: list[FrameRecord] = []
    for line_number, raw_line in enumerate(events_payload.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            value = _load_strict_json(raw_line)
            record = SESSION_RECORD_ADAPTER.validate_python(value)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ValueError(
                f"invalid recording event during size preflight at line {line_number}"
            ) from exc
        if isinstance(record, FrameRecord):
            frames.append(record)

    declared_total = sum(frame.byte_size for frame in frames)
    if any(frame.byte_size > MAX_FRAME_BYTES for frame in frames):
        raise ValueError("raw frame exceeds the fixed per-frame audit size limit")
    if declared_total > MAX_SESSION_FRAME_BYTES:
        raise ValueError("raw session exceeds the fixed frame audit size limit")
    if declared_total > remaining_corpus_frame_bytes:
        raise ValueError("recording corpus exceeds the fixed frame audit size limit")
    for frame in frames:
        frame_path = _safe_existing_child(session_root, frame.path)
        payload = read_regular_file(frame_path, max_bytes=MAX_FRAME_BYTES)
        if (
            len(payload) != frame.byte_size
            or hashlib.sha256(payload).hexdigest() != frame.sha256
        ):
            raise ValueError("raw frame fails the bounded size preflight")
    return frames


def _resolve_directory_root(path: Path, *, label: str) -> Path:
    if path.is_symlink():
        raise ValueError(f"{label} cannot be a symlink")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"{label} does not exist") from exc
    if not resolved.is_dir():
        raise ValueError(f"{label} is not a directory")
    return resolved


def _safe_session_root(root: Path, session_id: str) -> Path:
    candidate = root / session_id
    if candidate.is_symlink():
        raise ValueError("session directory cannot be a symlink")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError("registered session directory does not exist") from exc
    if resolved.parent != root or resolved.name != session_id or not resolved.is_dir():
        raise ValueError("registered session must be a direct UUID-named directory")
    return resolved


def _safe_review_file(root: Path, relative: str) -> Path:
    _validate_relative_review_path(relative)
    return _safe_existing_child(root, relative)


def _safe_existing_child(root: Path, relative: str) -> Path:
    if "\\" in relative:
        raise ValueError("artifact path must use normalized POSIX separators")
    parsed = PurePosixPath(relative)
    if parsed.is_absolute() or not parsed.parts or any(
        part in {"", ".", ".."} for part in parsed.parts
    ):
        raise ValueError("artifact path must stay beneath its configured root")
    current = root
    for index, part in enumerate(parsed.parts):
        current = current / part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise ValueError("registered artifact does not exist") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("registered artifact path cannot contain a symlink")
        if index < len(parsed.parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("registered artifact parent is not a directory")
    try:
        resolved = current.resolve(strict=True)
    except OSError as exc:
        raise ValueError("registered artifact does not exist") from exc
    if resolved == root or root not in resolved.parents:
        raise ValueError("registered artifact escapes its configured root")
    return resolved


def _validate_relative_review_path(value: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 240
        or "\\" in value
        or ":" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError("review path must be a safe relative POSIX path")
    parsed = PurePosixPath(value)
    if (
        parsed.is_absolute()
        or str(parsed) != value
        or not parsed.parts
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or parsed.suffix != ".json"
    ):
        raise ValueError("review path must be a normalized relative JSON path")
    if any(
        not part
        or part[0] in {" ", "."}
        or part[-1] in {" ", "."}
        or any(
            not (character.isascii() and (character.isalnum() or character in "._-"))
            for character in part
        )
        for part in parsed.parts
    ):
        raise ValueError("review path contains unsupported characters")
    return value


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
