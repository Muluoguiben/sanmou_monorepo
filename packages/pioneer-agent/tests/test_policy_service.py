"""Offline service-boundary tests. No endpoint, model, GPU, or game is used."""
from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sanmou_common.policy_contracts import (
    PolicyManifest, PolicyRequest, PolicyTransportResponse, PolicyUsage, SealedJson,
)
from pioneer_agent.adapters.policy_service import (
    MockPolicyTransport, PolicyServiceAdapter, ToolDefinition, ToolRegistry,
)
from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger


class QueryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)


class CompleteArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1)


def registry():
    return ToolRegistry([
        ToolDefinition(name="query_knowledge", arguments_model=QueryArguments,
                       state_effect="read_only", window_effect="passive"),
        ToolDefinition(name="complete_task", arguments_model=CompleteArguments,
                       state_effect="control", window_effect="passive"),
        ToolDefinition(name="observe_panel", arguments_model=QueryArguments,
                       state_effect="read_only", window_effect="ui_navigation"),
    ])


def manifest():
    return PolicyManifest(
        policy_id="mock-policy-v1", model="mock-no-model", checkpoint_revision="mock-v1",
        adapter_revision="none", tokenizer_revision="unavailable",
        chat_template_revision="mock-template-v1", prompt_revision="mock-prompt-v1",
        sampling=SealedJson.from_value({"temperature": 0}), model_context_limit=4096,
    )


def make_request(number=1, *, messages=None, tools=None, policy_manifest=None):
    return PolicyRequest(
        episode_id="mock-episode", run_id="mock-run", decision_id=f"decision-{number}",
        invocation_id=f"invocation-{number}", context_id=f"context-{number}",
        task_ref="mock-task-v1", binding_ref="mock-binding-v1", observation_ref="mock-frame-1",
        manifest=policy_manifest or manifest(),
        messages=SealedJson.from_value(messages or [
            {"role": "system", "content": "只生成工具提议。"},
            {"role": "user", "content": "查询建筑升级规则。"},
        ]),
        tools=tools or registry().tools, estimated_input_tokens=100, reserved_output_tokens=50,
    )


def fixtures():
    path = Path(__file__).parent / "fixtures" / "policy_service" / "roundtrip.json"
    return [SealedJson.from_value(item) for item in json.loads(path.read_text())]


def proposal(*calls):
    return SealedJson.from_value({"choices": [{"index": 0, "finish_reason": "tool_calls",
        "message": {"role": "assistant", "content": None, "tool_calls": list(calls)}}]})


def call(name="query_knowledge", arguments='{"query":"建筑升级"}', call_id="call-1"):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


class EditedTransport(MockPolicyTransport):
    def __init__(self, edit, raw=None):
        super().__init__([raw or fixtures()[0], raw or fixtures()[0]])
        self.edit = edit

    async def generate(self, request):
        response = await super().generate(request)
        return PolicyTransportResponse.model_validate({**response.model_dump(), **self.edit(response)})


class HangingTransport:
    def __init__(self):
        self.started = asyncio.Event()
        self.stopped = asyncio.Event()
        self.calls = 0

    async def generate(self, request):
        self.calls += 1
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            self.stopped.set()


class PolicyServiceTests(unittest.IsolatedAsyncioTestCase):
    def adapter(self, transport=None, **kwargs):
        self.transport = transport or MockPolicyTransport(fixtures())
        self.budget = RunBudgetLedger(BudgetLimits(max_tokens=1000, max_model_attempts=5))
        return PolicyServiceAdapter(transport=self.transport, manifest=manifest(),
                                    registry=registry(), budget=self.budget, **kwargs)

    def assert_settled(self, outcome, count=1, charge=150):
        summary = self.budget.summary()
        self.assertEqual(summary["pending"], 0)
        self.assertEqual(summary["counts"]["model"], count)
        self.assertEqual(summary["charged_tokens"], charge)
        entries = list(self.budget.snapshot()["reservations"].values())
        self.assertEqual(entries[-1]["outcome"], outcome)

    async def test_two_rounds_preserve_actual_input_reply_order_and_unknown_usage(self):
        adapter = self.adapter()
        first_request = make_request()
        first = await adapter.decide(first_request)
        self.assertEqual(first.status, "ok")
        raw_message = first.raw_response.value()["choices"][0]["message"]
        messages = first_request.messages.value() + [raw_message, {
            "role": "tool", "tool_call_id": "call-knowledge-1",
            "content": '{"status":"ok","source":"mock","text":"模拟规则"}',
        }]
        second_request = make_request(2, messages=messages)
        second = await adapter.decide(second_request)
        messages[-1]["content"] = "外部修改"
        self.assertEqual(second.status, "ok")
        self.assertEqual(second.proposed_calls[0].tool_name, "complete_task")
        self.assertEqual(self.transport.requests[1].messages.value()[-1]["content"],
                         '{"status":"ok","source":"mock","text":"模拟规则"}')
        self.assertNotEqual(first_request.sha256, second_request.sha256)
        self.assertIsNone(first.usage.input_tokens)
        self.assertIsNone(first.generation.response_token_ids)
        self.assertEqual(first.generation.probability_kind, "unavailable")
        self.assert_settled("ok", count=2, charge=300)
        self.assertEqual(self.budget.summary()["unknown_token_attempts"], 2)
        self.assertEqual(len(adapter.records), 2)

    async def test_unknown_tool_rejects_entire_mixed_batch(self):
        adapter = self.adapter(MockPolicyTransport([proposal(call(), call("unknown", call_id="2"))]))
        result = await adapter.decide(make_request())
        self.assertEqual(result.error_code, "unknown_tool")
        self.assertEqual(result.proposed_calls, ())
        self.assert_settled("unknown_tool")

    async def test_invalid_params_fail_closed(self):
        invalid = ['{"query":"x","role_binding":"forged"}', '{"query":12}',
                   '{"query":"x","query":"y"}', '{"query":NaN}', '[]', 'not-json']
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                adapter = self.adapter(MockPolicyTransport([proposal(call(arguments=arguments))]))
                result = await adapter.decide(make_request())
                self.assertEqual(result.error_code, "invalid_params")
                self.assertEqual(result.proposed_calls, ())
                self.assert_settled("invalid_params")

    async def test_two_active_control_and_navigation_are_rejected(self):
        raw = proposal(call("complete_task", '{"reason":"done"}'),
                       call("observe_panel", call_id="2"))
        adapter = self.adapter(MockPolicyTransport([raw]))
        result = await adapter.decide(make_request())
        self.assertEqual(result.error_code, "multiple_non_passive_calls_in_step")
        self.assertEqual(result.proposed_calls, ())
        self.assert_settled("multiple_non_passive_calls_in_step")

    async def test_multiple_passive_calls_are_returned_in_request_order(self):
        adapter = self.adapter(MockPolicyTransport([proposal(call(call_id="second"), call(call_id="first"))]))
        result = await adapter.decide(make_request())
        self.assertEqual([item.call_id for item in result.proposed_calls], ["second", "first"])

    async def test_duplicate_call_ids_reject_batch(self):
        adapter = self.adapter(MockPolicyTransport([proposal(call(), call())]))
        result = await adapter.decide(make_request())
        self.assertEqual(result.error_code, "duplicate_call_id")
        self.assertEqual(result.proposed_calls, ())

    async def test_historical_call_id_reuse_rejects_entire_batch(self):
        history = [
            {"role": "system", "content": "只生成工具提议。"},
            {"role": "user", "content": "查询建筑升级规则。"},
            {"role": "assistant", "content": None,
             "tool_calls": [call(call_id="call-reused")]},
            {"role": "tool", "tool_call_id": "call-reused", "content": '{"status":"ok"}'},
        ]
        for calls in ((call(call_id="call-reused"),),
                      (call(call_id="call-new"), call(call_id="call-reused"))):
            with self.subTest(call_ids=[item["id"] for item in calls]):
                adapter = self.adapter(MockPolicyTransport([proposal(*calls)]))
                result = await adapter.decide(make_request(messages=history))
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.error_code, "duplicate_call_id")
                self.assertEqual(result.proposed_calls, ())
                self.assert_settled("duplicate_call_id")

    async def test_new_call_id_after_completed_history_remains_valid(self):
        history = [
            {"role": "user", "content": "查询建筑升级规则。"},
            {"role": "assistant", "content": None,
             "tool_calls": [call(call_id="call-history")]},
            {"role": "tool", "tool_call_id": "call-history", "content": '{"status":"ok"}'},
        ]
        adapter = self.adapter(MockPolicyTransport([proposal(call(call_id="call-new"))]))
        result = await adapter.decide(make_request(messages=history))
        self.assertEqual(result.status, "ok")
        self.assertEqual([item.call_id for item in result.proposed_calls], ["call-new"])

    async def test_truncated_and_reasoning_only_output_fail(self):
        for raw in ({"choices": []}, {"choices": [{"finish_reason": "length", "message": {}}]},
                    {"choices": [{"finish_reason": "tool_calls", "message": {
                        "role": "assistant", "reasoning_content": "tool call hidden in thought"}}]}):
            with self.subTest(raw=raw):
                adapter = self.adapter(MockPolicyTransport([SealedJson.from_value(raw)]))
                result = await adapter.decide(make_request())
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.proposed_calls, ())
                self.assert_settled(result.error_code)

    async def test_request_version_mismatch_does_not_call_or_reserve(self):
        adapter = self.adapter()
        other = PolicyManifest.model_validate({**manifest().model_dump(), "prompt_revision": "other"})
        result = await adapter.decide(make_request(policy_manifest=other))
        self.assertEqual(result.error_code, "policy_version_mismatch")
        self.assertEqual(self.transport.requests, [])
        self.assertEqual(self.budget.summary()["counts"]["model"], 0)

    async def test_tool_catalog_mismatch_does_not_call(self):
        adapter = self.adapter()
        result = await adapter.decide(make_request(tools=SealedJson.from_value([])))
        self.assertEqual(result.error_code, "tool_catalog_mismatch")
        self.assertEqual(self.transport.requests, [])

    async def test_bound_service_version_mismatch_preserves_unknown_reserve(self):
        transport = EditedTransport(lambda response: {"manifest_sha256": "0" * 64,
            "usage": PolicyUsage(input_tokens=1, output_tokens=1, cost=0.0)})
        adapter = self.adapter(transport)
        result = await adapter.decide(make_request())
        self.assertEqual(result.error_code, "policy_version_mismatch")
        self.assertIsNone(result.usage.input_tokens)
        self.assertIsNotNone(result.raw_response)
        self.assert_settled("policy_version_mismatch")

    async def test_wrong_invocation_or_input_hash_is_rejected(self):
        for edit in ({"invocation_id": "other"}, {"request_sha256": "0" * 64}):
            with self.subTest(edit=edit):
                adapter = self.adapter(EditedTransport(lambda response: edit))
                result = await adapter.decide(make_request())
                self.assertEqual(result.error_code, "response_binding_mismatch")
                self.assertEqual(result.proposed_calls, ())
                self.assert_settled("response_binding_mismatch")

    async def test_duplicate_invocation_never_calls_twice(self):
        adapter = self.adapter()
        await adapter.decide(make_request())
        result = await adapter.decide(make_request())
        self.assertEqual(result.error_code, "duplicate_invocation")
        self.assertEqual(len(self.transport.requests), 1)
        self.assert_settled("ok")

    async def test_replayed_provider_response_is_rejected_for_new_request(self):
        adapter = self.adapter(EditedTransport(lambda response: {"provider_response_id": "same"}))
        await adapter.decide(make_request())
        result = await adapter.decide(make_request(2))
        self.assertEqual(result.error_code, "repeated_response")
        self.assertEqual(result.proposed_calls, ())
        self.assert_settled("repeated_response", count=2, charge=300)

    async def test_known_usage_settles_even_after_parse_failure(self):
        adapter = self.adapter(EditedTransport(lambda response: {
            "usage": PolicyUsage(input_tokens=20, output_tokens=8, cost=0.01)},
            raw=proposal(call("missing"))))
        result = await adapter.decide(make_request())
        self.assertEqual(result.error_code, "unknown_tool")
        self.assertEqual(result.usage.output_tokens, 8)
        self.assert_settled("unknown_tool", charge=28)

    async def test_timeout_cancels_transport_and_settles_unknown(self):
        transport = HangingTransport()
        adapter = self.adapter(transport, timeout_seconds=0.01)
        result = await adapter.decide(make_request())
        await asyncio.wait_for(transport.stopped.wait(), timeout=0.5)
        self.assertEqual(result.error_code, "timeout")
        self.assertEqual(result.proposed_calls, ())
        self.assertEqual(transport.calls, 1)
        self.assert_settled("timeout")

    async def test_pre_cancel_has_zero_transport_and_reservations(self):
        adapter = self.adapter()
        cancel = asyncio.Event()
        cancel.set()
        result = await adapter.decide(make_request(), cancel_event=cancel)
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(self.transport.requests, [])
        self.assertEqual(self.budget.summary()["counts"]["model"], 0)

    async def test_cancel_event_interrupts_inflight_and_settles(self):
        transport = HangingTransport()
        adapter = self.adapter(transport)
        cancel = asyncio.Event()
        pending = asyncio.create_task(adapter.decide(make_request(), cancel_event=cancel))
        await transport.started.wait()
        cancel.set()
        result = await asyncio.wait_for(pending, timeout=0.5)
        await asyncio.wait_for(transport.stopped.wait(), timeout=0.5)
        self.assertEqual(result.status, "cancelled")
        self.assert_settled("cancelled")

    async def test_task_cancellation_propagates_and_keeps_record(self):
        transport = HangingTransport()
        adapter = self.adapter(transport)
        pending = asyncio.create_task(adapter.decide(make_request()))
        await transport.started.wait()
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        await asyncio.wait_for(transport.stopped.wait(), timeout=0.5)
        self.assertEqual(adapter.records[-1].status, "cancelled")
        self.assert_settled("cancelled")

    async def test_same_budget_cancellation_stops_new_calls(self):
        adapter = self.adapter()
        self.budget.cancel()
        result = await adapter.decide(make_request())
        self.assertEqual(result.error_code, "budget_exceeded")
        self.assertEqual(self.transport.requests, [])

    async def test_budget_cancel_during_request_stops_transport(self):
        transport = HangingTransport()
        adapter = self.adapter(transport)
        pending = asyncio.create_task(adapter.decide(make_request()))
        await transport.started.wait()
        self.budget.cancel()
        result = await asyncio.wait_for(pending, timeout=0.5)
        await asyncio.wait_for(transport.stopped.wait(), timeout=0.5)
        self.assertEqual(result.error_code, "budget_exceeded")
        self.assert_settled("budget_exceeded")

    async def test_transport_failure_does_not_retry_and_retains_reserve(self):
        class FailureTransport:
            calls = 0
            async def generate(self, request):
                self.calls += 1
                raise ConnectionError("not emitted to diagnostics")
        transport = FailureTransport()
        adapter = self.adapter(transport)
        result = await adapter.decide(make_request())
        self.assertEqual(result.error_code, "transport_error")
        self.assertEqual(transport.calls, 1)
        self.assert_settled("transport_error")

    async def test_constructed_request_is_revalidated_before_dispatch(self):
        adapter = self.adapter()
        valid = make_request()
        forged = valid.model_copy(update={"estimated_input_tokens": 4096})
        with self.assertRaises(ValidationError):
            await adapter.decide(forged)
        self.assertEqual(self.transport.requests, [])
        self.assertEqual(self.budget.summary()["counts"]["model"], 0)

    async def test_model_metadata_cannot_replace_trusted_response_metadata(self):
        raw = fixtures()[0].value()
        raw.update(manifest_sha256="forged", invocation_id="forged", usage={"input_tokens": 0})
        adapter = self.adapter(MockPolicyTransport([SealedJson.from_value(raw)]))
        result = await adapter.decide(make_request())
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.invocation_id, "invocation-1")
        self.assertIsNone(result.usage.input_tokens)
        self.assert_settled("ok")

    async def test_quota_exhaustion_blocks_second_request_without_retry(self):
        transport = MockPolicyTransport(fixtures())
        self.budget = RunBudgetLedger(BudgetLimits(max_tokens=150, max_model_attempts=1))
        adapter = PolicyServiceAdapter(transport=transport, manifest=manifest(),
                                       registry=registry(), budget=self.budget)
        await adapter.decide(make_request())
        result = await adapter.decide(make_request(2))
        self.assertEqual(result.error_code, "budget_exceeded")
        self.assertEqual(len(transport.requests), 1)
        self.assert_settled("ok")

    async def test_noncooperative_transport_late_success_cannot_be_accepted(self):
        class LateTransport(MockPolicyTransport):
            def __init__(self):
                super().__init__(fixtures())
                self.released = asyncio.Event()
                self.cancel_seen = asyncio.Event()
            async def generate(self, request):
                try:
                    await self.released.wait()
                except asyncio.CancelledError:
                    self.cancel_seen.set()
                    await self.released.wait()
                return await super().generate(request)
        transport = LateTransport()
        adapter = self.adapter(transport, timeout_seconds=0.01)
        first = await adapter.decide(make_request())
        await transport.cancel_seen.wait()
        second = await adapter.decide(make_request(2))
        self.assertEqual(first.error_code, "timeout")
        self.assertEqual(second.error_code, "transport_not_quiescent")
        transport.released.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(adapter.records[0].status, "failed")
        self.assertEqual(adapter.records[0].proposed_calls, ())
        self.assert_settled("timeout")

    async def test_settlement_failure_never_publishes_ok_or_retries_settlement(self):
        class BrokenSettlement(RunBudgetLedger):
            settlements = 0
            def settle(self, reservation_id, usage, *, outcome):
                self.settlements += 1
                raise RuntimeError("storage error")
        budget = BrokenSettlement()
        adapter = PolicyServiceAdapter(transport=MockPolicyTransport(fixtures()), manifest=manifest(),
                                       registry=registry(), budget=budget)
        result = await adapter.decide(make_request())
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, "budget_settlement_failed")
        self.assertEqual(result.proposed_calls, ())
        self.assertTrue(all(record.status != "ok" for record in adapter.records))
        self.assertEqual(budget.settlements, 1)
        self.assertEqual(budget.summary()["pending"], 1)
        next_result = await adapter.decide(make_request(2))
        self.assertEqual(next_result.error_code, "budget_settlement_failed")
        self.assertEqual(next_result.status, "blocked")
        self.assertEqual(budget.summary()["counts"]["model"], 1)

    async def test_settlement_failure_does_not_replace_primary_cancellation(self):
        class BrokenSettlement(RunBudgetLedger):
            def settle(self, reservation_id, usage, *, outcome):
                raise RuntimeError("storage error")
        transport = HangingTransport()
        adapter = PolicyServiceAdapter(transport=transport, manifest=manifest(),
                                       registry=registry(), budget=BrokenSettlement())
        pending = asyncio.create_task(adapter.decide(make_request()))
        await transport.started.wait()
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertEqual(adapter.records[-1].status, "cancelled")
        self.assertEqual(adapter.records[-1].error_code, "budget_settlement_failed")
        self.assertEqual(adapter.records[-1].proposed_calls, ())

    async def test_deadline_or_cancellation_during_parse_or_settle_blocks_publication(self):
        for phase in ("parse", "settle"):
            for interruption in ("deadline", "cancel_event", "budget_cancel"):
                with self.subTest(phase=phase, interruption=interruption):
                    now = [1000.0]
                    cancel = asyncio.Event()
                    class AdvancingBudget(RunBudgetLedger):
                        def settle(self, reservation_id, usage, *, outcome):
                            super().settle(reservation_id, usage, outcome=outcome)
                            if phase == "settle":
                                interrupt()
                    budget = AdvancingBudget(BudgetLimits(max_seconds=1.0),
                        clock=lambda: now[0], monotonic=lambda: now[0])
                    def interrupt():
                        if interruption == "deadline":
                            now[0] += 2.0
                        elif interruption == "cancel_event":
                            cancel.set()
                        else:
                            budget.cancel()
                    registered = registry()
                    original_parse = registered.parse
                    def interrupted_parse(response):
                        result = original_parse(response)
                        if phase == "parse":
                            interrupt()
                        return result
                    registered.parse = interrupted_parse
                    transport = EditedTransport(lambda response: {
                        "usage": PolicyUsage(input_tokens=20, output_tokens=8, cost=0.01)})
                    adapter = PolicyServiceAdapter(transport=transport, manifest=manifest(),
                                                   registry=registered, budget=budget)
                    result = await adapter.decide(make_request(), cancel_event=cancel)
                    expected_code = "cancelled" if interruption == "cancel_event" else "budget_exceeded"
                    self.assertEqual(result.error_code, expected_code)
                    self.assertEqual(result.status, "cancelled" if interruption == "cancel_event" else "failed")
                    self.assertEqual(result.proposed_calls, ())
                    self.assertEqual(result.usage.input_tokens, 20)
                    self.assertEqual(result.usage.output_tokens, 8)
                    self.assertEqual(budget.summary()["pending"], 0)
                    self.assertEqual(budget.summary()["charged_tokens"], 28)
                    self.assertEqual(budget.summary()["counts"]["model"], 1)
                    self.assertEqual(len(adapter.records), 1)
                    self.assertNotEqual(adapter.records[0].status, "ok")


if __name__ == "__main__":
    unittest.main()
