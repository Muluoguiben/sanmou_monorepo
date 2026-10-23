"""Immutable DTOs for MS0 v4 section 8, independent of runtime storage.

Artifact metadata and settled rewards come from the trusted Harness boundary.
This module checks structure and token layout, not the truth of game outcomes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Name = Annotated[str, Field(min_length=1, pattern=r"\S")]
Index = Annotated[int, Field(ge=0)]
Bit = Annotated[int, Field(ge=0, le=1)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ProjectionVersion = Literal["ppo-token-gae-v1"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, allow_inf_nan=False,
        revalidate_instances="always",
    )

    def digest(self) -> str:
        raw = json.dumps(self.model_dump(mode="json"), sort_keys=True,
                         separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ArtifactRef(FrozenModel):
    artifact_id: Name
    sha256: Digest
    byte_length: Index
    ready: bool = True


class BatchIdentity(FrozenModel):
    role_session_id: Name
    episode_id: Name
    learning_segment_id: Name
    batch_id: Name
    behavior_policy_revision: Name
    critic_revision: Name
    reference_revision: Name
    tokenizer_revision: Name
    template_revision: Name
    sampling_revision: Name


class TokenArtifact(FrozenModel):
    """Exact dense input/response layout supplied by the captured invocation.

``response_token_ids`` retains masked tool, environment and padding slots.
The actor and critic must consume this same layout. Critic outputs are indexed
by dense sequence position; a sampled token reads the last attended *earlier*
position. No context concatenation or tokenization happens here.
"""
    artifact_ref: ArtifactRef
    input_token_ids: tuple[Index, ...] = Field(min_length=1)
    response_token_ids: tuple[Index, ...]
    attention_mask: tuple[Bit, ...]
    position_ids: tuple[Index, ...]
    response_origins: tuple[Literal["policy", "tool", "environment", "template", "padding"], ...]
    policy_token_mask: tuple[Bit, ...]
    value_alignment_version: Literal["dense-last-attended-prefix-v1"] = "dense-last-attended-prefix-v1"

    @model_validator(mode="after")
    def valid_layout(self):
        n = len(self.response_token_ids)
        size = len(self.input_token_ids) + n
        if len(self.attention_mask) != size or len(self.position_ids) != size:
            raise ValueError("attention and position IDs must match the actual dense sequence")
        if len(self.response_origins) != n or len(self.policy_token_mask) != n:
            raise ValueError("origins and policy mask must match response slots")
        for j, (origin, mask) in enumerate(zip(self.response_origins, self.policy_token_mask)):
            attended = self.attention_mask[len(self.input_token_ids) + j]
            if mask != int(origin == "policy"):
                raise ValueError("every actually sampled policy token, and only it, must be masked in")
            if origin == "padding" and attended != 0:
                raise ValueError("padding must not be attended")
            if origin != "padding" and attended != 1:
                raise ValueError("non-padding response slots must be attended")
            if mask and not any(self.attention_mask[:len(self.input_token_ids) + j]):
                raise ValueError("a sampled token requires an attended earlier prefix")
        return self

    def pre_token_index(self, response_index: int) -> int:
        if not 0 <= response_index < len(self.response_token_ids):
            raise ValueError("response index out of range")
        if self.policy_token_mask[response_index] != 1:
            raise ValueError("masked slots have no policy pre-token value")
        stop = len(self.input_token_ids) + response_index
        return max(i for i in range(stop) if self.attention_mask[i] == 1)


class PolicyStepProjection(FrozenModel):
    projection_version: ProjectionVersion = "ppo-token-gae-v1"
    identity: BatchIdentity
    decision_id: Name
    invocation_id: Name
    decision_index: Index
    row_index: Index
    context_artifact: ArtifactRef
    context_origin: Literal["captured_runtime_context"] = "captured_runtime_context"
    tokens: TokenArtifact | None
    # Distribution provenance is explicit; Reference is never old-policy.
    probability_kind: Literal["behavior_sampling_distribution"] = "behavior_sampling_distribution"
    old_logprobs: tuple[float | None, ...] | None
    reference_logprobs: tuple[float | None, ...] | None = None
    critic_outputs: tuple[float, ...] | None
    pre_token_value_indices: tuple[Index | None, ...] | None

    @model_validator(mode="after")
    def aligned_arrays(self):
        if self.tokens is None:
            if any(v is not None for v in (self.old_logprobs, self.reference_logprobs,
                                          self.critic_outputs, self.pre_token_value_indices)):
                raise ValueError("values and probabilities require the original token artifact")
            return self
        n = len(self.tokens.response_token_ids)
        for values in (self.old_logprobs, self.reference_logprobs, self.pre_token_value_indices):
            if values is not None and len(values) != n:
                raise ValueError("response arrays must have exactly the response slot length")
        if self.critic_outputs is not None and len(self.critic_outputs) != len(self.tokens.attention_mask):
            raise ValueError("critic outputs must match the actual dense token layout")
        for j, mask in enumerate(self.tokens.policy_token_mask):
            for probabilities in (self.old_logprobs, self.reference_logprobs):
                if probabilities is not None:
                    if (probabilities[j] is not None) != bool(mask):
                        raise ValueError("probabilities exist exactly at policy token positions")
                    if probabilities[j] is not None and probabilities[j] > 0:
                        raise ValueError("log probabilities must not be positive")
            if self.pre_token_value_indices is not None:
                expected = self.tokens.pre_token_index(j) if mask else None
                if self.pre_token_value_indices[j] != expected:
                    raise ValueError("value must come from the attended prefix before this token")
        return self


class RewardCounts(FrozenModel):
    success: Bit = 0
    invalid: Index = 0
    duplicate: Index = 0

    @property
    def score(self) -> float:
        return self.success - 0.1 * min(self.invalid / 5, 1) - 0.1 * min(self.duplicate / 5, 1)


class RewardEvent(FrozenModel):
    event_id: Name
    role_session_id: Name
    episode_id: Name
    learning_segment_id: Name
    decision_id: Name
    invocation_id: Name
    decision_index: Index
    delta_success: Bit = 0
    delta_invalid: Bit = 0
    delta_duplicate: Bit = 0
    settled: bool = True
    policy_attributed: bool = True


class EventDigest(FrozenModel):
    event_id: Name
    sha256: Digest


class RewardPrefix(FrozenModel):
    """Sealed previous projection receipt; counts do not reset at segmentation.

The source digest is verified by the caller's artifact store before use. This
CPU projection is not a replacement for that store or RewardRecorder.
"""
    role_session_id: Name
    episode_id: Name
    next_decision_index: Index
    counts: RewardCounts
    events: tuple[EventDigest, ...]
    source_projection_sha256: Digest
    continuation_allowed: bool

    @model_validator(mode="after")
    def unique_event_ids(self):
        if len({e.event_id for e in self.events}) != len(self.events):
            raise ValueError("reward prefix contains duplicate event identities")
        return self


EndReason = Literal[
    "task_success", "unreachable", "policy_failure", "task_budget_exhausted",
    "segment_limit", "infrastructure_interruption", "user_cancelled", "human_takeover",
    "recovery_takeover", "unknown_effect", "unknown_reward", "unknown_next_state", "open",
]


class BootstrapEvidence(FrozenModel):
    projection_kind: Literal["bootstrap_only"] = "bootstrap_only"
    identity: BatchIdentity
    end_reason: Literal["segment_limit", "infrastructure_interruption"]
    cutoff_decision_index: Index
    next_state_artifact: ArtifactRef
    next_observation_artifact: ArtifactRef
    next_context_artifact: ArtifactRef
    builder_version: Name
    source_cutoff: Name
    value: float
    effects_verified: bool
    rewards_settled: bool


class ProjectionRequest(FrozenModel):
    projection_version: ProjectionVersion = "ppo-token-gae-v1"
    identity: BatchIdentity
    steps: tuple[PolicyStepProjection, ...]
    reward_events: tuple[RewardEvent, ...] = ()
    reward_revision: Name
    rewards_complete: bool
    end_reason: EndReason
    prefix: RewardPrefix | None = None
    bootstrap: BootstrapEvidence | None = None
    gamma: float = Field(default=1.0, ge=0, le=1)
    gae_lambda: float = Field(default=1.0, ge=0, le=1)
    normalize_actor: bool = False


class TokenRef(FrozenModel):
    row_index: Index
    response_index: Index
    decision_id: Name
    invocation_id: Name


class EventTokenMapping(FrozenModel):
    event_id: Name
    token: TokenRef


class TokenChainManifest(FrozenModel):
    projection_version: ProjectionVersion = "ppo-token-gae-v1"
    advantage_timebase: Literal["policy_token"] = "policy_token"
    identity: BatchIdentity
    source_projection_sha256: Digest
    oracle_version: Literal["ms0-v4-g1-g6"] = "ms0-v4-g1-g6"
    value_alignment_version: Literal["dense-last-attended-prefix-v1"] = "dense-last-attended-prefix-v1"
    reward_revision: Name
    row_projection_sha256: tuple[Digest, ...]
    tokens: tuple[TokenRef, ...]
    successors: tuple[Index | None, ...]
    boundary_reasons: tuple[str, ...]
    rewards: tuple[float, ...]
    values: tuple[float, ...]
    bootstrap_mask: tuple[Bit, ...]
    continuation_mask: tuple[Bit, ...]
    bootstrap_value: float | None
    gamma: float = Field(ge=0, le=1)
    gae_lambda: float = Field(ge=0, le=1)
    event_to_token: tuple[EventTokenMapping, ...]
    # A numeric projection never claims the eventual verl worker has passed G6.
    verl_hook_status: Literal["not_validated"] = "not_validated"
    ms5_ready: Literal[False] = False

    @model_validator(mode="after")
    def valid_chain(self):
        n = len(self.tokens)
        if n == 0 or any(len(v) != n for v in (
            self.successors, self.boundary_reasons, self.rewards, self.values,
            self.bootstrap_mask, self.continuation_mask,
        )):
            raise ValueError("chain arrays must have identical nonzero lengths")
        if len({(t.row_index, t.response_index) for t in self.tokens}) != n:
            raise ValueError("a policy token may occur only once")
        if not self.row_projection_sha256 or any(t.row_index >= len(self.row_projection_sha256) for t in self.tokens):
            raise ValueError("every token must reference a sealed source row")
        coordinates = tuple((t.row_index, t.response_index) for t in self.tokens)
        if coordinates != tuple(sorted(coordinates)):
            raise ValueError("policy tokens must remain in actual row/token order")
        if len({e.event_id for e in self.event_to_token}) != len(self.event_to_token):
            raise ValueError("each reward event has exactly one token owner")
        if any(e.token not in self.tokens for e in self.event_to_token):
            raise ValueError("reward owner must be an effective policy token")
        for i in range(n - 1):
            if self.successors[i] != i + 1 or (self.bootstrap_mask[i], self.continuation_mask[i]) != (1, 1):
                raise ValueError("internal chain must continue to exactly the next token")
        if self.successors[-1] is not None or self.continuation_mask[-1] != 0:
            raise ValueError("last token cannot recurse outside the learning segment")
        if bool(self.bootstrap_mask[-1]) != (self.bootstrap_value is not None):
            raise ValueError("last value mask and bootstrap evidence must agree")
        return self


class AdvantageBatch(FrozenModel):
    projection_version: ProjectionVersion = "ppo-token-gae-v1"
    manifest_sha256: Digest
    raw_advantages: tuple[float, ...]
    returns: tuple[float, ...]
    actor_advantages: tuple[float, ...]
    normalization_count: Literal[0, 1]
    advantages_computed: Literal[True] = True
    eligible: Literal[True] = True
    oracle_version: Literal["ms0-v4-g1-g6"] = "ms0-v4-g1-g6"

    @model_validator(mode="after")
    def same_lengths(self):
        if not self.returns or len(self.raw_advantages) != len(self.returns) or len(self.actor_advantages) != len(self.returns):
            raise ValueError("advantage arrays must have identical nonzero lengths")
        return self


class AdvantageRow(FrozenModel):
    row_index: Index
    policy_token_mask: tuple[Bit, ...]
    rewards: tuple[float, ...]
    raw_advantages: tuple[float, ...]
    returns: tuple[float, ...]
    actor_advantages: tuple[float, ...]

    @model_validator(mode="after")
    def masked_slots_are_zero(self):
        for values in (self.rewards, self.raw_advantages, self.returns, self.actor_advantages):
            if len(values) != len(self.policy_token_mask):
                raise ValueError("scattered arrays must match the row mask")
            if any(value != 0.0 for value, mask in zip(values, self.policy_token_mask) if mask == 0):
                raise ValueError("masked positions must have zero loss targets")
        return self


class ProjectionResult(FrozenModel):
    projection_version: ProjectionVersion = "ppo-token-gae-v1"
    source_projection_sha256: Digest
    eligible: bool
    reasons: tuple[str, ...]
    manifest: TokenChainManifest | None = None
    advantages: AdvantageBatch | None = None
    rows: tuple[AdvantageRow, ...] = ()
    next_prefix: RewardPrefix | None = None

    @model_validator(mode="after")
    def eligibility_matches_payload(self):
        has_targets = self.manifest is not None and self.advantages is not None and bool(self.rows)
        if self.eligible != has_targets or self.eligible == bool(self.reasons):
            raise ValueError("ineligible projections cannot contain training targets")
        if not self.eligible and any((self.manifest, self.advantages, self.rows, self.next_prefix)):
            raise ValueError("ineligible segments have no targets or authoritative prefix")
        return self
