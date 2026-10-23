"""Numerical GAE over a verified logical policy-token chain, then row scatter."""
from __future__ import annotations

import math

from .contracts import (
    AdvantageBatch, AdvantageRow, PolicyStepProjection, TokenChainManifest,
)


class TokenChainGAE:
    @staticmethod
    def compute(manifest: TokenChainManifest, *, normalize_actor: bool = False) -> AdvantageBatch:
        manifest = TokenChainManifest.model_validate(manifest)
        if type(normalize_actor) is not bool:
            raise TypeError("normalize_actor must be a boolean")
        advantages = [0.0] * len(manifest.tokens)
        for q in reversed(range(len(advantages))):
            successor = manifest.successors[q]
            next_value = (manifest.values[successor] if successor is not None
                          else manifest.bootstrap_value if manifest.bootstrap_value is not None else 0.0)
            next_advantage = advantages[successor] if successor is not None else 0.0
            delta = (manifest.rewards[q] + manifest.gamma * manifest.bootstrap_mask[q] * next_value
                     - manifest.values[q])
            advantages[q] = delta + manifest.gamma * manifest.gae_lambda * manifest.continuation_mask[q] * next_advantage
        returns = tuple(a + v for a, v in zip(advantages, manifest.values))
        actor = tuple(advantages)
        if normalize_actor:
            mean = math.fsum(actor) / len(actor)
            variance = math.fsum((a - mean) ** 2 for a in actor) / len(actor)
            scale = math.sqrt(variance + 1e-8)
            actor = tuple((a - mean) / scale for a in actor)
        return AdvantageBatch(
            manifest_sha256=manifest.digest(), raw_advantages=tuple(advantages),
            returns=returns, actor_advantages=actor, normalization_count=int(normalize_actor),
        )

    @staticmethod
    def scatter(manifest: TokenChainManifest, batch: AdvantageBatch,
                steps: tuple[PolicyStepProjection, ...]) -> tuple[AdvantageRow, ...]:
        """Scatter once; masked slots are zero and never enter normalization."""
        manifest = TokenChainManifest.model_validate(manifest)
        batch = AdvantageBatch.model_validate(batch)
        if batch.manifest_sha256 != manifest.digest() or len(batch.returns) != len(manifest.tokens):
            raise ValueError("advantage targets do not belong to this token chain")
        if tuple(step.row_index for step in steps) != tuple(range(len(steps))):
            raise ValueError("rows must remain in their sealed order")
        if tuple(step.digest() for step in steps) != manifest.row_projection_sha256:
            raise ValueError("actual source rows or token artifacts changed after projection")
        expected = tuple(
            (step.row_index, j, step.decision_id, step.invocation_id)
            for step in steps if step.tokens is not None
            for j, valid in enumerate(step.tokens.policy_token_mask) if valid
        )
        actual = tuple((t.row_index, t.response_index, t.decision_id, t.invocation_id)
                       for t in manifest.tokens)
        if expected != actual or any(step.identity != manifest.identity for step in steps):
            raise ValueError("scatter rows do not match the sealed chain")
        offsets = {(ref.row_index, ref.response_index): q for q, ref in enumerate(manifest.tokens)}
        rows = []
        for step in steps:
            if step.tokens is None:
                raise ValueError("scatter requires original token artifacts")
            def row(values):
                return tuple(values[offsets[(step.row_index, j)]] if mask else 0.0
                             for j, mask in enumerate(step.tokens.policy_token_mask))
            rows.append(AdvantageRow(
                row_index=step.row_index, policy_token_mask=step.tokens.policy_token_mask,
                rewards=row(manifest.rewards), raw_advantages=row(batch.raw_advantages),
                returns=row(batch.returns), actor_advantages=row(batch.actor_advantages),
            ))
        return tuple(rows)

    @staticmethod
    def assert_targets_preserved(before: AdvantageBatch, after: AdvantageBatch) -> None:
        """A diagnostic for a future trainer hook, not evidence of verl integration."""
        before = AdvantageBatch.model_validate(before)
        after = AdvantageBatch.model_validate(after)
        if before.digest() != after.digest():
            raise ValueError("precomputed targets or normalization were modified")
