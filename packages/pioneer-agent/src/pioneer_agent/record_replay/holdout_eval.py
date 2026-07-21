"""External-oracle holdout evaluation for Record & Replay.

Developer-side code can create and inspect prediction submissions without
opening oracle labels.  An external evaluator binds the frozen corpus, approved
annotations, and evaluator-only oracle, then signs aggregate-only results with
Ed25519.  Local verification trusts only an explicit public-key policy and
never receives per-sample expected outcomes.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from typing import Any, Literal, TypeVar

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    field_validator,
    model_validator,
)

from pioneer_agent.record_replay.annotations import TransitionOutcome
from pioneer_agent.record_replay.corpus_catalog import (
    AuditedCorpusCatalog,
    audit_corpus_catalog_bundle,
)
from pioneer_agent.record_replay.validation import (
    load_strict_json_bytes,
    read_bounded_regular_file,
    reject_linked_path_components,
    validate_canonical_uuid,
    validate_identifier,
    validate_reviewer_id,
)


HOLDOUT_EVAL_SCHEMA_VERSION = 1
HOLDOUT_AGGREGATE_SCHEMA_VERSION = 2
MAX_EVAL_ARTIFACT_BYTES = 4_194_304
MAX_PRIVATE_KEY_BYTES = 65_536
MAX_HOLDOUT_PREDICTIONS = 4_096
SHA256_PATTERN = r"^[0-9a-f]{64}$"
ACCURACY_SCALE = 1_000_000

CountableOutcome = Literal["applied", "no_change", "ambiguous", "interrupted"]
PredictedOutcome = Literal[
    "applied", "no_change", "ambiguous", "interrupted", "unknown"
]


class HoldoutPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dataset_id: str
    session_id: str
    source_events_sha256: str = Field(pattern=SHA256_PATTERN)
    evaluation_input_sha256: str = Field(pattern=SHA256_PATTERN)
    predicted_outcome: PredictedOutcome
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("dataset_id")
    @classmethod
    def _dataset_id(cls, value: str) -> str:
        return validate_identifier(value, field_name="dataset_id", max_length=120)

    @field_validator("session_id")
    @classmethod
    def _session_id(cls, value: str) -> str:
        return validate_canonical_uuid(value, field_name="session_id")

    @field_validator("confidence", mode="before")
    @classmethod
    def _finite_confidence(cls, value: object) -> object:
        if type(value) is not float or not math.isfinite(value):
            raise ValueError("confidence must be one finite JSON float")
        return value


class HoldoutPredictionSubmission(BaseModel):
    """Unlabeled predictions safe to hand to an external evaluator."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = HOLDOUT_EVAL_SCHEMA_VERSION
    artifact_type: Literal["record_replay_holdout_prediction_submission"] = (
        "record_replay_holdout_prediction_submission"
    )
    submission_id: str
    created_at: AwareDatetime
    corpus_id: str
    catalog_sha256: str = Field(pattern=SHA256_PATTERN)
    predictor_id: str
    predictor_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    image_model_exercised_claimed: StrictBool
    predictions: list[HoldoutPrediction] = Field(
        min_length=1, max_length=MAX_HOLDOUT_PREDICTIONS
    )
    oracle_accessed: Literal[False] = False
    oracle_labels_included: Literal[False] = False
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    safe_for_live_replay: Literal[False] = False
    terminal_source_eligible: Literal[False] = False
    closure_eligible: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False

    @field_validator("submission_id")
    @classmethod
    def _submission_id(cls, value: str) -> str:
        return validate_canonical_uuid(value, field_name="submission_id")

    @field_validator("created_at", mode="before")
    @classmethod
    def _created_at(cls, value: object) -> object:
        return _parse_aware_datetime(value, field_name="created_at")

    @field_validator("corpus_id", "predictor_id")
    @classmethod
    def _identifier(cls, value: str, info: Any) -> str:
        return validate_identifier(value, field_name=info.field_name, max_length=120)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _strict_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != HOLDOUT_EVAL_SCHEMA_VERSION:
            raise ValueError("schema_version must be integer 1")
        return value

    @field_validator(
        "oracle_accessed",
        "oracle_labels_included",
        "live_dispatch_allowed",
        "safe_for_live_replay",
        "terminal_source_eligible",
        "closure_eligible",
        "knowledge_publication_allowed",
        mode="before",
    )
    @classmethod
    def _strict_false_flag(cls, value: object, info: Any) -> object:
        if value is not False:
            raise ValueError(f"{info.field_name} must be boolean false")
        return value

    @model_validator(mode="after")
    def _prediction_keys_are_unique(self) -> HoldoutPredictionSubmission:
        keys = [
            (prediction.dataset_id, prediction.session_id)
            for prediction in self.predictions
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("submission contains a duplicate dataset/session prediction")
        return self


class HoldoutOracleEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dataset_id: str
    session_id: str
    source_events_sha256: str = Field(pattern=SHA256_PATTERN)
    evaluation_input_sha256: str = Field(pattern=SHA256_PATTERN)
    expected_outcome: CountableOutcome

    @field_validator("dataset_id")
    @classmethod
    def _dataset_id(cls, value: str) -> str:
        return validate_identifier(value, field_name="dataset_id", max_length=120)

    @field_validator("session_id")
    @classmethod
    def _session_id(cls, value: str) -> str:
        return validate_canonical_uuid(value, field_name="session_id")


class HoldoutOracle(BaseModel):
    """Evaluator-only labels; never accepted by the ordinary Record & Replay CLI."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = HOLDOUT_EVAL_SCHEMA_VERSION
    artifact_type: Literal["record_replay_holdout_oracle"] = (
        "record_replay_holdout_oracle"
    )
    oracle_id: str
    created_at: AwareDatetime
    corpus_id: str
    catalog_sha256: str = Field(pattern=SHA256_PATTERN)
    review_status: Literal["approved"] = "approved"
    reviewed_by: str
    sealed_by: str
    reviewed_at: AwareDatetime
    storage_scope: Literal["external_evaluator_only"] = "external_evaluator_only"
    developer_access_allowed: Literal[False] = False
    per_sample_release_allowed: Literal[False] = False
    entries: list[HoldoutOracleEntry] = Field(
        min_length=1, max_length=MAX_HOLDOUT_PREDICTIONS
    )
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    safe_for_live_replay: Literal[False] = False
    terminal_source_eligible: Literal[False] = False
    closure_eligible: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False

    @field_validator("oracle_id")
    @classmethod
    def _oracle_id(cls, value: str) -> str:
        return validate_canonical_uuid(value, field_name="oracle_id")

    @field_validator("created_at", "reviewed_at", mode="before")
    @classmethod
    def _timestamps(cls, value: object, info: Any) -> object:
        return _parse_aware_datetime(value, field_name=info.field_name)

    @field_validator("corpus_id")
    @classmethod
    def _corpus_id(cls, value: str) -> str:
        return validate_identifier(value, field_name="corpus_id", max_length=120)

    @field_validator("reviewed_by", "sealed_by")
    @classmethod
    def _reviewer(cls, value: str) -> str:
        return validate_reviewer_id(value)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _strict_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != HOLDOUT_EVAL_SCHEMA_VERSION:
            raise ValueError("schema_version must be integer 1")
        return value

    @field_validator(
        "developer_access_allowed",
        "per_sample_release_allowed",
        "live_dispatch_allowed",
        "safe_for_live_replay",
        "terminal_source_eligible",
        "closure_eligible",
        "knowledge_publication_allowed",
        mode="before",
    )
    @classmethod
    def _strict_false_flag(cls, value: object, info: Any) -> object:
        if value is not False:
            raise ValueError(f"{info.field_name} must be boolean false")
        return value

    @model_validator(mode="after")
    def _oracle_contract(self) -> HoldoutOracle:
        if self.reviewed_by == self.sealed_by:
            raise ValueError("oracle reviewer and sealer must be different identities")
        if self.reviewed_at < self.created_at:
            raise ValueError("oracle review cannot predate oracle creation")
        keys = [(entry.dataset_id, entry.session_id) for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("oracle contains a duplicate dataset/session entry")
        return self


class EvaluatorTrustPolicy(BaseModel):
    """Explicit public-key trust anchor supplied by the evaluation owner."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = HOLDOUT_EVAL_SCHEMA_VERSION
    artifact_type: Literal["record_replay_evaluator_trust_policy"] = (
        "record_replay_evaluator_trust_policy"
    )
    policy_id: str
    evaluator_key_id: str
    ed25519_public_key_base64: str
    corpus_id: str
    catalog_sha256: str = Field(pattern=SHA256_PATTERN)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    minimum_holdout_count: int = Field(ge=1, le=MAX_HOLDOUT_PREDICTIONS)
    minimum_accuracy_ppm: int = Field(ge=0, le=ACCURACY_SCALE)
    maximum_unknown_count: int = Field(ge=0, le=MAX_HOLDOUT_PREDICTIONS)
    maximum_signed_submissions_per_catalog: Literal[1] = 1
    evaluator_owner: str
    approved_by: str
    approved_at: AwareDatetime
    trust_scope: Literal["external_evaluator_aggregate_only"] = (
        "external_evaluator_aggregate_only"
    )
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    safe_for_live_replay: Literal[False] = False
    terminal_source_eligible: Literal[False] = False
    closure_eligible: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False

    @field_validator("policy_id", "evaluator_key_id", "corpus_id")
    @classmethod
    def _identifier(cls, value: str, info: Any) -> str:
        return validate_identifier(value, field_name=info.field_name, max_length=120)

    @field_validator("valid_from", "valid_until", "approved_at", mode="before")
    @classmethod
    def _timestamps(cls, value: object, info: Any) -> object:
        return _parse_aware_datetime(value, field_name=info.field_name)

    @field_validator("evaluator_owner", "approved_by")
    @classmethod
    def _reviewer(cls, value: str) -> str:
        return validate_reviewer_id(value)

    @field_validator("ed25519_public_key_base64")
    @classmethod
    def _public_key(cls, value: str) -> str:
        _decode_base64_exact(value, expected_size=32, label="Ed25519 public key")
        return value

    @field_validator("schema_version", mode="before")
    @classmethod
    def _strict_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != HOLDOUT_EVAL_SCHEMA_VERSION:
            raise ValueError("schema_version must be integer 1")
        return value

    @field_validator(
        "minimum_holdout_count",
        "minimum_accuracy_ppm",
        "maximum_unknown_count",
        mode="before",
    )
    @classmethod
    def _strict_integer(cls, value: object, info: Any) -> object:
        if type(value) is not int:
            raise ValueError(f"{info.field_name} must be an integer")
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
    def _strict_false_flag(cls, value: object, info: Any) -> object:
        if value is not False:
            raise ValueError(f"{info.field_name} must be boolean false")
        return value

    @model_validator(mode="after")
    def _trust_contract(self) -> EvaluatorTrustPolicy:
        if self.valid_until <= self.valid_from:
            raise ValueError("evaluator trust policy validity window is invalid")
        if not self.valid_from <= self.approved_at <= self.valid_until:
            raise ValueError("trust approval must fall inside the validity window")
        if self.evaluator_owner == self.approved_by:
            raise ValueError("evaluator owner and trust approver must differ")
        return self


class HoldoutEvalAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[2] = HOLDOUT_AGGREGATE_SCHEMA_VERSION
    artifact_type: Literal["record_replay_holdout_eval_aggregate"] = (
        "record_replay_holdout_eval_aggregate"
    )
    attestation_id: str
    submission_sha256: str = Field(pattern=SHA256_PATTERN)
    trust_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    policy_id: str
    corpus_id: str
    catalog_sha256: str = Field(pattern=SHA256_PATTERN)
    evaluator_key_id: str
    evaluated_at: AwareDatetime
    holdout_session_count: int = Field(ge=1, le=MAX_HOLDOUT_PREDICTIONS)
    exact_match_count: int = Field(ge=0, le=MAX_HOLDOUT_PREDICTIONS)
    unknown_prediction_count: int = Field(ge=0, le=MAX_HOLDOUT_PREDICTIONS)
    accuracy_ppm: int = Field(ge=0, le=ACCURACY_SCALE)
    passed_policy: StrictBool
    oracle_integrity_verified: Literal[True] = True
    oracle_matches_approved_annotations: Literal[True] = True
    holdout_set_complete: Literal[True] = True
    single_submission_budget_enforced: Literal[True] = True
    visual_near_duplicate_checked: Literal[True]
    visual_near_duplicate_algorithm: Literal["sanmou-multisignal-v1"]
    visual_frame_count: int = Field(ge=1)
    visual_candidate_comparison_count: int = Field(ge=0)
    per_sample_results_included: Literal[False] = False
    oracle_labels_disclosed: Literal[False] = False
    evaluator_isolation_attested: Literal[True] = True
    evaluator_host_isolation_verified: Literal[False] = False
    image_model_execution_verified: Literal[False] = False
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    safe_for_live_replay: Literal[False] = False
    terminal_source_eligible: Literal[False] = False
    closure_eligible: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False

    @field_validator("attestation_id")
    @classmethod
    def _attestation_id(cls, value: str) -> str:
        return validate_canonical_uuid(value, field_name="attestation_id")

    @field_validator("evaluated_at", mode="before")
    @classmethod
    def _evaluated_at(cls, value: object) -> object:
        return _parse_aware_datetime(value, field_name="evaluated_at")

    @field_validator("policy_id", "corpus_id", "evaluator_key_id")
    @classmethod
    def _identifier(cls, value: str, info: Any) -> str:
        return validate_identifier(value, field_name=info.field_name, max_length=120)

    @field_validator(
        "schema_version",
        "holdout_session_count",
        "exact_match_count",
        "unknown_prediction_count",
        "accuracy_ppm",
        "visual_frame_count",
        "visual_candidate_comparison_count",
        mode="before",
    )
    @classmethod
    def _strict_integer(cls, value: object, info: Any) -> object:
        if type(value) is not int:
            raise ValueError(f"{info.field_name} must be an integer")
        return value

    @field_validator(
        "per_sample_results_included",
        "oracle_labels_disclosed",
        "evaluator_host_isolation_verified",
        "image_model_execution_verified",
        "live_dispatch_allowed",
        "safe_for_live_replay",
        "terminal_source_eligible",
        "closure_eligible",
        "knowledge_publication_allowed",
        mode="before",
    )
    @classmethod
    def _strict_false_flag(cls, value: object, info: Any) -> object:
        if value is not False:
            raise ValueError(f"{info.field_name} must be boolean false")
        return value

    @model_validator(mode="after")
    def _aggregate_arithmetic(self) -> HoldoutEvalAggregate:
        if self.exact_match_count > self.holdout_session_count:
            raise ValueError("exact matches cannot exceed the holdout count")
        if self.unknown_prediction_count > self.holdout_session_count:
            raise ValueError("unknown predictions cannot exceed the holdout count")
        if self.accuracy_ppm != _accuracy_ppm(
            self.exact_match_count, self.holdout_session_count
        ):
            raise ValueError("aggregate accuracy is inconsistent with exact matches")
        return self


class SignedHoldoutEvalAttestation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    payload: HoldoutEvalAggregate
    signature_algorithm: Literal["ed25519"] = "ed25519"
    signature_base64: str

    @field_validator("signature_base64")
    @classmethod
    def _signature(cls, value: str) -> str:
        _decode_base64_exact(value, expected_size=64, label="Ed25519 signature")
        return value


class HoldoutSubmissionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["valid"] = "valid"
    submission_sha256: str = Field(pattern=SHA256_PATTERN)
    submission_id: str
    corpus_id: str
    catalog_sha256: str = Field(pattern=SHA256_PATTERN)
    prediction_count: int = Field(ge=1)
    image_model_exercised_claimed: StrictBool
    oracle_accessed: Literal[False] = False
    oracle_labels_included: Literal[False] = False
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    independent_eval_ready: Literal[False] = False


class HoldoutAttestationVerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["valid"] = "valid"
    submission_sha256: str = Field(pattern=SHA256_PATTERN)
    trust_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    policy_id: str
    attestation_id: str
    corpus_id: str
    catalog_sha256: str = Field(pattern=SHA256_PATTERN)
    evaluator_key_id: str
    signature_valid: Literal[True] = True
    trust_policy_valid: Literal[True] = True
    aggregate_consistent: Literal[True] = True
    external_evaluator_attestation_verified: Literal[True] = True
    holdout_oracle_integrity_verified: Literal[True] = True
    holdout_oracle_verified: Literal[True] = True
    single_submission_budget_enforced: Literal[True] = True
    visual_near_duplicate_checked: Literal[True]
    visual_near_duplicate_algorithm: Literal["sanmou-multisignal-v1"]
    visual_frame_count: int = Field(ge=1)
    visual_candidate_comparison_count: int = Field(ge=0)
    oracle_labels_disclosed: Literal[False] = False
    evaluator_host_isolation_verified: Literal[False] = False
    image_model_execution_verified: Literal[False] = False
    holdout_session_count: int = Field(ge=1)
    exact_match_count: int = Field(ge=0)
    unknown_prediction_count: int = Field(ge=0)
    accuracy_ppm: int = Field(ge=0, le=ACCURACY_SCALE)
    passed_policy: StrictBool
    independent_eval_ready: Literal[False] = False
    remaining_blockers: list[str]
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    safe_for_live_replay: Literal[False] = False
    manual_promotion_required: Literal[True] = True
    terminal_source_eligible: Literal[False] = False
    closure_eligible: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False


@dataclass(frozen=True)
class LoadedEvalArtifact:
    path: Path
    sha256: str
    artifact: BaseModel


@dataclass(frozen=True)
class _ExpectedHoldout:
    dataset_id: str
    session_id: str
    source_events_sha256: str
    evaluation_input_sha256: str
    expected_outcome: CountableOutcome
    annotation_reviewed_at: datetime


ModelT = TypeVar("ModelT", bound=BaseModel)


def load_holdout_submission(path: Path) -> LoadedEvalArtifact:
    return _load_eval_artifact(
        path, HoldoutPredictionSubmission, label="holdout prediction submission"
    )


def load_holdout_oracle(path: Path) -> LoadedEvalArtifact:
    return _load_eval_artifact(path, HoldoutOracle, label="holdout oracle")


def load_evaluator_trust_policy(path: Path) -> LoadedEvalArtifact:
    return _load_eval_artifact(
        path, EvaluatorTrustPolicy, label="evaluator trust policy"
    )


def load_holdout_attestation(path: Path) -> LoadedEvalArtifact:
    return _load_eval_artifact(
        path, SignedHoldoutEvalAttestation, label="holdout eval attestation"
    )


def summarize_holdout_submission(path: Path) -> HoldoutSubmissionSummary:
    loaded = load_holdout_submission(path)
    submission = _as_model(loaded, HoldoutPredictionSubmission)
    return HoldoutSubmissionSummary(
        submission_sha256=loaded.sha256,
        submission_id=submission.submission_id,
        corpus_id=submission.corpus_id,
        catalog_sha256=submission.catalog_sha256,
        prediction_count=len(submission.predictions),
        image_model_exercised_claimed=submission.image_model_exercised_claimed,
    )


def score_holdout_submission_external(
    *,
    submission_path: Path,
    oracle_path: Path,
    trust_policy_path: Path,
    private_key_path: Path,
    catalog_path: Path,
    registries_root: Path,
    sessions_root: Path,
    reviews_root: Path,
    artifacts_root: Path,
    evaluator_state_root: Path,
    attestation_id: str,
    now: datetime | None = None,
) -> SignedHoldoutEvalAttestation:
    """Score inside the external evaluator and return aggregate-only evidence."""

    checked_at = _aware_utc(now or datetime.now(UTC), field_name="evaluation time")
    loaded_submission = load_holdout_submission(submission_path)
    submission = _as_model(loaded_submission, HoldoutPredictionSubmission)
    oracle = _as_model(load_holdout_oracle(oracle_path), HoldoutOracle)
    loaded_policy = load_evaluator_trust_policy(trust_policy_path)
    policy = _as_model(loaded_policy, EvaluatorTrustPolicy)
    _validate_policy_time(policy, checked_at)
    audited_corpus = audit_corpus_catalog_bundle(
        catalog_path,
        registries_root=registries_root,
        sessions_root=sessions_root,
        reviews_root=reviews_root,
        artifacts_root=artifacts_root,
    )
    if not audited_corpus.report.coverage_ready:
        raise ValueError("external holdout evaluation requires frozen coverage-ready data")
    _validate_common_bindings(
        submission=submission,
        oracle=oracle,
        policy=policy,
        audited_corpus=audited_corpus,
    )
    if submission.created_at > checked_at or oracle.reviewed_at > checked_at:
        raise ValueError("evaluation inputs cannot be dated after the evaluation")
    expected = _expected_holdout_inventory(audited_corpus)
    _validate_oracle(expected, oracle)
    _validate_submission(expected, submission)

    private_key = _load_private_key(private_key_path)
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    trusted_public_key = _decode_base64_exact(
        policy.ed25519_public_key_base64,
        expected_size=32,
        label="Ed25519 public key",
    )
    if public_key_bytes != trusted_public_key:
        raise ValueError("evaluator private key does not match the trust policy")

    checked_attestation_id = validate_canonical_uuid(
        attestation_id, field_name="attestation_id"
    )
    _claim_evaluation_budget(
        evaluator_state_root=evaluator_state_root,
        policy=policy,
        policy_sha256=loaded_policy.sha256,
        submission_sha256=loaded_submission.sha256,
        attestation_id=checked_attestation_id,
        claimed_at=checked_at,
    )

    oracle_by_key = {
        (entry.dataset_id, entry.session_id): entry for entry in oracle.entries
    }
    exact_matches = 0
    unknown_predictions = 0
    for prediction in submission.predictions:
        expected_entry = oracle_by_key[(prediction.dataset_id, prediction.session_id)]
        if prediction.predicted_outcome == "unknown":
            unknown_predictions += 1
        if prediction.predicted_outcome == expected_entry.expected_outcome:
            exact_matches += 1
    holdout_count = len(submission.predictions)
    accuracy_ppm = _accuracy_ppm(exact_matches, holdout_count)
    passed_policy = (
        holdout_count >= policy.minimum_holdout_count
        and accuracy_ppm >= policy.minimum_accuracy_ppm
        and unknown_predictions <= policy.maximum_unknown_count
    )
    aggregate = HoldoutEvalAggregate(
        attestation_id=checked_attestation_id,
        submission_sha256=loaded_submission.sha256,
        trust_policy_sha256=loaded_policy.sha256,
        policy_id=policy.policy_id,
        corpus_id=submission.corpus_id,
        catalog_sha256=submission.catalog_sha256,
        evaluator_key_id=policy.evaluator_key_id,
        evaluated_at=checked_at,
        holdout_session_count=holdout_count,
        exact_match_count=exact_matches,
        unknown_prediction_count=unknown_predictions,
        accuracy_ppm=accuracy_ppm,
        passed_policy=passed_policy,
        visual_near_duplicate_checked=(
            audited_corpus.report.visual_near_duplicate_checked
        ),
        visual_near_duplicate_algorithm=(
            audited_corpus.report.visual_near_duplicate_algorithm
        ),
        visual_frame_count=audited_corpus.report.visual_frame_count,
        visual_candidate_comparison_count=(
            audited_corpus.report.visual_candidate_comparison_count
        ),
    )
    signature = private_key.sign(_canonical_model_bytes(aggregate))
    return SignedHoldoutEvalAttestation(
        payload=aggregate,
        signature_base64=base64.b64encode(signature).decode("ascii"),
    )


def verify_holdout_attestation(
    *,
    submission_path: Path,
    attestation_path: Path,
    trust_policy_path: Path,
    now: datetime | None = None,
) -> HoldoutAttestationVerificationReport:
    """Verify aggregate external evidence without opening an oracle."""

    checked_at = _aware_utc(now or datetime.now(UTC), field_name="verification time")
    loaded_submission = load_holdout_submission(submission_path)
    submission = _as_model(loaded_submission, HoldoutPredictionSubmission)
    attestation = _as_model(
        load_holdout_attestation(attestation_path), SignedHoldoutEvalAttestation
    )
    loaded_policy = load_evaluator_trust_policy(trust_policy_path)
    policy = _as_model(loaded_policy, EvaluatorTrustPolicy)
    _validate_policy_time(policy, checked_at)
    payload = attestation.payload
    _validate_policy_time(policy, payload.evaluated_at)
    if payload.evaluated_at < submission.created_at or payload.evaluated_at > checked_at:
        raise ValueError("attestation evaluation time is inconsistent")
    if payload.submission_sha256 != loaded_submission.sha256:
        raise ValueError("attestation does not bind the exact submission")
    if (
        payload.trust_policy_sha256 != loaded_policy.sha256
        or payload.policy_id != policy.policy_id
    ):
        raise ValueError("attestation does not bind the exact trust policy")
    if (
        payload.corpus_id != submission.corpus_id
        or payload.catalog_sha256 != submission.catalog_sha256
        or policy.corpus_id != submission.corpus_id
        or policy.catalog_sha256 != submission.catalog_sha256
    ):
        raise ValueError("attestation, submission, and trust policy disagree")
    if payload.evaluator_key_id != policy.evaluator_key_id:
        raise ValueError("attestation evaluator key is not trusted")
    if payload.holdout_session_count != len(submission.predictions):
        raise ValueError("attestation holdout count does not match the submission")
    expected_pass = (
        payload.holdout_session_count >= policy.minimum_holdout_count
        and payload.accuracy_ppm >= policy.minimum_accuracy_ppm
        and payload.unknown_prediction_count <= policy.maximum_unknown_count
    )
    if payload.passed_policy is not expected_pass:
        raise ValueError("attestation pass verdict conflicts with the trust policy")

    public_key_bytes = _decode_base64_exact(
        policy.ed25519_public_key_base64,
        expected_size=32,
        label="Ed25519 public key",
    )
    signature = _decode_base64_exact(
        attestation.signature_base64,
        expected_size=64,
        label="Ed25519 signature",
    )
    try:
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(
            signature, _canonical_model_bytes(payload)
        )
    except InvalidSignature as exc:
        raise ValueError("holdout attestation signature is invalid") from exc

    return HoldoutAttestationVerificationReport(
        submission_sha256=loaded_submission.sha256,
        trust_policy_sha256=loaded_policy.sha256,
        policy_id=policy.policy_id,
        attestation_id=payload.attestation_id,
        corpus_id=payload.corpus_id,
        catalog_sha256=payload.catalog_sha256,
        evaluator_key_id=payload.evaluator_key_id,
        holdout_session_count=payload.holdout_session_count,
        exact_match_count=payload.exact_match_count,
        unknown_prediction_count=payload.unknown_prediction_count,
        accuracy_ppm=payload.accuracy_ppm,
        passed_policy=payload.passed_policy,
        visual_near_duplicate_checked=payload.visual_near_duplicate_checked,
        visual_near_duplicate_algorithm=payload.visual_near_duplicate_algorithm,
        visual_frame_count=payload.visual_frame_count,
        visual_candidate_comparison_count=(
            payload.visual_candidate_comparison_count
        ),
        remaining_blockers=(
            ([] if payload.passed_policy else ["holdout_accuracy_policy_not_met"])
            + [
                "evaluator_host_isolation_not_machine_verified",
                "human_capture_provenance_unverified",
                "structured_start_state_unverified",
                "filesystem_parent_walk_not_handle_pinned",
                "image_model_execution_unverified",
            ]
        ),
    )


def write_attestation_once(
    path: Path, attestation: SignedHoldoutEvalAttestation
) -> None:
    """Create one aggregate attestation without overwriting an existing file."""

    payload = (
        json.dumps(
            attestation.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    if len(payload) > MAX_EVAL_ARTIFACT_BYTES:
        raise ValueError("attestation exceeds the fixed size limit")
    _write_bytes_once(path, payload, label="attestation output")


def _claim_evaluation_budget(
    *,
    evaluator_state_root: Path,
    policy: EvaluatorTrustPolicy,
    policy_sha256: str,
    submission_sha256: str,
    attestation_id: str,
    claimed_at: datetime,
) -> None:
    reject_linked_path_components(
        evaluator_state_root, label="evaluator state root"
    )
    if not evaluator_state_root.is_dir():
        raise ValueError("evaluator state root must be a directory")
    scope_digest = hashlib.sha256(
        (
            policy.evaluator_key_id
            + "\0"
            + policy.catalog_sha256
            + "\0single-submission-v1"
        ).encode("utf-8")
    ).hexdigest()
    ledger_path = evaluator_state_root / f"{scope_digest}.json"
    ledger = {
        "schema_version": 1,
        "artifact_type": "record_replay_holdout_release_budget_claim",
        "policy_id": policy.policy_id,
        "trust_policy_sha256": policy_sha256,
        "catalog_sha256": policy.catalog_sha256,
        "submission_sha256": submission_sha256,
        "attestation_id": attestation_id,
        "claimed_at": claimed_at.isoformat(),
        "maximum_signed_submissions_per_catalog": 1,
        "oracle_labels_disclosed": False,
        "execution_authority": "none",
    }
    payload = (
        json.dumps(
            ledger,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    try:
        _write_bytes_once(ledger_path, payload, label="evaluation budget claim")
    except ValueError as exc:
        raise ValueError(
            "evaluation budget already consumed for this policy and catalog"
        ) from exc


def _write_bytes_once(path: Path, payload: bytes, *, label: str) -> None:
    parent = path.parent
    reject_linked_path_components(parent, label=f"{label} parent")
    if not parent.is_dir():
        raise ValueError(f"{label} parent must be a directory")
    if path.exists() or path.is_symlink():
        raise ValueError(f"{label} already exists")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise ValueError(f"{label} could not be created") from exc
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"short {label} write")
            view = view[written:]
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size != len(payload)
        ):
            raise OSError(f"{label} output identity changed")
    except OSError as exc:
        os.close(descriptor)
        descriptor = -1
        try:
            path.unlink()
        except OSError:
            pass
        raise ValueError(f"{label} write failed") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    try:
        current = os.stat(path, follow_symlinks=False)
    except OSError as exc:
        raise ValueError(f"{label} path changed after creation") from exc
    if (
        not stat.S_ISREG(current.st_mode)
        or current.st_nlink != 1
        or current.st_size != len(payload)
        or current.st_dev != metadata.st_dev
        or current.st_ino != metadata.st_ino
    ):
        raise ValueError(f"{label} path changed after creation")
    if os.name != "nt" and hasattr(os, "O_DIRECTORY"):
        try:
            directory_descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except OSError as exc:
            raise ValueError(f"{label} directory sync failed") from exc


def evaluation_input_sha256(
    *,
    session_id: str,
    source_events_sha256: str,
    encoded_frame_sha256s: tuple[str, ...],
) -> str:
    """Hash only unlabeled immutable inputs shared with the predictor."""

    value = {
        "schema_version": 1,
        "session_id": session_id,
        "source_events_sha256": source_events_sha256,
        "encoded_frame_sha256s": list(encoded_frame_sha256s),
    }
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _expected_holdout_inventory(
    audited_corpus: AuditedCorpusCatalog,
) -> dict[tuple[str, str], _ExpectedHoldout]:
    expected: dict[tuple[str, str], _ExpectedHoldout] = {}
    for audited_registry in audited_corpus.audited_registries:
        dataset_id = audited_registry.loaded_registry.registry.dataset_id
        for identity in audited_registry.session_identities:
            if identity.split != "holdout":
                continue
            outcome = identity.expected_transition_outcome
            if outcome is None or outcome == TransitionOutcome.UNKNOWN:
                continue
            if outcome.value not in {
                "applied",
                "no_change",
                "ambiguous",
                "interrupted",
            }:
                raise ValueError("holdout annotation has a non-countable outcome")
            item = _ExpectedHoldout(
                dataset_id=dataset_id,
                session_id=identity.session_id,
                source_events_sha256=identity.source_events_sha256,
                evaluation_input_sha256=evaluation_input_sha256(
                    session_id=identity.session_id,
                    source_events_sha256=identity.source_events_sha256,
                    encoded_frame_sha256s=identity.encoded_frame_sha256s,
                ),
                expected_outcome=outcome.value,
                annotation_reviewed_at=identity.annotation_reviewed_at,
            )
            key = (dataset_id, identity.session_id)
            if key in expected:
                raise ValueError("holdout inventory contains a duplicate key")
            expected[key] = item
    if not expected:
        raise ValueError("corpus has no countable holdout sessions")
    return expected


def _validate_common_bindings(
    *,
    submission: HoldoutPredictionSubmission,
    oracle: HoldoutOracle,
    policy: EvaluatorTrustPolicy,
    audited_corpus: AuditedCorpusCatalog,
) -> None:
    catalog_sha256 = audited_corpus.loaded_catalog.sha256
    corpus_id = audited_corpus.loaded_catalog.catalog.corpus_id
    if any(
        value != catalog_sha256
        for value in (
            submission.catalog_sha256,
            oracle.catalog_sha256,
            policy.catalog_sha256,
        )
    ):
        raise ValueError("evaluation artifacts do not bind the audited catalog")
    if any(
        value != corpus_id
        for value in (submission.corpus_id, oracle.corpus_id, policy.corpus_id)
    ):
        raise ValueError("evaluation artifacts do not bind the audited corpus")


def _validate_oracle(
    expected: dict[tuple[str, str], _ExpectedHoldout],
    oracle: HoldoutOracle,
) -> None:
    latest_annotation_review = max(
        item.annotation_reviewed_at for item in expected.values()
    )
    if (
        oracle.created_at < latest_annotation_review
        or oracle.reviewed_at < latest_annotation_review
    ):
        raise ValueError("oracle predates an approved holdout annotation review")
    entries = {(entry.dataset_id, entry.session_id): entry for entry in oracle.entries}
    if set(entries) != set(expected):
        raise ValueError("oracle does not contain exactly the countable holdout set")
    for key, expected_item in expected.items():
        entry = entries[key]
        if (
            entry.source_events_sha256 != expected_item.source_events_sha256
            or entry.evaluation_input_sha256
            != expected_item.evaluation_input_sha256
            or entry.expected_outcome != expected_item.expected_outcome
        ):
            raise ValueError("oracle disagrees with approved holdout evidence")


def _validate_submission(
    expected: dict[tuple[str, str], _ExpectedHoldout],
    submission: HoldoutPredictionSubmission,
) -> None:
    predictions = {
        (prediction.dataset_id, prediction.session_id): prediction
        for prediction in submission.predictions
    }
    if set(predictions) != set(expected):
        raise ValueError("submission does not contain exactly the countable holdout set")
    for key, expected_item in expected.items():
        prediction = predictions[key]
        if (
            prediction.source_events_sha256 != expected_item.source_events_sha256
            or prediction.evaluation_input_sha256
            != expected_item.evaluation_input_sha256
        ):
            raise ValueError("submission does not bind the immutable holdout input")


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    if os.name != "nt":
        try:
            permissions = os.stat(path, follow_symlinks=False).st_mode & 0o777
        except OSError as exc:
            raise ValueError("evaluator private key is unreadable") from exc
        if permissions & 0o077:
            raise ValueError("evaluator private key must not be group/world accessible")
    read = read_bounded_regular_file(
        path, max_bytes=MAX_PRIVATE_KEY_BYTES, label="evaluator private key"
    )
    try:
        key = serialization.load_pem_private_key(read.payload, password=None)
    except (TypeError, ValueError) as exc:
        raise ValueError("evaluator private key is invalid") from exc
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("evaluator private key must be Ed25519")
    return key


def _load_eval_artifact(
    path: Path, model_type: type[ModelT], *, label: str
) -> LoadedEvalArtifact:
    read = read_bounded_regular_file(
        path, max_bytes=MAX_EVAL_ARTIFACT_BYTES, label=label
    )
    try:
        value = load_strict_json_bytes(read.payload)
        artifact = model_type.model_validate(value)
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        raise ValueError(f"{label} is invalid") from exc
    return LoadedEvalArtifact(
        path=path.resolve(strict=True),
        sha256=read.identity.sha256,
        artifact=artifact,
    )


def _as_model(loaded: LoadedEvalArtifact, model_type: type[ModelT]) -> ModelT:
    if not isinstance(loaded.artifact, model_type):
        raise TypeError("loaded evaluation artifact has an unexpected type")
    return loaded.artifact


def _validate_policy_time(policy: EvaluatorTrustPolicy, checked_at: datetime) -> None:
    if not policy.valid_from <= checked_at <= policy.valid_until:
        raise ValueError("evaluator trust policy is not valid at this time")
    if policy.approved_at > checked_at:
        raise ValueError("evaluator trust policy approval is in the future")


def _aware_utc(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(UTC)


def _parse_aware_datetime(value: object, *, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO-8601 datetime") from exc
    else:
        raise ValueError(f"{field_name} must be an ISO-8601 datetime")
    return _aware_utc(parsed, field_name=field_name)


def _decode_base64_exact(value: str, *, expected_size: int, label: str) -> bytes:
    if not isinstance(value, str) or not value or any(character.isspace() for character in value):
        raise ValueError(f"{label} must be canonical base64")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{label} must be canonical base64") from exc
    if len(decoded) != expected_size or base64.b64encode(decoded).decode("ascii") != value:
        raise ValueError(f"{label} has an invalid size or encoding")
    return decoded


def _accuracy_ppm(exact_matches: int, total: int) -> int:
    if total <= 0:
        raise ValueError("holdout total must be positive")
    return (exact_matches * ACCURACY_SCALE + total // 2) // total


def _canonical_model_bytes(model: BaseModel) -> bytes:
    return _canonical_json_bytes(model.model_dump(mode="json"))


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
