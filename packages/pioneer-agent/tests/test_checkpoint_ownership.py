"""H06a offline local ownership/CAS contract tests."""
import json
import asyncio
import multiprocessing
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pioneer_agent.agent_harness.run_store import JsonRunStore, CheckpointConflict
from pioneer_agent.agent_harness._checkpoint_lock import LocalLock, UnsupportedCheckpointBackend
from pioneer_agent.agent_harness.task_contracts import RunState, PolicyDecision
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.app import game_agent
import test_task_cli
from test_task_runner import BASE, SequenceClient, runner, task


def _race_child(root, start, release, pipe):
    class Client(test_task_cli.ManagedSequence):
        async def __aenter__(self):
            self.entries += 1
            pipe.send(("entered", self.entries))
            if not await asyncio.to_thread(release.wait, 15):
                raise RuntimeError("test rendezvous timed out")
            return self
    client = Client()
    root = Path(root)
    args = game_agent.build_parser().parse_args([
        "--screenshot", str(root / "unused.png"), "--task-spec", str(root / "task.json"),
        "--journal-path", str(root / "journal.json"), "--tool-log-path", str(root / "tools.jsonl"),
        "--run-state-path", str(root / "run.json"), "--run-trace-path", str(root / "trace.jsonl"),
    ])
    def harness(**kwargs):
        return RecommendationHarness(**kwargs, clock=lambda: BASE + timedelta(seconds=client.count + 1))
    if not start.wait(15):
        raise RuntimeError("test start timed out")
    with patch.object(game_agent, "RecommendationHarness", side_effect=harness):
        result = asyncio.run(game_agent._run_task(args, game_client=client))
    pipe.send(("result", result, client.entries, client.calls))


def _crash_child(path, boundary, pipe):
    store = JsonRunStore(Path(path))
    original_write = store._write
    original_replace = Path.replace
    def parked():
        pipe.send("parked")
        pipe.recv()  # Parent kills only this disposable process at this cut.
    def replace(temporary, target):
        raw = json.loads(temporary.read_text())
        if raw["state"]["pending_call"] == "session_status":
            if boundary == "temp-before-replace":
                parked()
            result = original_replace(temporary, target)
            if boundary == "after-replace":
                parked()
            return result
        return original_replace(temporary, target)
    def write(envelope):
        original_write(envelope)
        if boundary == "reservation-before-dispatch" and envelope.state.pending_call == "session_status":
            parked()
    store._write = write
    with patch.object(Path, "replace", replace):
        asyncio.run(runner(SequenceClient(count=1), store=store,
                           budget=RunBudgetLedger(clock=lambda: 1001., monotonic=lambda: 1001.)).run(resume=True))


class CheckpointOwnershipTests(unittest.TestCase):
    def test_exclusive_owner_revision_and_released_owner(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            store = JsonRunStore(path)
            with store.acquire() as owner:
                self.assertIsNone(owner.load())
                state = RunState(run_id="run", task=task())
                owner.save(state)
                original = path.read_bytes()
                with self.assertRaises(CheckpointConflict):
                    JsonRunStore(path).acquire()
                with self.assertRaises(CheckpointConflict):
                    store.save(state, owner=owner, expected_revision=0)
                self.assertEqual(path.read_bytes(), original)
                state.status = "succeeded"
                owner.save(state)
                self.assertEqual(owner.revision, 2)
            with self.assertRaises(CheckpointConflict):
                owner.save(state)
            with store.acquire() as successor:
                self.assertEqual(successor.load().status, "succeeded")
                self.assertEqual(successor.revision, 2)

    def test_identity_and_legacy_migration(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            state = RunState(run_id="run", task=task(), pending_call="observe_game",
                             status="waiting", reason="await_next_observation", completed_steps=2,
                             observation_ids=["obs-1", "obs-2"], session_id="fixture-session",
                             window_identity={"hwnd": 17}, last_captured_at=BASE,
                             evidence_refs=["frame_sha256:" + "a" * 64],
                             budget_state={"reserved": 3, "deadline": 12, "reservations": {"spent": 5}})
            path.write_text(state.model_dump_json(), encoding="utf-8")
            with JsonRunStore(path).acquire() as owner:
                loaded = owner.load()
                self.assertEqual(loaded, state)
                owner.save(loaded)
                encoded = json.loads(path.read_text())
                self.assertEqual(encoded["state"], state.model_dump(mode="json"))
                for changed in (state.model_copy(update={"run_id": "other"}),
                                state.model_copy(update={"task": task(max_steps=2)})):
                    with self.assertRaises(CheckpointConflict):
                        owner.save(changed)

    def test_stale_revision_owner_and_terminal_rollback_preserve_winner(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            store = JsonRunStore(path)
            with store.acquire() as old:
                old.load()
                state = RunState(run_id="run", task=task(), budget_state={"deadline": 123, "spent": 5})
                old.save(state)
            with store.acquire() as current:
                latest = current.load()
                latest.status = "succeeded"
                latest.budget_state["spent"] = 6
                current.save(latest)
                winner = path.read_bytes()
                for owner, revision in ((old, old.revision), (current, current.revision - 1)):
                    with self.assertRaises(CheckpointConflict):
                        store.save(state, owner=owner, expected_revision=revision)
                with self.assertRaises(CheckpointConflict):
                    current.save(state)
                self.assertEqual(path.read_bytes(), winner)
                self.assertEqual(current.load().budget_state, {"deadline": 123, "spent": 6})

    def test_foreign_store_owner_cannot_save(self):
        with TemporaryDirectory() as tmp:
            first = JsonRunStore(Path(tmp) / "first.json")
            second = JsonRunStore(Path(tmp) / "second.json")
            with first.acquire() as owner:
                owner.load()
                with self.assertRaises(CheckpointConflict):
                    second.save(RunState(run_id="run", task=task()), owner=owner, expected_revision=0)
            self.assertFalse(second.path.exists())

    def test_malformed_unknown_and_strict_revision_never_rewritten(self):
        for raw in ("{", '{"version":2}', '{"version":true}',
                    json.dumps({"storage_version": 1, "revision": True, "owner_id": "x",
                                "state": RunState(run_id="run", task=task()).model_dump(mode="json")})):
            with self.subTest(raw=raw), TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                path.write_text(raw)
                with JsonRunStore(path).acquire() as owner:
                    with self.assertRaises(ValueError):
                        owner.load()
                self.assertEqual(path.read_text(), raw)
                with JsonRunStore(path).acquire():
                    pass

    def test_backend_rejects_without_checkpoint_or_sidecar(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            with patch.object(LocalLock, "_validate_backend", side_effect=UnsupportedCheckpointBackend()):
                with self.assertRaises(UnsupportedCheckpointBackend):
                    JsonRunStore(path).acquire()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_replaced_checkpoint_does_not_replace_lock(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            with JsonRunStore(path).acquire() as owner:
                owner.load()
                before = path.with_name("run.json.lock").stat().st_ino
                state = RunState(run_id="run", task=task())
                for _ in range(3):
                    owner.save(state)
                self.assertEqual(path.with_name("run.json.lock").stat().st_ino, before)
                with self.assertRaises(CheckpointConflict):
                    JsonRunStore(path).acquire()
            self.assertTrue(path.with_name("run.json.lock").exists())

    def test_real_process_cli_race_loser_zero_connect_calls_writes(self):
        ctx = multiprocessing.get_context("spawn")
        with TemporaryDirectory() as tmp:
            test_task_cli.TaskCliTests().args(Path(tmp))
            start, release = ctx.Event(), ctx.Event()
            pairs = [ctx.Pipe() for _ in range(2)]
            children = [ctx.Process(target=_race_child, args=(tmp, start, release, pair[1])) for pair in pairs]
            try:
                for child in children:
                    child.start()
                start.set()
                messages = []
                for pair in pairs:
                    self.assertTrue(pair[0].poll(15), "child must report ownership decision")
                    messages.append(pair[0].recv())
                winner = next(i for i, item in enumerate(messages) if item[0] == "entered")
                loser = messages[1 - winner]
                self.assertEqual(loser[0], "result")
                self.assertEqual(loser[1]["reason"], "checkpoint_conflict")
                self.assertEqual(loser[2:], (0, []))
                self.assertFalse((Path(tmp) / "run.json").exists())
                release.set()
                self.assertTrue(pairs[winner][0].poll(15))
                self.assertEqual(pairs[winner][0].recv()[1]["status"], "succeeded")
                for child in children:
                    child.join(15)
                    self.assertEqual(child.exitcode, 0)
            finally:
                release.set()
                for child in children:
                    if child.is_alive():
                        child.terminate()
                    child.join(5)
                for pair in pairs:
                    for endpoint in pair:
                        endpoint.close()

    def test_real_process_crash_boundaries_preserve_budget_and_reobserve(self):
        ctx = multiprocessing.get_context("spawn")
        for boundary in ("reservation-before-dispatch", "temp-before-replace", "after-replace"):
            with self.subTest(boundary=boundary), TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                seed = runner(store=JsonRunStore(path),
                              budget=RunBudgetLedger(clock=lambda: 1000., monotonic=lambda: 1000.), policy=FakeDecisionPolicy([
                    PolicyDecision(action="pause", reason="seed")]))
                first = asyncio.run(seed.run())
                initial = first.budget_state
                parent, child_pipe = ctx.Pipe()
                child = ctx.Process(target=_crash_child, args=(str(path), boundary, child_pipe))
                try:
                    child.start()
                    self.assertTrue(parent.poll(15), "crash boundary not reached")
                    self.assertEqual(parent.recv(), "parked")
                    child.terminate()
                    child.join(5)
                    self.assertFalse(child.is_alive())
                    durable = JsonRunStore(path).load()
                    self.assertEqual(durable.budget_state["deadline"], initial["deadline"])
                    self.assertGreaterEqual(len(durable.budget_state["reservations"]), len(initial["reservations"]))
                    self.assertTrue(set(initial["reservations"]).issubset(durable.budget_state["reservations"]))
                    client = SequenceClient(count=1)
                    resumed = runner(client, store=JsonRunStore(path),
                                     budget=RunBudgetLedger(clock=lambda: 1002., monotonic=lambda: 1002.))
                    self.assertEqual(resumed.budget.snapshot()["deadline"], initial["deadline"])
                    result = asyncio.run(resumed.run(resume=True))
                    self.assertEqual(result.status, "succeeded")
                    self.assertEqual(client.calls[:2], ["session_status", "observe_game"])
                    self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])
                    self.assertTrue(set(durable.budget_state["reservations"]).issubset(result.budget_state["reservations"]))
                    self.assertLessEqual(result.budget_state["remaining"], durable.budget_state["remaining"])
                finally:
                    if child.is_alive():
                        child.terminate()
                    child.join(5)
                    parent.close()
                    child_pipe.close()


class RunnerOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_active_close_cannot_release_inflight_owner(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            client = SequenceClient()
            r = runner(client, store=JsonRunStore(path))
            def after_call(name):
                with self.assertRaisesRegex(RuntimeError, "cancel and await"):
                    r.close()
                with self.assertRaises(CheckpointConflict):
                    JsonRunStore(path).acquire()
                r.cancel()
            client.after_call = after_call
            self.assertEqual((await r.run()).status, "cancelled")
            with JsonRunStore(path).acquire():
                pass

    async def test_independent_runner_refused_then_pause_releases(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            first = runner(store=JsonRunStore(path))
            with self.assertRaises(CheckpointConflict):
                runner(store=JsonRunStore(path))
            first.pause()
            second = runner(SequenceClient(), store=JsonRunStore(path))
            self.assertEqual((await second.run()).status, "paused")
            first.cancel()
            self.assertEqual(JsonRunStore(path).load().status, "cancelled")

    async def test_conflict_never_settles_or_retries_finish(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            r = runner(store=JsonRunStore(path))
            original = r.store.save
            calls = []
            def conflict(state, **kwargs):
                calls.append(state.pending_call)
                if state.pending_call == "session_status":
                    raise CheckpointConflict("synthetic stale owner")
                return original(state, **kwargs)
            r.store.save = conflict
            with self.assertRaises(CheckpointConflict):
                await r.run()
            self.assertEqual(r._client.calls, [])
            self.assertEqual(calls, [None, None, "session_status"])
            self.assertEqual(r.budget.summary()["pending"], 2)
            self.assertEqual(JsonRunStore(path).load().status, "running")

    async def test_failed_construction_and_explicit_close_release(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            first = runner(store=JsonRunStore(path))
            first.pause()
            with self.assertRaises(ValueError):
                runner(store=JsonRunStore(path), spec=task(max_steps=2))
            second = runner(store=JsonRunStore(path))
            second.close()
            with JsonRunStore(path).acquire():
                pass

    async def test_other_owner_progress_requires_fresh_nonterminal_ledger(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            first = runner(store=JsonRunStore(path), policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="first")]))
            await first.run()
            second = runner(SequenceClient(count=1), store=JsonRunStore(path), policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="second")]))
            await second.run(resume=True)
            winner = path.read_bytes()
            with self.assertRaisesRegex(CheckpointConflict, "fresh runner"):
                await first.run(resume=True)
            self.assertEqual(path.read_bytes(), winner)
            third = runner(SequenceClient(count=2), store=JsonRunStore(path))
            self.assertEqual((await third.run(resume=True)).status, "succeeded")
            count = len(first._client.calls)
            self.assertEqual((await first.run(resume=True)).status, "succeeded")
            self.assertEqual(len(first._client.calls), count)

    async def test_direct_cancel_pause_async_and_runtime_release(self):
        for action in ("cancel", "pause", "async", "runtime"):
            with self.subTest(action=action), TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                client = SequenceClient()
                r = runner(client, store=JsonRunStore(path))
                if action in ("cancel", "pause"):
                    getattr(r, action)()
                else:
                    async def fail(*args):
                        if action == "async":
                            raise asyncio.CancelledError()
                        raise RuntimeError("synthetic")
                    client.call_tool = fail
                    if action == "async":
                        with self.assertRaises(asyncio.CancelledError):
                            await r.run()
                    else:
                        self.assertEqual((await r.run()).status, "failed")
                with JsonRunStore(path).acquire() as owner:
                    self.assertEqual(owner.load().status,
                                     "paused" if action == "pause" else "failed" if action == "runtime" else "cancelled")

    async def test_cli_holds_through_cleanup_and_releases_on_all_exits(self):
        for phase in ("enter", "call", "exit", "async_enter", "async_call", "async_exit", "pause", "success"):
            with self.subTest(phase=phase), TemporaryDirectory() as tmp:
                root = Path(tmp)
                args = test_task_cli.TaskCliTests().args(root)
                test = self
                class Client(test_task_cli.ManagedSequence):
                    exits = 0
                    async def __aenter__(self):
                        self.entries += 1
                        if phase == "enter":
                            raise RuntimeError("enter")
                        if phase == "async_enter":
                            raise asyncio.CancelledError()
                        return self
                    async def call_tool(self, name, arguments):
                        if phase == "call":
                            raise RuntimeError("call")
                        if phase == "async_call":
                            raise asyncio.CancelledError()
                        return await super().call_tool(name, arguments)
                    async def __aexit__(self, *unused):
                        self.exits += 1
                        with test.assertRaises(CheckpointConflict):
                            JsonRunStore(args.run_state_path).acquire()
                        if phase == "exit":
                            raise RuntimeError("exit")
                        if phase == "async_exit":
                            raise asyncio.CancelledError()
                        return False
                client = Client()
                def harness(**kwargs):
                    return RecommendationHarness(**kwargs, clock=lambda: BASE + timedelta(seconds=client.count + 1))
                policy = FakeDecisionPolicy([PolicyDecision(action="pause", reason="pause")])
                with patch.object(game_agent, "RecommendationHarness", side_effect=harness):
                    if phase == "pause":
                        with patch("pioneer_agent.agent_harness.task_policy.RuleDecisionPolicy", return_value=policy):
                            result = await game_agent._run_task(args, game_client=client)
                            self.assertEqual(result["status"], "paused")
                    elif phase.startswith("async"):
                        with self.assertRaises(asyncio.CancelledError):
                            await game_agent._run_task(args, game_client=client)
                    else:
                        result = await game_agent._run_task(args, game_client=client)
                        self.assertEqual(result["status"], "failed" if phase in ("enter", "call") else "succeeded")
                with JsonRunStore(args.run_state_path).acquire():
                    pass
                self.assertEqual(client.exits, 0 if phase in ("enter", "async_enter") else 1)


if __name__ == "__main__":
    unittest.main()
