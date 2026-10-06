"""Synthetic recipe selection and existing TaskRunner integration only."""
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pioneer_agent.agent_harness import skill_registry as registry
from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.agent_harness.task_contracts import PolicyDecision
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy
from pioneer_agent.runbook.models import ConditionStatus
from test_task_runner import SequenceClient, runner

KEY = ("chapter-observer", "1.0.0")
TOOLS = ["session_status", "observe_game", "get_runtime_state", "list_action_candidates"]


def compile_target(target=3, metrics=None):
    return registry.compile_skill(*KEY, {"target_chapter": target},
        metrics={"progress.current_chapter_id": 1} if metrics is None else metrics)


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


class SkillRegistryTests(unittest.TestCase):
    def test_only_explicit_versioned_builtin(self):
        skills = registry.list_skills()
        self.assertEqual([(item.skill_id, item.version) for item in skills], [KEY])
        self.assertEqual(registry.resolve_skill(*KEY), skills[0])
        self.assertEqual(skills[0].admission, "repository_builtin_allowlist")
        self.assertEqual(skills[0].execution_authority, "none")
        self.assertFalse(skills[0].executable)

    def test_invalid_or_unknown_identity_never_falls_back(self):
        for key in ((None, "1.0.0"), (True, "1.0.0"), ("", "1.0.0"), ("chapter-observer", None),
                    ("chapter-observer", "latest"), ("chapter-observer", "1.0"), ("chapter-observer", "1.0.1"),
                    ("chapter-observer ", "1.0.0"), ("Chapter-Observer", "1.0.0"),
                    ("../chapter-observer", "1.0.0"), ("observe next chapter", "1.0.0")):
            with self.subTest(key=key), self.assertRaises(ValueError): registry.resolve_skill(*key)
        with self.assertRaises(TypeError): registry.resolve_skill("chapter-observer")

    def test_exact_fixed_task_spec(self):
        result = compile_target()
        self.assertEqual(result.status, "ready")
        self.assertEqual(result.task.model_dump(mode="json"), {
            "version": 1, "task_id": "chapter-observer@1.0.0:target-3", "goal": "Observe chapter >= 3 (read-only)",
            "success_when": [{"metric": "progress.current_chapter_id", "op": ">=", "value": 3}],
            "stop_when": [], "required_domains": ["chapter_panel"], "allowed_tools": TOOLS,
            "max_steps": 3, "wait_seconds": 0.0, "execution_authority": "none", "executable": False})
        self.assertEqual(result.missing_metrics, [])
        self.assertEqual(result.preflight.status, ConditionStatus.SATISFIED)

    def test_target_engineering_bounds_without_coercion(self):
        for target in (1, 1000): self.assertEqual(compile_target(target).parameters.target_chapter, target)
        for target in (0, -1, 1001, True, False, 3.0, "3", None, float("nan"), float("inf")):
            with self.subTest(target=target), self.assertRaises(ValueError): compile_target(target)

    def test_parameters_are_exact_and_no_authority_or_budget_override(self):
        for extra in ("allowed_tools", "max_steps", "wait_seconds", "success_when", "execution_authority", "executable", "reviewed", "path", "script"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                registry.compile_skill(*KEY, {"target_chapter": 3, extra: True}, metrics={})
        for params in ({}, [], None, registry.ChapterParameters(target_chapter=3)):
            with self.subTest(params=params), self.assertRaises(ValueError): registry.compile_skill(*KEY, params, metrics={})

    def test_external_catalog_and_self_reviewed_objects_not_admitted(self):
        external = {"skill_id": KEY[0], "version": KEY[1], "reviewed": True, "path": "draft/recipe.json"}
        with self.assertRaises(TypeError): registry.list_skills(catalog=[external])
        with self.assertRaises(TypeError): registry.resolve_skill(*KEY, catalog=[external])
        with self.assertRaises(ValueError): registry.resolve_skill(external, KEY[1])
        with self.assertRaises(TypeError): registry.compile_skill(*KEY, {"target_chapter": 3}, metrics={}, catalog=[external])
        self.assertFalse(hasattr(registry, "register_skill"))
        self.assertFalse(hasattr(registry, "load_skill"))

    def test_full_internal_catalog_duplicate_rejected_by_all_entrypoints(self):
        original = registry._BUILTINS
        with patch.object(registry, "_BUILTINS", original + (original[0].model_copy(deep=True),)):
            for call in (registry.list_skills, lambda: registry.resolve_skill(*KEY), lambda: compile_target()):
                with self.assertRaisesRegex(ValueError, "duplicate"): call()

    def test_internal_unknown_or_changed_descriptor_not_allowlisted(self):
        for field, value in (("skill_id", "draft"), ("version", "2.0.0"), ("template_digest", "0" * 64)):
            item = registry._BUILTINS[0].model_copy(deep=True)
            setattr(item, field, value)
            with patch.object(registry, "_BUILTINS", (item,)):
                with self.assertRaisesRegex(ValueError, "allowlist"): registry.list_skills()

    def test_template_digest_exact_full_preimage(self):
        definition = registry.resolve_skill(*KEY)
        raw = definition.model_dump(mode="json")
        actual = raw.pop("template_digest")
        self.assertEqual(actual, canonical_digest(raw))
        for key in ("execution_authority", "executable", "parameter_schema", "preconditions", "template", "admission", "version"):
            modified = copy.deepcopy(raw)
            modified.pop(key)
            self.assertNotEqual(actual, canonical_digest(modified))

    def test_task_digest_covers_all_fields_and_target(self):
        first, second = compile_target(3), compile_target(4)
        self.assertEqual(first.template_digest, second.template_digest)
        self.assertEqual(first.task_digest, canonical_digest(first.task.model_dump(mode="json")))
        self.assertNotEqual(first.task_digest, second.task_digest)
        modified = first.task.model_dump(mode="json")
        modified["max_steps"] = 4
        self.assertNotEqual(first.task_digest, canonical_digest(modified))

    def test_deep_copy_listing_resolution_compilation_and_input_isolation(self):
        expected = registry.resolve_skill(*KEY)
        listed = registry.list_skills()[0]
        listed.parameter_schema["properties"]["target_chapter"]["maximum"] = 99
        listed.preconditions[0].value = 999
        listed.template.allowed_tools.append("other")
        listed.execution_authority = "forged"
        resolved = registry.resolve_skill(*KEY)
        resolved.template.required_domains.clear()
        self.assertEqual(registry.resolve_skill(*KEY), expected)
        params, metrics = {"target_chapter": 3}, {"progress": {"current_chapter_id": 1}}
        original = copy.deepcopy((params, metrics))
        result = registry.compile_skill(*KEY, params, metrics=metrics)
        result.task.allowed_tools.clear()
        result.task.success_when[0].value = 1000
        result.parameters.target_chapter = 1000
        result.preflight.evaluations[0].value = -1
        self.assertEqual((params, metrics), original)
        self.assertEqual(compile_target().task.allowed_tools, TOOLS)
        self.assertEqual(compile_target().task.success_when[0].value, 3)
        self.assertEqual(compile_target().preflight.evaluations[0].value, 1)

    def test_false_is_blocked_without_task(self):
        for chapter in (0, -1):
            result = compile_target(metrics={"progress.current_chapter_id": chapter})
            self.assertEqual((result.status, result.reason), ("blocked", "precondition_not_satisfied"))
            self.assertEqual(result.preflight.status, ConditionStatus.NOT_SATISFIED)
            self.assertEqual(result.missing_metrics, [])
            self.assertIsNone(result.task)
            self.assertIsNone(result.task_digest)

    def test_missing_and_bad_metric_types_are_unknown(self):
        values = [None, True, False, "1", 1.0, float("nan"), float("inf"), [], {}]
        for metrics in [{}, {"progress": {}}, {"progress": 1}] + [{"progress.current_chapter_id": value} for value in values]:
            with self.subTest(metrics=metrics):
                result = compile_target(metrics=metrics)
                self.assertEqual((result.status, result.reason), ("blocked", "precondition_unknown"))
                self.assertEqual(result.preflight.status, ConditionStatus.UNKNOWN)
                self.assertEqual(result.missing_metrics, ["progress.current_chapter_id"])
                self.assertIsNone(result.task)
                self.assertIsNone(result.task_digest)

    def test_flat_metric_precedence_matches_existing_conditions(self):
        result = compile_target(metrics={"progress.current_chapter_id": False, "progress": {"current_chapter_id": 3}})
        self.assertEqual(result.preflight.status, ConditionStatus.UNKNOWN)
        self.assertEqual(compile_target(metrics={"progress": {"current_chapter_id": 1}}).status, "ready")

    def test_malformed_metrics_container_is_invalid_not_blocked(self):
        for metrics in (None, [], True, {1: 3}):
            with self.assertRaises(ValueError): registry.compile_skill(*KEY, {"target_chapter": 3}, metrics=metrics)

    def test_selection_has_zero_tool_model_and_runtime_calls(self):
        with patch("pioneer_agent.agent_harness.task_runner.TaskRunner.run", side_effect=AssertionError("must not run")), \
             patch("test_task_runner.SequenceClient.call_tool", side_effect=AssertionError("must not call tool")), \
             patch("pioneer_agent.agent_harness.task_policy.RuleDecisionPolicy.decide", side_effect=AssertionError("must not decide")):
            registry.list_skills()
            registry.resolve_skill(*KEY)
            self.assertEqual(compile_target().status, "ready")
            self.assertEqual(compile_target(metrics={}).status, "blocked")
            self.assertEqual(compile_target(metrics={"progress.current_chapter_id": 0}).status, "blocked")

    def test_explicit_utf8_serialization_roundtrip(self):
        data = {"fixture": "合成只读配方", "result": compile_target().model_dump(mode="json")}
        with TemporaryDirectory() as directory:
            path = Path(directory) / "recipe.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), data)


class SkillRunnerIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_fresh_observations_and_terminal_noop(self):
        client = SequenceClient()
        run = runner(client, spec=compile_target().task)
        result = await run.run()
        self.assertEqual((result.status, result.reason, result.completed_steps), ("succeeded", "goal_verified", 3))
        self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])
        self.assertIn("observation:obs-3", result.evidence_refs)
        self.assertEqual(run.budget.summary()["counts"], {"step": 3, "tool": 12, "model": 0})
        calls = list(client.calls)
        self.assertEqual((await run.run()).status, "succeeded")
        self.assertEqual(client.calls, calls)
        self.assertEqual(set(calls), set(TOOLS))
        self.assertEqual(result.execution_authority, "none")
        self.assertFalse(result.executable)

    async def test_preflight_already_met_still_requires_new_runtime_observation(self):
        compiled = compile_target(1, metrics={"progress.current_chapter_id": 999})
        client = SequenceClient()
        self.assertEqual(client.calls, [])
        result = await runner(client, spec=compiled.task).run()
        self.assertEqual(result.observation_ids, ["obs-1"])
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(len(client.calls), 4)

    async def test_missing_field_evidence_does_not_succeed(self):
        result = await runner(SequenceClient(evidence=False), spec=compile_target().task).run()
        self.assertEqual((result.status, result.reason), ("failed", "step_limit"))

    async def test_wrong_field_evidence_does_not_succeed(self):
        def mutate(name, payload):
            if "runtime_state" in payload:
                payload["runtime_state"]["field_meta"]["progress.current_chapter_id"]["observation_id"] = "wrong-observation"
        result = await runner(SequenceClient(mutate=mutate), spec=compile_target().task).run()
        self.assertEqual(result.status, "failed")
        self.assertNotEqual(result.reason, "goal_verified")

    async def test_budget_stop_still_applies(self):
        client = SequenceClient()
        budget = RunBudgetLedger(BudgetLimits(max_tool_calls=0))
        result = await runner(client, spec=compile_target().task, budget=budget).run()
        self.assertEqual(result.status, "failed")
        self.assertEqual(client.calls, [])

    async def test_pause_and_resume_use_existing_runner(self):
        client = SequenceClient()
        policy = FakeDecisionPolicy([PolicyDecision(action="pause", reason="synthetic pause"),
                                     PolicyDecision(action="continue", reason="synthetic resume"),
                                     PolicyDecision(action="continue", reason="verify third frame")])
        run = runner(client, spec=compile_target().task, policy=policy)
        first = await run.run()
        self.assertEqual(first.status, "paused")
        calls = list(client.calls)
        self.assertEqual((await run.run()).status, "paused")
        self.assertEqual(client.calls, calls)
        resumed = await run.run(resume=True)
        self.assertEqual(resumed.status, "succeeded")
        self.assertEqual(resumed.observation_ids, ["obs-1", "obs-2", "obs-3"])
        self.assertEqual(client.calls.count("observe_game"), 3)


if __name__ == "__main__":
    unittest.main()
