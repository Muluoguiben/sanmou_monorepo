"""H08b content binding, lifecycle and privacy cuts; all ports are offline."""
import asyncio
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from enum import IntEnum
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import traceback
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from pioneer_agent.agent_harness import skill_registry as registry
from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder
from pioneer_agent.agent_harness.journal import InMemoryJournalStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.agent_harness.run_store import CheckpointConflict, JsonRunStore, MemoryRunStore
from pioneer_agent.agent_harness.run_trace import InMemoryRunTrace, JsonlRunTrace
from pioneer_agent.agent_harness.task_contracts import (
    CausalTraceEvent, PolicyDecision, RunState, TaskSpec, TraceDeclaration,
    TraceEmissionError, TraceEvent, TraceProvenance,
)
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy, RuleDecisionPolicy
from pioneer_agent.agent_harness.task_runner import TaskRunner
from pioneer_agent.agent_harness.task_trace import CausalTraceProducer, canonical_digest
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
from pioneer_agent.runbook.models import Condition, ConditionStatus
from test_causal_trace import Fanout, graph
from test_task_runner import BASE, SequenceClient


KEY = ("chapter-observer", "1.0.0")
UNBOUND = object()


def compiled(target=3):
    return registry.compile_skill(*KEY, {"target_chapter": target},
        metrics={"progress.current_chapter_id": 1})


def declaration(compilation):
    return "recipe:chapter-observer@1.0.0#sha256=" + compilation.template_digest


def harness_for(client):
    return RecommendationHarness(game_client=client, journal_store=InMemoryJournalStore(),
        tool_log=InMemoryToolLog(), agent_session_id="run", model_id="offline-only",
        clock=lambda: BASE + timedelta(seconds=client.count + 1))


def runner(*, compilation=UNBOUND, spec=None, client=None, harness=None, store=None,
           policy=None, trace=None, budget=None, ownership=None, causal=True):
    if compilation is UNBOUND:
        compilation = compiled()
    if spec is None:
        spec = compilation.task if compilation is not None else compiled().task
    client = client or SequenceClient()
    return TaskRunner(task=spec, run_id="run", harness=harness or harness_for(client),
        store=store or MemoryRunStore(), policy=policy or RuleDecisionPolicy(),
        context_builder=BoundedContextBuilder(), budget=budget or RunBudgetLedger(),
        trace=trace or InMemoryRunTrace(), ownership=ownership, causal_trace=causal,
        skill_compilation=compilation)


def wire_event(value, slot="skill"):
    absent = TraceDeclaration(status="absent")
    fields = {key: absent for key in ("policy_version", "model", "prompt", "skill", "kb")}
    fields[slot] = TraceDeclaration(status="declared", value=value)
    return CausalTraceEvent(run_id="run", step_id="run:1", event="lifetime_start",
        event_id="a" * 32, lifetime_id="a" * 32, emitted_at=datetime.now(UTC),
        provenance=TraceProvenance(task_digest="b" * 64, task_version=1,
            state_version=1, policy_id="rule", **fields))


class BindingValidationTests(unittest.TestCase):
    def reject(self, value, task=None):
        with self.assertRaisesRegex(registry.SkillBindingError, "^invalid_skill_binding$"):
            registry.validate_skill_binding(value, task if task is not None else compiled().task)

    def test_exact_binding_has_only_two_frozen_scalar_fields(self):
        item = compiled()
        binding = registry.validate_skill_binding(item, item.task)
        self.assertEqual(binding.model_dump(), {
            "declaration_value": declaration(item), "task_digest": item.task_digest})
        self.assertEqual(len(binding.declaration_value), 101)
        with self.assertRaises(ValidationError):
            binding.declaration_value = "changed"
        copy = binding.model_copy(update={"task_digest": "0" * 64})
        self.assertNotEqual(copy, binding)
        self.assertEqual(registry.validate_skill_binding(item, item.task), binding)

    def test_valid_manually_reconstructed_content_does_not_require_compile_call(self):
        item = compiled()
        manual = registry.SkillCompilation.model_validate_json(item.model_dump_json())
        with patch.object(registry, "compile_skill", side_effect=AssertionError("no replay")), \
             patch.object(registry, "evaluate_all", side_effect=AssertionError("no fake metrics")):
            binding = registry.validate_skill_binding(manual, manual.task)
        self.assertEqual(binding.task_digest, item.task_digest)
        self.assertEqual(manual.preflight.evaluations[0].value, 1)

    def test_only_exact_existing_compilation_and_task_types_are_supported(self):
        class ExtendedCompilation(registry.SkillCompilation):
            pass
        class ExtendedTask(TaskSpec):
            pass
        item = compiled()
        for value in (item.model_dump(), None, [], object(),
                      ExtendedCompilation.model_validate(item.model_dump())):
            with self.subTest(kind=type(value).__name__):
                self.reject(value)
        for task in (item.task.model_dump(), ExtendedTask.model_validate(item.task.model_dump())):
            self.reject(item, task)

    def test_causal_flag_requires_identity_true_before_harness_access(self):
        class Untouchable:
            def __getattribute__(self, name):
                raise AssertionError("harness accessed before binding validation")
        for flag in (False, None, 0, 1, "true", [], {}):
            with self.subTest(flag=flag), self.assertRaisesRegex(
                    registry.SkillBindingError, "^skill_binding_requires_causal_trace$"):
                runner(compilation=compiled(), harness=Untouchable(), causal=flag)
        with self.assertRaisesRegex(registry.SkillBindingError, "^invalid_skill_binding$"):
            runner(compilation={}, spec=compiled().task, harness=Untouchable())

    def test_identity_admission_template_and_top_level_authority_are_exact(self):
        for key, value in (("skill_id", "other"), ("version", "1.0.1"),
                ("admission", "self-reviewed"), ("template_digest", "0" * 64),
                ("execution_authority", "control"), ("executable", True),
                ("executable", 0), ("template_digest", "A" * 64)):
            with self.subTest(key=key, value=value):
                self.reject(compiled().model_copy(update={key: value}))

    def test_parameter_bounds_types_and_extra_keys_are_not_coerced(self):
        class Number(IntEnum):
            THREE = 3
        for value in (0, 1001, True, False, 3.0, "3", None, Number.THREE):
            item = compiled()
            item.parameters.__dict__["target_chapter"] = value
            with self.subTest(kind=type(value).__name__, value=value):
                self.reject(item)
        item = compiled()
        item.parameters.__dict__["reviewed"] = True
        self.reject(item)
        for target in (1, 1000):
            item = compiled(target)
            self.assertEqual(registry.validate_skill_binding(item, item.task).task_digest, item.task_digest)

    def test_ready_reason_missing_metrics_and_preflight_status_must_agree(self):
        blocked = registry.compile_skill(*KEY, {"target_chapter": 3}, metrics={})
        self.reject(blocked)
        for key, value in (("status", "blocked"), ("reason", "precondition_unknown"),
                           ("missing_metrics", ["progress.current_chapter_id"]),
                           ("task", None), ("task_digest", None)):
            self.reject(compiled().model_copy(update={key: value}))
        for status in (ConditionStatus.UNKNOWN, ConditionStatus.NOT_SATISFIED):
            item = compiled()
            item.preflight.status = status
            self.reject(item)

    def test_preflight_is_exact_one_condition_and_integer_threshold_not_observation(self):
        class Number(IntEnum):
            ONE = 1
        for evaluations in ([], [compiled().preflight.evaluations[0]] * 2):
            item = compiled()
            item.preflight.evaluations = evaluations
            self.reject(item)
        for key, value in (("metric", "resources.wood"), ("op", "=="),
                ("status", ConditionStatus.UNKNOWN), ("value", 999), ("value", True),
                ("value", 1.0), ("value", "1"), ("value", Number.ONE)):
            item = compiled()
            setattr(item.preflight.evaluations[0], key, value)
            with self.subTest(key=key, kind=type(value).__name__):
                self.reject(item)

    def test_full_task_and_reported_digest_both_are_recomputed(self):
        for field, value in (("goal", "different"), ("task_id", "different"),
                ("required_domains", []), ("allowed_tools", []), ("max_steps", 2),
                ("wait_seconds", 1.0), ("stop_when", [Condition(metric="x", value=1)])):
            item = compiled()
            setattr(item.task, field, value)
            item.task_digest = canonical_digest(item.task.model_dump(mode="json"))
            with self.subTest(field=field):
                self.reject(item, item.task)
        item = compiled().model_copy(update={"task_digest": "0" * 64})
        self.reject(item)
        self.reject(compiled(), compiled(4).task)
        item = compiled()
        item.parameters.target_chapter = 4
        self.reject(item)

    def test_actual_task_strict_revalidation_rejects_construct_copy_and_extra_bypasses(self):
        for field, value in (("max_steps", "3"), ("max_steps", 3.0), ("version", True),
                ("version", 1.0), ("executable", 0), ("execution_authority", "execute"),
                ("wait_seconds", 0), ("allowed_tools", tuple(compiled().task.allowed_tools))):
            actual = compiled().task.model_copy(update={field: value})
            with self.subTest(field=field, kind=type(value).__name__):
                self.reject(compiled(), actual)
        actual = TaskSpec.model_construct(**compiled().task.model_dump())
        actual.__dict__["extra"] = "unreviewed"
        self.reject(compiled(), actual)
        actual = compiled().task
        actual.success_when[0].__dict__["extra"] = "unreviewed"
        self.reject(compiled(), actual)

    def test_nested_extra_data_is_never_silently_dropped(self):
        for path in ((), ("parameters",), ("preflight",), ("task",)):
            item = compiled()
            target = item
            for name in path:
                target = getattr(target, name)
            target.__dict__["private_extra"] = "secret"
            self.reject(item)
        item = compiled()
        item.preflight.evaluations[0].__pydantic_extra__ = {"private_extra": "secret"}
        self.reject(item)
        item = compiled()
        item.preflight = {**item.preflight.model_dump(mode="json"), "private_extra": "secret"}
        self.reject(item)
        class ExtendedCondition(Condition):
            pass
        item = compiled()
        item.task.success_when[0] = ExtendedCondition.model_validate(item.task.success_when[0].model_dump())
        self.reject(item)

    def test_mutated_nested_dicts_and_string_status_are_not_rematerialized(self):
        for field in ("parameters", "preflight", "task"):
            item = compiled()
            setattr(item, field, getattr(item, field).model_dump(mode="json"))
            with self.subTest(field=field):
                self.reject(item)
        item = compiled()
        item.preflight.evaluations[0] = item.preflight.evaluations[0].model_dump(mode="json")
        self.reject(item)
        item = compiled()
        item.task.success_when[0] = item.task.success_when[0].model_dump(mode="json")
        self.reject(item)
        for field in ("set", "evaluation"):
            item = compiled()
            target = item.preflight if field == "set" else item.preflight.evaluations[0]
            target.status = "satisfied"
            self.reject(item)

    def test_rejection_precedes_external_owner_load_bind_close_and_all_ports(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            store, item = JsonRunStore(path), compiled()
            with store.acquire() as initial:
                initial.load()
                initial.save(RunState(run_id="run", task=item.task))
            before = path.read_bytes()
            owner = store.acquire()
            client, trace, budget = SequenceClient(), InMemoryRunTrace(), RunBudgetLedger()
            harness = harness_for(client)
            try:
                with ExitStack() as stack:
                    spies = [stack.enter_context(patch.object(obj, name,
                        side_effect=AssertionError("invalid binding reached side effect")))
                        for obj, name in ((store, "acquire"), (owner, "bind_runner"),
                            (owner, "load"), (owner, "save"), (owner, "check"),
                            (owner, "close"), (budget, "restore"), (budget, "reserve"),
                            (trace, "emit"), (client, "call_tool"))]
                    bad = item.model_copy(update={"template_digest": "0" * 64})
                    with self.assertRaises(registry.SkillBindingError):
                        runner(compilation=bad, store=store, ownership=owner,
                               harness=harness, budget=budget, trace=trace)
                    self.assertTrue(all(spy.call_count == 0 for spy in spies))
                self.assertTrue(owner.active)
                self.assertIsNone(owner._runner)
                self.assertIs(harness.game_client, client)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(trace.events, [])
                valid = runner(compilation=item, store=store, ownership=owner, harness=harness)
                valid.close()
                self.assertTrue(owner.active)
                self.assertIs(owner._runner, valid)
            finally:
                owner.close()

    def test_rejection_without_owner_creates_no_checkpoint_or_client_installation(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "new" / "checkpoint.json"
            store, client = JsonRunStore(path), SequenceClient()
            harness = harness_for(client)
            with patch.object(store, "acquire", side_effect=AssertionError("must not acquire")) as acquire:
                with self.assertRaises(registry.SkillBindingError):
                    runner(compilation={}, spec=compiled().task, store=store, harness=harness)
                acquire.assert_not_called()
            self.assertFalse(path.parent.exists())
            self.assertIs(harness.game_client, client)

    def test_validation_errors_have_no_payload_cause_context_even_in_ambient_handler(self):
        for secret in ("binding-canary-9", "binding-canary-long-" * 40):
            for placement in ("skill_id", "parameter", "task", "preflight", "causal"):
                item = compiled()
                if placement == "parameter":
                    item.parameters.__dict__["target_chapter"] = secret
                elif placement == "task":
                    item.task.__dict__["max_steps"] = secret
                elif placement == "preflight":
                    item.preflight.evaluations[0].value = secret
                elif placement == "skill_id":
                    item.skill_id = secret
                try:
                    raise RuntimeError(secret)
                except RuntimeError:
                    try:
                        if placement == "causal":
                            runner(compilation=item, causal=1)
                        else:
                            registry.validate_skill_binding(item, compiled().task)
                    except registry.SkillBindingError as error:
                        self.assertIsNone(error.__cause__)
                        self.assertIsNone(error.__context__)
                        rendered = str(error) + repr(error) + "".join(traceback.format_exception(error))
                        self.assertNotIn(secret, rendered)
                    else:
                        self.fail("invalid binding accepted")


class BindingSinkTests(unittest.TestCase):
    def project(self, event):
        with TemporaryDirectory() as directory:
            path, memory = Path(directory) / "trace.jsonl", InMemoryRunTrace()
            Fanout(memory, JsonlRunTrace(path)).emit(event)
            self.assertEqual(memory.events[0].model_dump(mode="json"),
                             json.loads(path.read_text(encoding="utf-8")))
            return memory.events[0]

    def test_only_exact_declared_skill_format_survives_both_sinks(self):
        for digest in ("0" * 64, "abcdef0123456789" * 4):
            value = "recipe:chapter-observer@1.0.0#sha256=" + digest
            self.assertEqual(self.project(wire_event(value)).provenance.skill.value, value)

    def test_near_formats_prefix_suffix_newline_unicode_and_hex_length_hash(self):
        value = declaration(compiled())
        wrong = ["x" + value, value + "x", value + "\n", value + "\r\n",
            value.replace("1.0.0", "1.0.1"), value.replace("recipe:", "Recipe:"),
            value.replace("chapter", "chаpter"), value.replace("=", "＝"),
            value[:-1], value + "0", value[:-64] + "A" * 64,
            value[:-64] + "g" * 64, value[:-64] + "０" * 64]
        for candidate in wrong:
            with self.subTest(candidate=candidate):
                expected = "sha256:" + hashlib.sha256(candidate.encode("utf-8")).hexdigest()
                self.assertEqual(self.project(wire_event(candidate)).provenance.skill.value, expected)

    def test_other_provenance_slots_and_v1_fields_keep_original_identifier_rules(self):
        value = declaration(compiled())
        expected = "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
        for slot in ("policy_version", "model", "prompt", "kb"):
            self.assertEqual(getattr(self.project(wire_event(value, slot)).provenance, slot).value, expected)
        memory = InMemoryRunTrace()
        memory.emit(TraceEvent(run_id="run", step_id="run:1", event="tool", name=value,
                               metadata={"skill_version": value}))
        self.assertEqual(memory.events[0].name, expected)
        self.assertEqual(memory.events[0].metadata["skill_version"], expected)

    def test_unknown_absent_declarations_remain_unchanged_and_nonnull_is_invalid(self):
        for status in ("unknown", "absent"):
            event = wire_event(declaration(compiled()))
            event = event.model_copy(update={"provenance": event.provenance.model_copy(
                update={"skill": TraceDeclaration(status=status)})})
            self.assertEqual(self.project(event).provenance.skill, TraceDeclaration(status=status))
            forged = event.provenance.skill.model_copy(update={"value": declaration(compiled())})
            bad = event.model_copy(update={"provenance": event.provenance.model_copy(update={"skill": forged})})
            with self.assertRaises(ValidationError):
                self.project(bad)


class BindingRunnerTests(unittest.IsolatedAsyncioTestCase):
    def assert_bound(self, events, item):
        self.assertTrue(events)
        self.assertTrue(all(event.provenance.skill == TraceDeclaration(
            status="declared", value=declaration(item)) for event in events))
        self.assertTrue(all(event.provenance.task_digest == item.task_digest for event in events))

    async def test_three_fresh_observations_two_sinks_and_terminal_noop_lifetime(self):
        with TemporaryDirectory() as directory:
            item, client, memory = compiled(), SequenceClient(), InMemoryRunTrace()
            path = Path(directory) / "trace.jsonl"
            run = runner(compilation=item, client=client, trace=Fanout(memory, JsonlRunTrace(path)))
            result = await run.run()
            self.assertEqual((result.status, result.reason, result.completed_steps), ("succeeded", "goal_verified", 3))
            self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])
            self.assertIn("observation:obs-3", result.evidence_refs)
            self.assertEqual(run.budget.summary()["counts"], {"step": 3, "tool": 12, "model": 0})
            self.assertEqual(result.execution_authority, "none")
            self.assertFalse(result.executable)
            calls, prior = list(client.calls), list(memory.events)
            self.assertEqual((await run.run()).status, "succeeded")
            self.assertEqual(client.calls, calls)
            self.assertEqual([event.event for event in memory.events[len(prior):]], ["lifetime_start", "lifetime_end"])
            self.assertEqual(len({event.lifetime_id for event in memory.events}), 2)
            graph(self, memory.events)
            self.assert_bound(memory.events, item)
            self.assertEqual([event.model_dump(mode="json") for event in memory.events],
                [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()])

    async def test_pause_resume_and_idle_controls_keep_binding_and_fresh_observations(self):
        item, client = compiled(), SequenceClient()
        run = runner(compilation=item, client=client)
        run.pause()
        self.assertEqual(client.calls, [])
        self.assertEqual((await run.run()).status, "paused")
        self.assertEqual((await run.run(resume=True)).status, "succeeded")
        run.pause()
        run.cancel()
        self.assertEqual(client.calls.count("observe_game"), 3)
        self.assert_bound(run.trace.events, item)
        self.assertGreaterEqual(len({event.lifetime_id for event in run.trace.events}), 5)

    async def test_json_restart_requires_explicit_binding_without_checkpoint_metadata(self):
        with TemporaryDirectory() as directory:
            item = compiled()
            path = Path(directory) / "checkpoint.json"
            store = JsonRunStore(path)
            first = runner(compilation=item, store=store, policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="offline pause")]))
            self.assertEqual((await first.run()).status, "paused")
            self.assert_bound(first.trace.events, item)
            self.assertNotIn("recipe:", path.read_text(encoding="utf-8"))
            self.assertNotIn("skill", path.read_text(encoding="utf-8"))
            client = SequenceClient(count=1)
            second = runner(compilation=None, spec=item.task, store=store, client=client)
            self.assertEqual((await second.run()).status, "paused")
            self.assertEqual(client.calls, [])
            self.assertEqual((await second.run(resume=True)).status, "succeeded")
            self.assertEqual(client.calls.count("observe_game"), 2)
            self.assertTrue(all(event.provenance.skill.status == "absent" for event in second.trace.events))
            third = runner(compilation=item, store=store)
            self.assertEqual((await third.run()).status, "succeeded")
            self.assert_bound(third.trace.events, item)
            self.assertTrue(set(event.lifetime_id for event in first.trace.events).isdisjoint(
                event.lifetime_id for event in third.trace.events))

    async def test_caller_mutation_during_acquire_and_after_construction_cannot_drift_runner(self):
        item, expected, store = compiled(), compiled(), MemoryRunStore()
        task = item.task.model_copy(deep=True)
        acquire = store.acquire
        def mutate_caller():
            item.parameters.target_chapter = 1000
            item.task.success_when[0].value = 1000
            task.goal = "caller changed goal"
            return acquire()
        with patch.object(store, "acquire", side_effect=mutate_caller):
            run = runner(compilation=item, spec=task, store=store)
        item.preflight.evaluations.clear()
        task.allowed_tools.clear()
        self.assertEqual(run.state.task, expected.task)
        self.assertEqual((await run.run()).status, "succeeded")
        self.assert_bound(run.trace.events, expected)
        second_item = compiled(1)
        second = runner(compilation=second_item)
        self.assertEqual((await second.run()).completed_steps, 1)
        self.assert_bound(second.trace.events, second_item)
        self.assertNotEqual(run._skill_binding.task_digest, second._skill_binding.task_digest)

    async def test_default_v1_and_unbound_v2_keep_original_declarations(self):
        for causal in (False, True):
            run = runner(compilation=None, causal=causal)
            self.assertEqual((await run.run()).status, "succeeded")
            if causal:
                self.assertTrue(all(event.provenance.skill.status == "absent" for event in run.trace.events))
            else:
                self.assertTrue(all(type(event) is TraceEvent for event in run.trace.events))
                self.assertEqual({event.event for event in run.trace.events}, {"tool", "policy", "lifecycle"})
                before = run.trace.events
                await run.run()
                self.assertEqual(run.trace.events, before)
        class Custom(RuleDecisionPolicy):
            pass
        run = runner(compilation=None, policy=Custom())
        await run.run()
        self.assertTrue(all(event.provenance.skill.status == "unknown" for event in run.trace.events))

    async def test_binding_cannot_replace_goal_evidence_or_budget(self):
        for client in (SequenceClient(evidence=False), SequenceClient(mutate=lambda name, payload:
                payload.get("runtime_state", {}).get("field_meta", {}).get(
                    "progress.current_chapter_id", {}).update(observation_id="wrong"))):
            run = runner(client=client)
            self.assertEqual((await run.run()).reason, "step_limit")
        client = SequenceClient()
        run = runner(client=client, budget=RunBudgetLedger(BudgetLimits(max_tool_calls=0)))
        self.assertEqual((await run.run()).status, "failed")
        self.assertEqual(client.calls, [])

    async def test_owned_task_drift_before_entry_is_latched_without_any_bound_event(self):
        client = SequenceClient()
        run = runner(client=client)
        run.state.task.goal = "changed owned task"
        with self.assertRaises(TraceEmissionError):
            await run.run()
        self.assertIsNotNone(run._causal.failure)
        self.assertEqual(client.calls, [])
        self.assertEqual(run.trace.events, [])

    async def test_prepared_provenance_cannot_hide_owned_task_or_declaration_drift(self):
        for cut in ("task", "digest", "skill"):
            run = runner()
            producer = CausalTraceProducer(run)
            producer.start("run")
            _, provenance = producer.prepare_invocation()
            if cut == "task":
                run.state.task.goal = "changed after provenance"
            elif cut == "digest":
                provenance = provenance.model_copy(update={"task_digest": "0" * 64})
            else:
                provenance = provenance.model_copy(update={"skill": TraceDeclaration(status="unknown")})
            before = list(run.trace.events)
            producer.emit(producer.event("policy"), provenance=provenance)
            with self.assertRaises(TraceEmissionError):
                producer.check()
            self.assertEqual(run.trace.events, before)
            run.close()

    async def test_budget_clock_drift_after_prepared_tool_and_policy_stops_dispatch(self):
        for cut in ("tool", "policy"):
            item, client = compiled(), SequenceClient()
            policy = FakeDecisionPolicy([PolicyDecision(action="continue", reason="offline")])
            budget = RunBudgetLedger()
            run = runner(compilation=item, client=client, policy=policy, budget=budget)
            prepared, fired = [False], [False]
            original_prepare = CausalTraceProducer.prepare_invocation
            original_clock = budget._clock
            def prepare(producer, context=None, **kwargs):
                result = original_prepare(producer, context, **kwargs)
                if (context is None) == (cut == "tool"):
                    prepared[0] = True
                return result
            def clock():
                if prepared[0] and not fired[0]:
                    fired[0] = True
                    run.state.task.goal = "drift between preparation and dispatch"
                return original_clock()
            budget._clock = clock
            with patch.object(CausalTraceProducer, "prepare_invocation", prepare):
                with self.assertRaises((TraceEmissionError, CheckpointConflict)):
                    await run.run()
            self.assertTrue(fired[0])
            self.assertIsNotNone(run._causal.failure)
            self.assertEqual(client.calls, [] if cut == "tool" else [
                "session_status", "observe_game", "get_runtime_state", "list_action_candidates"])
            self.assertEqual(policy.contexts, [])
            self.assertFalse(any(event.event == cut for event in run.trace.events))
            self.assert_bound(run.trace.events, item)

    async def test_completed_tool_drift_does_not_emit_cached_provenance_or_dispatch_again(self):
        item = compiled()
        run = runner(compilation=item)
        run._client.after_call = lambda name: setattr(run.state.task, "goal", "changed after tool")
        with self.assertRaises((TraceEmissionError, CheckpointConflict)):
            await run.run()
        self.assertEqual(run._client.calls, ["session_status"])
        self.assertFalse(any(event.event == "tool" for event in run.trace.events))
        self.assert_bound(run.trace.events, item)

    async def test_drift_error_clears_ambient_secret_cause_context(self):
        secret = "ambient-binding-secret-7"
        run = runner()
        run.state.task.__dict__["goal"] = secret
        try:
            raise RuntimeError(secret)
        except RuntimeError:
            try:
                await run.run()
            except TraceEmissionError as error:
                self.assertIsNone(error.__cause__)
                self.assertIsNone(error.__context__)
                self.assertNotIn(secret, str(error) + repr(error) + "".join(traceback.format_exception(error)))
            else:
                self.fail("drift did not fail")
        self.assertEqual(run.trace.events, [])

    async def test_genuine_policy_cancel_and_checkpoint_primaries_outrank_binding_failure(self):
        for kind in ("policy", "cancel", "checkpoint"):
            failure = asyncio.CancelledError() if kind == "cancel" else ValueError("original-private-primary")
            run = runner()
            if kind == "checkpoint":
                original = run._ownership.save
                def save(state):
                    if state.pending_call:
                        run.state.task.goal = "drift before primary storage failure"
                        raise failure
                    return original(state)
                run._ownership.save = save
            else:
                class FailPolicy(RuleDecisionPolicy):
                    async def decide(self, context):
                        run.state.task.goal = "drift with primary"
                        raise failure
                run.policy = FailPolicy()
                # Preserve the established primary; persistence is a separate
                # fault dimension, not the cause under test in this case.
                original = run._ownership.save
                def save(state):
                    state_copy = state.model_copy(deep=True)
                    state_copy.task = run._task.model_copy(deep=True)
                    return original(state_copy)
                run._ownership.save = save
            if kind == "policy":
                result = await run.run()
                self.assertEqual(result.reason, "runtime_error:ValueError")
            else:
                with self.assertRaises(type(failure)) as caught:
                    await run.run()
                self.assertIs(caught.exception, failure)
            self.assertIs(run._causal.primary, failure)
            self.assertIn("trace_emission_error:SkillBindingError", failure.__notes__)
            self.assertNotIn("original-private-primary", json.dumps([
                event.model_dump(mode="json") for event in run.trace.events]))


if __name__ == "__main__":
    unittest.main()
