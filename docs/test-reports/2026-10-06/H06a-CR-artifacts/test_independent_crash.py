"""Independent process-death checks at acknowledged persistence boundaries."""
import asyncio
import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pioneer_agent.agent_harness.run_store import JsonRunStore
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from pioneer_agent.agent_harness.task_contracts import PolicyDecision
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy
from test_task_runner import runner, SequenceClient


def doomed(path, boundary, pipe):
    path = Path(path)
    store = JsonRunStore(path)
    write = store._write
    replace = Path.replace
    def barrier():
        pipe.send({"boundary": boundary, "durable": json.loads(path.read_text())})
        pipe.recv()
        raise AssertionError("parent must terminate child, not release barrier")
    def intercept_write(envelope):
        write(envelope)
        if boundary == "reservation" and envelope.state.pending_call == "session_status":
            barrier()
    def intercept_replace(temp, target):
        payload = json.loads(temp.read_text())
        targeted = payload["state"]["pending_call"] == "session_status"
        if targeted and boundary == "temporary":
            barrier()
        answer = replace(temp, target)
        if targeted and boundary == "replaced":
            barrier()
        return answer
    store._write = intercept_write
    with patch.object(Path, "replace", intercept_replace):
        asyncio.run(runner(SequenceClient(count=1), store=store,
            budget=RunBudgetLedger(clock=lambda: 1001., monotonic=lambda: 1001.)).run(resume=True))


class IndependentCrash(unittest.TestCase):
    def test_three_acknowledged_process_deaths(self):
        ctx = mp.get_context("spawn")
        for boundary in ("reservation", "temporary", "replaced"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                initial = asyncio.run(runner(store=JsonRunStore(path),
                    budget=RunBudgetLedger(clock=lambda: 1000., monotonic=lambda: 1000.),
                    policy=FakeDecisionPolicy([PolicyDecision(action="pause", reason="seed")])).run())
                original = initial.budget_state
                parent, child = ctx.Pipe()
                proc = ctx.Process(target=doomed, args=(str(path), boundary, child))
                proc.start()
                try:
                    self.assertTrue(parent.poll(10), "boundary not reached")
                    acknowledged = parent.recv()
                    self.assertEqual(acknowledged["boundary"], boundary)
                    proc.terminate()
                    proc.join(5)
                    self.assertIsNotNone(proc.exitcode)
                    self.assertNotEqual(proc.exitcode, 0)
                    durable = json.loads(path.read_text())
                    self.assertEqual(durable, acknowledged["durable"])
                    self.assertGreater(durable["revision"], 1)
                    saved = durable["state"]["budget_state"]
                    self.assertEqual(saved["deadline"], original["deadline"])
                    self.assertTrue(set(original["reservations"]) <= set(saved["reservations"]))
                    client = SequenceClient(count=1)
                    restored = runner(client, store=JsonRunStore(path),
                        budget=RunBudgetLedger(clock=lambda: 1002., monotonic=lambda: 1002.))
                    self.assertEqual(restored.budget.snapshot()["deadline"], original["deadline"])
                    result = asyncio.run(restored.run(resume=True))
                    self.assertEqual(result.status, "succeeded")
                    self.assertEqual(client.calls[:2], ["session_status", "observe_game"])
                    self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])
                    self.assertTrue(set(saved["reservations"]) <= set(result.budget_state["reservations"]))
                    self.assertLessEqual(result.budget_state["remaining"], saved["remaining"])
                    self.assertGreater(json.loads(path.read_text())["revision"], durable["revision"])
                finally:
                    if proc.is_alive():
                        proc.terminate()
                        proc.join(3)
                    parent.close(); child.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
