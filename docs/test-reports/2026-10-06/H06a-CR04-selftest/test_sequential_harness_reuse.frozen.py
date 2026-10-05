"""Fresh runner/ledger resume must not dispatch through a retired TaskClient."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from pioneer_agent.agent_harness.run_store import JsonRunStore
from pioneer_agent.agent_harness.run_trace import InMemoryRunTrace
from pioneer_agent.agent_harness.task_contracts import PolicyDecision
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy, RuleDecisionPolicy
from pioneer_agent.agent_harness.task_runner import TaskRunner
from test_task_runner import runner, task, SequenceClient


class SequentialHarnessReuse(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_runner_same_harness_can_resume_or_reject_without_damage(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            client = SequenceClient()
            first = runner(client, store=JsonRunStore(path), policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="operator")]))
            paused = await first.run()
            self.assertEqual(paused.status, "paused")
            before = path.read_bytes()
            calls = len(client.calls)
            try:
                fresh = TaskRunner(task=task(), run_id="run", harness=first.harness,
                    store=JsonRunStore(path), policy=RuleDecisionPolicy(),
                    context_builder=BoundedContextBuilder(), budget=RunBudgetLedger(), trace=InMemoryRunTrace())
            except (ValueError, RuntimeError) as rejection:
                print({"explicit_admission_rejection": type(rejection).__name__}, flush=True)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(len(client.calls), calls)
                with JsonRunStore(path).acquire():
                    pass
                return
            result = await fresh.run(resume=True)
            print({"status": result.status, "reason": result.reason,
                   "new_physical_calls": client.calls[calls:],
                   "before_reservations": len(paused.budget_state["reservations"]),
                   "after_reservations": len(result.budget_state["reservations"])}, flush=True)
            self.assertEqual(result.status, "succeeded", "retired wrapper corrupts resumed run")
            self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])

    async def test_fresh_harness_control_succeeds(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            client = SequenceClient()
            first = runner(client, store=JsonRunStore(path), policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="operator")]))
            await first.run()
            fresh = runner(client, store=JsonRunStore(path))
            result = await fresh.run(resume=True)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
