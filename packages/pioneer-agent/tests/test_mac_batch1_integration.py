"""Explicit synthetic service artifacts cross into the CPU training projection.

The token IDs and Critic values below are authored test data, never model output.
"""
import hashlib
import unittest

from pydantic import BaseModel, ConfigDict

from sanmou_common.ports import Evidence, KnowledgeAnswer
from sanmou_common.policy_contracts import (
    GenerationRecord, PolicyManifest, PolicyRequest, PolicyTransportResponse,
    PolicyUsage, SealedJson, seal_knowledge_answer,
)
from pioneer_agent.adapters.policy_service import PolicyServiceAdapter, ToolDefinition, ToolRegistry
from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.training import TrainingProjector
from pioneer_agent.training.contracts import (
    ArtifactRef, BatchIdentity, PolicyStepProjection, ProjectionRequest,
    ProjectionResult, RewardEvent, TokenArtifact,
)


class CompleteArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str


class SyntheticTokenTransport:
    def __init__(self):
        self.requests = []

    async def generate(self, request):
        index = len(self.requests)
        self.requests.append(request.payload)
        raw = {} if index == 0 else {"choices": [{"finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": None, "tool_calls": [{"id": "finish", "type": "function",
                "function": {"name": "complete_task", "arguments": '{"reason":"synthetic"}'}}]}}]}
        return PolicyTransportResponse(
            invocation_id=request.invocation_id, request_sha256=request.sha256,
            manifest_sha256=request.manifest.sha256, provider_response_id=f"synthetic-{index}",
            raw_response=SealedJson.from_value(raw), usage=PolicyUsage(input_tokens=2, output_tokens=1),
            generation=GenerationRecord(input_token_ids=(10, 11 + index), response_token_ids=(20 + index,),
                                        response_logprobs=(-0.5,), policy_token_mask=(1,),
                                        probability_kind="sampling", finish_reason="tool_calls"))


class MacBatchIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_sealed_request_and_failed_generation_reach_numeric_projection(self):
        manifest = PolicyManifest(policy_id="synthetic", model="no-model",
            checkpoint_revision="fixture", adapter_revision="none", tokenizer_revision="fixture-tokenizer",
            chat_template_revision="fixture-template", prompt_revision="fixture-prompt",
            sampling=SealedJson.from_value({"temperature": 1.0}), model_context_limit=128)
        registry = ToolRegistry([ToolDefinition(name="complete_task", arguments_model=CompleteArguments,
                                                state_effect="control", window_effect="passive")])
        transport = SyntheticTokenTransport()
        budget = RunBudgetLedger(BudgetLimits(max_model_attempts=2, max_tokens=128))
        adapter = PolicyServiceAdapter(transport=transport, manifest=manifest, registry=registry, budget=budget)
        knowledge = seal_knowledge_answer(KnowledgeAnswer(answer="模拟知识", evidence=(
            Evidence(entry_id="fixture", topic="模拟", domain="building", summary="仅用于接口测试"),)),
            query="模拟问题", kb_revision="fixture-kb", retriever_revision="fixture-retriever")
        identity = BatchIdentity(role_session_id="fixture-role", episode_id="fixture-episode",
            learning_segment_id="fixture-segment", batch_id="fixture-batch",
            behavior_policy_revision=manifest.sha256, critic_revision="fixture-critic",
            reference_revision="fixture-reference", tokenizer_revision=manifest.tokenizer_revision,
            template_revision=manifest.chat_template_revision, sampling_revision=manifest.sampling.sha256)
        steps, events, requests = [], [], []
        for index, value in enumerate((0.2, 0.3)):
            request = PolicyRequest(episode_id=identity.episode_id, run_id="fixture-run",
                decision_id=f"d{index}", invocation_id=f"i{index}", context_id=f"c{index}",
                task_ref="fixture-task", binding_ref=identity.role_session_id, observation_ref=f"obs{index}",
                manifest=manifest, messages=SealedJson.from_value([{"role": "user", "content": f"模拟观察 {index}"}]),
                tools=registry.tools, knowledge=knowledge, estimated_input_tokens=16, reserved_output_tokens=8)
            requests.append(request)
            result = await adapter.decide(request)
            self.assertEqual(result.status, "failed" if index == 0 else "ok")
            if index == 0:
                self.assertEqual(result.error_code, "parse_error")
                self.assertEqual(result.proposed_calls, ())
            self.assertEqual(result.request_sha256, hashlib.sha256(transport.requests[index]).hexdigest())
            generation = result.generation
            self.assertEqual(generation.availability, "complete")
            raw_tokens = generation.model_dump_json().encode()
            token_artifact = TokenArtifact(
                artifact_ref=ArtifactRef(artifact_id=f"tokens{index}", sha256=hashlib.sha256(raw_tokens).hexdigest(),
                                         byte_length=len(raw_tokens)), input_token_ids=generation.input_token_ids,
                response_token_ids=generation.response_token_ids, attention_mask=(1, 1, 1), position_ids=(0, 1, 2),
                response_origins=("policy",), policy_token_mask=generation.policy_token_mask)
            steps.append(PolicyStepProjection(identity=identity, decision_id=request.decision_id,
                invocation_id=request.invocation_id, decision_index=index, row_index=index,
                context_artifact=ArtifactRef(artifact_id=request.context_id, sha256=request.sha256,
                                             byte_length=len(request.payload)), tokens=token_artifact,
                old_logprobs=generation.response_logprobs, critic_outputs=(99.0, value, 99.0),
                pre_token_value_indices=(1,)))
            events.append(RewardEvent(event_id=f"event{index}", role_session_id=identity.role_session_id,
                episode_id=identity.episode_id, learning_segment_id=identity.learning_segment_id,
                decision_id=request.decision_id, invocation_id=request.invocation_id, decision_index=index,
                delta_invalid=int(index == 0), delta_success=int(index == 1)))
        projection = TrainingProjector().build(ProjectionRequest(identity=identity, steps=tuple(steps),
            reward_events=tuple(reversed(events)), reward_revision="fixture-rewards", rewards_complete=True,
            end_reason="task_success"))
        self.assertTrue(projection.eligible, projection.reasons)
        for actual, expected in zip(projection.advantages.returns, (0.98, 1.0)):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(sum(projection.manifest.rewards), 0.98)
        self.assertNotEqual(steps[0].context_artifact.sha256, steps[1].context_artifact.sha256)
        self.assertEqual(projection.manifest.row_projection_sha256, tuple(step.digest() for step in steps))
        self.assertFalse(projection.manifest.ms5_ready)
        self.assertEqual(ProjectionResult.model_validate_json(projection.model_dump_json()), projection)
        self.assertEqual(tuple(request.payload for request in requests), tuple(transport.requests))
        self.assertEqual(budget.summary()["pending"], 0)


if __name__ == "__main__":
    unittest.main()
