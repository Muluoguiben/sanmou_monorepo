"""Fixed-public-schema H10a probes; independent digest and exception-path oracles."""
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import traceback
import unittest

from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder
from pioneer_agent.agent_harness.journal import InMemoryJournalStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.agent_harness.run_store import MemoryRunStore
from pioneer_agent.agent_harness.run_trace import InMemoryRunTrace, JsonlRunTrace
from pioneer_agent.agent_harness.task_contracts import CausalTraceEvent, PolicyDecision, TraceEmissionError, Usage
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy, RuleDecisionPolicy
from pioneer_agent.agent_harness.task_runner import TaskRunner
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
from test_task_approval import response_for
from test_task_runner import BASE, SequenceClient, task, timedelta


SENTINEL = "H10A_PRIVATE_SINK_OR_INPUT_71c9a2"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def build(policy=None, trace=None, spec=None):
    client = SequenceClient()
    harness = RecommendationHarness(game_client=client, journal_store=InMemoryJournalStore(),
        tool_log=InMemoryToolLog(), agent_session_id="run", model_id="merely-a-label",
        clock=lambda: BASE + timedelta(seconds=client.count + 1))
    return TaskRunner(task=spec or task(), run_id="run", harness=harness, store=MemoryRunStore(),
        policy=policy or RuleDecisionPolicy(), context_builder=BoundedContextBuilder(),
        budget=RunBudgetLedger(BudgetLimits(max_model_attempts=0)), trace=trace or InMemoryRunTrace(),
        causal_trace=True, synthetic_approval=True)


class TargetedProvenanceProbes(unittest.IsolatedAsyncioTestCase):
    async def test_actual_input_digest_is_independent_precall_snapshot(self):
        class RecordingPolicy:
            policy_id, uses_model = "custom-unknown", False
            def __init__(self): self.inputs = []
            async def decide(self, context):
                self.inputs.append(copy.deepcopy(context.model_dump(mode="json")))
                context.text = SENTINEL
                return PolicyDecision(action="continue", reason="continue")
        spec = task()
        spec.goal = "private task " + SENTINEL
        policy = RecordingPolicy()
        r = build(policy=policy, spec=spec)
        self.assertEqual((await r.run()).reason, "goal_verified")
        rows = [event.model_dump(mode="json") for event in r.trace.events]
        called = [row for row in rows if row["event"] == "policy"]
        self.assertEqual([row["provenance"]["context_digest"] for row in called], [digest(value) for value in policy.inputs])
        self.assertEqual({row["provenance"]["task_digest"] for row in rows}, {digest(spec.model_dump(mode="json"))})
        self.assertTrue(all(row["provenance"]["policy_version"]["status"] == "unknown" for row in called))
        self.assertTrue(all(row["provenance"]["model"]["status"] == "unknown" for row in called))
        self.assertNotIn(SENTINEL, json.dumps(rows))
        self.assertEqual(r.budget.summary()["counts"]["model"], 0)

    async def test_policy_completion_identity_is_frozen_with_invocation(self):
        class RenamingPolicy:
            policy_id, policy_version, uses_model = "before-call", "before-version", False
            async def decide(self, context):
                self.policy_id, self.policy_version = "after-call", "after-version"
                return PolicyDecision(action="continue", reason="continue")
        r = build(policy=RenamingPolicy(), spec=task(max_steps=1))
        await r.run()
        event = next(event for event in r.trace.events if event.event == "policy")
        self.assertEqual((event.name, event.metadata["policy_id"], event.provenance.policy_id,
                          event.provenance.policy_version.value),
                         ("before-call", "before-call", "before-call", "before-version"))

    async def test_new_trace_wrapper_traceback_does_not_expose_private_secondary_text(self):
        class SecretSink:
            def __init__(self): self.failure = OSError(SENTINEL)
            def emit(self, event): raise self.failure
        class InvalidDeclaration:
            policy_id, uses_model = "invalid-declaration", False
            policy_version = {"private": SENTINEL}
            async def decide(self, context): raise AssertionError("must not call")
        for mode in ("sink", "declaration"):
            with self.subTest(mode=mode):
                r = build(trace=SecretSink()) if mode == "sink" else build(policy=InvalidDeclaration())
                with self.assertRaises(TraceEmissionError) as caught:
                    await r.run()
                formatted = "".join(traceback.format_exception(caught.exception))
                self.assertNotIn(SENTINEL, formatted)
                self.assertIn("TraceEmissionError", formatted)

    async def test_two_sinks_have_same_minimized_provenance_and_unknown_usage(self):
        r = build(spec=task(max_steps=1))
        await r.run()
        source = next(event for event in r.trace.events if event.event == "tool")
        raw = source.model_dump(mode="json")
        raw["metadata"] = {"prompt": SENTINEL, "nested": {"cookie": SENTINEL}, "image": SENTINEL}
        raw["provenance"]["policy_id"] = "private " + SENTINEL
        raw["provenance"]["policy_version"] = {"status": "declared", "value": "private " + SENTINEL}
        raw["usage"] = Usage().model_dump(mode="json")
        event = CausalTraceEvent.model_validate(raw)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            memory = InMemoryRunTrace()
            memory.emit(event)
            JsonlRunTrace(path).emit(event)
            saved = memory.events[0].model_dump(mode="json")
            self.assertEqual(saved, json.loads(path.read_text()))
            self.assertEqual(saved["event_id"], source.event_id)
            self.assertNotIn(SENTINEL, json.dumps(saved))
            self.assertEqual(saved["usage"], {"input_tokens": None, "output_tokens": None, "cost": None})
            event.metadata.clear()
            self.assertEqual(saved, memory.events[0].model_dump(mode="json"))

    async def test_h07_versions_are_event_time_values_and_task_digest_stays_constant(self):
        r = build(policy=FakeDecisionPolicy([PolicyDecision(action="request_approval", reason="handoff")]))
        saved = await r.run()
        r.policy = RuleDecisionPolicy()
        self.assertEqual((await r.resume_synthetic(response_for(saved))).reason, "goal_verified")
        rows = r.trace.events
        root = next(row for row in rows if row.event == "lifetime_start")
        approval = next(row for row in rows if row.event == "approval")
        self.assertEqual((root.provenance.state_version, approval.provenance.state_version), (1, 2))
        self.assertEqual({row.provenance.task_digest for row in rows}, {digest(saved.task.model_dump(mode="json"))})
        later = [row for row in rows if row.lifetime_id != root.lifetime_id]
        self.assertTrue(later)
        self.assertTrue(all(row.provenance.state_version == 2 for row in later))


if __name__ == "__main__":
    unittest.main(verbosity=2)
