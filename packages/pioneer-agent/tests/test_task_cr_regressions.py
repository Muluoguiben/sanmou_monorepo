"""CR01-CR03 deterministic cut points, real B services, no live calls."""
import asyncio
import unittest

from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from pioneer_agent.agent_harness.run_store import MemoryRunStore
from pioneer_agent.agent_harness.task_contracts import PolicyDecision
from test_task_runner import SequenceClient, runner


class CheckpointInterruptStore(MemoryRunStore):
    def __init__(self, action, boundary):
        super().__init__()
        self.action, self.boundary = action, boundary
        self.owner = None
        self.armed = True

    def save(self, state):
        super().save(state)
        if self.armed and state.pending_call == self.boundary:
            self.armed = False
            getattr(self.owner, self.action)()


class ModelPolicy:
    policy_id = "cr-policy"
    uses_model = True

    def __init__(self):
        self.calls = 0

    async def decide(self, context):
        self.calls += 1
        return PolicyDecision(action="continue", reason="observe")


class TaskCRRegressions(unittest.IsolatedAsyncioTestCase):
    async def test_cr01_cancel_after_checkpoint_before_tool_or_policy(self):
        for boundary in ("session_status", "policy:cr-policy"):
            with self.subTest(boundary=boundary):
                store = CheckpointInterruptStore("cancel", boundary)
                client, policy = SequenceClient(), ModelPolicy()
                r = runner(client, store=store, policy=policy)
                store.owner = r
                result = await r.run()
                self.assertFalse(store.armed)
                self.assertEqual((result.status, result.reason), ("cancelled", "cancel_requested"))
                self.assertEqual(len(client.calls), 0 if boundary == "session_status" else 4)
                self.assertEqual(policy.calls, 0)
                self.assertEqual(r.budget.summary()["pending"], 0)
                self.assertEqual(result.completed_steps, 0)
                event = next(e for e in r.trace.events if e.event == (
                    "tool" if boundary == "session_status" else "policy"))
                self.assertEqual((event.transport, event.contract), ("not_attempted", "not_checked"))
                self.assertEqual(event.business, "cancel_requested")
                restarted_client = SequenceClient(count=client.count)
                restarted = runner(restarted_client, store=store)
                self.assertEqual((await restarted.run(resume=True)).status, "cancelled")
                self.assertEqual(restarted_client.calls, [])

    async def test_cr02_pause_after_checkpoint_before_tool_or_policy(self):
        for boundary in ("session_status", "policy:cr-policy"):
            with self.subTest(boundary=boundary):
                store = CheckpointInterruptStore("pause", boundary)
                client, policy = SequenceClient(), ModelPolicy()
                r = runner(client, store=store, policy=policy)
                store.owner = r
                result = await r.run()
                self.assertEqual((result.status, result.reason), ("paused", "pause_requested"))
                self.assertEqual(len(client.calls), 0 if boundary == "session_status" else 4)
                self.assertEqual(policy.calls, 0)
                self.assertEqual(result.completed_steps, 0)
                prior_counts = r.budget.summary()["counts"]
                self.assertEqual(r.budget.summary()["pending"], 0)
                event = next(e for e in r.trace.events if e.event == (
                    "tool" if boundary == "session_status" else "policy"))
                self.assertEqual((event.transport, event.contract), ("not_attempted", "not_checked"))
                self.assertEqual(event.business, "pause_requested")
                resumed_client = SequenceClient(count=client.count)
                resumed = runner(resumed_client, store=store)
                self.assertEqual(resumed.budget.summary()["counts"], prior_counts)
                done = await resumed.run(resume=True)
                self.assertEqual(done.status, "succeeded")
                self.assertEqual(resumed_client.calls[:2], ["session_status", "observe_game"])
                self.assertGreater(resumed.budget.summary()["counts"]["step"], prior_counts["step"])
                self.assertEqual(resumed.budget.summary()["counts"]["model"], prior_counts["model"])

    async def check_policy_trace(self, policy, expected, *, budget=None, cancelled=False):
        r = runner(policy=policy, budget=budget)
        if cancelled:
            with self.assertRaises(asyncio.CancelledError):
                await r.run()
        else:
            await r.run()
        event = next(e for e in r.trace.events if e.event == "policy")
        self.assertEqual((event.transport, event.contract, event.business), expected)
        self.assertIsNone(event.usage.input_tokens)
        self.assertIsNone(event.usage.output_tokens)
        self.assertIsNone(event.usage.cost)
        self.assertEqual(r.budget.summary()["counts"]["model"], 1)
        self.assertEqual(r.budget.summary()["pending"], 0)
        self.assertIsNone(r.budget.summary()["measured_tokens"])
        self.assertIsNone(r.budget.summary()["measured_cost"])
        return r

    async def test_cr03_invalid_return_is_transport_ok_contract_error(self):
        class Invalid(ModelPolicy):
            async def decide(self, context):
                return {"action": "succeed", "reason": "bad", "executable": True}
        await self.check_policy_trace(Invalid(), ("ok", "error", "error"))

    async def test_cr03_connection_failure_does_not_validate(self):
        class Broken(ModelPolicy):
            async def decide(self, context):
                raise ConnectionError("synthetic")
        await self.check_policy_trace(Broken(), ("error", "not_checked", "error"))

    async def test_cr03_policy_timeout_does_not_validate(self):
        class ShortPolicyBudget(RunBudgetLedger):
            model_reserved = False
            def reserve(self, request):
                result = super().reserve(request)
                self.model_reserved |= request.kind == "model"
                return result
            def remaining_seconds(self):
                remaining = super().remaining_seconds()
                return min(remaining, 0.01) if self.model_reserved else remaining
        class Slow(ModelPolicy):
            async def decide(self, context):
                await asyncio.sleep(60)
        r = await self.check_policy_trace(Slow(), ("error", "not_checked", "error"),
                                         budget=ShortPolicyBudget())
        self.assertEqual(r.state.reason, "run_deadline")

    async def test_cr03_async_cancel_does_not_validate(self):
        class Cancelled(ModelPolicy):
            async def decide(self, context):
                raise asyncio.CancelledError()
        r = await self.check_policy_trace(Cancelled(), ("cancelled", "not_checked", "error"), cancelled=True)
        self.assertEqual(r.store.load().status, "cancelled")

    async def test_cr03_valid_business_stop_is_separate(self):
        class Stop(ModelPolicy):
            async def decide(self, context):
                return PolicyDecision(action="stop", reason="bounded refusal")
        r = await self.check_policy_trace(Stop(), ("ok", "ok", "stop"))
        self.assertEqual(r.state.reason, "policy_stop")

    async def test_cr01_cancel_wins_when_inflight_tool_or_policy_times_out(self):
        for boundary in ("tool", "policy"):
            with self.subTest(boundary=boundary):
                class TimeoutClient(SequenceClient):
                    async def call_tool(self, name, arguments):
                        r.cancel()
                        raise TimeoutError()
                class TimeoutPolicy(ModelPolicy):
                    async def decide(self, context):
                        r.cancel()
                        raise TimeoutError()
                r = runner(TimeoutClient()) if boundary == "tool" else runner(policy=TimeoutPolicy())
                result = await r.run()
                self.assertEqual((result.status, result.reason), ("cancelled", "cancel_requested"))
                self.assertEqual(r.budget.summary()["pending"], 0)


if __name__ == "__main__":
    unittest.main()
