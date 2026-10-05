"""Adversarial checks for the standalone task evaluator, not its runtime implementation."""
import copy
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from pioneer_agent.agent_harness._task_eval_inputs import (
    Fixture, Inputs, InputError, Suite, decode, digest, safe_path,
)
from pioneer_agent.agent_harness._task_eval_source import SourceBinding
from pioneer_agent.agent_harness.task_eval import execute, score, stable_projection, write_new


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "packages/pioneer-agent/evaluation/task/development-v1"


def suite():
    return Suite.model_validate(decode((DATA / "suite.json").read_bytes()))


class TaskEvalTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, case, inputs=None):
        with tempfile.TemporaryDirectory() as directory:
            actual = await execute(case.execution, inputs or Inputs(DATA), Path(directory))
        return actual, score(actual, case.expected)

    async def test_eight_cases_real_runtime(self):
        for case in suite().cases:
            with self.subTest(case=case.id):
                actual, scored = await self.run_case(case)
                self.assertFalse(actual["infra_errors"])
                self.assertTrue(scored["control_pass"], [k for k, v in scored["assertions"].items() if not v])

    async def test_expected_only_change_never_changes_execution(self):
        original = suite().cases[0]
        changed = original.model_copy(deep=True)
        changed.expected.phases[0].reason = "wrong-label"
        first, _ = await self.run_case(original)
        second, scored = await self.run_case(changed)
        def projection(actual):
            report = {"cases": [{"id": "same", "actual": actual}]}
            return stable_projection(report)
        self.assertEqual(projection(first), projection(second))
        self.assertFalse(scored["control_pass"])

    async def mutated_fixture(self, index, mutate):
        case = suite().cases[index]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixtures = root / "fixtures"
            fixtures.mkdir()
            for phase in case.execution.phases:
                data = decode((DATA / phase.fixture.path).read_bytes())
                mutate(data)
                raw = json.dumps(data).encode()
                (root / phase.fixture.path).write_bytes(raw)
                phase.fixture.sha256 = digest(raw)
            return await self.run_case(case, Inputs(root))

    async def test_new_id_old_capture_time_stops_before_state(self):
        def mutate(data):
            for call in data["calls"][4:8]:
                observation = call["response"]["structuredContent"].get("observation")
                if observation:
                    observation["captured_at"] = "2026-10-06T00:00:01+00:00"
        actual, scored = await self.mutated_fixture(0, mutate)
        self.assertEqual(actual["phases"][0]["state"]["reason"], "nonincreasing_capture_time")
        self.assertEqual(len(actual["phases"][0]["tool_calls"]), 6)
        self.assertFalse(scored["goal_success"])

    async def test_fixture_sequence_exhaustion_is_infra_not_safe_stop(self):
        actual, scored = await self.mutated_fixture(0, lambda data: data["calls"].__delitem__(slice(1, None)))
        self.assertTrue(scored["infra_error"])
        self.assertFalse(scored["control_pass"])
        self.assertEqual(actual["phases"][0]["script_errors"], ["response_sequence_exhausted"])

    async def test_checkpoint_failure_not_safety_pass(self):
        case = suite().cases[0]
        with patch("pioneer_agent.agent_harness.run_store.JsonRunStore.acquire", side_effect=OSError("write-failure")):
            actual, scored = await self.run_case(case)
        self.assertTrue(scored["infra_error"])
        self.assertFalse(scored["control_pass"])
        self.assertEqual(actual["phases"][0]["tool_calls"], [])

    async def test_resume_does_not_grant_extra_budget(self):
        case = suite().cases[5]
        case.execution.budget = case.execution.budget.model_copy(update={"max_tool_calls": 5})
        actual, scored = await self.run_case(case)
        self.assertEqual(actual["phases"][-1]["state"]["reason"], "budget_exhausted")
        self.assertEqual(sum(len(p["tool_calls"]) for p in actual["phases"]), 5)
        self.assertTrue(scored["assertions"]["phase_2.resume_no_refill"])

    async def test_trace_budget_mismatch_fails(self):
        actual, _ = await self.run_case(suite().cases[0])
        actual["phases"][0]["trace"][0]["attempt_id"] = "forged"
        self.assertFalse(score(actual, suite().cases[0].expected)["control_pass"])

    def test_empty_duplicate_and_extra_suite_fields_rejected(self):
        for mutate in (lambda d: d.update(cases=[]),
                       lambda d: d["cases"][1].update(id=d["cases"][0]["id"]),
                       lambda d: d.update(provider="live")):
            data = suite().model_dump(mode="json")
            mutate(data)
            with self.assertRaises(ValueError):
                Suite.model_validate(data)

    def test_unknown_tool_rejected(self):
        data = decode((DATA / "fixtures/first-observation.json").read_bytes())
        data["calls"][0]["tool"] = "click_game"
        with self.assertRaises(ValueError):
            Fixture.model_validate(data)

    def test_category_cannot_disguise_goal_as_safe_stop(self):
        data = suite().model_dump(mode="json")
        data["cases"][0]["expected"]["category"] = "safety_stop"
        data["cases"][1]["expected"]["category"] = "goal"
        with self.assertRaises(ValueError):
            Suite.model_validate(data)

    def test_fixture_bytes_and_parsing_same_buffer(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "fixture.json"
            path.write_bytes(b'{"x":1}')
            inputs = Inputs(root)
            first = inputs.read("fixture.json")
            path.write_bytes(b'{"x":2}')
            self.assertEqual(inputs.read("fixture.json"), first)
            with self.assertRaises(InputError):
                inputs.read("fixture.json", digest(path.read_bytes()))

    def test_path_escape_and_symlink_rejected(self):
        with self.assertRaises(InputError):
            safe_path(DATA, "../suite.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "linked.json"
            try:
                path.symlink_to(DATA / "suite.json")
            except OSError:
                self.skipTest("host does not grant symlink creation")
            with self.assertRaises(InputError):
                safe_path(Path(directory), "linked.json")

    def test_duplicate_json_and_output_overwrite_rejected(self):
        with self.assertRaises(InputError):
            decode(b'{"x":1,"x":2}')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            write_new(path, {"first": True})
            with self.assertRaises(FileExistsError):
                write_new(path, {"first": False})

    def test_lazy_shadow_import_detected(self):
        binding = SourceBinding.__new__(SourceBinding)
        binding.root = ROOT
        binding.modules = {}
        binding.manifest = {}
        # A lone shadow is sufficient; unrelated modules are isolated for this check.
        module = types.ModuleType("pioneer_agent.lazy_shadow")
        module.__file__ = "/tmp/shadow.py"
        module.__spec__ = types.SimpleNamespace(origin="/tmp/shadow.py")
        remaining = {name: value for name, value in sys.modules.items()
                     if not name.startswith(("pioneer_agent", "sanmou_common"))}
        remaining["pioneer_agent.lazy_shadow"] = module
        with patch.dict(sys.modules, remaining, clear=True):
            with self.assertRaisesRegex(InputError, "shadow_import"):
                binding.verify_imports()

    def test_source_drift_and_untracked_source_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "packages/pioneer-agent/src/test.py"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"x = 1\n")
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout
            git("init", "-q")
            git("add", ".")
            git("-c", "user.name=Offline Test", "-c", "user.email=offline@example.invalid", "commit", "-qm", "fixture")
            binding = SourceBinding.__new__(SourceBinding)
            binding.root, binding.manifest = root, {}
            binding.commit = git("rev-parse", "HEAD").decode().strip()
            binding.verify_bytes()
            path.write_bytes(b"x = 2\n")
            with self.assertRaisesRegex(InputError, "source_byte_drift"):
                binding.verify_bytes()
            path.write_bytes(b"x = 1\n")
            (path.parent / "untracked.py").write_bytes(b"x = 3\n")
            with self.assertRaisesRegex(InputError, "untracked_source"):
                binding.verify_bytes()


if __name__ == "__main__":
    unittest.main()
