"""The outer ownership teardown must also preserve the primary exception."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from pioneer_agent.agent_harness._checkpoint_lock import LocalLock
from pioneer_agent.agent_harness.run_store import JsonRunStore
from pioneer_agent.app import game_agent
import test_task_cli as fixtures


class OwnerCleanupPrimary(unittest.IsolatedAsyncioTestCase):
    async def test_cli_cancel_survives_lock_cleanup_error(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = LocalLock.close
            def failing_close(lock):
                original(lock)
                raise OSError("secondary lock cleanup failure")
            class Client(fixtures.ManagedSequence):
                async def call_tool(self, name, arguments):
                    raise asyncio.CancelledError("primary cancellation")
            with patch.object(LocalLock, "close", failing_close):
                with self.assertRaises(asyncio.CancelledError):
                    await game_agent._run_task(fixtures.TaskCliTests().args(root), game_client=Client())
            with JsonRunStore(root / "run.json").acquire() as owner:
                self.assertEqual(owner.load().status, "cancelled")


if __name__ == "__main__":
    unittest.main(verbosity=2)
