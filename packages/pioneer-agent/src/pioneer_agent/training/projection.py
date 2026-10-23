"""Build the MS0 training projection without loading models or touching storage."""
from __future__ import annotations

from .contracts import (
    EventDigest, EventTokenMapping, ProjectionRequest, ProjectionResult,
    RewardCounts, RewardPrefix, TokenChainManifest, TokenRef,
)
from .token_chain_gae import TokenChainGAE

TERMINAL_REASONS = frozenset({"task_success", "unreachable", "policy_failure", "task_budget_exhausted"})
TRUNCATION_REASONS = frozenset({"segment_limit", "infrastructure_interruption"})


class TrainingProjector:
    def build(self, request: ProjectionRequest) -> ProjectionResult:
        request = ProjectionRequest.model_validate(request)
        source_hash = request.digest()
        reasons: set[str] = set()
        identity = request.identity
        steps = request.steps
        if not steps:
            reasons.add("missing_decisions")
        if request.end_reason not in TERMINAL_REASONS | TRUNCATION_REASONS:
            reasons.add(f"ineligible_boundary:{request.end_reason}")
        if not request.rewards_complete:
            reasons.add("incomplete_reward_settlement")

        prefix = request.prefix
        start = prefix.next_decision_index if prefix else 0
        counts = prefix.counts if prefix else RewardCounts()
        prior_digests = {e.event_id: e.sha256 for e in prefix.events} if prefix else {}
        if prefix and (prefix.role_session_id, prefix.episode_id) != (identity.role_session_id, identity.episode_id):
            reasons.add("prefix_identity_mismatch")
        if prefix and prefix.next_decision_index == 0:
            reasons.add("prefix_not_before_segment")
        if prefix and not prefix.continuation_allowed:
            reasons.add("prefix_already_terminal")
        if steps and tuple(s.decision_index for s in steps) != tuple(range(start, start + len(steps))):
            reasons.add("missing_or_reordered_decision")
        if tuple(s.row_index for s in steps) != tuple(range(len(steps))):
            reasons.add("row_order_mismatch")
        if len({s.decision_id for s in steps}) != len(steps) or len({s.invocation_id for s in steps}) != len(steps):
            reasons.add("duplicate_decision_or_invocation")

        token_refs: list[TokenRef] = []
        values: list[float] = []
        last_token_by_decision: dict[str, int] = {}
        by_decision = {s.decision_id: s for s in steps}
        for step in steps:
            if step.identity != identity:
                reasons.add("step_identity_or_frozen_version_mismatch")
            if not step.context_artifact.ready:
                reasons.add("context_artifact_not_ready")
            if step.tokens is None:
                reasons.add("missing_token_artifact")
                continue
            if not step.tokens.artifact_ref.ready:
                reasons.add("token_artifact_not_ready")
            if not any(step.tokens.policy_token_mask):
                reasons.add("zero_generated_tokens")
            if step.old_logprobs is None:
                reasons.add("missing_behavior_logprobs")
            if step.critic_outputs is None or step.pre_token_value_indices is None:
                reasons.add("missing_pre_token_values")
                continue
            for j, valid in enumerate(step.tokens.policy_token_mask):
                if not valid:
                    continue
                token_refs.append(TokenRef(row_index=step.row_index, response_index=j,
                                           decision_id=step.decision_id, invocation_id=step.invocation_id))
                index = step.pre_token_value_indices[j]
                # Validated against the actual token artifact by PolicyStepProjection.
                assert index is not None
                values.append(step.critic_outputs[index])
                last_token_by_decision[step.decision_id] = len(token_refs) - 1

        bootstrap_value = None
        bootstrap = request.bootstrap
        if request.end_reason in TRUNCATION_REASONS:
            if bootstrap is None:
                reasons.add("missing_bootstrap_evidence")
            else:
                if (bootstrap.identity != identity or bootstrap.end_reason != request.end_reason
                        or not steps or bootstrap.cutoff_decision_index != steps[-1].decision_index):
                    reasons.add("bootstrap_identity_or_cutoff_mismatch")
                if not bootstrap.effects_verified or not bootstrap.rewards_settled:
                    reasons.add("unverified_bootstrap_boundary")
                if not all(a.ready for a in (bootstrap.next_state_artifact,
                                            bootstrap.next_observation_artifact, bootstrap.next_context_artifact)):
                    reasons.add("bootstrap_artifact_not_ready")
                bootstrap_value = bootstrap.value
        elif bootstrap is not None:
            reasons.add("unexpected_bootstrap_evidence")

        # Deduplicate before canonical decision ordering. Arrival order has no
        # influence on reward ownership or cap accounting.
        unique = {}
        for event in request.reward_events:
            digest = event.digest()
            existing = prior_digests.get(event.event_id)
            if existing is None and event.event_id in unique:
                existing = unique[event.event_id].digest()
            if existing is not None:
                if existing != digest:
                    reasons.add("conflicting_reward_event_identity")
                continue
            unique[event.event_id] = event
            if not event.settled:
                reasons.add("pending_reward_event")
            if not event.policy_attributed:
                reasons.add("unattributed_reward_event")
            step = by_decision.get(event.decision_id)
            if (event.role_session_id, event.episode_id, event.learning_segment_id) != (
                identity.role_session_id, identity.episode_id, identity.learning_segment_id
            ):
                reasons.add("reward_identity_mismatch")
            if step is None or (event.invocation_id, event.decision_index) != (step.invocation_id, step.decision_index):
                reasons.add("reward_decision_or_invocation_mismatch")
            if event.decision_id not in last_token_by_decision:
                reasons.add("reward_without_policy_token")

        if reasons:
            return ProjectionResult(source_projection_sha256=source_hash, eligible=False, reasons=tuple(sorted(reasons)))

        rewards = [0.0] * len(token_refs)
        mappings = []
        invalid, duplicate, success = counts.invalid, counts.duplicate, counts.success
        previous_score = counts.score
        for step in steps:
            owned = sorted((e for e in unique.values() if e.decision_id == step.decision_id), key=lambda e: e.event_id)
            for event in owned:
                invalid += event.delta_invalid
                duplicate += event.delta_duplicate
                success += event.delta_success
                q = last_token_by_decision[step.decision_id]
                mappings.append(EventTokenMapping(event_id=event.event_id, token=token_refs[q]))
                prior_digests[event.event_id] = event.digest()
            if success > 1:
                return ProjectionResult(source_projection_sha256=source_hash, eligible=False,
                                        reasons=("success_already_settled",))
            current = RewardCounts(success=success, invalid=invalid, duplicate=duplicate)
            rewards[last_token_by_decision[step.decision_id]] = current.score - previous_score
            previous_score = current.score
        if (request.end_reason == "task_success") != bool(success):
            return ProjectionResult(source_projection_sha256=source_hash, eligible=False,
                                    reasons=("success_boundary_mismatch",))
        n = len(token_refs)
        manifest = TokenChainManifest(
            identity=identity, source_projection_sha256=source_hash,
            reward_revision=request.reward_revision, tokens=tuple(token_refs),
            row_projection_sha256=tuple(step.digest() for step in steps),
            successors=tuple(range(1, n)) + (None,),
            boundary_reasons=("continue",) * (n - 1) + (request.end_reason,),
            rewards=tuple(rewards), values=tuple(values),
            bootstrap_mask=(1,) * (n - 1) + (int(bootstrap_value is not None),),
            continuation_mask=(1,) * (n - 1) + (0,), bootstrap_value=bootstrap_value,
            gamma=request.gamma, gae_lambda=request.gae_lambda,
            event_to_token=tuple(mappings),
        )
        advantages = TokenChainGAE.compute(manifest, normalize_actor=request.normalize_actor)
        rows = TokenChainGAE.scatter(manifest, advantages, steps)
        next_prefix = RewardPrefix(
            role_session_id=identity.role_session_id, episode_id=identity.episode_id,
            next_decision_index=steps[-1].decision_index + 1,
            counts=RewardCounts(success=success, invalid=invalid, duplicate=duplicate),
            events=tuple(EventDigest(event_id=k, sha256=v) for k, v in sorted(prior_digests.items())),
            source_projection_sha256=source_hash,
            continuation_allowed=request.end_reason in TRUNCATION_REASONS,
        )
        return ProjectionResult(source_projection_sha256=source_hash, eligible=True, reasons=(),
                                manifest=manifest, advantages=advantages, rows=rows, next_prefix=next_prefix)
