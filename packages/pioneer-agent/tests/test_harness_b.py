"""Offline B component tests; synthetic metadata/Fake calls, no provider/game IO."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest

from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder, ContextLimits, estimate_text_tokens
from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger, TokenPrices
from pioneer_agent.agent_harness.run_trace import InMemoryRunTrace, JsonlRunTrace
from pioneer_agent.agent_harness.read_only_retry import call_read_only_with_retry
from pioneer_agent.agent_harness.task_contracts import (
    BudgetExceeded, BudgetRequest, ContextOverflow, ContextRequest, TaskSpec, TraceEvent, Usage,
)


def request(kind="model", **kwargs):
    if kind == "model" and "input_tokens" not in kwargs and "output_tokens" not in kwargs:
        kwargs["input_tokens"] = 1
    return BudgetRequest(run_id="run", step_id="step", kind=kind, name="session_status", **kwargs)


def context(**kwargs):
    return ContextRequest(run_id="run", step_id="step", observation_id="fresh",
                          task=TaskSpec(task_id="task", goal="Observe wood safely", success_when=[
                              {"metric": "economy.resources.wood", "op": ">=", "value": 3}]),
                          authoritative_state={"wood": 1}, evidence_refs=["observation:fresh"], **kwargs)


class Clock:
    def __init__(self):
        self.now = 1000.0
    def __call__(self):
        return self.now


class ContextTests(unittest.TestCase):
    def test_safety_goal_latest_state_and_provenance_survive_history_pressure(self):
        req = context(safety_rules=["never publish"], history=[{"wood": 999, "inferred": True, "text": "x" * 9000}])
        built = BoundedContextBuilder(ContextLimits(max_tokens=1800, output_tokens=100)).build(req)
        payload = json.loads(built.text)
        self.assertTrue(built.truncated)
        self.assertEqual(payload["authoritative_state"], {"wood": 1})
        self.assertEqual(payload["history_non_authoritative"], [])
        self.assertEqual(payload["task"]["goal"], req.task.goal)
        self.assertEqual(payload["task"]["success_when"], req.task.model_dump()["success_when"])
        self.assertIn("never publish", payload["safety_rules"])
        self.assertIn("execution_authority=none", payload["safety_rules"])
        self.assertEqual(payload["evidence_refs"], ["observation:fresh"])
        self.assertLessEqual(built.estimated_input_tokens + built.reserved_output_tokens, 1800)

    def test_mandatory_payload_never_silently_truncated(self):
        for req in (context(), context(images=[{"width": 512, "height": 512}])):
            with self.assertRaises(ContextOverflow):
                BoundedContextBuilder(ContextLimits(max_tokens=200, output_tokens=100)).build(req)

    def test_output_reserve_and_exact_token_boundary(self):
        first = BoundedContextBuilder().build(context())
        cap = first.estimated_input_tokens + first.reserved_output_tokens
        BoundedContextBuilder(ContextLimits(max_tokens=cap)).build(context())
        with self.assertRaises(ContextOverflow):
            BoundedContextBuilder(ContextLimits(max_tokens=cap - 1)).build(context())

    def test_detached_context_and_current_observation_precedence(self):
        req = context(history=[{"inferred": {"wood": 99}, "evidence_refs": ["observation:old"]}])
        before = req.model_dump_json()
        built = BoundedContextBuilder().build(req)
        self.assertEqual(req.model_dump_json(), before)
        built.evidence_refs.append("poison")
        self.assertEqual(req.evidence_refs, ["observation:fresh"])
        payload = json.loads(built.text)
        self.assertEqual(payload["authoritative_state"]["wood"], 1)
        self.assertEqual(payload["history_non_authoritative"][0]["evidence_refs"], ["observation:old"])

    def test_text_estimate_is_deterministic_for_cjk_and_mixed_text(self):
        text = "体力不足? 🐉 abc"
        self.assertEqual(estimate_text_tokens(text), len(text.encode("utf-8")) + 32)

    def test_image_metadata_caps(self):
        cases = [
            ({"max_images": 0}, [{"width": 1, "height": 1}]),
            ({"max_image_pixels": 20}, [{"width": 5, "height": 5}]),
            ({"max_total_pixels": 30}, [{"width": 5, "height": 5}] * 2),
            ({"max_image_tokens": 100}, [{"width": 1, "height": 1}]),
            ({}, [{"width": 1, "height": 1, "token_estimate": -1}]),
            ({}, [{"width": True, "height": 1}]),
            ({}, [{"width": 1, "height": 1, "path": "private.png"}]),
        ]
        for limits, images in cases:
            with self.subTest(limits=limits, images=images), self.assertRaises(ContextOverflow):
                BoundedContextBuilder(ContextLimits(**limits)).build(context(images=images))

    def test_understated_image_estimate_cannot_bypass_budget(self):
        req = context(images=[{"width": 512, "height": 512, "token_estimate": 0}])
        built = BoundedContextBuilder().build(req)
        self.assertEqual(built.estimated_input_tokens, estimate_text_tokens(built.text) + 255)
        with self.assertRaises(ContextOverflow):
            BoundedContextBuilder(ContextLimits(max_image_tokens=254)).build(req)


class BudgetTests(unittest.TestCase):
    def test_each_dimension_denies_before_dispatch(self):
        for kind, option in (("step", "max_steps"), ("tool", "max_tool_calls"), ("model", "max_model_attempts")):
            with self.subTest(kind=kind):
                ledger = RunBudgetLedger(BudgetLimits(**{option: 1}))
                reservation = ledger.reserve(request(kind))
                ledger.settle(reservation, Usage(), outcome="error")
                with self.assertRaises(BudgetExceeded):
                    ledger.reserve(request(kind))
                self.assertEqual(ledger.summary()["counts"][kind], 1)

    def test_token_denial_is_atomic_and_exact_cap_is_allowed(self):
        ledger = RunBudgetLedger(BudgetLimits(max_tokens=10))
        ledger.reserve(request(input_tokens=6, output_tokens=4))
        before = ledger.summary()
        with self.assertRaises(BudgetExceeded):
            ledger.reserve(request(input_tokens=1))
        self.assertEqual(ledger.summary()["counts"], before["counts"])
        self.assertEqual(ledger.summary()["charged_tokens"], 10)

    def test_missing_and_partial_usage_keeps_unknown_and_reservations(self):
        ledger = RunBudgetLedger(BudgetLimits(max_tokens=20))
        reservation = ledger.reserve(request(input_tokens=7, output_tokens=5))
        ledger.settle(reservation, Usage(input_tokens=3), outcome="error")
        summary = ledger.summary()
        self.assertEqual(summary["charged_tokens"], 8)
        self.assertIsNone(summary["measured_tokens"])
        self.assertIsNone(summary["measured_cost"])
        self.assertIsNone(summary["charged_cost"])
        self.assertEqual(summary["unknown_token_attempts"], 1)

    def test_actual_usage_reconciles_and_duplicate_settlement_never_refunds(self):
        ledger = RunBudgetLedger(BudgetLimits(max_tokens=20))
        reservation = ledger.reserve(request(input_tokens=10, output_tokens=10))
        ledger.settle(reservation, Usage(input_tokens=2, output_tokens=3, cost=0.1), outcome="ok")
        self.assertEqual(ledger.summary()["charged_tokens"], 5)
        self.assertEqual(ledger.summary()["measured_tokens"], 5)
        with self.assertRaises(ValueError):
            ledger.settle(reservation, Usage(input_tokens=0, output_tokens=0), outcome="ok")
        with self.assertRaises(ValueError):
            ledger.settle("unknown", Usage(), outcome="ok")
        self.assertEqual(ledger.summary()["charged_tokens"], 5)

    def test_actual_overrun_latches_stop_even_for_zero_token_tools(self):
        ledger = RunBudgetLedger(BudgetLimits(max_tokens=10))
        reservation = ledger.reserve(request(input_tokens=2, output_tokens=2))
        ledger.settle(reservation, Usage(input_tokens=20, output_tokens=1), outcome="ok")
        with self.assertRaises(BudgetExceeded):
            ledger.reserve(request("tool"))
        self.assertTrue(ledger.summary()["overrun"])

    def test_multi_worker_race_has_one_winner(self):
        ledger = RunBudgetLedger(BudgetLimits(max_tokens=10))
        barrier = threading.Barrier(8)
        def compete(_):
            barrier.wait()
            try:
                return ledger.reserve(request(input_tokens=10))
            except BudgetExceeded:
                return None
        with ThreadPoolExecutor(max_workers=8) as workers:
            results = list(workers.map(compete, range(8)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(ledger.summary()["counts"]["model"], 1)

    def test_cancel_denies_every_kind_but_allows_settlement(self):
        ledger = RunBudgetLedger()
        reservation = ledger.reserve(request(input_tokens=10))
        ledger.cancel()
        ledger.settle(reservation, Usage(), outcome="cancelled")
        for kind in ("step", "tool", "model"):
            with self.assertRaises(BudgetExceeded):
                ledger.reserve(request(kind))
        self.assertEqual(ledger.summary()["charged_tokens"], 10)

    def test_time_includes_wait_cleanup_downtime_and_monotonic_rollback_guard(self):
        wall, mono = Clock(), Clock()
        ledger = RunBudgetLedger(BudgetLimits(max_seconds=10.0), clock=wall, monotonic=mono)
        wall.now -= 3
        mono.now += 8
        self.assertEqual(ledger.remaining_seconds(), 2)
        mono.now += 2
        with self.assertRaises(BudgetExceeded):
            ledger.reserve(request("tool"))

    def test_restore_keeps_pending_consumption_and_original_deadline(self):
        clock = Clock()
        limits = BudgetLimits(max_seconds=10.0, max_model_attempts=1)
        ledger = RunBudgetLedger(limits, clock=clock, monotonic=clock)
        ledger.reserve(request(input_tokens=8))
        clock.now += 2
        snapshot = json.loads(json.dumps(ledger.snapshot()))
        clock.now += 5
        restored = RunBudgetLedger(limits, clock=clock, monotonic=clock)
        restored.restore(snapshot)
        self.assertEqual(restored.remaining_seconds(), 3)
        self.assertEqual(restored.summary()["charged_tokens"], 8)
        self.assertIsNone(restored.summary()["measured_tokens"])
        with self.assertRaises(BudgetExceeded):
            restored.reserve(request())
        clock.now += 4
        with self.assertRaises(BudgetExceeded):
            restored.reserve(request("tool"))

    def test_restore_rejects_quota_reset_or_mismatched_run(self):
        ledger = RunBudgetLedger()
        ledger.reserve(request())
        snapshot = ledger.snapshot()
        with self.assertRaises(ValueError):
            ledger.restore(snapshot)
        with self.assertRaises(ValueError):
            RunBudgetLedger(BudgetLimits(max_steps=100)).restore(snapshot)
        snapshot["run_id"] = "other"
        with self.assertRaises(ValueError):
            RunBudgetLedger().restore(snapshot)

    def test_restore_cancelled_and_unknown_version_fail_closed(self):
        ledger = RunBudgetLedger()
        ledger.cancel()
        restored = RunBudgetLedger()
        restored.restore(ledger.snapshot())
        with self.assertRaises(BudgetExceeded):
            restored.reserve(request())
        invalid = ledger.snapshot()
        invalid["version"] = 2
        with self.assertRaises(ValueError):
            RunBudgetLedger().restore(invalid)

    def test_unknown_price_does_not_claim_zero_or_pass_cost_cap(self):
        ledger = RunBudgetLedger(BudgetLimits(max_cost=1.0))
        with self.assertRaisesRegex(BudgetExceeded, "unknown_price"):
            ledger.reserve(request(input_tokens=1))
        self.assertEqual(ledger.summary()["counts"]["model"], 0)

    def test_model_requires_nonzero_reserve_even_when_usage_is_unknown(self):
        ledger = RunBudgetLedger()
        with self.assertRaisesRegex(BudgetExceeded, "model_token_reservation_required"):
            ledger.reserve(request(input_tokens=0, output_tokens=0))
        self.assertEqual(ledger.summary()["counts"]["model"], 0)

    def test_exhausted_tokens_block_even_zero_token_tool_calls(self):
        ledger = RunBudgetLedger(BudgetLimits(max_tokens=10))
        ledger.reserve(request(input_tokens=10))
        with self.assertRaises(BudgetExceeded):
            ledger.reserve(request("tool"))

    def test_measured_cost_overrun_and_cross_run_requests_fail_closed(self):
        ledger = RunBudgetLedger(BudgetLimits(max_cost=1.0),
                                 prices=TokenPrices(input_per_token=0.1, output_per_token=0.2))
        reservation = ledger.reserve(request(input_tokens=1))
        ledger.settle(reservation, Usage(input_tokens=1, output_tokens=0, cost=2.0), outcome="ok")
        with self.assertRaises(BudgetExceeded):
            ledger.reserve(request("tool"))
        other = RunBudgetLedger()
        other.reserve(request("step"))
        bad = request("tool")
        bad.run_id = "other-run"
        with self.assertRaises(BudgetExceeded):
            other.reserve(bad)

    def test_restore_rejects_clock_rollback(self):
        clock = Clock()
        ledger = RunBudgetLedger(clock=clock, monotonic=clock)
        saved = ledger.snapshot()
        clock.now -= 1
        with self.assertRaises(ValueError):
            RunBudgetLedger(clock=clock, monotonic=clock).restore(saved)

    def test_explicit_prices_reserve_cost_unknown_usage_remains_unknown(self):
        ledger = RunBudgetLedger(BudgetLimits(max_cost=1.0),
                                 prices=TokenPrices(input_per_token=0.1, output_per_token=0.2))
        reservation = ledger.reserve(request(input_tokens=2, output_tokens=3))
        ledger.settle(reservation, Usage(), outcome="error")
        self.assertAlmostEqual(ledger.summary()["charged_cost"], 0.8)
        self.assertIsNone(ledger.summary()["measured_cost"])
        with self.assertRaises(BudgetExceeded):
            ledger.reserve(request(output_tokens=2))


class TraceTests(unittest.TestCase):
    def test_layered_outcomes_correlate_without_false_success(self):
        trace = InMemoryRunTrace()
        event = TraceEvent(run_id="run", step_id="s1", event="tool", name="observe_game",
                           attempt_id="a1", observation_id="o1", evidence_refs=["frame:abc"],
                           transport="ok", contract="error", error_type="ValidationError",
                           usage=Usage(), metadata={"model_id": "fake-v1", "policy_version": "v1"})
        trace.emit(event)
        got = trace.events[0]
        self.assertEqual((got.transport, got.contract, got.business), ("ok", "error", None))
        self.assertEqual((got.run_id, got.step_id, got.attempt_id, got.observation_id), ("run", "s1", "a1", "o1"))
        self.assertEqual(got.metadata["model_id"], "fake-v1")
        self.assertIsNone(got.usage.input_tokens)
        event.evidence_refs.clear()
        self.assertEqual(trace.events[0].evidence_refs, ["frame:abc"])

    def test_jsonl_keeps_unknown_and_redacts_free_text_secrets_images(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "run.jsonl"
            trace = JsonlRunTrace(path)
            trace.emit(TraceEvent(run_id="run", step_id="s1", event="tool", usage=Usage(),
                                  metadata={"authorization": "secret-value", "prompt": "private-goal",
                                            "image": "private-pixels", "nested": {"cookie": "private-cookie"}}))
            text = path.read_text(encoding="utf-8")
            for secret in ("secret-value", "private-goal", "private-pixels", "private-cookie"):
                self.assertNotIn(secret, text)
            data = json.loads(text)
            self.assertIsNone(data["usage"]["cost"])
            self.assertEqual(data["trace_id"], "run")
            self.assertEqual(data["transport"], "not_attempted")

    def test_impossible_contract_success_rejected(self):
        with self.assertRaises(ValueError):
            InMemoryRunTrace().emit(TraceEvent(run_id="r", step_id="s", event="tool",
                                               transport="error", contract="ok"))


class RetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_retry_each_attempt_accounted(self):
        ledger, trace = RunBudgetLedger(), InMemoryRunTrace()
        calls = 0
        async def call():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ConnectionError("private failure detail")
            return {"status": "blocked"}
        result = await call_read_only_with_retry(budget=ledger, trace=trace, request=request("tool"),
                                                call=call, validate=lambda x: x, backoff_seconds=0)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(calls, 3)
        self.assertEqual(ledger.summary()["counts"]["tool"], 3)
        self.assertEqual([x.transport for x in trace.events], ["error", "error", "ok"])
        self.assertEqual(trace.events[-1].business, "not_evaluated")
        self.assertEqual(len({x.attempt_id for x in trace.events}), 3)

    async def test_schema_permission_binding_and_business_errors_never_retry(self):
        for failure in (ValueError, PermissionError, ConnectionError):
            ledger, trace = RunBudgetLedger(), InMemoryRunTrace()
            calls = []
            async def call():
                calls.append(1)
                return {}
            def validate(raw):
                raise failure("invalid_contract_or_binding")
            with self.subTest(failure=failure), self.assertRaises(failure):
                await call_read_only_with_retry(budget=ledger, trace=trace, request=request("tool"),
                                               call=call, validate=validate, backoff_seconds=0)
            self.assertEqual(len(calls), 1)
            self.assertEqual((trace.events[0].transport, trace.events[0].contract), ("ok", "error"))

    async def test_quota_exhaustion_stops_retry_before_dispatch(self):
        ledger = RunBudgetLedger(BudgetLimits(max_tool_calls=1))
        calls = []
        async def call():
            calls.append(1)
            raise TimeoutError()
        with self.assertRaises(BudgetExceeded):
            await call_read_only_with_retry(budget=ledger, trace=InMemoryRunTrace(), request=request("tool"),
                                           call=call, validate=lambda x: x, backoff_seconds=0)
        self.assertEqual(len(calls), 1)

    async def test_cancellation_inflight_counts_and_prevents_next_dispatch(self):
        ledger, trace = RunBudgetLedger(), InMemoryRunTrace()
        entered = asyncio.Event()
        async def call():
            entered.set()
            await asyncio.Event().wait()
        pending = asyncio.create_task(call_read_only_with_retry(
            budget=ledger, trace=trace, request=request("tool"), call=call, validate=lambda x: x))
        await entered.wait()
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertEqual(trace.events[0].transport, "cancelled")
        self.assertEqual(ledger.summary()["pending"], 0)
        with self.assertRaises(BudgetExceeded):
            ledger.reserve(request("tool"))

    async def test_cancel_between_reservation_and_dispatch_prevents_call(self):
        class CancelsAtReserve(RunBudgetLedger):
            def reserve(self, req):
                identity = super().reserve(req)
                self.cancel()
                return identity
        ledger = CancelsAtReserve()
        calls = []
        async def call():
            calls.append(1)
        with self.assertRaises(BudgetExceeded):
            await call_read_only_with_retry(budget=ledger, trace=InMemoryRunTrace(),
                                           request=request("tool"), call=call, validate=lambda x: x)
        self.assertEqual(calls, [])
        self.assertEqual(ledger.summary()["pending"], 0)

    async def test_timeout_and_backoff_stay_within_run_deadline(self):
        ledger = RunBudgetLedger(BudgetLimits(max_seconds=0.02))
        trace = InMemoryRunTrace()
        calls = []
        async def call():
            calls.append(1)
            await asyncio.Event().wait()
        with self.assertRaises(BudgetExceeded):
            await call_read_only_with_retry(budget=ledger, trace=trace, request=request("tool"),
                                           call=call, validate=lambda x: x)
        self.assertEqual(len(calls), 1)
        self.assertEqual(trace.events[0].error_type, "TimeoutError")

    async def test_pre_cancelled_and_noncanonical_call_never_dispatch(self):
        ledger = RunBudgetLedger()
        ledger.cancel()
        calls = []
        async def call():
            calls.append(1)
        with self.assertRaises(BudgetExceeded):
            await call_read_only_with_retry(budget=ledger, trace=InMemoryRunTrace(), request=request("tool"),
                                           call=call, validate=lambda x: x)
        bad = request("tool")
        bad.name = "click"
        with self.assertRaises(ValueError):
            await call_read_only_with_retry(budget=RunBudgetLedger(), trace=InMemoryRunTrace(), request=bad,
                                           call=call, validate=lambda x: x)
        self.assertEqual(calls, [])

    async def test_cancellation_during_backoff_cannot_start_next_attempt(self):
        ledger, trace = RunBudgetLedger(), InMemoryRunTrace()
        entered = asyncio.Event()
        calls = []
        async def call():
            calls.append(1)
            entered.set()
            raise ConnectionError()
        pending = asyncio.create_task(call_read_only_with_retry(
            budget=ledger, trace=trace, request=request("tool"), call=call,
            validate=lambda x: x, backoff_seconds=1.0))
        await entered.wait()
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertEqual(calls, [1])
        self.assertEqual(ledger.summary()["pending"], 0)
        self.assertTrue(ledger.summary()["cancelled"])

    async def test_retry_limit_and_permission_transport_error(self):
        for error, expected in ((ConnectionError, 3), (PermissionError, 1)):
            ledger, trace = RunBudgetLedger(), InMemoryRunTrace()
            calls = []
            async def call():
                calls.append(1)
                raise error()
            with self.assertRaises(error):
                await call_read_only_with_retry(
                    budget=ledger, trace=trace, request=request("tool"), call=call,
                    validate=lambda x: x, backoff_seconds=0)
            self.assertEqual(len(calls), expected)
            self.assertEqual(ledger.summary()["counts"]["tool"], expected)


if __name__ == "__main__":
    unittest.main()
