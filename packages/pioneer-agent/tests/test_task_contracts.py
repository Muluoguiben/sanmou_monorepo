import unittest

from pydantic import ValidationError

from pioneer_agent.agent_harness.task_contracts import TaskSpec, RunState, PolicyDecision
from pioneer_agent.runbook.models import Condition, ConditionStatus, evaluate_all


class TaskContractTests(unittest.TestCase):
    def task(self, **kwargs):
        return TaskSpec(task_id="test", goal="observe target", success_when=[
            Condition(metric="economy.resources.wood", op=">=", value=3)
        ], **kwargs)

    def test_reuses_three_valued_conditions(self):
        self.assertEqual(evaluate_all(self.task().success_when, {}).status, ConditionStatus.UNKNOWN)

    def test_nonempty_goal_evidence(self):
        with self.assertRaises(ValidationError):
            TaskSpec(task_id="test", goal="goal", success_when=[])

    def test_authority_and_catalog_cannot_expand(self):
        for kwargs in ({"executable": True}, {"execution_authority": "live"},
                       {"allowed_tools": ["click"]}):
            with self.assertRaises(ValidationError):
                self.task(**kwargs)

    def test_checkpoint_round_trip_and_version(self):
        run = RunState(run_id="run", task=self.task())
        self.assertEqual(RunState.model_validate_json(run.model_dump_json()), run)
        with self.assertRaises(ValidationError):
            RunState.model_validate({**run.model_dump(), "version": 2})

    def test_policy_never_grants_execution(self):
        with self.assertRaises(ValidationError):
            PolicyDecision(action="succeed", reason="done", executable=True)


if __name__ == "__main__":
    unittest.main()
