"""Additional H06a primary-conflict plus cleanup failure oracle."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from pioneer_agent.agent_harness.run_store import JsonRunStore, CheckpointConflict
from pioneer_agent.app import game_agent
import test_task_cli as fixtures


class PrimaryConflict(unittest.IsolatedAsyncioTestCase):
    async def test_checkpoint_conflict_survives_secondary_cleanup_error(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = JsonRunStore.save
            saves = []
            def save(store, state, **kwargs):
                saves.append(state.pending_call)
                if state.pending_call == "session_status":
                    raise CheckpointConflict("primary conflict")
                return original(store, state, **kwargs)
            class Client(fixtures.ManagedSequence):
                async def __aexit__(self, kind, error, tb):
                    self.primary = error
                    raise RuntimeError("secondary cleanup failure")
            client = Client()
            with patch.object(JsonRunStore, "save", save):
                result = await game_agent._run_task(fixtures.TaskCliTests().args(root), game_client=client)
            self.assertIsInstance(client.primary, CheckpointConflict)
            self.assertEqual(result["reason"], "checkpoint_conflict")
            self.assertEqual(client.calls, [])
            self.assertEqual(saves, [None, None, "session_status"])
            with JsonRunStore(root / "run.json").acquire() as owner:
                self.assertEqual(owner.load().status, "running")


if __name__ == "__main__":
    unittest.main(verbosity=2)
