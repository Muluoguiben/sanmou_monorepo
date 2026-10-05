"""Post-fix admission oracle: rejected runner cannot damage incumbent lifetime."""
import asyncio
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import test_shared_external_owner as f


def make(client, store, owner):
    harness = f.RecommendationHarness(game_client=client, journal_store=f.InMemoryJournalStore(),
        tool_log=f.InMemoryToolLog(), agent_session_id="run", model_id="fake",
        clock=lambda: f.BASE + timedelta(seconds=client.count + 1))
    return f.TaskRunner(task=f.task(), run_id="run", harness=harness, store=store,
        policy=f.FakeDecisionPolicy([f.PolicyDecision(action="pause", reason="stop")]),
        context_builder=f.BoundedContextBuilder(), budget=f.RunBudgetLedger(),
        trace=f.InMemoryRunTrace(), ownership=owner)


class SharedOwnerAdmission(unittest.IsolatedAsyncioTestCase):
    async def test_second_construction_is_zero_effect_and_first_keeps_owner(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            store = f.JsonRunStore(path)
            with store.acquire() as owner:
                first_client, second_client = f.SequenceClient(), f.SequenceClient()
                first = make(first_client, store, owner)
                before = path.read_bytes() if path.exists() else None
                with self.assertRaises(f.CheckpointConflict):
                    make(second_client, store, owner)
                self.assertEqual(second_client.calls, [])
                self.assertEqual(path.read_bytes() if path.exists() else None, before)
                owner.check()
                with self.assertRaises(f.CheckpointConflict):
                    f.JsonRunStore(path).acquire()
                result = await first.run()
                self.assertEqual(result.status, "paused")
                self.assertEqual(len(first_client.calls), 4)
                owner.check()
                charged = sum(e["request"]["kind"] == "tool" for e in owner.load().budget_state["reservations"].values())
                self.assertEqual(charged, len(first_client.calls))
            with f.JsonRunStore(path).acquire():
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
