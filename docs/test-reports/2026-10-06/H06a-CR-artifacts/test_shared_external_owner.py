"""One external owner cannot safely lend the same mutable CAS cursor twice."""
import asyncio
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder
from pioneer_agent.agent_harness.journal import InMemoryJournalStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from pioneer_agent.agent_harness.run_store import JsonRunStore, CheckpointConflict
from pioneer_agent.agent_harness.run_trace import InMemoryRunTrace
from pioneer_agent.agent_harness.task_contracts import PolicyDecision
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy
from pioneer_agent.agent_harness.task_runner import TaskRunner
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
from test_task_runner import BASE, SequenceClient, task


class SharedExternalOwner(unittest.IsolatedAsyncioTestCase):
    async def test_shared_owner_does_not_lose_duplicate_dispatch_accounting(self):
        with TemporaryDirectory() as tmp:
            store = JsonRunStore(Path(tmp) / "run.json")
            with store.acquire() as owner:
                clients = [SequenceClient(), SequenceClient()]
                runners = []
                for client in clients:
                    harness = RecommendationHarness(game_client=client, journal_store=InMemoryJournalStore(),
                        tool_log=InMemoryToolLog(), agent_session_id="run", model_id="fake",
                        clock=lambda client=client: BASE + timedelta(seconds=client.count + 1))
                    try:
                        runners.append(TaskRunner(task=task(), run_id="run", harness=harness, store=store,
                            policy=FakeDecisionPolicy([PolicyDecision(action="pause", reason="stop")]),
                            context_builder=BoundedContextBuilder(), budget=RunBudgetLedger(),
                            trace=InMemoryRunTrace(), ownership=owner))
                    except CheckpointConflict:
                        break
                results = await asyncio.gather(*(r.run() for r in runners), return_exceptions=True)
                saved = owner.load()
                actual = sum(len(c.calls) for c in clients)
                charged = sum(entry["request"]["kind"] == "tool"
                    for entry in saved.budget_state["reservations"].values())
                print({"runners": len(runners), "actual_calls": actual, "charged_calls": charged,
                       "results": [getattr(x, "status", type(x).__name__) for x in results]}, flush=True)
                self.assertGreaterEqual(charged, actual, "shared owner loses already dispatched call charges")


if __name__ == "__main__":
    unittest.main(verbosity=2)
