"""Memo-bound registry and existing-runner controls; no implementation repair."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from datetime import timedelta
import unittest
from unittest.mock import patch

from pioneer_agent.agent_harness.task_contracts import TaskSpec, PolicyDecision
from pioneer_agent.agent_harness.task_runner import TaskRunner
from pioneer_agent.agent_harness.task_policy import RuleDecisionPolicy, FakeDecisionPolicy
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger, BudgetLimits
from pioneer_agent.agent_harness.run_store import JsonRunStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.runbook.models import Condition, ConditionStatus
from test_task_runner import BASE, SequenceClient, runner

ID, VERSION = "chapter-observer", "1.0.0"
METRIC = "progress.current_chapter_id"
TOOLS = ["session_status", "observe_game", "get_runtime_state", "list_action_candidates"]
BASELINE_RUNTIME = sys.argv[1:] == ["--verify-baseline-runtime"]


def api():
    from pioneer_agent.agent_harness import skill_registry
    return skill_registry


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def expected_task(target=3):
    return TaskSpec(task_id=f"{ID}@{VERSION}:target-{target}",
        goal=f"Observe chapter >= {target} (read-only)",
        success_when=[Condition(metric=METRIC, op=">=", value=target)], stop_when=[],
        required_domains=["chapter_panel"], allowed_tools=list(TOOLS), max_steps=3,
        wait_seconds=0, execution_authority="none", executable=False)


def compile_result(target=3, metrics=None, **kwargs):
    return api().compile_skill(ID, VERSION, {"target_chapter": target},
        metrics={METRIC: 1} if metrics is None else metrics, **kwargs)


def compiled_task(target=3, metrics=None):
    if BASELINE_RUNTIME:
        return expected_task(target)
    result = compile_result(target, metrics)
    assert result.status == "ready"
    return result.task


def poison_nested(value):
    if isinstance(value, dict):
        for child in list(value.values()):
            poison_nested(child)
        value["independent_mutation"] = ["not-a-catalog-entry"]
    elif isinstance(value, list):
        for child in list(value):
            poison_nested(child)
        if value:
            value.append(copy.deepcopy(value[0]))
    elif hasattr(value, "model_dump"):
        for field in type(value).model_fields:
            poison_nested(getattr(value, field))


class RegistryPublicControls(unittest.TestCase):
    def test_builtin_exact_template_and_full_digests(self):
        registry = api()
        listed = registry.list_skills()
        self.assertEqual([(s.skill_id, s.version) for s in listed], [(ID, VERSION)])
        definition = registry.resolve_skill(ID, VERSION)
        raw = definition.model_dump(mode="json")
        declared = raw.pop("template_digest")
        self.assertEqual(declared, canonical_digest(raw))
        self.assertEqual(raw["admission"], "repository_builtin_allowlist")
        self.assertEqual((raw["execution_authority"], raw["executable"]), ("none", False))
        prior_digest = None
        for target in (1, 3, 1000):
            result = compile_result(target)
            self.assertEqual(result.status, "ready")
            self.assertEqual(result.reason, "preconditions_satisfied")
            self.assertEqual(result.template_digest, declared)
            self.assertEqual(result.task.model_dump(mode="json"), expected_task(target).model_dump(mode="json"))
            self.assertEqual(result.task_digest, canonical_digest(result.task.model_dump(mode="json")))
            self.assertNotEqual(result.task_digest, prior_digest)
            prior_digest = result.task_digest
        self.assertEqual(compile_result(3, {METRIC: 999}).task_digest, compile_result(3).task_digest)

    def test_nested_output_mutations_never_pollute_future_results(self):
        registry = api()
        definition = registry.resolve_skill(ID, VERSION).model_dump(mode="json")
        compiled = compile_result().model_dump(mode="json")
        returned = registry.list_skills()[0]
        poison_nested(returned.parameter_schema)
        poison_nested(returned.template)
        poison_nested(returned.preconditions)
        self.assertNotEqual(returned.model_dump(mode="json"), definition)
        self.assertEqual(registry.resolve_skill(ID, VERSION).model_dump(mode="json"), definition)
        resolved = registry.resolve_skill(ID, VERSION)
        poison_nested(resolved.template)
        self.assertEqual(registry.list_skills()[0].model_dump(mode="json"), definition)
        first, second = compile_result(), compile_result()
        first.task.allowed_tools.append("forbidden-probe-tool")
        first.task.success_when[0].value = 999
        first.task.required_domains.append("not-a-real-domain")
        self.assertEqual(second.model_dump(mode="json"), compiled)
        self.assertEqual(compile_result().model_dump(mode="json"), compiled)

    def test_identity_parameters_and_external_admission_rejected(self):
        registry = api()
        for identity, version in (("unknown", VERSION), (ID, "latest"), (ID, "1.0"),
                (ID, ""), (ID, None), (ID, 1), ("/tmp/self-reviewed.json", VERSION),
                ({"skill_id": ID, "reviewed": True}, VERSION), (None, VERSION)):
            with self.subTest(identity=identity, version=version), self.assertRaises((ValueError, TypeError)):
                registry.resolve_skill(identity, version)
        with self.assertRaises(TypeError): registry.resolve_skill(ID)
        for target in (None, True, False, 0, -1, 1001, 3.0, "3"):
            with self.subTest(target=target), self.assertRaises((ValueError, TypeError)):
                compile_result(target)
        for key, value in (("reviewed", True), ("max_steps", 100), ("allowed_tools", ["execute"]),
                ("success_when", []), ("execution_authority", "live"), ("executable", True), ("path", "/tmp/draft")):
            with self.subTest(key=key), self.assertRaises((ValueError, TypeError)):
                registry.compile_skill(ID, VERSION, {"target_chapter": 3, key: value}, metrics={METRIC: 1})
        with self.assertRaises(TypeError): compile_result(catalog=registry.list_skills())
        with self.assertRaises((ValueError, TypeError)): registry.compile_skill(ID, VERSION, {}, metrics={METRIC: 1})
        for metrics in (None, [], {1: 3}):
            with self.subTest(metrics=metrics), self.assertRaises((ValueError, TypeError)):
                registry.compile_skill(ID, VERSION, {"target_chapter": 3}, metrics=metrics)

    def test_tristate_and_flat_invalid_never_fall_back_to_nested(self):
        controls = [({}, ConditionStatus.UNKNOWN), ({"progress": {}}, ConditionStatus.UNKNOWN)]
        controls += [({METRIC: value}, ConditionStatus.UNKNOWN) for value in (None, True, False, 1.0, "3", [], {}, float("nan"), float("inf"))]
        controls += [({METRIC: value}, ConditionStatus.NOT_SATISFIED) for value in (0, -1)]
        controls += [({METRIC: value}, ConditionStatus.SATISFIED) for value in (1, 1001)]
        controls += [({METRIC: bad, "progress": {"current_chapter_id": 3}}, status) for bad, status in
                     ((None, ConditionStatus.UNKNOWN), (True, ConditionStatus.UNKNOWN), (0, ConditionStatus.NOT_SATISFIED))]
        controls.append(({METRIC: 2, "progress": {"current_chapter_id": 0}}, ConditionStatus.SATISFIED))
        for metrics, status in controls:
            before = repr(metrics)
            result = compile_result(metrics=metrics)
            with self.subTest(metrics=metrics):
                self.assertEqual(result.preflight.status, status)
                self.assertEqual(repr(metrics), before)
                if status != ConditionStatus.SATISFIED:
                    self.assertEqual(result.status, "blocked")
                    self.assertIsNone(result.task)
                    self.assertIsNone(result.task_digest)
                    self.assertEqual(result.reason, "precondition_unknown" if status == ConditionStatus.UNKNOWN else "precondition_not_satisfied")
                    self.assertEqual(result.missing_metrics, [METRIC] if status == ConditionStatus.UNKNOWN else [])

    def test_preflight_invalid_and_blocked_have_zero_runtime_or_model_calls(self):
        registry = api()
        with patch.object(TaskRunner, "run") as run, patch.object(RecommendationHarness, "run_decision_window") as window, \
                patch.object(SequenceClient, "call_tool") as tool, patch.object(RuleDecisionPolicy, "decide") as policy:
            for metrics in ({}, {METRIC: 0}, {METRIC: True}, {METRIC: 99}):
                registry.compile_skill(ID, VERSION, {"target_chapter": 3}, metrics=metrics)
            with self.assertRaises((ValueError, TypeError)):
                registry.compile_skill(ID, VERSION, {"target_chapter": True}, metrics={METRIC: 1})
            for port in (run, window, tool, policy): port.assert_not_called()


class RegistryRuntimeControls(unittest.IsolatedAsyncioTestCase):
    async def test_actual_three_fresh_observations_opaque_id_and_terminal_noop(self):
        with TemporaryDirectory() as directory:
            store = JsonRunStore(Path(directory) / "checkpoint.json")
            client = SequenceClient()
            task = compiled_task(3, {METRIC: 99})
            r = runner(client, store=store, spec=task)
            result = await r.run()
            self.assertEqual((result.status, result.reason, result.completed_steps), ("succeeded", "goal_verified", 3))
            self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])
            self.assertEqual(client.calls, TOOLS * 3)
            self.assertIn("observation:obs-3", result.evidence_refs)
            self.assertEqual(r.budget.summary()["counts"], {"step": 3, "tool": 12, "model": 0})
            before = list(client.calls)
            self.assertEqual((await r.run()).status, "succeeded")
            self.assertEqual(client.calls, before)
            self.assertEqual(store.load().task.task_id, f"{ID}@{VERSION}:target-3")

    async def test_missing_or_wrong_field_evidence_cannot_use_precheck_as_success(self):
        def wrong_evidence(name, payload):
            if name == "get_runtime_state":
                payload["runtime_state"]["field_meta"][METRIC]["observation_id"] = "obs-wrong"
        for client in (SequenceClient(evidence=False), SequenceClient(mutate=wrong_evidence)):
            result = await runner(client, spec=compiled_task(3, {METRIC: 99})).run()
            self.assertEqual((result.status, result.reason), ("failed", "step_limit"))
            self.assertEqual(client.calls.count("observe_game"), 3)

    async def test_existing_budget_and_pause_stop_dispatch(self):
        client = SequenceClient()
        budget = RunBudgetLedger(BudgetLimits(max_tool_calls=1, max_model_attempts=0))
        result = await runner(client, spec=compiled_task(), budget=budget).run()
        self.assertEqual((result.status, result.reason), ("failed", "budget_exhausted"))
        self.assertEqual(client.calls, ["session_status"])
        client = SequenceClient()
        r = runner(client, spec=compiled_task())
        client.after_call = lambda name: r.pause()
        self.assertEqual((await r.run()).status, "paused")
        self.assertEqual(client.calls, ["session_status"])
        self.assertEqual((await r.run()).status, "paused")
        self.assertEqual(client.calls, ["session_status"])

    async def test_old_observation_is_rejected_before_policy(self):
        def stale(name, payload):
            if name == "observe_game":
                payload["observation"]["captured_at"] = (BASE - timedelta(hours=1)).isoformat()
        client = SequenceClient(mutate=stale)
        policy = FakeDecisionPolicy([PolicyDecision(action="continue", reason="must not execute")])
        result = await runner(client, spec=compiled_task(3, {METRIC: 99}), policy=policy).run()
        self.assertEqual((result.status, result.reason), ("failed", "observation_stale"))
        self.assertEqual(policy.contexts, [])


if __name__ == "__main__":
    if BASELINE_RUNTIME:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(RegistryRuntimeControls)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(not result.wasSuccessful())
    unittest.main()
