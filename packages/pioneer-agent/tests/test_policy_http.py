"""HTTP mapping tests; all upstream bodies are synthetic fixtures."""
from __future__ import annotations

import asyncio
import copy
import json
import unittest
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict

from sanmou_common.policy_contracts import PolicyManifest, PolicyRequest, PolicyTransportResponse, SealedJson
from pioneer_agent.adapters.policy_http import HttpPolicyTransport, PolicyHttpError, SGLangChatBackend, assistant_message
from pioneer_agent.adapters.policy_service import ToolDefinition, ToolRegistry
from pioneer_agent.adapters.policy_service import PolicyServiceAdapter
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger


def native_fixtures():
    path = Path(__file__).parent / "fixtures/policy_service/sglang_http_roundtrip.json"
    return json.loads(path.read_text(encoding="utf-8"))


class QueryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


class CompleteArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str


def registry():
    return ToolRegistry([
        ToolDefinition(name="query_knowledge", arguments_model=QueryArgs,
                       state_effect="read_only", window_effect="passive"),
        ToolDefinition(name="complete_task", arguments_model=CompleteArgs,
                       state_effect="control", window_effect="passive"),
    ])


def manifest():
    return PolicyManifest(policy_id="http-fixture-policy", model="cpu-fake-qwen",
        checkpoint_revision="synthetic-no-weights", adapter_revision="none",
        tokenizer_revision="unavailable", chat_template_revision="qwen-no-thinking-v1",
        prompt_revision="synthetic-v1", sampling=SealedJson.from_value({
            "temperature": 0.0, "top_p": 1.0, "top_k": -1, "min_p": 0.0,
            "repetition_penalty": 1.0, "frequency_penalty": 0.0, "presence_penalty": 0.0,
            "seed": 0, "stop": None}),
        model_context_limit=4096)


def request(number=1, messages=None, selected_manifest=None):
    return PolicyRequest(episode_id="http-episode", run_id="http-run", decision_id=f"decision-{number}",
        invocation_id=f"invocation-{number}", context_id=f"context-{number}", task_ref="fixture-task",
        binding_ref="fixture-binding", observation_ref="fixture-observation", manifest=selected_manifest or manifest(),
        messages=SealedJson.from_value(messages or [{"role": "user", "content": "查建筑规则"}]),
        tools=registry().tools, estimated_input_tokens=100, reserved_output_tokens=50)


class PolicyHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_mapping_exact_payload_and_metadata(self):
        seen = []
        async def handler(req):
            seen.append(req)
            return httpx.Response(200, json=native_fixtures()[0])
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            backend = SGLangChatBackend(base_url="http://127.0.0.1:30000", manifest=manifest(),
                                        api_key="test-upstream-key", client=client)
            result = await backend.generate(request())
        sent = json.loads(seen[0].content)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].url.path, "/v1/chat/completions")
        self.assertEqual(seen[0].headers["authorization"], "Bearer test-upstream-key")
        self.assertEqual(sent["messages"], request().messages.value())
        self.assertEqual(sent["tools"], registry().tools.value())
        self.assertEqual(sent["model"], manifest().model)
        self.assertEqual(sent["max_tokens"], 50)
        self.assertEqual(sent["chat_template_kwargs"], {"enable_thinking": False})
        self.assertFalse(sent["stream"])
        self.assertEqual(sent["n"], 1)
        self.assertTrue(sent["return_token_ids"])
        self.assertTrue(sent["return_meta_info"])
        self.assertTrue(sent["logprobs"])
        self.assertEqual(result.raw_response.value(), native_fixtures()[0])
        self.assertEqual(result.generation.response_token_ids, (21, 22))
        self.assertIsNone(result.generation.response_logprobs)
        self.assertEqual(result.generation.probability_kind, "unavailable")
        self.assertIsNone(result.generation.policy_token_mask)
        self.assertEqual(result.usage.input_tokens, 2)

    async def test_explicit_raw_declaration_preserves_native_triples(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json=native_fixtures()[0]))) as client:
            backend = SGLangChatBackend(base_url="http://127.0.0.1", manifest=manifest(),
                                        client=client, declared_probability_kind="raw")
            result = await backend.generate(request())
        self.assertEqual(result.generation.response_logprobs, (-0.2, -0.3))
        self.assertEqual(result.generation.probability_kind, "raw")
        self.assertEqual(result.generation.availability, "unavailable")

    async def test_missing_native_tokens_stay_unavailable(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json=native_fixtures()[1]))) as client:
            result = await SGLangChatBackend(base_url="http://127.0.0.1", manifest=manifest(),
                                              client=client).generate(request())
        self.assertIsNone(result.generation.input_token_ids)
        self.assertIsNone(result.generation.response_token_ids)
        self.assertIsNone(result.usage.input_tokens)

    async def test_native_invalid_fields_fail_closed(self):
        changes = [
            lambda raw: raw.update(model="wrong-model"),
            lambda raw: raw["choices"][0].update(response_token_ids=[999]),
            lambda raw: raw["choices"][0]["meta_info"].update(output_token_logprobs=[[0.2, 21, "invalid"]]),
            lambda raw: raw.update(usage={"prompt_tokens": True}),
            lambda raw: raw.update(usage={"prompt_tokens": 999, "completion_tokens": 2}),
            lambda raw: raw.update(usage={"prompt_tokens": 2, "completion_tokens": 999}),
        ]
        for change in changes:
            raw = native_fixtures()[0]
            change(raw)
            async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json=raw))) as client:
                backend = SGLangChatBackend(base_url="http://127.0.0.1", manifest=manifest(), client=client)
                with self.assertRaises(PolicyHttpError):
                    await backend.generate(request())

    async def test_manifest_mismatch_never_calls_upstream(self):
        seen = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda req: seen.append(req) or httpx.Response(200, json=native_fixtures()[0]))) as client:
            backend = SGLangChatBackend(base_url="http://127.0.0.1", manifest=manifest(), client=client)
            changed = manifest().model_copy(update={"prompt_revision": "other"})
            with self.assertRaisesRegex(PolicyHttpError, "policy_version_mismatch"):
                await backend.generate(request(selected_manifest=changed))
        self.assertEqual(seen, [])

    async def test_failures_are_single_attempt_and_redacted(self):
        for status in (401, 409, 429, 500, 503, 307):
            calls = []
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:
                calls.append(req) or httpx.Response(status, text="secret-prompt-and-key",
                    headers={"Location": "https://elsewhere.invalid"}))) as client:
                transport = HttpPolicyTransport(base_url="http://127.0.0.1", api_key="private-key", client=client)
                with self.assertRaises(PolicyHttpError) as raised:
                    await transport.generate(request())
                self.assertEqual(raised.exception.status_code, status)
                self.assertNotIn("private-key", str(raised.exception))
                self.assertNotIn("secret-prompt", str(raised.exception))
                self.assertEqual(len(calls), 1)

    async def test_timeout_cancels_once_without_retry(self):
        calls = []
        stopped = asyncio.Event()
        async def handler(req):
            calls.append(req)
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            transport = HttpPolicyTransport(base_url="http://127.0.0.1", api_key="private-key",
                                            client=client, timeout_seconds=0.01)
            with self.assertRaisesRegex(PolicyHttpError, "http_timeout"):
                await transport.generate(request())
        self.assertEqual(len(calls), 1)
        self.assertTrue(stopped.is_set())

    async def test_external_cancellation_propagates(self):
        started, stopped = asyncio.Event(), asyncio.Event()
        async def handler(req):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            transport = HttpPolicyTransport(base_url="http://127.0.0.1", api_key="private-key", client=client)
            task = asyncio.create_task(transport.generate(request()))
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(stopped.is_set())

    async def test_oversized_or_non_json_response_rejected(self):
        for response in (httpx.Response(200, text="secret upstream error"),
                         httpx.Response(200, content=b'{"x":"' + b'a' * 100 + b'"}',
                                        headers={"Content-Type": "application/json"})):
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: response)) as client:
                transport = HttpPolicyTransport(base_url="http://127.0.0.1", api_key="private-key",
                                                client=client, max_response_bytes=50)
                with self.assertRaises(PolicyHttpError):
                    await transport.generate(request())

    async def test_gateway_response_metadata_is_checked_again(self):
        response = PolicyTransportResponse(invocation_id="wrong", request_sha256=request().sha256,
            manifest_sha256=manifest().sha256, provider_response_id="response-id",
            raw_response=SealedJson.from_value(native_fixtures()[0]))
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:
            httpx.Response(200, content=response.model_dump_json(), headers={"Content-Type": "application/json"}))) as client:
            transport = HttpPolicyTransport(base_url="http://127.0.0.1", api_key="private-key", client=client)
            with self.assertRaisesRegex(PolicyHttpError, "gateway_binding_mismatch"):
                await transport.generate(request())

    def test_history_projection_keeps_exact_arguments_and_raw_unmodified(self):
        raw = native_fixtures()[0]
        before = copy.deepcopy(raw)
        projected = assistant_message(raw)
        self.assertEqual(set(projected), {"role", "content", "tool_calls"})
        self.assertEqual(set(projected["tool_calls"][0]), {"id", "type", "function"})
        self.assertEqual(projected["tool_calls"][0]["function"]["arguments"],
                         raw["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
        self.assertEqual(raw, before)

    def test_endpoint_and_sampling_overrides_are_rejected(self):
        for url in ("http://example.com", "http://user:secret@127.0.0.1", "https://host/path", "https://host?key=x"):
            with self.assertRaises(ValueError):
                HttpPolicyTransport(base_url=url, api_key="private-key")
        for override in ({"model": "x"}, {"messages": []}, {"stream": True}, {"max_tokens": 999}):
            changed = manifest().model_copy(update={"sampling": SealedJson.from_value(override)})
            with self.assertRaises(ValueError):
                SGLangChatBackend(base_url="http://127.0.0.1", manifest=changed)

    def test_sampling_types_ranges_and_missing_defaults_rejected(self):
        for name, value in (("temperature", True), ("top_p", 0), ("top_p", 1.1),
                            ("top_k", 0), ("top_k", -2), ("min_p", -0.1),
                            ("repetition_penalty", 0), ("frequency_penalty", "0"),
                            ("presence_penalty", 3), ("seed", True), ("stop", [])):
            with self.subTest(name=name, value=value):
                sampling = manifest().sampling.value()
                sampling[name] = value
                changed = manifest().model_copy(update={"sampling": SealedJson.from_value(sampling)})
                with self.assertRaises(ValueError):
                    SGLangChatBackend(base_url="http://127.0.0.1", manifest=changed)
        changed = manifest().model_copy(update={"sampling": SealedJson.from_value({"temperature": 0.0})})
        with self.assertRaises(ValueError):
            SGLangChatBackend(base_url="http://127.0.0.1", manifest=changed)

    async def test_model_errors_preserve_raw_usage_tokens_for_adapter_rejection(self):
        for code, change in (
            ("incomplete_generation", lambda raw: raw["choices"][0].update(finish_reason="length")),
            ("invalid_params", lambda raw: raw["choices"][0]["message"]["tool_calls"][0]["function"].update(arguments="bad-json")),
            ("incomplete_generation", lambda raw: raw["choices"][0].update(finish_reason="stop", message={"role":"assistant","content":"普通回答"})),
            ("parse_error", lambda raw: raw.update(choices=[])),
        ):
            with self.subTest(code=code):
                raw = native_fixtures()[0]
                change(raw)
                async with httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda req: httpx.Response(200, json=raw))) as client:
                    backend = SGLangChatBackend(base_url="http://127.0.0.1", manifest=manifest(), client=client)
                    budget = RunBudgetLedger()
                    result = await PolicyServiceAdapter(transport=backend, manifest=manifest(),
                        registry=registry(), budget=budget).decide(request())
                self.assertEqual(result.error_code, code)
                self.assertEqual(result.proposed_calls, ())
                self.assertEqual(result.raw_response.value(), raw)
                self.assertEqual(result.usage.input_tokens, 2)
                self.assertEqual(result.usage.output_tokens, 2)
                if code != "parse_error":
                    self.assertEqual(result.generation.response_token_ids, (21, 22))
                self.assertEqual(budget.summary()["charged_tokens"], 4)

    async def test_reasoning_output_is_preserved_but_history_helper_refuses_loss(self):
        raw = native_fixtures()[0]
        raw["choices"][0]["message"]["reasoning_content"] = "unexpected reasoning"
        async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json=raw))) as client:
            backend = SGLangChatBackend(base_url="http://127.0.0.1", manifest=manifest(), client=client)
            result = await backend.generate(request())
        self.assertEqual(result.raw_response.value(), raw)
        self.assertEqual(result.usage.input_tokens, 2)
        with self.assertRaisesRegex(PolicyHttpError, "unsupported_reasoning_output"):
            assistant_message(result.raw_response.value())


if __name__ == "__main__":
    unittest.main()
