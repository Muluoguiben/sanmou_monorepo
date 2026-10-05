"""Offline policy-in-loop development cases; no provider or live action."""
import asyncio
import copy
import json
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pioneer_agent.agent_harness.journal import InMemoryJournalStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.run_store import JsonRunStore, MemoryRunStore
from pioneer_agent.agent_harness.task_contracts import (
    BudgetExceeded, PolicyContext, PolicyDecision, TaskSpec,
)
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy, RuleDecisionPolicy
from pioneer_agent.agent_harness.task_runner import TaskRunner
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
from pioneer_agent.runbook.models import Condition

BASE = datetime.fromisoformat("2026-08-26T10:00:00+08:00")
FIXTURE = Path(__file__).parent / "fixtures/agent_harness/recommendation_ready.json"


class SequenceClient:
    def __init__(self, *, count=0, evidence=True, mutate=None, after_call=None):
        self.count, self.evidence, self.mutate, self.after_call = count, evidence, mutate, after_call
        self.calls = []
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))["game"]

    async def call_tool(self, name, arguments):
        self.calls.append(name)
        if name == "observe_game":
            self.count += 1
        raw = copy.deepcopy(self.fixture[name])
        payload = raw["structuredContent"]
        if "observation" in payload:
            obs = payload["observation"]
            obs["observation_id"] = f"obs-{self.count}"
            obs["captured_at"] = (BASE + timedelta(seconds=self.count)).isoformat()
            obs["frame_sha256"] = f"{self.count:064x}"
        if "runtime_state" in payload:
            state = payload["runtime_state"]
            state["progress"]["current_chapter_id"] = self.count
            if self.evidence:
                state["field_meta"] = {"progress.current_chapter_id": {
                    "source": "vision.chapter_panel", "observation_id": f"obs-{self.count}",
                    "updated_at": (BASE + timedelta(seconds=self.count)).isoformat(),
                }}
        if self.mutate:
            self.mutate(name, payload)
        if self.after_call:
            self.after_call(name)
        return raw


class PortBudget:
    """Contract test double only. Real B implementation has separate wiring tests."""
    def __init__(self, limit=100):
        self.calls, self.settled, self.limit, self.cancelled = [], [], limit, False
    def reserve(self, request):
        if self.cancelled or len(self.calls) >= self.limit:
            raise BudgetExceeded()
        self.calls.append(request)
        return str(len(self.calls))
    def settle(self, reservation_id, usage, *, outcome):
        self.settled.append(reservation_id)
    def remaining_seconds(self):
        return 60
    def cancel(self):
        self.cancelled = True
    def snapshot(self):
        return {"consumed": len(self.calls)}
    def restore(self, snapshot):
        self.calls = [None] * snapshot["consumed"]


class PortContext:
    def build(self, request):
        return PolicyContext(run_id=request.run_id, step_id=request.step_id,
            observation_id=request.observation_id, text=request.model_dump_json(),
            estimated_input_tokens=10, reserved_output_tokens=10, evidence_refs=request.evidence_refs)


class PortTrace:
    def __init__(self):
        self.events = []
    def emit(self, event):
        self.events.append(event.model_copy(deep=True))


def task(**kwargs):
    return TaskSpec(task_id="chapter-observer", goal="observe chapter 3", success_when=[
        Condition(metric="progress.current_chapter_id", op=">=", value=3)],
        required_domains=["chapter_panel"], **kwargs)


def runner(client=None, *, store=None, policy=None, spec=None, budget=None, context=None, trace=None):
    client = client or SequenceClient()
    harness = RecommendationHarness(game_client=client, journal_store=InMemoryJournalStore(),
        tool_log=InMemoryToolLog(), agent_session_id="run", model_id="offline-rule",
        clock=lambda: BASE + timedelta(seconds=client.count + 1))
    return TaskRunner(task=spec or task(), run_id="run", harness=harness,
        store=store or MemoryRunStore(), policy=policy or RuleDecisionPolicy(),
        context_builder=context or PortContext(), budget=budget or PortBudget(), trace=trace or PortTrace())


class TaskRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_frozen_development_policy_cases(self):
        cases = json.loads((FIXTURE.parent / "task_cases_v1.json").read_text())
        self.assertFalse(cases["independent_holdout"])
        for case in cases["cases"]:
            with self.subTest(case=case["id"]):
                policy = RuleDecisionPolicy() if case["policy"] == "rule" else FakeDecisionPolicy([
                    PolicyDecision(action="succeed", reason="unsupported claim")])
                result = await runner(SequenceClient(evidence=case["field_evidence"]),
                    spec=task(max_steps=case["max_steps"]), policy=policy).run()
                self.assertEqual((result.status, result.reason, result.completed_steps),
                    (case["status"], case["reason"], case["steps"]))

    async def test_three_fresh_observations_and_terminal_noop(self):
        client = SequenceClient()
        r = runner(client)
        result = await r.run()
        self.assertEqual((result.status, result.completed_steps), ("succeeded", 3))
        self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])
        calls = list(client.calls)
        self.assertEqual((await r.run()).status, "succeeded")
        self.assertEqual(client.calls, calls)
        self.assertEqual(len(r.budget.calls), len(r.budget.settled))
        self.assertFalse(result.executable)

    async def test_missing_field_evidence_never_succeeds(self):
        r = runner(SequenceClient(evidence=False), spec=task(max_steps=3))
        result = await r.run()
        self.assertEqual((result.status, result.reason), ("failed", "step_limit"))

    async def test_policy_cannot_assert_success(self):
        r = runner(policy=FakeDecisionPolicy([PolicyDecision(action="succeed", reason="guess")]))
        self.assertEqual((await r.run()).reason, "unverified_success_proposal")

    async def test_pause_and_restart_reobserves_without_repeating_cursor(self):
        with TemporaryDirectory() as tmp:
            store = JsonRunStore(Path(tmp) / "checkpoint.json")
            first = runner(store=store, policy=FakeDecisionPolicy([PolicyDecision(action="pause", reason="operator")]))
            self.assertEqual((await first.run()).status, "paused")
            second_client = SequenceClient(count=1)
            second = runner(second_client, store=store)
            self.assertEqual((await second.run()).status, "paused")
            self.assertEqual(second_client.calls, [])
            result = await second.run(resume=True)
            self.assertEqual((result.status, result.completed_steps), ("succeeded", 3))
            self.assertEqual(second_client.calls.count("observe_game"), 2)
            self.assertEqual(store.load().status, "succeeded")

    async def test_cancel_after_call_prevents_next_call(self):
        client = SequenceClient()
        r = runner(client)
        client.after_call = lambda _: r.cancel()
        result = await r.run()
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(client.calls, ["session_status"])

    async def test_pause_after_call_prevents_next_call(self):
        client = SequenceClient()
        r = runner(client)
        client.after_call = lambda _: r.pause()
        self.assertEqual((await r.run()).status, "paused")
        self.assertEqual(client.calls, ["session_status"])

    async def test_cancelled_error_persisted_and_propagated(self):
        class CancelPolicy(RuleDecisionPolicy):
            async def decide(self, context):
                raise asyncio.CancelledError()
        r = runner(policy=CancelPolicy())
        with self.assertRaises(asyncio.CancelledError):
            await r.run()
        self.assertEqual(r.store.load().status, "cancelled")

    async def test_restart_rejects_old_observation(self):
        store = MemoryRunStore()
        r = runner(store=store, policy=FakeDecisionPolicy([PolicyDecision(action="pause", reason="pause")]))
        await r.run()
        restarted = runner(store=store)
        self.assertEqual((await restarted.run(resume=True)).reason, "reused_observation")

    async def test_session_changes_stop_before_observe(self):
        def mutate(name, payload):
            if name == "session_status" and client.count:
                payload["session"]["session_id"] = "different"
        client = SequenceClient(mutate=mutate)
        result = await runner(client).run()
        self.assertEqual(result.reason, "session_identity_changed")
        self.assertEqual(client.calls.count("observe_game"), 1)

    async def test_inactive_or_control_session_rejected(self):
        for key, value in (("active", False), ("observe_only", False)):
            def mutate(name, payload):
                if name == "session_status":
                    payload["session"][key] = value
            client = SequenceClient(mutate=mutate)
            self.assertEqual((await runner(client).run()).reason, "session_permission_violation")
            self.assertEqual(client.calls, ["session_status"])

    async def test_stale_policy_result_is_rejected(self):
        client = SequenceClient()
        class SlowPolicy(RuleDecisionPolicy):
            async def decide(self, context):
                client.count += 500
                return await super().decide(context)
        self.assertEqual((await runner(client, policy=SlowPolicy()).run()).reason, "observation_stale")

    async def test_budget_exhaustion_dispatches_no_extra_tool(self):
        client = SequenceClient()
        result = await runner(client, budget=PortBudget(limit=2)).run()
        self.assertEqual((result.status, result.reason), ("failed", "budget_exhausted"))
        self.assertEqual(client.calls, ["session_status"])

    async def test_schema_error_has_no_success_log(self):
        def mutate(name, payload):
            if name == "observe_game":
                payload["execution_authority"] = "live"
        r = runner(SequenceClient(mutate=mutate))
        self.assertEqual((await r.run()).status, "failed")
        events = [event for event in r.trace.events if event.name == "observe_game"]
        self.assertEqual((events[0].transport, events[0].contract), ("ok", "error"))
        self.assertFalse(r.harness.tool_log.records[-1].success)

    async def test_stop_condition_wins_over_success(self):
        spec = task(stop_when=[Condition(metric="progress.current_chapter_id", op=">=", value=1)])
        self.assertEqual((await runner(spec=spec).run()).reason, "stop_condition")

    async def test_disallowed_tool_never_dispatched(self):
        client = SequenceClient()
        result = await runner(client, spec=task(allowed_tools=[])).run()
        self.assertEqual(result.reason, "tool_not_allowed")
        self.assertEqual(client.calls, [])

    async def test_old_field_metadata_cannot_prove_current_goal(self):
        def mutate(name, payload):
            if name == "get_runtime_state":
                payload["runtime_state"]["field_meta"]["progress.current_chapter_id"]["observation_id"] = "old"
        result = await runner(SequenceClient(mutate=mutate), spec=task(max_steps=3)).run()
        self.assertEqual(result.status, "failed")

    async def test_policy_context_mutation_cannot_rewrite_goal(self):
        class MutatingContext(PortContext):
            def build(self, request):
                request.authoritative_state["progress"]["current_chapter_id"] = 500
                request.task.success_when[0].value = 0
                return super().build(request)
        result = await runner(context=MutatingContext(), spec=task(max_steps=1)).run()
        self.assertEqual(result.status, "failed")

    async def test_crash_pending_call_reobserves_and_preserves_cursor(self):
        store = MemoryRunStore()
        first = runner(store=store, policy=FakeDecisionPolicy([PolicyDecision(action="pause", reason="pause")]))
        await first.run()
        checkpoint = store.load()
        checkpoint.status = "running"
        checkpoint.pending_call = "get_runtime_state"
        store.save(checkpoint)
        client = SequenceClient(count=1)
        resumed = runner(client, store=store)
        result = await resumed.run()
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(client.calls[:2], ["session_status", "observe_game"])
        self.assertEqual(result.completed_steps, 3)

    async def test_wait_can_be_cancelled_without_next_observation(self):
        r = runner(spec=task(wait_seconds=30))
        running = asyncio.create_task(r.run())
        for _ in range(100):
            await asyncio.sleep(0)
            if r.state.status == "waiting":
                break
        self.assertEqual(r.state.status, "waiting")
        r.cancel()
        result = await asyncio.wait_for(running, 1)
        self.assertEqual(result.status, "cancelled")
        self.assertEqual(r._client.calls.count("observe_game"), 1)


if __name__ == "__main__":
    unittest.main()
