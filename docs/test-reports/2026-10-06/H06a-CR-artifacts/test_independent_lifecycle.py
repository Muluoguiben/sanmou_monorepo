"""Independent H06a lifecycle oracles; existing fixture supplies only fake game data."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pioneer_agent.agent_harness.run_store import JsonRunStore, CheckpointConflict
from pioneer_agent.app import game_agent
from test_task_cli import ManagedSequence, TaskCliTests
from test_task_runner import runner, SequenceClient


class IndependentLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_async_cancellation_survives_cleanup_failure(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            class Client(ManagedSequence):
                async def call_tool(self, name, arguments):
                    raise asyncio.CancelledError("primary cancellation")
                async def __aexit__(self, kind, error, tb):
                    self.primary = error
                    raise RuntimeError("secondary cleanup failure")
            client = Client()
            with self.assertRaises(asyncio.CancelledError):
                await game_agent._run_task(TaskCliTests().args(root), game_client=client)
            self.assertIsInstance(client.primary, asyncio.CancelledError)
            with JsonRunStore(root / "run.json").acquire() as owner:
                self.assertEqual(owner.load().status, "cancelled")

    async def test_delayed_close_cannot_release_successor(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            store = JsonRunStore(path)
            old = store.acquire()
            old.load()
            old.close()
            new = store.acquire()
            try:
                new.load()
                old.close()
                with self.assertRaises(CheckpointConflict):
                    JsonRunStore(path).acquire()
                new.check()
            finally:
                new.close()

    async def test_same_instance_concurrent_entry_retains_owner(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            entered, release = asyncio.Event(), asyncio.Event()
            class Client(SequenceClient):
                async def call_tool(self, name, args):
                    entered.set()
                    await release.wait()
                    return await super().call_tool(name, args)
            r = runner(Client(), store=JsonRunStore(path))
            outer = asyncio.create_task(r.run())
            try:
                await asyncio.wait_for(entered.wait(), 3)
                with self.assertRaisesRegex(RuntimeError, "already active"):
                    await r.run()
                with self.assertRaises(CheckpointConflict):
                    JsonRunStore(path).acquire()
            finally:
                r.cancel()
                release.set()
                await asyncio.wait_for(outer, 3)
            with JsonRunStore(path).acquire():
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
