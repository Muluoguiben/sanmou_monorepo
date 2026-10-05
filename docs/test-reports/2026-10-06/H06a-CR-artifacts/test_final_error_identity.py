"""Final primary object identity, no-write, reacquisition, terminal cleanup oracles."""
import asyncio
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from pioneer_agent.agent_harness._checkpoint_lock import LocalLock
from pioneer_agent.agent_harness.run_store import JsonRunStore, CheckpointConflict
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.app import game_agent
from test_task_runner import BASE, runner, SequenceClient
import test_task_cli as fixtures


ORIGINAL_CLOSE = LocalLock.close
def failed_cleanup(lock):
    ORIGINAL_CLOSE(lock)
    raise OSError("cleanup")


class FinalErrorIdentity(unittest.IsolatedAsyncioTestCase):
    async def test_original_checkpoint_exception_identity_no_retry_write(self):
        for primary in (CheckpointConflict("specific conflict"), ValueError("specific persistence error")):
            with self.subTest(kind=type(primary).__name__), TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                client = SequenceClient()
                with patch.object(LocalLock, "close", failed_cleanup):
                    r = runner(client, store=JsonRunStore(path))
                    original = r.store.save
                    before = []
                    def save(store_state, **kwargs):
                        if store_state.pending_call == "session_status":
                            before.append(path.read_bytes())
                            raise primary
                        return original(store_state, **kwargs)
                    with patch.object(r.store, "save", save):
                        try:
                            await r.run()
                        except BaseException as caught:
                            self.assertIs(caught, primary)
                        else:
                            self.fail("original persistence exception disappeared")
                self.assertEqual(len(before), 1)
                self.assertEqual(path.read_bytes(), before[0])
                self.assertEqual(client.calls, [])
                self.assertIn("checkpoint_cleanup_error:OSError", primary.__notes__)
                with JsonRunStore(path).acquire():
                    pass

    async def test_original_cancel_identity_and_release(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            primary = asyncio.CancelledError("original-cancel")
            class Client(SequenceClient):
                async def call_tool(self, name, args):
                    raise primary
            with patch.object(LocalLock, "close", failed_cleanup):
                r = runner(Client(), store=JsonRunStore(path))
                try:
                    await r.run()
                except BaseException as caught:
                    self.assertIs(caught, primary)
                else:
                    self.fail("cancel swallowed")
            with JsonRunStore(path).acquire() as owner:
                self.assertEqual(owner.load().status, "cancelled")

    async def test_terminal_mcp_cleanup_error_visible_without_state_rewrite(self):
        for mode in ("succeeded", "failed"):
            with self.subTest(mode=mode), TemporaryDirectory() as tmp:
                root = Path(tmp)
                class Client(fixtures.ManagedSequence):
                    async def call_tool(self, name, args):
                        if mode == "failed":
                            raise RuntimeError("runtime failure")
                        return await super().call_tool(name, args)
                    async def __aexit__(self, *args):
                        self.committed = (root / "run.json").read_bytes()
                        raise OSError("MCP cleanup")
                client = Client()
                def harness(**kwargs):
                    return RecommendationHarness(**kwargs, clock=lambda: BASE + timedelta(seconds=client.count + 1))
                with patch.object(game_agent, "RecommendationHarness", side_effect=harness):
                    result = await game_agent._run_task(fixtures.TaskCliTests().args(root), game_client=client)
                self.assertEqual(result["status"], mode)
                self.assertEqual(result["transport_lifecycle_error"], "transport:OSError")
                self.assertEqual((root / "run.json").read_bytes(), client.committed)
                with JsonRunStore(root / "run.json").acquire():
                    pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
