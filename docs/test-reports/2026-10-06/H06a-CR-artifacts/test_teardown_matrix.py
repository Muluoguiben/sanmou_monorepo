"""Owned teardown error-priority matrix; real release then injected failure."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from pioneer_agent.agent_harness._checkpoint_lock import LocalLock
from pioneer_agent.agent_harness.run_store import JsonRunStore, CheckpointConflict
from pioneer_agent.agent_harness.task_contracts import RunState
from test_task_runner import runner, task, SequenceClient


ORIGINAL_CLOSE = LocalLock.close
def cleanup_fault(lock):
    ORIGINAL_CLOSE(lock)
    raise OSError("secondary cleanup")


class TeardownMatrix(unittest.IsolatedAsyncioTestCase):
    async def test_owner_context_primary_conflict(self):
        with TemporaryDirectory() as tmp:
            store = JsonRunStore(Path(tmp) / "run.json")
            with patch.object(LocalLock, "close", cleanup_fault):
                with self.assertRaises(CheckpointConflict):
                    with store.acquire():
                        raise CheckpointConflict("primary")

    async def test_successful_owner_body_does_not_hide_cleanup_failure(self):
        with TemporaryDirectory() as tmp:
            with patch.object(LocalLock, "close", cleanup_fault):
                with self.assertRaises(OSError):
                    with JsonRunStore(Path(tmp) / "run.json").acquire():
                        pass

    async def test_direct_runner_cancel_primary(self):
        with TemporaryDirectory() as tmp:
            class Client(SequenceClient):
                async def call_tool(self, name, args):
                    raise asyncio.CancelledError("primary")
            with patch.object(LocalLock, "close", cleanup_fault):
                r = runner(Client(), store=JsonRunStore(Path(tmp) / "run.json"))
                with self.assertRaises(asyncio.CancelledError):
                    await r.run()

    async def test_constructor_identity_primary(self):
        with TemporaryDirectory() as tmp:
            store = JsonRunStore(Path(tmp) / "run.json")
            with store.acquire() as owner:
                owner.load()
                owner.save(RunState(run_id="run", task=task()))
            with patch.object(LocalLock, "close", cleanup_fault):
                with self.assertRaisesRegex(ValueError, "identity"):
                    runner(store=store, spec=task(max_steps=2))

    async def test_idle_pause_and_cancel_preserve_save_failure(self):
        for action in ("pause", "cancel"):
            with self.subTest(action=action), TemporaryDirectory() as tmp:
                with patch.object(LocalLock, "close", cleanup_fault):
                    r = runner(store=JsonRunStore(Path(tmp) / "run.json"))
                    with patch.object(r.store, "save", side_effect=ValueError("primary-save")):
                        with self.assertRaisesRegex(ValueError, "primary-save"):
                            getattr(r, action)()

    async def test_reacquire_reload_primary(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            r = runner(store=JsonRunStore(path))
            r.pause()
            with JsonRunStore(path).acquire() as owner:
                state = owner.load()
                state.budget_state["deadline"] -= 1
                owner.save(state)
            with patch.object(LocalLock, "close", cleanup_fault):
                with self.assertRaisesRegex(CheckpointConflict, "fresh runner"):
                    await r.run(resume=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
