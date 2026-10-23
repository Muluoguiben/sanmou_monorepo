"""CPU oracle and adversarial boundary tests for MS0 v4, no trainer claims."""
import json
import math
from pathlib import Path
import unittest

from pydantic import ValidationError

from pioneer_agent.training.contracts import (
    AdvantageBatch, ArtifactRef, BatchIdentity, BootstrapEvidence, PolicyStepProjection,
    ProjectionRequest, ProjectionResult, RewardCounts, RewardEvent, TokenArtifact,
)
from pioneer_agent.training import TokenChainGAE, TrainingProjector


ORACLES = json.loads((Path(__file__).parent / "fixtures/training/gae_oracles.json").read_text())


def replace(model, **updates):
    """Revalidate mutations; model_copy(update=...) intentionally bypasses validation."""
    return type(model).model_validate({**model.model_dump(), **updates})


def artifact(name):
    return ArtifactRef(artifact_id=name, sha256="a" * 64, byte_length=12)


def identity(**updates):
    values = dict(role_session_id="role-1", episode_id="episode-1", learning_segment_id="segment-1",
                  batch_id="batch-1", behavior_policy_revision="policy-1", critic_revision="critic-1",
                  reference_revision="reference-1", tokenizer_revision="tokenizer-1",
                  template_revision="template-1", sampling_revision="sampling-1")
    values.update(updates)
    return BatchIdentity(**values)


def step(index, values, *, row=None, ident=None, origins=None):
    ident = ident or identity()
    origins = origins if origins is not None else ("policy",) * len(values)
    tokens = TokenArtifact(
        artifact_ref=artifact(f"tokens-{index}"), input_token_ids=(100, 101),
        response_token_ids=tuple(range(200, 200 + len(origins))),
        attention_mask=(1, 1) + tuple(int(o != "padding") for o in origins),
        position_ids=tuple(range(2 + len(origins))), response_origins=origins,
        policy_token_mask=tuple(int(o == "policy") for o in origins),
    )
    # Non-prefix outputs deliberately differ greatly; using post-token values
    # instead of the declared actual prefixes must fail the numerical oracle.
    outputs = [1000.0] * len(tokens.attention_mask)
    indices = tuple(tokens.pre_token_index(j) if valid else None
                    for j, valid in enumerate(tokens.policy_token_mask))
    iterator = iter(values)
    for j in indices:
        if j is not None:
            outputs[j] = float(next(iterator))
    return PolicyStepProjection(
        identity=ident, decision_id=f"decision-{index}", invocation_id=f"invocation-{index}",
        decision_index=index, row_index=index if row is None else row,
        context_artifact=artifact(f"context-{index}"), tokens=tokens,
        old_logprobs=tuple(-0.5 if valid else None for valid in tokens.policy_token_mask),
        reference_logprobs=tuple(-0.7 if valid else None for valid in tokens.policy_token_mask),
        critic_outputs=tuple(outputs), pre_token_value_indices=indices,
    )


def event(index, *, name=None, invalid=0, duplicate=0, success=0, ident=None, **updates):
    ident = ident or identity()
    values = dict(event_id=name or f"event-{index}", role_session_id=ident.role_session_id,
                  episode_id=ident.episode_id, learning_segment_id=ident.learning_segment_id,
                  decision_id=f"decision-{index}", invocation_id=f"invocation-{index}",
                  decision_index=index, delta_invalid=invalid, delta_duplicate=duplicate,
                  delta_success=success)
    values.update(updates)
    return RewardEvent(**values)


def bootstrap(index, value=0.4, *, ident=None, end_reason="segment_limit", **updates):
    values = dict(identity=ident or identity(), end_reason=end_reason, cutoff_decision_index=index,
                  next_state_artifact=artifact("next-state"), next_observation_artifact=artifact("next-observation"),
                  next_context_artifact=artifact("next-context"), builder_version="builder-1",
                  source_cutoff=f"decision-{index}", value=value, effects_verified=True, rewards_settled=True)
    values.update(updates)
    return BootstrapEvidence(**values)


def request(steps, events=(), *, end_reason="task_success", **updates):
    values = dict(identity=identity(), steps=tuple(steps), reward_events=tuple(events),
                  reward_revision="rewards-1", rewards_complete=True, end_reason=end_reason)
    values.update(updates)
    return ProjectionRequest(**values)


class TrainingProjectionTests(unittest.TestCase):
    def setUp(self):
        self.projector = TrainingProjector()

    def assert_vector(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b, places=11)

    def assert_oracle(self, result, name):
        self.assertTrue(result.eligible, result.reasons)
        self.assert_vector(result.advantages.returns, ORACLES[name]["returns"])
        self.assert_vector(result.advantages.raw_advantages, ORACLES[name]["advantages"])
        self.assertFalse(result.manifest.ms5_ready)
        self.assertEqual(result.manifest.verl_hook_status, "not_validated")

    def assert_rejected(self, req, reason):
        result = self.projector.build(req)
        self.assertFalse(result.eligible)
        self.assertIn(reason, result.reasons)
        self.assertIsNone(result.advantages)
        self.assertIsNone(result.next_prefix)
        self.assertEqual(result.rows, ())
        return result

    def g1_request(self):
        return request([step(0, [0.2]), step(1, [0.3]), step(2, [0.4])],
                       [event(0, invalid=1), event(2, success=1)])

    def test_g1_cross_three_real_context_rows(self):
        req = self.g1_request()
        before = req.model_dump_json()
        result = self.projector.build(req)
        self.assert_oracle(result, "G1")
        self.assertEqual(result.manifest.successors, (1, 2, None))
        self.assertEqual(req.model_dump_json(), before)
        self.assertEqual(result.source_projection_sha256, req.digest())

    def test_g2_clean_truncation_and_actual_task_failure_are_distinct(self):
        steps = [step(0, [0.2]), step(1, [0.3])]
        events = [event(0, invalid=1)]
        truncated = self.projector.build(request(steps, events, end_reason="segment_limit", bootstrap=bootstrap(1)))
        self.assert_oracle(truncated, "G2_truncated")
        self.assertEqual(truncated.manifest.bootstrap_mask, (1, 1))
        self.assertEqual(truncated.manifest.continuation_mask, (1, 0))
        for reason in ("policy_failure", "unreachable", "task_budget_exhausted"):
            terminal = self.projector.build(request(steps, events, end_reason=reason))
            self.assert_oracle(terminal, "G2_terminal")
            self.assertEqual(terminal.manifest.bootstrap_mask, (1, 0))

    def test_g3_tool_success_is_on_last_policy_token(self):
        req = request([step(0, [0.1, 0.2]), step(1, [0.3], origins=("policy", "tool", "padding"))],
                      [event(0, invalid=1), event(1, success=1)])
        result = self.projector.build(req)
        self.assert_oracle(result, "G3")
        self.assert_vector(result.manifest.rewards, (0.0, -0.02, 1.0))
        self.assertEqual(result.rows[1].returns, (1.0, 0.0, 0.0))
        self.assertEqual(result.manifest.event_to_token[-1].token.response_index, 0)

    def test_g4_independent_penalty_caps_and_sixth_increment_zero(self):
        steps = [step(i, [0.0]) for i in range(6)]
        for field in ("invalid", "duplicate"):
            events = [event(i, **{field: 1}) for i in range(6)]
            result = self.projector.build(request(steps, events, end_reason="policy_failure"))
            self.assert_vector(result.manifest.rewards, ORACLES["G4"]["increments"])
        events = [event(i, invalid=1, duplicate=1, success=int(i == 5)) for i in range(6)]
        result = self.projector.build(request(steps, events))
        self.assertAlmostEqual(sum(result.manifest.rewards), ORACLES["G4"]["total"])
        self.assertEqual(result.next_prefix.counts, RewardCounts(success=1, invalid=6, duplicate=6))

    def test_g4_replayed_events_and_arrival_order_do_not_change_rewards(self):
        req = self.g1_request()
        first = self.projector.build(req)
        replay = self.projector.build(replace(req, reward_events=tuple(reversed(req.reward_events)) + req.reward_events))
        self.assertEqual(first.manifest.rewards, replay.manifest.rewards)
        self.assertEqual(first.manifest.event_to_token, replay.manifest.event_to_token)
        self.assertEqual(first.advantages.returns, replay.advantages.returns)
        self.assertEqual(first.next_prefix.counts, replay.next_prefix.counts)

    def test_g4_conflicting_event_identity_is_rejected(self):
        req = self.g1_request()
        conflict = replace(req.reward_events[0], delta_duplicate=1)
        self.assert_rejected(replace(req, reward_events=req.reward_events + (conflict,)), "conflicting_reward_event_identity")

    def test_g4_multiple_events_share_one_increment_not_final_reward_broadcast(self):
        events = [event(0, name="invalid", invalid=1), event(0, name="duplicate", duplicate=1), event(1, success=1)]
        result = self.projector.build(request([step(0, [0.0, 0.0]), step(1, [0.0, 0.0])], events))
        self.assert_vector(result.manifest.rewards, (0.0, -0.04, 0.0, 1.0))
        self.assertEqual(len(result.manifest.event_to_token), 3)

    def test_g4_prefix_counts_and_event_receipts_survive_segment_boundary(self):
        events = tuple(event(i, invalid=1) for i in range(5))
        first = self.projector.build(request([step(i, [0.0]) for i in range(5)], events,
                                            end_reason="segment_limit", bootstrap=bootstrap(4, 0.0)))
        second_identity = identity(learning_segment_id="segment-2")
        second = request([step(5, [0.0], row=0, ident=second_identity)],
                         events + (event(5, invalid=1, success=1, ident=second_identity),),
                         identity=second_identity, prefix=first.next_prefix)
        result = self.projector.build(second)
        self.assertTrue(result.eligible, result.reasons)
        self.assertEqual(result.manifest.rewards, (1.0,))
        self.assertAlmostEqual(sum(first.manifest.rewards) + sum(result.manifest.rewards), 0.9)
        conflict = replace(events[0], delta_duplicate=1)
        self.assert_rejected(replace(second, reward_events=(conflict,) + second.reward_events), "conflicting_reward_event_identity")

    def test_g5_cancel_takeover_unknown_and_open_segments_have_no_targets(self):
        req = self.g1_request()
        for reason in ("user_cancelled", "human_takeover", "recovery_takeover", "unknown_effect",
                       "unknown_reward", "unknown_next_state", "open"):
            with self.subTest(reason=reason):
                self.assert_rejected(replace(req, end_reason=reason), f"ineligible_boundary:{reason}")

    def test_g5_cancelled_07b_later_success_cannot_make_it_trainable(self):
        req = request([step(0, [0.2])], [event(0, success=1)], end_reason="user_cancelled")
        result = self.assert_rejected(req, "ineligible_boundary:user_cancelled")
        self.assertIsNone(result.manifest)

    def test_g5_missing_bootstrap_and_incomplete_bootstrap_are_rejected(self):
        req = request([step(0, [0.2])], end_reason="segment_limit")
        self.assert_rejected(req, "missing_bootstrap_evidence")
        self.assert_rejected(replace(req, bootstrap=bootstrap(0, effects_verified=False)), "unverified_bootstrap_boundary")
        bad_artifact = replace(artifact("next"), ready=False)
        self.assert_rejected(replace(req, bootstrap=bootstrap(0, next_state_artifact=bad_artifact)), "bootstrap_artifact_not_ready")
        self.assert_rejected(replace(req, bootstrap=bootstrap(0, ident=identity(critic_revision="critic-new"))),
                             "bootstrap_identity_or_cutoff_mismatch")
        self.assert_rejected(replace(req, bootstrap=bootstrap(1)), "bootstrap_identity_or_cutoff_mismatch")

    def test_g5_verified_infrastructure_cut_uses_bootstrap(self):
        req = request([step(0, [0.2])], end_reason="infrastructure_interruption",
                      bootstrap=bootstrap(0, end_reason="infrastructure_interruption"))
        result = self.projector.build(req)
        self.assertTrue(result.eligible)
        self.assertEqual(result.advantages.returns, (0.4,))

    def test_g5_pending_or_unattributed_reward_is_rejected(self):
        req = self.g1_request()
        for changes, reason in (({"settled": False}, "pending_reward_event"),
                                ({"policy_attributed": False}, "unattributed_reward_event")):
            self.assert_rejected(replace(req, reward_events=(replace(req.reward_events[0], **changes), req.reward_events[1])), reason)
        self.assert_rejected(replace(req, rewards_complete=False), "incomplete_reward_settlement")

    def test_g5_zero_generated_tokens_and_missing_artifacts_are_not_skipped(self):
        req = self.g1_request()
        empty = step(1, [], origins=("tool", "padding"))
        self.assert_rejected(replace(req, steps=(req.steps[0], empty, req.steps[2])), "zero_generated_tokens")
        missing = replace(req.steps[1], tokens=None, old_logprobs=None, reference_logprobs=None,
                          critic_outputs=None, pre_token_value_indices=None)
        self.assert_rejected(replace(req, steps=(req.steps[0], missing, req.steps[2])), "missing_token_artifact")
        no_probabilities = replace(req.steps[1], old_logprobs=None)
        self.assert_rejected(replace(req, steps=(req.steps[0], no_probabilities, req.steps[2])), "missing_behavior_logprobs")

    def test_g5_frozen_identity_and_all_revisions_must_match(self):
        req = self.g1_request()
        for key in BatchIdentity.model_fields:
            other = replace(req.steps[1], identity=replace(req.identity, **{key: "different"}))
            with self.subTest(key=key):
                self.assert_rejected(replace(req, steps=(req.steps[0], other, req.steps[2])),
                                     "step_identity_or_frozen_version_mismatch")

    def test_g5_missing_or_reordered_decision_and_duplicate_invocation(self):
        req = self.g1_request()
        self.assert_rejected(replace(req, steps=(req.steps[0], req.steps[2])), "missing_or_reordered_decision")
        self.assert_rejected(replace(req, steps=tuple(reversed(req.steps))), "missing_or_reordered_decision")
        same = replace(req.steps[1], invocation_id=req.steps[0].invocation_id)
        self.assert_rejected(replace(req, steps=(req.steps[0], same, req.steps[2])), "duplicate_decision_or_invocation")

    def test_g5_reward_must_bind_exact_role_episode_segment_decision_invocation(self):
        req = self.g1_request()
        for key, value, reason in (
            ("role_session_id", "other", "reward_identity_mismatch"),
            ("episode_id", "other", "reward_identity_mismatch"),
            ("learning_segment_id", "other", "reward_identity_mismatch"),
            ("decision_id", "other", "reward_decision_or_invocation_mismatch"),
            ("invocation_id", "other", "reward_decision_or_invocation_mismatch"),
            ("decision_index", 5, "reward_decision_or_invocation_mismatch"),
        ):
            self.assert_rejected(replace(req, reward_events=(replace(req.reward_events[0], **{key: value}),)), reason)

    def test_g6_row_repartition_and_context_reconstruction_preserve_returns(self):
        first = self.projector.build(request([step(0, [0.1, 0.2]), step(1, [0.3])],
                                            [event(0, invalid=1), event(1, success=1)]))
        second = self.projector.build(request([step(0, [0.1]), step(1, [0.2]), step(2, [0.3])],
                                             [event(1, invalid=1), event(2, success=1)]))
        self.assert_oracle(first, "G3")
        self.assertEqual(first.advantages.returns, second.advantages.returns)
        self.assertEqual(first.advantages.raw_advantages, second.advantages.raw_advantages)

    def test_g6_nonunit_discount_terminal_and_truncated_with_masked_slots(self):
        for padded in (False, True):
            origins = ("template", "policy", "padding", "tool", "policy", "padding") if padded else None
            steps = [step(0, [0.2, 0.3], origins=origins), step(1, [0.4])]
            terminal = request(steps, [event(0, invalid=1), event(1, success=1)], gamma=0.9, gae_lambda=0.8)
            truncated = request(steps, [event(0, invalid=1)], gamma=0.9, gae_lambda=0.8,
                                end_reason="segment_limit", bootstrap=bootstrap(1, 0.5))
            self.assert_oracle(self.projector.build(terminal), "G6_discount_terminal")
            self.assert_oracle(self.projector.build(truncated), "G6_discount_truncated")

    def test_g6_pre_token_value_indices_reject_post_token_values(self):
        valid = step(0, [0.2, 0.3], origins=("policy", "padding", "tool", "policy"))
        self.assertEqual(valid.pre_token_value_indices, (1, None, None, 4))
        with self.assertRaises(ValidationError):
            replace(valid, pre_token_value_indices=(2, None, None, 5))

    def test_g6_normalize_once_across_valid_tokens_only_and_preserve_targets(self):
        req = request([step(0, [0.1, 0.2], origins=("policy", "padding", "policy")), step(1, [0.3])],
                      [event(0, invalid=1), event(1, success=1)], normalize_actor=True)
        result = self.projector.build(req)
        self.assert_oracle(result, "G3")
        self.assertEqual(result.advantages.normalization_count, 1)
        self.assertAlmostEqual(sum(result.advantages.actor_advantages), 0.0)
        self.assertEqual(result.rows[0].actor_advantages[1], 0.0)
        restored = AdvantageBatch.model_validate_json(result.advantages.model_dump_json())
        TokenChainGAE.assert_targets_preserved(result.advantages, restored)
        mutated = replace(restored, actor_advantages=(0.0,) * 3)
        with self.assertRaises(ValueError):
            TokenChainGAE.assert_targets_preserved(result.advantages, mutated)
        # The real verl hook is intentionally absent in this CPU-only slice.
        self.assertEqual(result.manifest.verl_hook_status, "not_validated")

    def test_scatter_rejects_different_chain_or_row_binding(self):
        req = self.g1_request()
        result = self.projector.build(req)
        bad_batch = replace(result.advantages, manifest_sha256="b" * 64)
        with self.assertRaises(ValueError):
            TokenChainGAE.scatter(result.manifest, bad_batch, req.steps)
        with self.assertRaises(ValueError):
            TokenChainGAE.scatter(result.manifest, result.advantages, tuple(reversed(req.steps)))
        changed_tokens = replace(req.steps[0].tokens, input_token_ids=(102, 103))
        changed_step = replace(req.steps[0], tokens=changed_tokens)
        with self.assertRaisesRegex(ValueError, "source rows"):
            TokenChainGAE.scatter(result.manifest, result.advantages, (changed_step, *req.steps[1:]))

    def test_terminal_prefix_cannot_restart_an_episode(self):
        first = self.projector.build(self.g1_request())
        req = request([step(3, [0.0], row=0)], prefix=first.next_prefix)
        self.assert_rejected(req, "prefix_already_terminal")

    def test_strict_types_finite_values_unknown_fields_and_deep_immutability(self):
        valid = step(0, [0.2])
        for changes in ({"decision_index": True}, {"decision_index": "0"}, {"unexpected": 1},
                        {"old_logprobs": (math.nan,)}, {"old_logprobs": (math.inf,)},
                        {"critic_outputs": (0.0, math.inf, 0.0)}, {"old_logprobs": (0.1,)}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                replace(valid, **changes)
        with self.assertRaises(ValidationError):
            replace(valid.tokens, policy_token_mask=(True,))
        with self.assertRaises(ValidationError):
            valid.identity.critic_revision = "updated"
        with self.assertRaises(TypeError):
            valid.tokens.input_token_ids[0] = 5

    def test_shape_mask_and_provenance_validation(self):
        valid = step(0, [0.2])
        for changes in ({"old_logprobs": ()}, {"old_logprobs": (None,)},
                        {"pre_token_value_indices": (None,)}, {"critic_outputs": (0.0,)},
                        {"context_origin": "reconstructed_demo_context"}):
            with self.assertRaises(ValidationError):
                replace(valid, **changes)
        with self.assertRaises(ValidationError):
            replace(valid.tokens, policy_token_mask=(0,))
        with self.assertRaises(ValidationError):
            replace(valid.tokens, attention_mask=(1, 1))

    def test_not_ready_artifacts_do_not_publish_training(self):
        req = self.g1_request()
        changed = replace(req.steps[0], context_artifact=replace(req.steps[0].context_artifact, ready=False))
        self.assert_rejected(replace(req, steps=(changed, *req.steps[1:])), "context_artifact_not_ready")

    def test_success_requires_unique_settlement_and_terminal_consistency(self):
        steps = [step(0, [0.0]), step(1, [0.0])]
        self.assert_rejected(request(steps, [event(0, success=1), event(1, success=1)]), "success_already_settled")
        self.assert_rejected(request(steps), "success_boundary_mismatch")
        self.assert_rejected(request(steps, [event(1, success=1)], end_reason="policy_failure"), "success_boundary_mismatch")

    def test_terminal_cannot_receive_bootstrap_and_empty_request_is_ineligible(self):
        self.assert_rejected(replace(self.g1_request(), bootstrap=bootstrap(2)), "unexpected_bootstrap_evidence")
        self.assert_rejected(request([]), "missing_decisions")

    def test_projection_json_roundtrip_preserves_source_and_targets(self):
        result = self.projector.build(self.g1_request())
        restored = ProjectionResult.model_validate_json(result.model_dump_json())
        self.assertEqual(result, restored)
        TokenChainGAE.assert_targets_preserved(result.advantages, restored.advantages)


if __name__ == "__main__":
    unittest.main()
