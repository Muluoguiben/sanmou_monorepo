"""H08b memo-only public probes, frozen before author implementation access.

No provider/network/game; temporary files use the explicitly authorized TMPDIR.
Baseline mode never
passes the absent skill_compilation keyword. Actual binding tests require a fixed
implementing source. Keep original assertions/results across repair rounds.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import traceback
import unittest
from uuid import uuid4

from pioneer_agent.agent_harness import skill_registry as registry
from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder
from pioneer_agent.agent_harness.journal import InMemoryJournalStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.run_store import JsonRunStore, MemoryRunStore
from pioneer_agent.agent_harness.run_trace import InMemoryRunTrace, JsonlRunTrace
from pioneer_agent.agent_harness.task_contracts import PolicyDecision, TraceDeclaration, TraceEmissionError
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy, RuleDecisionPolicy
from pioneer_agent.agent_harness.task_runner import TaskRunner
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
from test_task_runner import BASE, PortBudget, SequenceClient, timedelta

ROOT = Path(__file__).resolve().parents[3]
SCRATCH = ROOT / "data/agent_runs/h08b-independent-20261018"
KEY = ("chapter-observer", "1.0.0")
FROZEN = Path(__file__).with_name("h08b-unbound-oracle.json")


def compilation(target=3):
    return registry.compile_skill(*KEY, {"target_chapter": target},
        metrics={"progress.current_chapter_id": 1})


def directory():
    result = Path(os.environ.get("TMPDIR", str(SCRATCH))) / uuid4().hex
    result.mkdir(parents=True, exist_ok=False)
    return result


def make(*, compiled=None, bind=False, causal=True, client=None, store=None,
         trace=None, budget=None, policy=None, task=None, ownership=None):
    client = client or SequenceClient()
    compiled = compiled or compilation()
    harness = RecommendationHarness(game_client=client,
        journal_store=InMemoryJournalStore(), tool_log=InMemoryToolLog(),
        agent_session_id="run", model_id="offline-rule",
        clock=lambda: BASE + timedelta(seconds=client.count + 1))
    kwargs = dict(task=task or compiled.task, run_id="run", harness=harness,
        store=store or MemoryRunStore(), policy=policy or RuleDecisionPolicy(),
        context_builder=BoundedContextBuilder(), budget=budget or PortBudget(),
        trace=trace or InMemoryRunTrace(), ownership=ownership)
    if causal:
        kwargs["causal_trace"] = causal
    if bind:
        kwargs["skill_compilation"] = compiled
    return TaskRunner(**kwargs)


def normalized(rows):
    """Only predeclared v2 random causal IDs and timestamp; all other data stays."""
    result, ids = copy.deepcopy(rows), {}
    id_fields = ("event_id", "lifetime_id", "parent_event_id", "window_id", "invocation_id")
    for row in result:
        for field in id_fields:
            value = row.get(field)
            if value is not None:
                ids.setdefault(value, f"causal-{len(ids) + 1}")
                row[field] = ids[value]
        if "emitted_at" in row:
            row["emitted_at"] = "<nondeterministic-emitted-at>"
    return result


async def baseline():
    result = {}
    for causal in (False, True):
        run = make(causal=causal)
        first = await run.run()
        before = [event.model_dump(mode="json") for event in run.trace.events]
        second = await run.run()
        after = [event.model_dump(mode="json") for event in run.trace.events]
        result[str(causal)] = dict(before=normalized(before), after=normalized(after),
            statuses=[first.status, second.status], calls=list(run._client.calls),
            budget_calls=[item.model_dump(mode="json") for item in run.budget.calls],
            budget_settled=list(run.budget.settled))
    return result


class BindingBoundaryProbes(unittest.TestCase):
    def assert_clean_error(self, call, canary="PRIVATE_H08B_INPUT"):
        error = None
        try:
            call()
        except Exception as caught:
            error = caught
        self.assertIsNotNone(error, "invalid binding was accepted")
        self.assertEqual(type(error).__name__, "SkillBindingError")
        self.assertIn(str(error), {"invalid_skill_binding", "skill_binding_requires_causal_trace"})
        self.assertNotIn(canary, str(error) + repr(error) + "".join(traceback.format_exception(error)))
        self.assertIsNone(error.__cause__)
        self.assertIsNone(error.__context__)
        self.assertFalse(getattr(error, "__notes__", ()))

    def test_mutated_and_constructed_models_do_not_bypass_strict_binding(self):
        cases = [
            ("skill_id", "PRIVATE_H08B_INPUT"), ("version", "1.0.1"),
            ("admission", "external"), ("execution_authority", "execute"),
            ("executable", 0), ("status", "blocked"), ("reason", "precondition_unknown"),
            ("template_digest", "0" * 64), ("task_digest", "0" * 64),
            ("missing_metrics", ["PRIVATE_H08B_INPUT"]),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                item = compilation().model_copy(deep=True, update={field: value})
                self.assert_clean_error(lambda: registry.validate_skill_binding(item, compilation().task))
        for value in (True, False, 3.0, "3", 0, 1001):
            with self.subTest(target=repr(value)):
                item = compilation()
                item.parameters.target_chapter = value
                self.assert_clean_error(lambda: registry.validate_skill_binding(item, item.task))
        for value in (True, 1.0, "1", 0, 3):
            with self.subTest(threshold=repr(value)):
                item = compilation()
                item.preflight.evaluations[0].value = value
                self.assert_clean_error(lambda: registry.validate_skill_binding(item, item.task))

    def test_nested_extra_fields_cannot_disappear_during_serialization(self):
        for path in ((), ("parameters",), ("preflight",), ("preflight", "evaluations", 0),
                     ("task",), ("task", "success_when", 0)):
            for storage in ("dict", "extra"):
                with self.subTest(path=path, storage=storage):
                    item = compilation()
                    target = item
                    for key in path:
                        target = target[key] if isinstance(key, int) else getattr(target, key)
                    if storage == "dict":
                        target.__dict__["PRIVATE_H08B_INPUT"] = "unknown"
                    else:
                        object.__setattr__(target, "__pydantic_extra__", {"PRIVATE_H08B_INPUT": "unknown"})
                    self.assert_clean_error(lambda: registry.validate_skill_binding(item, compilation().task))

    def test_exact_types_and_complete_preflight_are_required(self):
        good = compilation()
        class SubCompilation(type(good)):
            pass
        for item in (good.model_dump(), None, "PRIVATE_H08B_INPUT",
                     SubCompilation.model_construct(**good.__dict__)):
            with self.subTest(type=type(item).__name__):
                self.assert_clean_error(lambda: registry.validate_skill_binding(item, good.task))
        for count in (0, 2):
            item = compilation()
            item.preflight.evaluations = item.preflight.evaluations * count
            self.assert_clean_error(lambda: registry.validate_skill_binding(item, item.task))
        item = compilation()
        item.task.success_when[0].value = 3.0
        item.task_digest = hashlib.sha256(json.dumps(item.task.model_dump(mode="json"),
            sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assert_clean_error(lambda: registry.validate_skill_binding(item, item.task))

    def test_validation_error_is_clean_inside_ambient_exception(self):
        for causal in (False, True, 1, "yes"):
            try:
                raise LookupError("PRIVATE_H08B_AMBIENT")
            except LookupError as ambient:
                bad = compilation()
                bad.skill_id = "PRIVATE_H08B_INPUT"
                self.assert_clean_error(lambda: make(compiled=bad, bind=True, causal=causal),
                    canary="PRIVATE_H08B_AMBIENT")
                self.assertFalse(getattr(ambient, "__notes__", ()))

    def test_invalid_constructor_has_no_external_side_effects(self):
        path = directory() / "checkpoint.json"
        path.write_text("existing checkpoint bytes must survive", encoding="utf-8")
        store = JsonRunStore(path)
        owner = store.acquire()
        before = path.read_bytes()
        calls = []
        class UntouchedHarness:
            @property
            def qa_client(self):
                calls.append("qa_client")
                raise AssertionError("validation must precede harness reads")
            @property
            def game_client(self):
                calls.append("game_client")
                raise AssertionError("validation must precede harness reads")
        try:
            bad = compilation()
            bad.parameters.target_chapter = True
            self.assert_clean_error(lambda: TaskRunner(task=compilation().task,
                run_id="run", harness=UntouchedHarness(), store=store, ownership=owner,
                policy=RuleDecisionPolicy(), context_builder=BoundedContextBuilder(),
                budget=PortBudget(), trace=InMemoryRunTrace(), causal_trace=True,
                skill_compilation=bad))
            self.assertEqual(calls, [])
            self.assertTrue(owner.active)
            self.assertIsNone(owner._runner)
            self.assertFalse(owner._loaded)
            owner.check()
            self.assertEqual(path.read_bytes(), before)
        finally:
            owner.close()


class BindingLifetimeProbes(unittest.IsolatedAsyncioTestCase):
    async def test_cached_tool_completion_rechecks_drift_after_budget_settlement(self):
        state = {"changed": False}
        class Budget(PortBudget):
            def settle(self, reservation_id, usage, *, outcome):
                super().settle(reservation_id, usage, outcome=outcome)
                run = state["run"]
                if run.state.pending_call == "session_status" and not state["changed"]:
                    state["changed"] = True
                    state["rows"] = len(run.trace.events)
                    run.state.task.goal = "drift during settlement"
        run = make(bind=True, budget=Budget())
        state["run"] = run
        original_save = run._ownership.save
        def save_original_task(snapshot):
            # Isolate trace completion from the separate checkpoint-conflict cut.
            detached = snapshot.model_copy(deep=True)
            detached.task = compilation().task
            return original_save(detached)
        run._ownership.save = save_original_task
        with self.assertRaises(TraceEmissionError):
            await run.run()
        self.assertTrue(state["changed"])
        self.assertEqual(run._client.calls, ["session_status"])
        self.assertEqual(len(run.trace.events), state["rows"])
        self.assertEqual(len(run.budget.settled), len(set(run.budget.settled)))
        self.assertIsNotNone(run._causal.failure)

    async def test_terminal_already_saved_is_not_rolled_back_on_late_drift(self):
        path = directory() / "checkpoint.json"
        store = JsonRunStore(path)
        run = make(bind=True, store=store)
        save = run._ownership.save
        state = {"changed": False}
        def late_drift(snapshot):
            result = save(snapshot)
            if snapshot.status == "succeeded" and not state["changed"]:
                state["changed"] = True
                state["rows"] = len(run.trace.events)
                run.state.task.goal = "drift after durable success"
            return result
        run._ownership.save = late_drift
        try:
            await run.run()
        except BaseException:
            pass  # A real subsequent checkpoint conflict must retain priority.
        self.assertTrue(state["changed"])
        self.assertEqual((store.load().status, store.load().reason), ("succeeded", "goal_verified"))
        self.assertEqual(store.load().task, compilation().task)
        self.assertEqual(len(run._client.calls), 12)
        self.assertEqual(len(run.trace.events), state["rows"])
        self.assertIsNotNone(run._causal.failure)

    async def test_prepared_provenance_then_budget_drift_stops_lazy_dispatch(self):
        for cut, uses_model in (("session_status", False), ("policy:drift-probe", False),
                                ("policy:drift-probe", True)):
            with self.subTest(cut=cut, uses_model=uses_model):
                state = {"prepared": False, "changed": False}
                calls = []
                class Policy:
                    policy_id = "drift-probe"
                    @property
                    def policy_version(self):
                        run = state.get("run")
                        if run is not None and run.state.pending_call == cut:
                            state["prepared"] = True
                        return "v1"
                    async def decide(self, context):
                        calls.append(context.observation_id)
                        return PolicyDecision(action="continue", reason="offline")
                policy = Policy()
                policy.uses_model = uses_model
                class Budget(PortBudget):
                    def remaining_seconds(self):
                        if state["prepared"] and not state["changed"]:
                            state["changed"] = True
                            state["rows_at_drift"] = len(state["run"].trace.events)
                            state["run"].state.task.goal = "drift after prepared provenance"
                        return 60
                run = make(bind=True, policy=policy, budget=Budget())
                state["run"] = run
                try:
                    await run.run()
                except BaseException:
                    pass  # Classification is checked by original H10 primary probes.
                self.assertTrue(state["changed"], "probe did not reach its prepared-provenance cut")
                self.assertEqual(len(run._client.calls), 0 if cut == "session_status" else 4)
                self.assertEqual(calls, [], "policy entered after bound task changed")
                self.assertIsNotNone(run._causal.failure, "drift did not latch trace failure")
                self.assertEqual(len(run.trace.events), state["rows_at_drift"])
                self.assertEqual(len(run.budget.calls), 2 if cut == "session_status" else 5 + int(uses_model))

    async def test_runtime_drift_failure_is_not_hidden_by_ambient_exception(self):
        run = make(bind=True)
        run.state.task.goal = "drift before run"
        try:
            raise LookupError("PRIVATE_H08B_AMBIENT_RUNTIME")
        except LookupError as ambient:
            with self.assertRaises(TraceEmissionError) as caught:
                await run.run()
            self.assertIsNone(caught.exception.__cause__)
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn("PRIVATE_H08B_AMBIENT_RUNTIME", "".join(traceback.format_exception(caught.exception)))
            self.assertFalse(getattr(ambient, "__notes__", ()))
        self.assertEqual(run._client.calls, [])
        self.assertEqual(run.trace.events, [])

    async def test_same_task_snapshot_survives_acquire_hook_and_caller_mutation(self):
        item = compilation()
        original_task = item.task
        class MutatingStore(MemoryRunStore):
            def acquire(self):
                item.parameters.target_chapter = 999
                item.task.goal = "changed caller goal"
                item.task.success_when[0].value = 999
                return super().acquire()
        run = make(compiled=item, bind=True, store=MutatingStore())
        self.assertIsNot(run.state.task, original_task)
        self.assertEqual(run.state.task.model_dump(), compilation().task.model_dump())
        result = await run.run()
        self.assertEqual((result.status, result.completed_steps), ("succeeded", 3))
        self.assertEqual(run._client.calls.count("observe_game"), 3)
        expected = "recipe:chapter-observer@1.0.0#sha256=" + compilation().template_digest
        self.assertEqual(len(expected), 101)
        self.assertTrue(all(event.provenance.skill.value == expected for event in run.trace.events))

    async def test_dual_sink_exact_exception_and_cross_slot_controls(self):
        run = make(bind=True)
        await run.run()
        original = run.trace.events[0]
        exact = "recipe:chapter-observer@1.0.0#sha256=" + compilation().template_digest
        syntax_only = exact[:-64] + "0" * 64
        values = (exact, syntax_only, exact + "\n", exact + "\r\n", " " + exact, exact + "a", exact[:-1],
            exact.replace("1.0.0", "1.0.1"), exact[:-64] + "A" * 64,
            exact.replace("#", "＃"), exact.replace("=", "＝"))
        for slot in ("policy_version", "model", "prompt", "skill", "kb"):
            for value in values:
                with self.subTest(slot=slot, value=value):
                    declaration = TraceDeclaration(status="declared", value=value)
                    provenance = original.provenance.model_copy(deep=True, update={slot: declaration})
                    record = original.model_copy(deep=True, update={"provenance": provenance})
                    memory = InMemoryRunTrace()
                    path = directory() / "trace.jsonl"
                    disk = JsonlRunTrace(path)
                    memory.emit(record)
                    disk.emit(record)
                    expected = value if slot == "skill" and value in (exact, syntax_only) else (
                        "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest())
                    memory_row = memory.events[0].model_dump(mode="json")
                    disk_row = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(memory_row, disk_row)
                    self.assertEqual(memory_row["provenance"][slot]["value"], expected)


if __name__ == "__main__":
    if sys.argv[1:] == ["--freeze-baseline"]:
        with FROZEN.open("x", encoding="utf-8") as handle:
            json.dump(asyncio.run(baseline()), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        print("baseline frozen", FROZEN)
    elif sys.argv[1:] == ["--verify-baseline"]:
        assert asyncio.run(baseline()) == json.loads(FROZEN.read_text(encoding="utf-8"))
        print("full baseline unchanged; only declared random v2 IDs/timestamp normalized")
    else:
        unittest.main(verbosity=2)
