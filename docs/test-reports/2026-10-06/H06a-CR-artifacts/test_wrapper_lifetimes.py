"""Narrow CR04 ownership of borrowed harness client slots."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from pioneer_agent.agent_harness._checkpoint_lock import LocalLock
import test_shared_external_owner as f
from test_task_runner import runner


def fresh(harness, store, owner=None):
    return f.TaskRunner(task=f.task(), run_id="run", harness=harness, store=store,
        policy=f.RuleDecisionPolicy() if hasattr(f, "RuleDecisionPolicy") else __import__(
            "pioneer_agent.agent_harness.task_policy", fromlist=["RuleDecisionPolicy"]).RuleDecisionPolicy(),
        context_builder=f.BoundedContextBuilder(), budget=f.RunBudgetLedger(),
        trace=f.InMemoryRunTrace(), ownership=owner)


def pause_policy():
    return f.FakeDecisionPolicy([f.PolicyDecision(action="pause", reason="pause")])


class WrapperLifetimes(unittest.IsolatedAsyncioTestCase):
    async def test_old_close_preserves_new_wrapper_and_same_runner_reinstalls(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            client = f.SequenceClient()
            old = runner(client, store=f.JsonRunStore(path), policy=pause_policy())
            await old.run()
            self.assertIs(old.harness.game_client, client)
            newer = fresh(old.harness, f.JsonRunStore(path))
            installed = old.harness.game_client
            old.close(); old.close()
            self.assertIs(old.harness.game_client, installed)
            self.assertEqual((await newer.run(resume=True)).status, "succeeded")
            self.assertIs(old.harness.game_client, client)
            count = len(client.calls)
            self.assertEqual((await newer.run()).status, "succeeded")
            self.assertEqual(len(client.calls), count)
            self.assertIs(old.harness.game_client, client)

    async def test_same_runner_paused_resume_restores_borrowed_slot(self):
        with TemporaryDirectory() as tmp:
            client = f.SequenceClient()
            r = runner(client, store=f.JsonRunStore(Path(tmp) / "run.json"), policy=pause_policy())
            result = await r.run()
            self.assertEqual(result.status, "paused")
            self.assertIs(r.harness.game_client, client)
            result = await r.run(resume=True)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])
            self.assertIs(r.harness.game_client, client)

    async def test_third_party_replacement_not_overwritten_and_reuse_nonmutating(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            client = f.SequenceClient()
            r = runner(client, store=f.JsonRunStore(path), policy=pause_policy())
            await r.run()
            before, calls = path.read_bytes(), list(client.calls)
            third_party = object()
            r.harness.game_client = third_party
            r.close()
            self.assertIs(r.harness.game_client, third_party)
            with self.assertRaises(f.CheckpointConflict):
                await r.run(resume=True)
            self.assertIs(r.harness.game_client, third_party)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(client.calls, calls)
            with f.JsonRunStore(path).acquire():
                pass

    async def test_failed_second_constructor_preserves_first_binding(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = runner(store=f.JsonRunStore(root / "first.json"))
            binding = first.harness.game_client
            with self.assertRaises(f.CheckpointConflict):
                fresh(first.harness, f.JsonRunStore(root / "second.json"))
            self.assertIs(first.harness.game_client, binding)
            self.assertFalse((root / "second.json").exists())
            self.assertFalse((root / "second.json.lock").exists())
            with self.assertRaises(f.CheckpointConflict):
                f.JsonRunStore(root / "first.json").acquire()
            first.pause()

    async def test_cleanup_failure_detaches_and_preserves_cancel_object(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            primary = asyncio.CancelledError("cancel")
            class Client(f.SequenceClient):
                async def call_tool(self, name, args):
                    raise primary
            original_close = LocalLock.close
            def close(lock):
                original_close(lock)
                raise OSError("cleanup")
            client = Client()
            with patch.object(LocalLock, "close", close):
                r = runner(client, store=f.JsonRunStore(path))
                try:
                    await r.run()
                except BaseException as caught:
                    self.assertIs(caught, primary)
                else:
                    self.fail("cancellation disappeared")
            self.assertIs(r.harness.game_client, client)
            with f.JsonRunStore(path).acquire() as owner:
                self.assertEqual(owner.load().status, "cancelled")


if __name__ == "__main__":
    unittest.main(verbosity=2)
