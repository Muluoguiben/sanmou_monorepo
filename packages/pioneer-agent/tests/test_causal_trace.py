"""H10a opt-in producer causality, declarations and fault cuts; all calls synthetic."""
import asyncio
import copy
from datetime import UTC, datetime, timedelta
import json
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from pydantic import ValidationError

from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder, ContextLimits
from pioneer_agent.agent_harness.journal import InMemoryJournalStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.agent_harness.run_store import JsonRunStore, MemoryRunStore
from pioneer_agent.agent_harness.run_trace import InMemoryRunTrace, JsonlRunTrace
from pioneer_agent.agent_harness.task_contracts import (
    CausalTraceEvent, PolicyContext, PolicyDecision, TraceDeclaration, TraceEmissionError,
    TraceEvent, TraceProvenance, Usage,
)
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy, RuleDecisionPolicy
from pioneer_agent.agent_harness.task_runner import TaskRunner
from pioneer_agent.agent_harness.task_trace import canonical_digest
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
from test_task_approval import response_for
from test_task_runner import BASE, SequenceClient, task


def runner(*, client=None, store=None, trace=None, policy=None, spec=None, context=None, budget=None, causal=True):
    client = client or SequenceClient()
    return TaskRunner(task=spec or task(), run_id="run", harness=RecommendationHarness(
        game_client=client, journal_store=InMemoryJournalStore(), tool_log=InMemoryToolLog(),
        agent_session_id="run", model_id="not-a-real-provider-label",
        clock=lambda: BASE + timedelta(seconds=client.count + 1)),
        store=store or MemoryRunStore(), trace=trace or InMemoryRunTrace(),
        policy=policy or RuleDecisionPolicy(), context_builder=context or BoundedContextBuilder(),
        budget=budget or RunBudgetLedger(BudgetLimits(max_model_attempts=0)),
        synthetic_approval=True, causal_trace=causal)


class FailingTrace(InMemoryRunTrace):
    def __init__(self, predicate):
        super().__init__()
        self.predicate, self.calls = predicate, []
        self.failure = OSError("private-sink-detail")

    def emit(self, event):
        self.calls.append(event.event)
        if self.predicate(event):
            raise self.failure
        super().emit(event)


class Fanout:
    def __init__(self, *sinks):
        self.sinks = sinks
    def emit(self, event):
        for sink in self.sinks:
            sink.emit(event)


def graph(test, events):
    seen = {}
    for event in events:
        test.assertNotIn(event.event_id, seen)
        if event.event == "lifetime_start":
            test.assertIsNone(event.parent_event_id)
            test.assertEqual(event.event_id, event.lifetime_id)
        else:
            test.assertIn(event.parent_event_id, seen)
            parent = seen[event.parent_event_id]
            test.assertEqual(parent.lifetime_id, event.lifetime_id)
            test.assertEqual(parent.run_id, event.run_id)
        if event.window_id is not None:
            test.assertTrue(event.event_id == event.window_id or event.window_id in seen)
            if event.parent_event_id != event.lifetime_id:
                test.assertEqual(seen[event.parent_event_id].window_id, event.window_id)
        seen[event.event_id] = event


class CausalWireTests(unittest.TestCase):
    def root(self):
        root = uuid4().hex
        absent = TraceDeclaration(status="absent")
        return CausalTraceEvent(run_id="run", step_id="run:1", event="lifetime_start",
            event_id=root, lifetime_id=root, emitted_at=datetime.now(UTC),
            provenance=TraceProvenance(task_digest="0" * 64, task_version=1, state_version=1,
                policy_id="rule", policy_version=TraceDeclaration(status="declared", value="1"),
                model=absent, prompt=absent, skill=absent, kb=absent))

    def test_same_event_has_identical_sink_identity_digest_and_minimization(self):
        event = self.root().model_copy(update={"metadata": {"authorization": "secret-token",
            "prompt": "private prompt", "image": "private pixels", "nested": {"cookie": "private cookie"}}})
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            memory = InMemoryRunTrace()
            memory.emit(event)
            JsonlRunTrace(path).emit(event)
            raw = path.read_text()
            self.assertEqual(json.loads(raw), memory.events[0].model_dump(mode="json"))
            self.assertEqual(memory.events[0].event_id, event.event_id)
            for secret in ("secret-token", "private prompt", "private pixels", "private cookie"):
                self.assertNotIn(secret, raw)
            event.metadata.clear()
            self.assertIn("authorization", memory.events[0].metadata)

    def test_v2_strict_versions_fields_relationships_and_frozen_identity(self):
        event = self.root()
        for update in ({"trace_version": 1}, {"trace_version": 3}, {"trace_version": 2.0},
                {"trace_version": "2"}, {"trace_version": True}, {"private_attachment": "x"},
                {"parent_event_id": event.event_id}, {"window_id": uuid4().hex},
                {"emitted_at": datetime.now()}, {"invocation_id": uuid4().hex}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                CausalTraceEvent.model_validate({**event.model_dump(), **update})
        with self.assertRaises(ValidationError):
            event.event_id = uuid4().hex
        with self.assertRaises(ValidationError):
            event.provenance.state_version = 2
        with self.assertRaises(ValidationError):
            TraceEvent.model_validate(event.model_dump())
        with self.assertRaises(ValidationError):
            TraceDeclaration(status="absent", value="fake-version")

    def test_default_v1_wire_and_memory_shape_unchanged(self):
        event = TraceEvent(run_id="run", step_id="run:1", event="tool", usage=Usage())
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "v1.jsonl"
            memory = InMemoryRunTrace()
            memory.emit(event)
            JsonlRunTrace(path).emit(event)
            self.assertEqual(memory.events[0].model_dump(), event.model_dump())
            raw = json.loads(path.read_text())
            self.assertEqual(set(raw), set(event.model_dump()) | {"trace_version", "event_id", "emitted_at", "trace_id"})
            self.assertEqual((raw["trace_version"], raw["trace_id"]), (1, "run"))
            self.assertIsNone(raw["usage"]["cost"])

    def test_canonical_outer_order_but_actual_text_not_reinterpreted(self):
        self.assertEqual(canonical_digest({"x": 1, "y": [2]}), canonical_digest({"y": [2], "x": 1}))
        self.assertNotEqual(canonical_digest({"text": '{"x":1,"y":2}'}),
                            canonical_digest({"text": '{"y":2,"x":1}'}))


class CausalRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_windows_rule_invocations_graph_and_two_sink_equality(self):
        with TemporaryDirectory() as tmp:
            memory, path = InMemoryRunTrace(), Path(tmp) / "trace.jsonl"
            r = runner(trace=Fanout(memory, JsonlRunTrace(path)))
            result = await r.run()
            self.assertEqual(result.status, "succeeded")
            events = memory.events
            graph(self, events)
            self.assertEqual([e.model_dump(mode="json") for e in events], [json.loads(line) for line in path.read_text().splitlines()])
            windows = [e for e in events if e.event == "window_start"]
            policies = [e for e in events if e.event == "policy"]
            self.assertEqual(len(windows), 3)
            self.assertEqual([e.observation_id for e in policies], ["obs-1", "obs-2", "obs-3"])
            self.assertEqual(len({e.invocation_id for e in policies}), 3)
            self.assertTrue(all(e.attempt_id is None and e.usage is None for e in policies))
            self.assertTrue(all(e.provenance.model.status == "absent" for e in policies))
            self.assertTrue(all(e.provenance.policy_version.status == "declared" for e in policies))
            self.assertEqual(r.budget.summary()["counts"], {"step": 3, "tool": 12, "model": 0})
            reservations = r.budget.snapshot()["reservations"]
            for event in events:
                if event.event == "tool":
                    self.assertEqual(reservations[event.attempt_id]["request"]["name"], event.name)
                    self.assertNotEqual(event.invocation_id, event.attempt_id)
            for outcome in (e for e in events if e.event == "outcome"):
                self.assertEqual(next(e for e in events if e.event_id == outcome.parent_event_id).event, "policy")

    async def test_default_runner_has_no_new_events_or_ids_even_terminal_noop(self):
        r = runner(causal=False)
        await r.run()
        events = r.trace.events
        self.assertTrue(all(type(e) is TraceEvent for e in events))
        self.assertEqual(len([e for e in events if e.event == "policy"]), 3)
        self.assertEqual(set(e.event for e in events), {"tool", "policy", "lifecycle"})
        await r.run()
        self.assertEqual(r.trace.events, events)

    async def test_context_snapshot_is_actual_precall_and_mutation_cannot_rewrite_it(self):
        class MutatingPolicy(RuleDecisionPolicy):
            def __init__(self): self.inputs = []
            async def decide(self, context):
                self.inputs.append(copy.deepcopy(context.model_dump(mode="json")))
                context.text = "private-mutated-after-entry"
                context.evidence_refs.append("private-forged")
                return PolicyDecision(action="continue", reason="unused private reason")
        policy = MutatingPolicy()
        r = runner(policy=policy)
        self.assertEqual((await r.run()).status, "succeeded")
        records = [e for e in r.trace.events if e.event == "policy"]
        self.assertEqual([e.provenance.context_digest for e in records], [canonical_digest(v) for v in policy.inputs])
        self.assertEqual(len({e.provenance.context_digest for e in records}), 3)
        self.assertTrue(all(e.provenance.model.status == "unknown" for e in records))
        text = json.dumps([e.model_dump(mode="json") for e in r.trace.events])
        self.assertNotIn("private-mutated-after-entry", text)
        self.assertNotIn("private-forged", text)
        self.assertNotIn("not-a-real-provider-label", text)

    async def test_task_content_changes_digest_without_changing_version(self):
        values = []
        for goal in ("first goal", "different goal"):
            spec = task(max_steps=1)
            spec.goal = goal
            r = runner(spec=spec)
            await r.run()
            values.append(r.trace.events[0].provenance.task_digest)
            self.assertEqual(r.trace.events[0].provenance.task_version, 1)
        self.assertNotEqual(*values)

    async def test_policy_display_identity_is_the_frozen_invocation_identity(self):
        class MutatingIdentity(RuleDecisionPolicy):
            policy_id = "before-policy"
            policy_version = "before-version"
            async def decide(self, context):
                self.policy_id = "after-policy"
                self.policy_version = "after-version"
                return PolicyDecision(action="stop", reason="stop")
        r = runner(policy=MutatingIdentity())
        await r.run()
        event = next(e for e in r.trace.events if e.event == "policy")
        self.assertEqual(event.provenance.policy_id, "before-policy")
        self.assertEqual(event.provenance.policy_version.value, "before-version")
        self.assertEqual(event.name, "before-policy")
        self.assertEqual(event.metadata["policy_id"], "before-policy")

    async def test_actual_policy_argument_is_detached_from_builder_and_rechecked_at_dispatch(self):
        class Builder(BoundedContextBuilder):
            def build(self, request):
                self.original = super().build(request)
                return self.original
        builder = Builder()
        class Policy(RuleDecisionPolicy):
            async def decide(self, context):
                before = context.text
                builder.original.text = "private-outside-mutation"
                self.detached = context is not builder.original and context.text == before
                return PolicyDecision(action="continue", reason="continue")
        policy = Policy()
        r = runner(policy=policy, context=builder, spec=task(max_steps=1))
        await r.run()
        self.assertTrue(policy.detached)
        store = MemoryRunStore()
        original = store._write
        def mutate(envelope):
            original(envelope)
            if envelope.state.pending_call == "policy:fake-script-v1":
                builder.original.run_id = "wrong-at-dispatch"
        store._write = mutate
        fake = FakeDecisionPolicy([PolicyDecision(action="continue", reason="must not call")])
        r = runner(store=store, context=builder, policy=fake)
        self.assertEqual((await r.run()).reason, "context_binding_mismatch")
        self.assertEqual(fake.contexts, [])
        noncall = next(e for e in r.trace.events if e.event == "policy")
        self.assertEqual(noncall.transport, "not_attempted")
        self.assertIsNone(noncall.invocation_id)
        self.assertIsNone(noncall.provenance.context_digest)

    async def test_custom_version_unknown_or_declared_is_not_source_authentication(self):
        class Custom:
            policy_id = "custom"
            uses_model = False
            async def decide(self, context): return PolicyDecision(action="continue", reason="continue")
        for version in (None, "self-reported-fake-source-version"):
            policy = Custom()
            if version is not None: policy.policy_version = version
            r = runner(policy=policy, spec=task(max_steps=1))
            await r.run()
            event = next(e for e in r.trace.events if e.event == "policy")
            self.assertEqual(event.provenance.policy_version.status, "unknown" if version is None else "declared")
            self.assertEqual(event.provenance.policy_version.value, version)
            self.assertTrue(all(getattr(event.provenance, key).status == "unknown" for key in ("model", "prompt", "skill", "kb")))

    async def test_bad_version_declaration_and_bad_context_binding_never_invoke_policy(self):
        class BadVersion(RuleDecisionPolicy): policy_version = {"fake": "version"}
        r = runner(policy=BadVersion())
        with self.assertRaises(TraceEmissionError): await r.run()
        self.assertEqual(r._client.calls, [])
        class BadContext(BoundedContextBuilder):
            def build(self, request):
                result = super().build(request)
                result.run_id = "other-run"
                return result
        r = runner(context=BadContext())
        self.assertEqual((await r.run()).reason, "context_binding_mismatch")
        self.assertFalse(any(e.event == "policy" for e in r.trace.events))
        self.assertTrue(all(e.provenance.context_digest is None for e in r.trace.events))

    async def test_reentry_new_lifetimes_and_same_step_retry_are_distinct(self):
        class OnceFail(SequenceClient):
            async def call_tool(self, name, arguments):
                return await super().call_tool(name, arguments)
        trace = FailingTrace(lambda event: event.event == "tool")
        r = runner(client=OnceFail(), trace=trace)
        with self.assertRaises(TraceEmissionError): await r.run()
        old_lifetime = r._causal.lifetime
        trace.predicate = lambda event: False
        self.assertEqual((await r.run()).status, "succeeded")
        self.assertNotEqual(r._causal.lifetime, old_lifetime)
        starts = [e for e in trace.events if e.event == "window_start"]
        self.assertEqual(starts[0].step_id, starts[1].step_id)
        self.assertNotEqual(starts[0].window_id, starts[1].window_id)
        self.assertIsNone(r._causal.failure)
        graph(self, trace.events)

    async def test_fresh_checkpoint_runner_uses_new_root_and_new_observation(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            trace = InMemoryRunTrace()
            first = runner(store=JsonRunStore(path), trace=trace, policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="pause")]))
            await first.run()
            second = runner(store=JsonRunStore(path), trace=trace, client=SequenceClient(count=1))
            self.assertEqual((await second.run(resume=True)).status, "succeeded")
            roots = [e for e in trace.events if e.event == "lifetime_start"]
            self.assertEqual(len({e.lifetime_id for e in roots}), 2)
            self.assertTrue(all(e.parent_event_id is None for e in roots))
            self.assertEqual([e.observation_id for e in trace.events if e.event == "policy"], ["obs-1", "obs-2", "obs-3"])
            graph(self, trace.events)

    async def test_h07_state_version_transition_is_sampled_per_event(self):
        r = runner(policy=FakeDecisionPolicy([PolicyDecision(action="request_approval", reason="handoff")]))
        saved = await r.run()
        events = r.trace.events
        self.assertEqual(events[0].provenance.state_version, 1)
        approval = next(e for e in events if e.event == "approval")
        self.assertEqual(approval.provenance.state_version, 2)
        self.assertTrue(all(e.provenance.task_version == 1 for e in events))
        r.policy = RuleDecisionPolicy()
        self.assertEqual((await r.resume_synthetic(response_for(saved))).status, "succeeded")
        self.assertEqual(len({e.lifetime_id for e in r.trace.events}), 2)
        graph(self, r.trace.events)

    async def test_no_policy_paths_have_honest_outcomes(self):
        cases = ((BudgetLimits(max_steps=0, max_model_attempts=0), None, "budget_exhausted"),
                 (BudgetLimits(max_tool_calls=0, max_model_attempts=0), None, "budget_exhausted"),
                 (BudgetLimits(max_model_attempts=0), BoundedContextBuilder(ContextLimits(max_tokens=100)), "context_overflow"))
        for limits, context, reason in cases:
            with self.subTest(reason=reason, limits=limits):
                r = runner(budget=RunBudgetLedger(limits), context=context)
                self.assertEqual((await r.run()).reason, reason)
                self.assertFalse(any(e.event == "policy" for e in r.trace.events))
                self.assertTrue(all(e.invocation_id is None for e in r.trace.events if e.event == "outcome"))
                graph(self, r.trace.events)

    async def test_observation_event_does_not_claim_goal_verified(self):
        r = runner(spec=task(max_steps=1))
        self.assertEqual((await r.run()).reason, "step_limit")
        observations = [e for e in r.trace.events if e.event == "observation"]
        self.assertEqual([e.business for e in observations], ["observation_guarded"])

    async def test_active_and_idle_control_roots_do_not_invent_calls(self):
        for control in ("cancel", "pause"):
            r = runner()
            getattr(r, control)()
            self.assertEqual(r._client.calls, [])
            self.assertEqual(len({e.lifetime_id for e in r.trace.events}), 1)
            graph(self, r.trace.events)
            if control == "pause":
                await r.run(resume=True)
                self.assertEqual(len({e.lifetime_id for e in r.trace.events}), 2)
            active = runner()
            active._client.after_call = lambda _: getattr(active, control)()
            result = await active.run()
            self.assertEqual(result.status, "cancelled" if control == "cancel" else "paused")
            self.assertEqual(len({e.lifetime_id for e in active.trace.events}), 1)
            self.assertEqual(active._client.calls, ["session_status"])
            graph(self, active.trace.events)


class CausalFaultTests(unittest.IsolatedAsyncioTestCase):
    async def test_trace_wrapper_has_no_private_explicit_or_inherited_context(self):
        sentinel = "H10A_AUTHOR_PRIVATE_SECONDARY"
        for mode in ("sink", "declaration", "late-declaration", "caller-context"):
            with self.subTest(mode=mode):
                trace = FailingTrace(lambda e: e.event == ("tool" if mode == "caller-context" else "lifetime_start"))
                trace.failure = OSError(sentinel)
                policy = RuleDecisionPolicy()
                if mode == "declaration": policy.policy_version = {"private": sentinel}
                class Builder(BoundedContextBuilder):
                    def build(self, request):
                        result = super().build(request)
                        policy.policy_version = {"private": sentinel}
                        return result
                r = runner(policy=policy, trace=trace if mode in {"sink", "caller-context"} else InMemoryRunTrace(),
                           context=Builder() if mode == "late-declaration" else None)
                if mode == "caller-context":
                    try:
                        raise ValueError(sentinel)
                    except ValueError:
                        with self.assertRaises(TraceEmissionError) as caught:
                            await r.run()
                else:
                    with self.assertRaises(TraceEmissionError) as caught:
                        await r.run()
                self.assertNotIn(sentinel, "".join(traceback.format_exception(caught.exception)))
                self.assertIsNone(caught.exception.__cause__)

    async def test_sink_failure_at_every_boundary_latches_without_retry_or_derived_success(self):
        for event_name in ("lifetime_start", "window_start", "tool", "observation", "policy", "outcome", "lifetime_end"):
            with self.subTest(event=event_name):
                trace = FailingTrace(lambda e: e.event == event_name)
                r = runner(trace=trace)
                with self.assertRaises(TraceEmissionError) as caught: await r.run()
                self.assertIs(caught.exception, r._causal.failure)
                self.assertEqual(trace.calls.count(event_name), 1)
                self.assertEqual(trace.calls[-1], event_name)
                if event_name in {"lifetime_start", "window_start"}: self.assertEqual(r._client.calls, [])
                if event_name == "tool": self.assertEqual(r._client.calls, ["session_status"])
                if event_name == "lifetime_end": self.assertEqual(r.store.load().status, "succeeded")

    async def test_genuine_tool_failure_retains_classification_and_primary_note(self):
        failure = ConnectionError("private-transport-detail")
        class Client(SequenceClient):
            async def call_tool(self, name, arguments):
                self.calls.append(name)
                raise failure
        trace = FailingTrace(lambda e: e.event == "tool")
        r = runner(client=Client(), trace=trace)
        result = await r.run()
        self.assertEqual(result.reason, "tool_failure")
        self.assertEqual(r._client.calls, ["session_status"])
        self.assertIs(r._causal.primary, failure)
        self.assertIn("trace_emission_error:OSError", failure.__notes__)

    async def test_policy_and_schema_failures_preserve_original_classification(self):
        for schema in (False, True):
            failure = ValueError("private-policy-detail")
            class Policy(RuleDecisionPolicy):
                async def decide(self, context):
                    if schema: return {"action": "impossible", "reason": "private-schema"}
                    raise failure
            r = runner(policy=Policy(), trace=FailingTrace(lambda e: e.event == "policy"))
            result = await r.run()
            self.assertEqual(result.reason, "runtime_error:ValidationError" if schema else "runtime_error:ValueError")
            if not schema:
                self.assertIs(r._causal.primary, failure)
                self.assertIn("trace_emission_error:OSError", failure.__notes__)

    async def test_cancel_and_checkpoint_primary_objects_survive_sink_failure(self):
        failure = asyncio.CancelledError()
        class Policy(RuleDecisionPolicy):
            async def decide(self, context): raise failure
        r = runner(policy=Policy(), trace=FailingTrace(lambda e: e.event == "policy"))
        with self.assertRaises(asyncio.CancelledError) as caught: await r.run()
        self.assertIs(caught.exception, failure)
        self.assertEqual(r.store.load().status, "cancelled")
        self.assertIn("trace_emission_error:OSError", failure.__notes__)
        store = MemoryRunStore()
        persist = OSError("private-checkpoint-detail")
        original = store._write
        def fail(envelope):
            if envelope.state.pending_call == "session_status": raise persist
            original(envelope)
        store._write = fail
        r = runner(store=store, trace=FailingTrace(lambda e: e.event == "outcome"))
        with self.assertRaises(OSError) as caught: await r.run()
        self.assertIs(caught.exception, persist)
        self.assertEqual(r._client.calls, [])
        self.assertIn("trace_emission_error:OSError", persist.__notes__)

    async def test_budget_primary_is_not_replaced_by_outcome_sink_failure(self):
        r = runner(budget=RunBudgetLedger(BudgetLimits(max_steps=0, max_model_attempts=0)),
                   trace=FailingTrace(lambda e: e.event == "outcome"))
        result = await r.run()
        self.assertEqual(result.reason, "budget_exhausted")
        self.assertEqual(r._client.calls, [])

    async def test_genuine_business_result_is_not_mistaken_for_wrapped_trace_failure(self):
        r = runner(spec=task(max_steps=1), trace=FailingTrace(lambda e: e.event == "lifecycle"))
        self.assertEqual((await r.run()).reason, "step_limit")
        self.assertEqual(r._causal.business_failure, "step_limit")
        self.assertIsNotNone(r._causal.failure)

    async def test_fake_model_unknown_usage_not_fabricated_from_log_label(self):
        class FakeModel(RuleDecisionPolicy): uses_model = True
        r = runner(policy=FakeModel(), spec=task(max_steps=1), budget=RunBudgetLedger())
        await r.run()
        policy = next(e for e in r.trace.events if e.event == "policy")
        self.assertIsNotNone(policy.attempt_id)
        self.assertIsNotNone(policy.invocation_id)
        self.assertIsNone(policy.usage.input_tokens)
        self.assertIsNone(policy.usage.cost)
        self.assertEqual(policy.provenance.model.status, "unknown")
        self.assertEqual(r.budget.summary()["counts"]["model"], 1)


class CausalDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_budget_sampling_cannot_replace_the_bound_policy_or_callable(self):
        for target in ("runner", "callable"):
            with self.subTest(target=target):
                state, calls = {"prepared": False, "swapped": False}, []
                class Original:
                    policy_id, uses_model = "policy-P", False
                    @property
                    def policy_version(self):
                        if state["runner"].state.pending_call == "policy:policy-P":
                            state["prepared"] = True
                        return "P-1"
                    async def decide(self, context):
                        calls.append("policy-P")
                        return PolicyDecision(action="stop", reason="stop")
                class Replacement:
                    policy_id, policy_version, uses_model = "policy-Q", "Q-1", True
                    async def decide(self, context):
                        calls.append("policy-Q")
                        return PolicyDecision(action="stop", reason="stop")
                original, replacement = Original(), Replacement()
                class Budget(RunBudgetLedger):
                    def remaining_seconds(self):
                        remaining = super().remaining_seconds()
                        if state["prepared"] and not state["swapped"]:
                            state["swapped"] = True
                            if target == "runner":
                                state["runner"].policy = replacement
                            else:
                                original.decide = replacement.decide
                        return remaining
                budget = Budget(BudgetLimits(max_model_attempts=0))
                r = runner(policy=original, budget=budget)
                state["runner"] = r
                await r.run()
                self.assertTrue(state["swapped"])
                self.assertEqual(calls, ["policy-P"])
                event = next(e for e in r.trace.events if e.event == "policy")
                self.assertEqual((event.name, event.provenance.policy_id, event.provenance.policy_version.value),
                                 ("policy-P", "policy-P", "P-1"))
                self.assertIsNone(event.attempt_id)
                self.assertEqual(budget.summary()["counts"]["model"], 0)

    async def test_reservation_and_provenance_share_the_same_captured_policy(self):
        state, calls = {"swapped": False}, []
        class Original:
            policy_id, policy_version, uses_model = "policy-P", "P-1", True
            async def decide(self, context):
                calls.append("policy-P")
                return PolicyDecision(action="stop", reason="stop")
        class Replacement:
            policy_id, policy_version, uses_model = "policy-Q", "Q-1", False
            async def decide(self, context):
                calls.append("policy-Q")
                return PolicyDecision(action="stop", reason="stop")
        class Budget(RunBudgetLedger):
            def reserve(self, request):
                reservation = super().reserve(request)
                if request.kind == "model":
                    state["swapped"] = True
                    state["runner"].policy = Replacement()
                return reservation
        budget = Budget(BudgetLimits(max_model_attempts=1))
        r = runner(policy=Original(), budget=budget)
        state["runner"] = r
        await r.run()
        self.assertTrue(state["swapped"])
        self.assertEqual(calls, ["policy-P"])
        event = next(e for e in r.trace.events if e.event == "policy")
        self.assertEqual((event.name, event.provenance.policy_id, event.provenance.policy_version.value),
                         ("policy-P", "policy-P", "P-1"))
        self.assertEqual(budget.snapshot()["reservations"][event.attempt_id]["request"]["name"], "policy-P")
        self.assertEqual(budget.summary()["counts"]["model"], 1)

    async def test_provenance_deadline_keeps_reservations_without_invocations(self):
        for boundary in ("tool", "policy", "model-policy"):
            with self.subTest(boundary=boundary):
                clock = [1000.]
                budget = RunBudgetLedger(BudgetLimits(max_model_attempts=1, max_seconds=1.),
                    clock=lambda: clock[0], monotonic=lambda: clock[0])
                class Policy:
                    policy_id, uses_model = "deadline-policy", boundary == "model-policy"
                    calls, advanced = 0, False
                    @property
                    def policy_version(self):
                        target = "session_status" if boundary == "tool" else "policy:deadline-policy"
                        if self.runner.state.pending_call == target and not self.advanced:
                            self.advanced = True
                            clock[0] += 2
                        return "1"
                    async def decide(self, context):
                        self.calls += 1
                        return PolicyDecision(action="continue", reason="continue")
                policy = Policy()
                r = runner(policy=policy, budget=budget)
                policy.runner = r
                result = await r.run()
                self.assertEqual((result.status, result.reason), ("failed", "run_deadline"))
                self.assertTrue(policy.advanced)
                self.assertEqual((len(r._client.calls), policy.calls), (0 if boundary == "tool" else 4, 0))
                records = [e for e in r.trace.events if e.event == ("tool" if boundary == "tool" else "policy")]
                self.assertTrue(records)
                for event in records:
                    self.assertEqual(event.transport, "not_attempted")
                    self.assertIsNone(event.invocation_id)
                    self.assertIsNone(event.provenance.context_digest)
                self.assertEqual(budget.summary()["counts"], {
                    "step": 1, "tool": 1 if boundary == "tool" else 4,
                    "model": 1 if boundary == "model-policy" else 0})

    async def test_provenance_pause_cancel_prevent_lazy_tool_and_policy_entry(self):
        for boundary in ("tool", "policy"):
            for operation in ("pause", "cancel"):
                with self.subTest(boundary=boundary, operation=operation):
                    class Policy:
                        policy_id, uses_model = "control-policy", False
                        calls, requested = 0, False
                        @property
                        def policy_version(self):
                            target = "session_status" if boundary == "tool" else "policy:control-policy"
                            if self.runner.state.pending_call == target and not self.requested:
                                self.requested = True
                                getattr(self.runner, operation)()
                            return "1"
                        async def decide(self, context):
                            self.calls += 1
                            return PolicyDecision(action="continue", reason="continue")
                    policy = Policy()
                    r = runner(policy=policy)
                    policy.runner = r
                    result = await r.run()
                    self.assertEqual(result.status, "paused" if operation == "pause" else "cancelled")
                    self.assertTrue(policy.requested)
                    self.assertEqual((len(r._client.calls), policy.calls), (0 if boundary == "tool" else 4, 0))
                    records = [e for e in r.trace.events if e.event == boundary]
                    self.assertTrue(records)
                    self.assertTrue(all(e.transport == "not_attempted" and e.invocation_id is None
                        and e.provenance.context_digest is None for e in records))

    async def test_h07_freshness_is_rechecked_after_provenance_before_policy(self):
        r = runner(policy=FakeDecisionPolicy([PolicyDecision(action="request_approval", reason="handoff")]))
        saved = await r.run()
        class Policy:
            policy_id, uses_model = "stale-policy", False
            calls, advanced = 0, False
            @property
            def policy_version(self):
                if r.state.pending_call == "policy:stale-policy" and not self.advanced:
                    self.advanced = True
                    r._client.count += 120
                return "1"
            async def decide(self, context):
                self.calls += 1
                return PolicyDecision(action="continue", reason="continue")
        policy = r.policy = Policy()
        result = await r.resume_synthetic(response_for(saved))
        self.assertTrue(policy.advanced)
        self.assertEqual((result.status, result.reason), ("failed", "observation_stale"))
        self.assertEqual(policy.calls, 0)
        event = [e for e in r.trace.events if e.event == "policy"][-1]
        self.assertEqual(event.transport, "not_attempted")
        self.assertIsNone(event.invocation_id)
        self.assertIsNone(event.provenance.context_digest)

    async def test_expired_wrapper_does_not_create_inner_awaitables(self):
        for boundary in ("tool", "policy"):
            with self.subTest(boundary=boundary):
                clock = [1000.]
                budget = RunBudgetLedger(BudgetLimits(max_model_attempts=0, max_seconds=1.),
                    clock=lambda: clock[0], monotonic=lambda: clock[0])
                class Client(SequenceClient):
                    created = 0
                    def call_tool(self, name, arguments):
                        self.created += 1
                        return super().call_tool(name, arguments)
                class Policy:
                    policy_id, uses_model = "lazy-policy", False
                    created, entered, advanced = 0, 0, False
                    @property
                    def policy_version(self):
                        target = "session_status" if boundary == "tool" else "policy:lazy-policy"
                        if self.runner.state.pending_call == target and not self.advanced:
                            self.advanced = True
                            clock[0] += 2
                        return "1"
                    def decide(self, context):
                        self.created += 1
                        async def inner():
                            self.entered += 1
                            return PolicyDecision(action="continue", reason="continue")
                        return inner()
                client, policy = Client(), Policy()
                r = runner(client=client, policy=policy, budget=budget)
                policy.runner = r
                self.assertEqual((await r.run()).reason, "run_deadline")
                self.assertEqual(client.created, 0 if boundary == "tool" else 4)
                self.assertEqual((policy.created, policy.entered), (0, 0))
