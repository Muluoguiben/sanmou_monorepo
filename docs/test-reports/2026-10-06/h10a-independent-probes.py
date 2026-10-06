"""Public-memo H10a controls, frozen before implementation. No private v2 API."""
import asyncio
import json
from pathlib import Path
import sys
import unittest

from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder
from pioneer_agent.agent_harness.journal import InMemoryJournalStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.run_store import MemoryRunStore
from pioneer_agent.agent_harness.run_trace import InMemoryRunTrace
from pioneer_agent.agent_harness.task_contracts import PolicyDecision, TraceEvent
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy, RuleDecisionPolicy
from pioneer_agent.agent_harness.task_runner import TaskRunner
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
from test_task_runner import BASE, PortBudget, SequenceClient, task, timedelta


def build(*, causal=True, client=None, trace=None, store=None, policy=None):
    client = client or SequenceClient()
    harness = RecommendationHarness(game_client=client, journal_store=InMemoryJournalStore(),
        tool_log=InMemoryToolLog(), agent_session_id="run", model_id="not-proof-of-model",
        clock=lambda: BASE + timedelta(seconds=client.count + 1))
    kwargs = dict(task=task(), run_id="run", harness=harness, store=store or MemoryRunStore(),
        policy=policy or RuleDecisionPolicy(), context_builder=BoundedContextBuilder(),
        budget=PortBudget(), trace=trace or InMemoryRunTrace())
    if causal:
        kwargs["causal_trace"] = True
    return TaskRunner(**kwargs)


async def default_snapshot():
    r = build(causal=False)
    first = await r.run()
    before = [event.model_dump(mode="json") for event in r.trace.events]
    second = await r.run()  # Terminal no-op must not append default events.
    return {"fields": sorted(TraceEvent.model_fields), "events": before,
        "after_terminal_events": [event.model_dump(mode="json") for event in r.trace.events],
        "statuses": [first.status, second.status], "calls": r._client.calls}


class EmitOnlySink:
    """Only the preexisting emit port; deliberately no new sink methods."""
    def __init__(self, fail_event):
        self.fail_event, self.failed, self.after_failure = fail_event, False, 0
        self.rows = []
    def emit(self, event):
        if self.failed:
            self.after_failure += 1
            raise OSError("PRIVATE_TRACE_FAILURE_SENTINEL")
        row = event.model_dump(mode="json")
        if row["event"] == self.fail_event:
            self.failed = True
            raise OSError("PRIVATE_TRACE_FAILURE_SENTINEL")
        self.rows.append(row)


class PublicMemoProbes(unittest.IsolatedAsyncioTestCase):
    async def test_default_v1_entire_event_sequence_matches_frozen_baseline(self):
        expected = json.loads(Path(__file__).with_name("h10a-default-v1-oracle.json").read_text())
        self.assertEqual(await default_snapshot(), expected)

    def check_graph(self, rows):
        known = {}
        for row in rows:
            self.assertEqual(row["trace_version"], 2)
            self.assertNotIn(row["event_id"], known)
            if row["event"] == "lifetime_start":
                self.assertIsNone(row["parent_event_id"])
                self.assertEqual(row["lifetime_id"], row["event_id"])
            else:
                self.assertIn(row["parent_event_id"], known)
                parent = known[row["parent_event_id"]]
                self.assertEqual(parent["lifetime_id"], row["lifetime_id"])
            if row.get("window_id") is not None and row["event"] != "window_start":
                self.assertIn(row["window_id"], known)
                self.assertEqual(known[row["window_id"]]["event"], "window_start")
            if row["event"] == "window_start":
                self.assertEqual(row["window_id"], row["event_id"])
                self.assertEqual(row["parent_event_id"], row["lifetime_id"])
            known[row["event_id"]] = row

    async def test_three_observations_match_actual_call_ledger_and_graph(self):
        policy = FakeDecisionPolicy([PolicyDecision(action="continue", reason="observe") for _ in range(3)])
        r = build(policy=policy)
        self.assertEqual((await r.run()).reason, "goal_verified")
        rows = [event.model_dump(mode="json") for event in r.trace.events]
        self.check_graph(rows)
        self.assertEqual(len([row for row in rows if row["event"] == "lifetime_start"]), 1)
        self.assertEqual(len([row for row in rows if row["event"] == "window_start"]), 3)
        tools = [row for row in rows if row["event"] == "tool" and row["transport"] != "not_attempted"]
        policies = [row for row in rows if row["event"] == "policy" and row["transport"] != "not_attempted"]
        self.assertEqual([row["name"] for row in tools], r._client.calls)
        self.assertEqual([row["observation_id"] for row in policies], [ctx.observation_id for ctx in policy.contexts])
        self.assertEqual(len(tools), 12)
        self.assertEqual(len(policies), 3)
        ids = [row["invocation_id"] for row in tools + policies]
        self.assertTrue(all(ids))
        self.assertEqual(len(set(ids)), len(ids))
        self.assertTrue(all(row["attempt_id"] is None for row in policies))
        self.assertFalse(any(call.kind == "model" for call in r.budget.calls))
        observations = [row for row in rows if row["event"] == "observation"]
        self.assertEqual([row["observation_id"] for row in observations], ["obs-1", "obs-2", "obs-3"])

    async def test_same_object_and_fresh_runner_reentry_do_not_cross_lifetimes(self):
        for fresh in (False, True):
            with self.subTest(fresh=fresh):
                trace, store = InMemoryRunTrace(), MemoryRunStore()
                first = build(trace=trace, store=store,
                    policy=FakeDecisionPolicy([PolicyDecision(action="pause", reason="pause")]))
                self.assertEqual((await first.run()).status, "paused")
                second = build(trace=trace, store=store, client=SequenceClient(count=1)) if fresh else first
                second.policy = RuleDecisionPolicy()
                self.assertEqual((await second.run(resume=True)).reason, "goal_verified")
                rows = [event.model_dump(mode="json") for event in trace.events]
                self.check_graph(rows)
                roots = [row for row in rows if row["event"] == "lifetime_start"]
                self.assertEqual(len(roots), 2)
                self.assertNotEqual(roots[0]["lifetime_id"], roots[1]["lifetime_id"])
                self.assertEqual(second.state.observation_ids, ["obs-1", "obs-2", "obs-3"])

    async def test_tool_completion_sink_failure_is_visible_and_never_redispatches(self):
        sink = EmitOnlySink("tool")
        r = build(trace=sink)
        with self.assertRaises(Exception) as caught:
            await r.run()
        self.assertEqual(type(caught.exception).__name__, "TraceEmissionError")
        self.assertTrue(sink.failed)
        self.assertEqual(sink.after_failure, 0)
        self.assertEqual(r._client.calls, ["session_status"])
        self.assertEqual([call.kind for call in r.budget.calls], ["step", "tool"])

    async def test_policy_primary_is_not_replaced_by_secondary_trace_failure(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel):
                primary = asyncio.CancelledError() if cancel else ValueError("PRIVATE_POLICY_FAILURE_SENTINEL")
                class BrokenPolicy:
                    policy_id, uses_model = "review-policy", False
                    calls = 0
                    async def decide(self, context):
                        self.calls += 1
                        raise primary
                policy, sink = BrokenPolicy(), EmitOnlySink("policy")
                r = build(trace=sink, policy=policy)
                if cancel:
                    with self.assertRaises(asyncio.CancelledError) as caught:
                        await r.run()
                    self.assertIs(caught.exception, primary)
                else:
                    result = await r.run()
                    self.assertEqual((result.status, result.reason), ("failed", "runtime_error:ValueError"))
                self.assertTrue(sink.failed)
                self.assertEqual((policy.calls, len(r._client.calls), sink.after_failure), (1, 4, 0))
                notes = " ".join(getattr(primary, "__notes__", []))
                self.assertNotIn("PRIVATE_TRACE_FAILURE_SENTINEL", notes)


if __name__ == "__main__":
    if sys.argv[1:] == ["--capture-default"]:
        print(json.dumps(asyncio.run(default_snapshot()), ensure_ascii=False, indent=2))
    else:
        unittest.main(verbosity=2)
