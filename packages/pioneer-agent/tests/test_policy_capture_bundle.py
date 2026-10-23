"""Native response capture crosses the bundle boundary without inventing PPO data."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import httpx
from pydantic import BaseModel, ConfigDict

from sanmou_common.policy_contracts import PolicyManifest, PolicyRequest, SealedJson
from pioneer_agent.adapters.policy_http import SGLangChatBackend
from pioneer_agent.adapters.policy_service import PolicyServiceAdapter, ToolDefinition, ToolRegistry
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from pioneer_agent.training.artifact_bundle import BundleFile, BundleManifest, TokenPayload, export_bundle, import_bundle
from pioneer_agent.training.contracts import ArtifactRef, BatchIdentity, PolicyStepProjection, ProjectionRequest, TokenArtifact


class QueryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


class CaptureBundleTests(unittest.IsolatedAsyncioTestCase):
    async def test_captured_ids_survive_handoff_without_sampling_probabilities_or_critic(self):
        raw = json.loads((Path(__file__).parent / "fixtures/policy_service/sglang_http_roundtrip.json").read_text())[0]
        policy = PolicyManifest(policy_id="synthetic-policy", model=raw["model"], checkpoint_revision="synthetic-weights",
            adapter_revision="none", tokenizer_revision="synthetic-tokenizer", chat_template_revision="synthetic-template",
            prompt_revision="synthetic-prompt", sampling=SealedJson.from_value({"temperature": 0.0, "top_p": 1.0,
                "top_k": -1, "min_p": 0.0, "repetition_penalty": 1.0, "frequency_penalty": 0.0,
                "presence_penalty": 0.0, "seed": 0, "stop": None}), model_context_limit=4096)
        tools = ToolRegistry([ToolDefinition(name="query_knowledge", arguments_model=QueryArguments,
                                             state_effect="read_only", window_effect="passive")])
        request = PolicyRequest(episode_id="episode", run_id="run", decision_id="decision", invocation_id="invocation",
            context_id="context", task_ref="task", binding_ref="role", observation_ref="observation",
            manifest=policy, messages=SealedJson.from_value([{"role": "user", "content": "合成输入"}]),
            tools=tools.tools, estimated_input_tokens=256, reserved_output_tokens=128)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=raw))) as client:
            backend = SGLangChatBackend(base_url="http://127.0.0.1", manifest=policy, client=client)
            adapter = PolicyServiceAdapter(transport=backend, manifest=policy, registry=tools, budget=RunBudgetLedger())
            response = await adapter.decide(request)
        self.assertEqual(response.status, "ok")
        self.assertEqual(response.raw_response.value(), raw)
        generation = response.generation
        self.assertEqual(generation.probability_kind, "unavailable")
        self.assertIsNone(generation.response_logprobs)
        self.assertIsNone(generation.policy_token_mask)
        identity = BatchIdentity(role_session_id="role", episode_id="episode", learning_segment_id="segment",
            batch_id="batch", behavior_policy_revision=policy.sha256, critic_revision="not-run-synthetic-critic",
            reference_revision="not-run-synthetic-reference", tokenizer_revision=policy.tokenizer_revision,
            template_revision=policy.chat_template_revision, sampling_revision=policy.sampling.sha256)
        n = len(generation.response_token_ids)
        # The following layout is authored fixture data, not reconstructed real
        # model telemetry. Missing probability/value data stays missing.
        layout = TokenPayload(input_token_ids=generation.input_token_ids, response_token_ids=generation.response_token_ids,
            attention_mask=(1,) * (len(generation.input_token_ids) + n),
            position_ids=tuple(range(len(generation.input_token_ids) + n)), response_origins=("policy",) * n,
            policy_token_mask=(1,) * n)
        token_bytes = layout.model_dump_json().encode()
        context_ref = ArtifactRef(artifact_id="context", sha256=request.sha256, byte_length=len(request.payload))
        token_ref = ArtifactRef(artifact_id="tokens", sha256=hashlib.sha256(token_bytes).hexdigest(), byte_length=len(token_bytes))
        step = PolicyStepProjection(identity=identity, decision_id="decision", invocation_id="invocation",
            decision_index=0, row_index=0, context_artifact=context_ref,
            tokens=TokenArtifact(artifact_ref=token_ref, **layout.model_dump(exclude={"schema_version"})),
            old_logprobs=None, critic_outputs=None, pre_token_value_indices=None)
        projection = ProjectionRequest(identity=identity, steps=(step,), rewards_complete=False,
                                       reward_revision="not-settled", end_reason="open")
        payloads = {"context.json": request.payload, "tokens.json": token_bytes,
                    "projection.json": projection.model_dump_json().encode()}
        entries = []
        for name, kind, artifact in (("context.json", "context", "context"), ("tokens.json", "tokens", "tokens"),
                                      ("projection.json", "projection", "projection")):
            entries.append(BundleFile(relative_path=name, artifact_id=artifact, kind=kind, owner_projection_id="projection",
                decision_id="decision" if kind != "projection" else None,
                invocation_id="invocation" if kind != "projection" else None,
                sha256=hashlib.sha256(payloads[name]).hexdigest(), byte_length=len(payloads[name])))
        manifest = BundleManifest(source_kind="synthetic", files=tuple(entries), **{
            key: getattr(identity, key) for key in ("batch_id", "behavior_policy_revision", "critic_revision",
                "reference_revision", "tokenizer_revision", "template_revision", "sampling_revision")})
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory).resolve() / "handoff"
            written = export_bundle(destination, manifest, payloads)
            restored = import_bundle(destination)
            self.assertEqual(written, restored)
            self.assertEqual((destination / "context.json").read_bytes(), request.payload)
            self.assertEqual((destination / "tokens.json").read_bytes(), token_bytes)
        result = restored.projections[0].result
        self.assertFalse(result.eligible)
        self.assertIn("missing_behavior_logprobs", result.reasons)
        self.assertIn("missing_pre_token_values", result.reasons)
        self.assertIsNone(result.advantages)
        self.assertFalse(restored.on_policy_runtime_evidence)
        self.assertFalse(restored.ms5_ready)


if __name__ == "__main__":
    unittest.main()
